import json
import math
import os
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from data import (
    COSTO_DELIVERY,
    DELIVERY_GRATIS_DESDE,
    GRUPOS,
    INGREDIENTES,
    PIZZAS,
    TAMANOS,
    cargar_desde_bd,
    cotizar,
    ingredientes_bloqueados,
    obtener_pizza,
    sembrar_si_hace_falta,
    validar_combinacion,
)
from menu_data import CATEGORY_ORDER, MENU_ITEMS, OBSOLETE_MENU_ITEM_IDS
from inventory_data import INVENTORY_CATEGORIES, INVENTORY_ITEMS
from modelos import IngredienteDB, MenuItemDB, PizzaDB, db
from backend.models import InventarioDB, MermaDB, PedidoDB, UsuarioDB


ADMIN_EMAIL = "pizzapronto@gmail.com"
ADMIN_PASSWORD = "pizzapronto"
STORE_ADDRESS = "Av. Manco Cápac 618, Cajamarca 06004"
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
DELIVERY_TYPES = {"delivery", "retiro_local", "comer_local"}
UNIDADES_INVENTARIO = {"unidad", "g", "kg", "ml", "l", "paquete"}
ACTIVE_ORDER_STATES = {"recibido", "en_preparacion"}
ORDER_TRANSITIONS = {
    "en_preparacion": "listo",
    "listo": "entregado",
    "entregado": "pagado",
}
MINUTOS_POR_PIZZA = 8
PREPARATION_START_DELAY_SECONDS = 10
KITCHEN_CAPACITY_PIZZAS = 6
BUSINESS_TIMEZONE = timezone(timedelta(hours=-5), "PET")
CRITICAL_STOCK_MINIMA = {
    "Queso Mozzarella": 2.0,
    "Salsa de tomate": 2.0,
    "Masa de pizza": 5.0,
    "Caja de pizza": 20.0,
}

# Consumo simulado expresado en la unidad de cada fila de inventario.
# Los productos y recetas sin entrada mantienen el pedido y generan una advertencia.
CONSUMO_POR_PRODUCTO = {
    # Una baguette se considera una porción de Pan al Ajo (5 unidades servidas).
    "pan-ajo": {"stock-panaderia-masas-y-cereales-04": 1.0},
}

CONSUMO_POR_INGREDIENTE_Y_TAMANO = {
    "masa_clasica": {
        "personal": {"stock-panaderia-masas-y-cereales-06": 0.15},
        "mediana": {"stock-panaderia-masas-y-cereales-06": 0.25},
        "familiar": {"stock-panaderia-masas-y-cereales-06": 0.40},
    },
    "salsa_tomate": {
        "personal": {"stock-salsas-condimentos-e-insumos-secos-01": 0.04},
        "mediana": {"stock-salsas-condimentos-e-insumos-secos-01": 0.06},
        "familiar": {"stock-salsas-condimentos-e-insumos-secos-01": 0.09},
    },
    "mozzarella": {
        "personal": {"stock-lacteos-y-quesos-01": 0.15},
        "mediana": {"stock-lacteos-y-quesos-01": 0.25},
        "familiar": {"stock-lacteos-y-quesos-01": 0.40},
    },
    "pepperoni": {
        "personal": {"stock-carnes-embutidos-y-proteinas-10": 0.04},
        "mediana": {"stock-carnes-embutidos-y-proteinas-10": 0.07},
        "familiar": {"stock-carnes-embutidos-y-proteinas-10": 0.11},
    },
    "jamon": {
        "personal": {"stock-carnes-embutidos-y-proteinas-08": 0.04},
        "mediana": {"stock-carnes-embutidos-y-proteinas-08": 0.07},
        "familiar": {"stock-carnes-embutidos-y-proteinas-08": 0.10},
    },
    "pollo": {
        "personal": {"stock-carnes-embutidos-y-proteinas-02": 0.05},
        "mediana": {"stock-carnes-embutidos-y-proteinas-02": 0.08},
        "familiar": {"stock-carnes-embutidos-y-proteinas-02": 0.12},
    },
    "champinones": {
        "personal": {"stock-verduras-hortalizas-y-hierbas-07": 0.03},
        "mediana": {"stock-verduras-hortalizas-y-hierbas-07": 0.05},
        "familiar": {"stock-verduras-hortalizas-y-hierbas-07": 0.08},
    },
    "cebolla": {
        "personal": {"stock-verduras-hortalizas-y-hierbas-03": 0.03},
        "mediana": {"stock-verduras-hortalizas-y-hierbas-03": 0.05},
        "familiar": {"stock-verduras-hortalizas-y-hierbas-03": 0.08},
    },
    "aceituna": {
        "personal": {"stock-verduras-hortalizas-y-hierbas-09": 0.02},
        "mediana": {"stock-verduras-hortalizas-y-hierbas-09": 0.04},
        "familiar": {"stock-verduras-hortalizas-y-hierbas-09": 0.06},
    },
    "albahaca": {
        "personal": {"stock-verduras-hortalizas-y-hierbas-12": 0.05},
        "mediana": {"stock-verduras-hortalizas-y-hierbas-12": 0.08},
        "familiar": {"stock-verduras-hortalizas-y-hierbas-12": 0.12},
    },
    "tomate_cherry": {
        "personal": {"stock-verduras-hortalizas-y-hierbas-02": 0.04},
        "mediana": {"stock-verduras-hortalizas-y-hierbas-02": 0.07},
        "familiar": {"stock-verduras-hortalizas-y-hierbas-02": 0.10},
    },
    "pina": {
        "personal": {"stock-frutas-02": 0.10},
        "mediana": {"stock-frutas-02": 0.18},
        "familiar": {"stock-frutas-02": 0.28},
    },
    "fresa": {
        "personal": {"stock-frutas-03": 0.05},
        "mediana": {"stock-frutas-03": 0.08},
        "familiar": {"stock-frutas-03": 0.12},
    },
}


def start_orders_after_delay(orders):
    now = datetime.now(timezone.utc)
    changed = False
    for order in orders:
        if order.estado != "recibido":
            continue
        created_at = order.creado_en
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if (now - created_at).total_seconds() >= PREPARATION_START_DELAY_SECONDS:
            order.estado = "en_preparacion"
            order.preparacion_inicio_en = now
            changed = True
    if changed:
        db.session.commit()


def estimate_order_queue(orders):
    active_orders = []
    for order in orders:
        if order.estado not in ACTIVE_ORDER_STATES:
            continue
        order_pizzas = sum(
            item.get("cantidad", 1)
            for item in json.loads(order.items_json)
            if item.get("es_pizza", True)
        )
        if order_pizzas:
            active_orders.append((order, order_pizzas))
    active_orders.sort(key=lambda entry: entry[0].creado_en)
    if not active_orders:
        return {}

    now = datetime.now(timezone.utc)
    first_created = active_orders[0][0].creado_en
    if first_created.tzinfo is None:
        first_created = first_created.replace(tzinfo=timezone.utc)
    preparation_started_at = first_created + timedelta(seconds=PREPARATION_START_DELAY_SECONDS)
    elapsed_minutes = max(0, (now - preparation_started_at).total_seconds() / 60)
    queued_pizzas = 0
    estimates = {}
    for order, order_pizzas in active_orders:
        queued_pizzas += order_pizzas
        remaining_minutes = max(0, queued_pizzas * MINUTOS_POR_PIZZA - elapsed_minutes)
        estimates[order.id] = math.ceil(remaining_minutes)
    return estimates


def as_utc_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def dashboard_period_bounds(period, now=None):
    local_now = (now or datetime.now(timezone.utc)).astimezone(BUSINESS_TIMEZONE)
    today = local_now.date()
    month_start = today.replace(day=1)
    if period == "today":
        local_start = datetime.combine(today, datetime.min.time(), BUSINESS_TIMEZONE)
        local_end = local_start + timedelta(days=1)
    elif period == "week":
        local_start = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time(), BUSINESS_TIMEZONE)
        local_end = local_start + timedelta(days=7)
    elif period in {"month", "compare"}:
        local_start = datetime.combine(month_start, datetime.min.time(), BUSINESS_TIMEZONE)
        local_end = local_now + timedelta(seconds=1)
    elif period == "previous_month":
        local_end = datetime.combine(month_start, datetime.min.time(), BUSINESS_TIMEZONE)
        previous_month_last_day = month_start - timedelta(days=1)
        local_start = datetime.combine(previous_month_last_day.replace(day=1), datetime.min.time(), BUSINESS_TIMEZONE)
    else:
        raise ValueError("Periodo no válido.")
    current = (local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc))
    comparison = None
    if period == "compare":
        previous_month_last_day = month_start - timedelta(days=1)
        previous_start = datetime.combine(previous_month_last_day.replace(day=1), datetime.min.time(), BUSINESS_TIMEZONE)
        previous_end = datetime.combine(month_start, datetime.min.time(), BUSINESS_TIMEZONE)
        comparison = (previous_start.astimezone(timezone.utc), previous_end.astimezone(timezone.utc))
    return current, comparison


def date_in_range(value, bounds):
    utc_value = as_utc_datetime(value)
    return bool(utc_value and bounds[0] <= utc_value < bounds[1])


def average_minutes(values):
    durations = [(end - start).total_seconds() / 60 for start, end in values if start and end and end >= start]
    return round(sum(durations) / len(durations), 1) if durations else None


def seed_menu_items():
    for item_id in OBSOLETE_MENU_ITEM_IDS:
        obsolete_item = db.session.get(MenuItemDB, item_id)
        if obsolete_item is not None:
            db.session.delete(obsolete_item)
    for order, item in enumerate(MENU_ITEMS):
        existing_item = db.session.get(MenuItemDB, item["id"])
        if existing_item is not None:
            existing_item.categoria_orden = CATEGORY_ORDER[item["categoria"]]
            existing_item.orden = order
            continue
        db.session.add(MenuItemDB(
            id=item["id"],
            categoria=item["categoria"],
            subcategoria=item["subcategoria"],
            nombre=item["nombre"],
            descripcion=item["descripcion"],
            ingredientes_json=json.dumps(item["ingredientes"], ensure_ascii=False),
            precio=item["precio"],
            precio_mediana=item.get("precio_mediana"),
            precio_familiar=item.get("precio_familiar"),
            imagen=item.get("imagen", ""),
            es_pizza=item["es_pizza"],
            categoria_orden=CATEGORY_ORDER[item["categoria"]],
            orden=order,
        ))
    db.session.commit()


def seed_inventory():
    expected_ids = {item["item_id"] for item in INVENTORY_ITEMS}
    for row in InventarioDB.query.all():
        if row.tipo == "pizza" or (
            row.tipo == "ingrediente"
            and not row.item_id.startswith("custom-")
            and row.item_id not in expected_ids
        ):
            db.session.delete(row)
        elif row.tipo == "ingrediente" and row.item_id.startswith("custom-") and not row.categoria:
            row.categoria = "Otros"

    for item in INVENTORY_ITEMS:
        row = InventarioDB.query.filter_by(tipo="ingrediente", item_id=item["item_id"]).first()
        if row is None:
            db.session.add(InventarioDB(
                tipo="ingrediente",
                item_id=item["item_id"],
                nombre=item["nombre"],
                categoria=item["categoria"],
                cantidad=100,
                unidad=item["unidad"],
                stock_minimo=CRITICAL_STOCK_MINIMA.get(item["nombre"], 0),
            ))
        else:
            row.nombre = item["nombre"]
            row.categoria = item["categoria"]
            if row.stock_minimo == 0 and item["nombre"] in CRITICAL_STOCK_MINIMA:
                row.stock_minimo = CRITICAL_STOCK_MINIMA[item["nombre"]]
    db.session.commit()


def normalize_pizza_dough():
    retired_dough_ids = {"masa_delgada", "masa_integral", "masa_sin_gluten"}
    for pizza in PizzaDB.query.all():
        ingredients = json.loads(pizza.ingredientes_json or "[]")
        if any(item_id in retired_dough_ids for item_id in ingredients):
            ingredients = ["masa_clasica" if item_id in retired_dough_ids else item_id for item_id in ingredients]
            pizza.ingredientes_json = json.dumps(list(dict.fromkeys(ingredients)))
        if pizza.id == "huerto-vegana":
            pizza.descripcion = pizza.descripcion.replace("masa integral", "masa italiana")
        elif pizza.id == "libre-gluten":
            pizza.nombre = "Jardín Italiano"
            pizza.descripcion = "Pesto, rúcula, tomate cherry y aceitunas negras sobre nuestra masa italiana."
            pizza.badge = "Vegetariana"
            pizza.tags_json = json.dumps([tag for tag in json.loads(pizza.tags_json or "[]") if "gluten" not in tag.lower()], ensure_ascii=False)
        elif pizza.id == "dulce-nutella":
            pizza.descripcion = pizza.descripcion.replace("Masa delgada", "Masa italiana")

    for ingredient in IngredienteDB.query.filter(IngredienteDB.grupo == "masa", IngredienteDB.id != "masa_clasica").all():
        db.session.delete(ingredient)
    italian_dough = db.session.get(IngredienteDB, "masa_clasica")
    if italian_dough is not None:
        italian_dough.nombre = "Masa italiana"
        italian_dough.precio = 0
    db.session.commit()


def create_app(database_uri=None):
    project_root = Path(__file__).resolve().parents[1]
    instance_dir = project_root / "instance"
    app = Flask(
        __name__,
        instance_path=str(instance_dir),
        instance_relative_config=True,
    )
    if not database_uri:
        instance_dir.mkdir(parents=True, exist_ok=True)
    database_path = instance_dir / "pizza_pronto.db"
    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_uri or f"sqlite:///{database_path.as_posix()}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JSON_AS_ASCII=False,
        SECRET_KEY=os.environ.get("PIZZA_PRONTO_SECRET_KEY", "pizza-pronto-local-dev-key"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        UPLOAD_FOLDER=os.path.join(os.path.dirname(__file__), "uploads"),
    )
    db.init_app(app)

    with app.app_context():
        db.create_all()
        user_columns = {column["name"] for column in inspect(db.engine).get_columns("usuarios")}
        if "rol" not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE usuarios ADD COLUMN rol VARCHAR(20) NOT NULL DEFAULT 'cliente'"))
        order_columns = {column["name"] for column in inspect(db.engine).get_columns("pedidos")}
        order_migrations = {
            "referencia": "VARCHAR(300) NOT NULL DEFAULT ''",
            "dni_ruc": "VARCHAR(300) NOT NULL DEFAULT ''",
            "numero_mesa": "VARCHAR(300) NOT NULL DEFAULT ''",
            "paga_con": "FLOAT NOT NULL DEFAULT 0",
            "vuelto": "FLOAT NOT NULL DEFAULT 0",
            "canal": "VARCHAR(30) NOT NULL DEFAULT 'sitio_web'",
            "preparacion_inicio_en": "DATETIME",
            "listo_en": "DATETIME",
            "entregado_en": "DATETIME",
            "pagado_en": "DATETIME",
        }
        for column_name, column_type in order_migrations.items():
            if column_name not in order_columns:
                with db.engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE pedidos ADD COLUMN {column_name} {column_type}"))
        inventory_columns = {column["name"] for column in inspect(db.engine).get_columns("inventario")}
        needs_stock_threshold_backfill = "stock_minimo" not in inventory_columns
        inventory_migrations = {
            "categoria": "VARCHAR(80) NOT NULL DEFAULT 'Otros'",
            "stock_minimo": "FLOAT NOT NULL DEFAULT 0",
            "costo_unitario": "FLOAT",
        }
        for column_name, column_type in inventory_migrations.items():
            if column_name not in inventory_columns:
                with db.engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE inventario ADD COLUMN {column_name} {column_type}"))
        if needs_stock_threshold_backfill:
            for item in InventarioDB.query.filter_by(tipo="ingrediente").all():
                item.stock_minimo = CRITICAL_STOCK_MINIMA.get(item.nombre, 0)
            db.session.commit()

        menu_columns = {column["name"] for column in inspect(db.engine).get_columns("menu_items")}
        menu_migrations = {
            "precio_mediana": "FLOAT",
            "precio_familiar": "FLOAT",
            "costo_personal": "FLOAT",
            "costo_mediana": "FLOAT",
            "costo_familiar": "FLOAT",
            "imagen": "VARCHAR(300) NOT NULL DEFAULT ''",
        }
        for column_name, column_type in menu_migrations.items():
            if column_name not in menu_columns:
                with db.engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE menu_items ADD COLUMN {column_name} {column_type}"))
        sembrar_si_hace_falta()
        seed_menu_items()
        normalize_pizza_dough()
        cargar_desde_bd()

        admin = UsuarioDB.query.filter_by(email=ADMIN_EMAIL).first()
        if admin is None:
            admin = UsuarioDB(
                nombre="Administrador",
                email=ADMIN_EMAIL,
                password_hash=generate_password_hash(ADMIN_PASSWORD),
                rol="admin",
            )
            db.session.add(admin)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                admin = UsuarioDB.query.filter_by(email=ADMIN_EMAIL).first()
                if admin is None:
                    raise
        elif admin.rol != "admin":
            admin.rol = "admin"
            admin.password_hash = generate_password_hash(ADMIN_PASSWORD)
            db.session.commit()

        seed_inventory()

    def auth_response(user=None, mode="account"):
        profile = user.to_dict() if user else {"nombre": "Invitado", "email": None}
        return {"authenticated": True, "mode": mode, "user": profile}

    def normalize_customer(payload):
        customer = {
            "nombre": str(payload.get("nombre", "")).strip(),
            "telefono": str(payload.get("telefono", "")).strip(),
            "tipo_entrega": str(payload.get("tipo_entrega", "")),
            "direccion": str(payload.get("direccion", "")).strip(),
            "referencia": str(payload.get("referencia", "")).strip(),
            "dni_ruc": str(payload.get("dni_ruc", "")).strip(),
            "numero_mesa": str(payload.get("numero_mesa", "")).strip(),
        }
        customer["tipo_entrega"] = {
            "domicilio": "delivery",
            "recojo": "retiro_local",
        }.get(customer["tipo_entrega"], customer["tipo_entrega"])
        if not customer["nombre"] or len(customer["nombre"]) > 120:
            return None, "Escribe tu nombre (máximo 120 caracteres)."
        if not customer["telefono"] or len(customer["telefono"]) > 40:
            return None, "Escribe un número de teléfono válido."
        if customer["tipo_entrega"] not in DELIVERY_TYPES:
            return None, "Selecciona delivery, retiro o comer en local."
        if customer["tipo_entrega"] == "delivery":
            if not customer["direccion"]:
                return None, "Escribe la dirección de delivery."
            if not customer["referencia"]:
                return None, "Agrega una referencia para encontrar la dirección."
        elif customer["tipo_entrega"] == "comer_local":
            if not customer["numero_mesa"]:
                return None, "Indica el número de mesa."
            if not customer["dni_ruc"]:
                return None, "Indica el DNI o RUC para la boleta."
            customer["direccion"] = STORE_ADDRESS
        else:
            customer["direccion"] = STORE_ADDRESS
            customer["referencia"] = ""
            customer["dni_ruc"] = ""
            customer["numero_mesa"] = ""
        return customer, None

    def current_account():
        user_id = session.get("user_id")
        return db.session.get(UsuarioDB, user_id) if user_id else None

    def has_valid_session():
        if session.get("guest"):
            return True
        user_id = session.get("user_id")
        if user_id and db.session.get(UsuarioDB, user_id):
            return True
        session.clear()
        return False

    def admin_error():
        user = current_account()
        if user is None:
            return jsonify({"error": "Inicia sesión para continuar."}), 401
        if user.rol != "admin":
            return jsonify({"error": "No tienes permisos para administrar el menú."}), 403
        return None

    def consume_soft_inventory(requested_items):
        def apply_consumption(stock_item_id, amount, order_quantity, source):
            stock = InventarioDB.query.filter_by(
                tipo="ingrediente",
                item_id=stock_item_id,
            ).first()
            if stock is None:
                app.logger.warning(
                    "Inventario blando: no existe el insumo %s mapeado para %s; "
                    "el pedido continuara.",
                    stock_item_id,
                    source,
                )
                return

            consumed = amount * order_quantity
            stock.cantidad = round(stock.cantidad - consumed, 4)
            if stock.cantidad < 0:
                app.logger.warning(
                    "Inventario blando: %s quedo en %.4f %s tras procesar %s; "
                    "el pedido continuara.",
                    stock.nombre,
                    stock.cantidad,
                    stock.unidad,
                    source,
                )

        for requested in requested_items:
            quantity = int(requested.get("cantidad", 1))
            menu_item_id = requested.get("menu_item_id")
            if menu_item_id:
                product_consumption = CONSUMO_POR_PRODUCTO.get(menu_item_id)
                if product_consumption is None:
                    app.logger.warning(
                        "Inventario blando: no hay receta de consumo para el producto %s; "
                        "el pedido continuara.",
                        menu_item_id,
                    )
                    continue
                for stock_item_id, amount in product_consumption.items():
                    apply_consumption(stock_item_id, amount, quantity, menu_item_id)
                continue

            size_id = requested.get("tamano_id", "mediana")
            for ingredient_id in requested.get("ingredientes", []):
                ingredient_consumption = CONSUMO_POR_INGREDIENTE_Y_TAMANO.get(ingredient_id)
                if ingredient_consumption is None or size_id not in ingredient_consumption:
                    app.logger.warning(
                        "Inventario blando: no hay receta de consumo para el ingrediente %s "
                        "en tamano %s; el pedido continuara.",
                        ingredient_id,
                        size_id,
                    )
                    continue
                for stock_item_id, amount in ingredient_consumption[size_id].items():
                    apply_consumption(stock_item_id, amount, quantity, ingredient_id)

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "service": "pizza-pronto-api"})

    @app.get("/api/auth/me")
    def current_session():
        if session.get("guest"):
            customer = session.get("guest_customer")
            if not isinstance(customer, dict):
                session.clear()
                return jsonify({"authenticated": False})
            return jsonify({**auth_response(mode="guest"), "cliente": customer})
        user_id = session.get("user_id")
        user = db.session.get(UsuarioDB, user_id) if user_id else None
        if user:
            return jsonify(auth_response(user))
        session.clear()
        return jsonify({"authenticated": False})

    @app.post("/api/auth/register")
    def register():
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("nombre", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        if not name or len(name) > 120:
            return jsonify({"error": "Escribe tu nombre (máximo 120 caracteres)."}), 400
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
            return jsonify({"error": "Escribe un correo electrónico válido."}), 400
        if len(password) < 8:
            return jsonify({"error": "La contraseña debe tener al menos 8 caracteres."}), 400
        if UsuarioDB.query.filter(db.func.lower(UsuarioDB.email) == email).first():
            return jsonify({"error": "Ya existe una cuenta con ese correo."}), 409

        user = UsuarioDB(nombre=name, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({"error": "Ya existe una cuenta con ese correo."}), 409
        session.clear()
        session["user_id"] = user.id
        return jsonify(auth_response(user)), 201

    @app.post("/api/auth/login")
    def login():
        payload = request.get_json(silent=True) or {}
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        user = UsuarioDB.query.filter(db.func.lower(UsuarioDB.email) == email).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "Correo o contraseña incorrectos."}), 401
        session.clear()
        session["user_id"] = user.id
        return jsonify(auth_response(user))

    @app.post("/api/auth/guest")
    def enter_as_guest():
        payload = request.get_json(silent=True) or {}
        customer, error = normalize_customer(payload.get("cliente") or {})
        if error:
            return jsonify({"error": error}), 400
        session.clear()
        session["guest"] = True
        session["guest_customer"] = customer
        return jsonify({**auth_response(mode="guest"), "cliente": customer})

    @app.post("/api/auth/logout")
    def logout():
        session.clear()
        return jsonify({"authenticated": False})

    @app.get("/api/catalog")
    def catalog():
        return jsonify({
            "pizzas": [pizza for pizza in PIZZAS if pizza.get("activo", True)],
            "menu_items": [
                item.to_dict()
                for item in MenuItemDB.query.filter_by(activo=True).order_by(MenuItemDB.categoria_orden, MenuItemDB.orden).all()
            ],
            "ingredientes": INGREDIENTES,
            "grupos": GRUPOS,
            "tamanos": TAMANOS,
            "delivery": {
                "costo": COSTO_DELIVERY,
                "gratis_desde": DELIVERY_GRATIS_DESDE,
            },
        })

    @app.get("/api/admin/catalog")
    def admin_catalog():
        error = admin_error()
        if error:
            return error
        return jsonify({
            "pizzas": PIZZAS,
            "menu_items": [item.to_dict() for item in MenuItemDB.query.order_by(MenuItemDB.categoria_orden, MenuItemDB.orden).all()],
            "ingredientes": INGREDIENTES,
            "delivery": {
                "costo": COSTO_DELIVERY,
                "gratis_desde": DELIVERY_GRATIS_DESDE,
            },
        })

    @app.post("/api/admin/pizzas")
    def create_menu_pizza():
        error = admin_error()
        if error:
            return error
        name = request.form.get("nombre", "").strip()
        description = request.form.get("descripcion", "").strip()
        subcategory = request.form.get("tipo", "").strip()
        ingredient_text = request.form.get("ingredientes", "")
        image = request.files.get("imagen")
        if not name or len(name) > 160:
            return jsonify({"error": "Escribe un nombre de pizza válido."}), 400
        if len(description) > 2000 or not subcategory or len(subcategory) > 80:
            return jsonify({"error": "Completa la descripción y el tipo de pizza."}), 400
        if image is None or not image.filename:
            return jsonify({"error": "Sube una imagen referencial de la pizza."}), 400
        extension = image.filename.rsplit(".", 1)[-1].lower() if "." in image.filename else ""
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({"error": "La imagen debe ser JPG, PNG o WEBP."}), 400
        try:
            prices = {size: float(request.form.get(f"precio_{size}", "")) for size in ("personal", "mediana", "familiar")}
        except (TypeError, ValueError):
            return jsonify({"error": "Completa el precio de los tres tamaños."}), 400
        if any(not math.isfinite(price) or price <= 0 for price in prices.values()):
            return jsonify({"error": "Los tres precios deben ser mayores que cero."}), 400
        costs = {}
        try:
            for size in ("personal", "mediana", "familiar"):
                raw_cost = request.form.get(f"costo_{size}", "").strip()
                costs[size] = float(raw_cost) if raw_cost else None
        except (TypeError, ValueError):
            return jsonify({"error": "Revisa los costos estimados de los tamaños."}), 400
        if any(value is not None and (not math.isfinite(value) or value < 0) for value in costs.values()):
            return jsonify({"error": "Los costos deben ser números iguales o mayores que cero."}), 400

        slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") or "pizza"
        item_id = f"pizza-admin-{slug}-{uuid.uuid4().hex[:8]}"
        filename = f"{uuid.uuid4().hex}.{extension}"
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        ingredient_names = [line.strip() for line in ingredient_text.splitlines() if line.strip()]
        next_order = db.session.query(db.func.max(MenuItemDB.orden)).filter_by(categoria="Pizzas").scalar() or 0
        pizza = MenuItemDB(
            id=item_id,
            categoria="Pizzas",
            subcategoria=subcategory,
            nombre=name,
            descripcion=description,
            ingredientes_json=json.dumps(ingredient_names, ensure_ascii=False),
            precio=prices["personal"],
            precio_mediana=prices["mediana"],
            precio_familiar=prices["familiar"],
            costo_personal=costs["personal"],
            costo_mediana=costs["mediana"],
            costo_familiar=costs["familiar"],
            imagen=f"/api/uploads/{filename}",
            es_pizza=True,
            activo=True,
            categoria_orden=CATEGORY_ORDER["Pizzas"],
            orden=next_order + 1,
        )
        db.session.add(pizza)
        db.session.commit()
        return jsonify({"pizza": pizza.to_dict()}), 201

    @app.get("/api/uploads/<path:filename>")
    def uploaded_image(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.get("/api/admin/orders")
    def admin_orders():
        error = admin_error()
        if error:
            return error
        orders = PedidoDB.query.order_by(PedidoDB.creado_en.asc(), PedidoDB.id.asc()).all()
        start_orders_after_delay(orders)
        estimates = estimate_order_queue(orders)
        result = []
        for order in reversed(orders):
            order_data = order.to_dict()
            order_data["estimado_minutos"] = estimates.get(order.id)
            result.append(order_data)
        return jsonify({"pedidos": result})

    @app.get("/api/admin/dashboard")
    def admin_dashboard():
        error = admin_error()
        if error:
            return error
        period = request.args.get("period", "today")
        try:
            bounds, comparison_bounds = dashboard_period_bounds(period)
        except ValueError:
            return jsonify({"error": "Periodo no válido."}), 400

        all_orders = PedidoDB.query.order_by(PedidoDB.creado_en.asc()).all()
        period_orders = [order for order in all_orders if date_in_range(order.creado_en, bounds)]
        paid_orders = [order for order in period_orders if order.estado == "pagado"]
        sales_total = round(sum(order.total for order in paid_orders), 2)
        ticket_average = round(sales_total / len(paid_orders), 2) if paid_orders else None

        menu_pizzas = MenuItemDB.query.filter_by(es_pizza=True).all()
        pizza_names = {item.nombre for item in menu_pizzas}
        pizza_names.update(pizza["nombre"] for pizza in PIZZAS if pizza.get("activo", True))
        pizza_units = {name: 0 for name in pizza_names}
        pizza_sales = {name: 0.0 for name in pizza_names}
        size_units = {"Personal": 0, "Mediana": 0, "Familiar": 0}
        extra_counts = {}
        hours = [{"hour": f"{hour:02d}:00", "orders": 0, "sales": 0.0} for hour in range(24)]
        channel_stats = {}
        fulfillment_stats = {}
        payment_stats = {}
        preparation_durations = []
        delivery_durations = []
        first_paid_by_customer = {}
        for order in all_orders:
            if order.estado != "pagado" or not order.telefono:
                continue
            timestamp = as_utc_datetime(order.creado_en)
            existing = first_paid_by_customer.get(order.telefono)
            if existing is None or timestamp < existing:
                first_paid_by_customer[order.telefono] = timestamp

        for order in paid_orders:
            created_at = as_utc_datetime(order.creado_en)
            local_hour = created_at.astimezone(BUSINESS_TIMEZONE).hour
            hours[local_hour]["orders"] += 1
            hours[local_hour]["sales"] += order.total

            channel = order.canal or "sitio_web"
            channel_stats.setdefault(channel, {"name": channel.replace("_", " ").title(), "orders": 0, "sales": 0.0})
            channel_stats[channel]["orders"] += 1
            channel_stats[channel]["sales"] += order.total
            fulfillment = order.tipo_entrega or "sin_dato"
            fulfillment_stats.setdefault(fulfillment, {"name": fulfillment.replace("_", " ").title(), "orders": 0, "sales": 0.0})
            fulfillment_stats[fulfillment]["orders"] += 1
            fulfillment_stats[fulfillment]["sales"] += order.total
            payment = order.metodo_pago or "sin_dato"
            payment_stats.setdefault(payment, {"name": payment.title(), "orders": 0, "sales": 0.0})
            payment_stats[payment]["orders"] += 1
            payment_stats[payment]["sales"] += order.total

            for item in json.loads(order.items_json):
                quantity = int(item.get("cantidad", 1))
                if item.get("es_pizza", True):
                    name = item.get("nombre", "Pizza sin nombre")
                    pizza_units[name] = pizza_units.get(name, 0) + quantity
                    pizza_sales[name] = pizza_sales.get(name, 0.0) + float(item.get("total", 0))
                    size_value = str(item.get("tamano_id") or item.get("tamano", "")).lower()
                    for size_key, size_label in (("personal", "Personal"), ("mediana", "Mediana"), ("familiar", "Familiar")):
                        if size_key in size_value:
                            size_units[size_label] += quantity
                            break
                if not item.get("menu_item_id"):
                    for extra in item.get("extras", []):
                        extra_counts[extra] = extra_counts.get(extra, 0) + quantity

            if order.preparacion_inicio_en and order.listo_en:
                preparation_durations.append((as_utc_datetime(order.preparacion_inicio_en), as_utc_datetime(order.listo_en)))
            if order.tipo_entrega == "delivery" and order.listo_en and order.entregado_en:
                delivery_durations.append((as_utc_datetime(order.listo_en), as_utc_datetime(order.entregado_en)))

        ordered_pizzas = sorted(pizza_units.items(), key=lambda item: (-item[1], item[0].casefold()))
        top_pizzas = [
            {"nombre": name, "unidades": units, "ventas": round(pizza_sales.get(name, 0), 2)}
            for name, units in ordered_pizzas if units > 0
        ][:5]
        flop_pizzas = [
            {"nombre": name, "unidades": units, "ventas": round(pizza_sales.get(name, 0), 2)}
            for name, units in sorted(pizza_units.items(), key=lambda item: (item[1], item[0].casefold()))
        ][:5]

        size_chart = [{"name": name, "value": count} for name, count in size_units.items()]
        extras = [{"name": name, "value": count} for name, count in sorted(extra_counts.items(), key=lambda item: (-item[1], item[0]))[:10]]
        for row in hours:
            row["sales"] = round(row["sales"], 2)

        first_dates_in_period = [
            phone for phone, first_order in first_paid_by_customer.items()
            if date_in_range(first_order, bounds)
        ]
        period_customers = {order.telefono for order in paid_orders if order.telefono}
        returning_customers = len(period_customers - set(first_dates_in_period))

        menu_items_by_id = {item.id: item for item in menu_pizzas}
        margins = {}
        pizzas_without_cost = set()
        for order in paid_orders:
            for line in json.loads(order.items_json):
                menu_item = menu_items_by_id.get(line.get("menu_item_id"))
                if menu_item is None or not line.get("es_pizza", True):
                    continue
                size_id = line.get("tamano_id", "personal")
                size_cost = {
                    "personal": menu_item.costo_personal,
                    "mediana": menu_item.costo_mediana,
                    "familiar": menu_item.costo_familiar,
                }.get(size_id)
                if size_cost is None:
                    pizzas_without_cost.add(menu_item.nombre)
                    continue
                row = margins.setdefault(menu_item.nombre, {"ventas": 0.0, "costo": 0.0, "unidades": 0})
                row["ventas"] += float(line.get("total", 0))
                row["costo"] += size_cost * int(line.get("cantidad", 1))
                row["unidades"] += int(line.get("cantidad", 1))
        margin_rows = [
            {
                "nombre": name,
                "ventas": round(row["ventas"], 2),
                "costo": round(row["costo"], 2),
                "margen": round(row["ventas"] - row["costo"], 2),
                "porcentaje": round((row["ventas"] - row["costo"]) / row["ventas"] * 100, 1) if row["ventas"] else None,
                "unidades": row["unidades"],
            }
            for name, row in sorted(margins.items(), key=lambda entry: -(entry[1]["ventas"] - entry[1]["costo"]))
        ]

        stock_rows = InventarioDB.query.filter_by(tipo="ingrediente").all()
        stock_alerts = []
        inventory_value = 0.0
        valued_stock_count = 0
        for item in stock_rows:
            if item.costo_unitario is not None:
                inventory_value += item.cantidad * item.costo_unitario
                valued_stock_count += 1
            if item.stock_minimo > 0 and item.cantidad <= item.stock_minimo:
                level = "critico" if item.cantidad <= item.stock_minimo * 0.5 else "bajo"
                stock_alerts.append({**item.to_dict(), "nivel": level})
        stock_alerts.sort(key=lambda item: (item["nivel"] != "critico", item["cantidad"]))

        active_orders = [order for order in all_orders if order.estado in ACTIVE_ORDER_STATES]
        queued_pizzas = sum(
            int(item.get("cantidad", 1))
            for order in active_orders
            for item in json.loads(order.items_json)
            if item.get("es_pizza", True)
        )
        waste_rows = MermaDB.query.order_by(MermaDB.creado_en.desc()).all()
        waste_in_period = [row for row in waste_rows if date_in_range(row.creado_en, bounds)]
        waste_totals = {}
        for row in waste_in_period:
            key = (row.nombre, row.unidad)
            waste_totals[key] = waste_totals.get(key, 0) + row.cantidad
        waste_summary = [
            {"nombre": name, "unidad": unit, "cantidad": round(quantity, 3)}
            for (name, unit), quantity in sorted(waste_totals.items())
        ]

        comparison = None
        if comparison_bounds:
            previous_orders = [order for order in all_orders if order.estado == "pagado" and date_in_range(order.creado_en, comparison_bounds)]
            previous_sales = round(sum(order.total for order in previous_orders), 2)
            comparison = {
                "ventas": previous_sales,
                "pedidos": len(previous_orders),
                "variacion_porcentual": round((sales_total - previous_sales) / previous_sales * 100, 1) if previous_sales else None,
            }

        return jsonify({
            "periodo": period,
            "resumen": {
                "ventas": sales_total,
                "pedidos": len(paid_orders),
                "pedidos_totales": len(period_orders),
                "ticket_promedio": ticket_average,
                "clientes_nuevos": len(first_dates_in_period),
                "clientes_recurrentes": returning_customers,
            },
            "comparacion": comparison,
            "ranking": {"top": top_pizzas, "flop": flop_pizzas},
            "ingredientes_extra": extras,
            "ventas_por_tamano": size_chart,
            "ventas_por_hora": hours,
            "operaciones": {
                "preparacion_promedio_minutos": average_minutes(preparation_durations),
                "preparacion_medida": len(preparation_durations),
                "delivery_promedio_minutos": average_minutes(delivery_durations),
                "delivery_medidos": len(delivery_durations),
                "pedidos_en_cola": len(active_orders),
                "pizzas_en_cola": queued_pizzas,
                "capacidad_pizzas": KITCHEN_CAPACITY_PIZZAS,
                "cuello_de_botella": queued_pizzas > KITCHEN_CAPACITY_PIZZAS,
            },
            "canales": list(sorted(channel_stats.values(), key=lambda row: -row["sales"])),
            "modalidades": list(sorted(fulfillment_stats.values(), key=lambda row: -row["sales"])),
            "metodos_pago": list(sorted(payment_stats.values(), key=lambda row: -row["sales"])),
            "margenes_pizza": margin_rows,
            "pizzas_sin_costo": len(pizzas_without_cost),
            "inventario": {
                "alertas": stock_alerts,
                "valor_estimado": round(inventory_value, 2) if valued_stock_count else None,
                "insumos_con_costo": valued_stock_count,
            },
            "mermas": waste_summary,
            "registros_merma": [row.to_dict() for row in waste_in_period[:10]],
        })

    @app.get("/api/admin/waste")
    def admin_waste():
        error = admin_error()
        if error:
            return error
        period = request.args.get("period", "month")
        try:
            bounds, _comparison = dashboard_period_bounds(period)
        except ValueError:
            return jsonify({"error": "Periodo no válido."}), 400
        rows = [row for row in MermaDB.query.order_by(MermaDB.creado_en.desc()).all() if date_in_range(row.creado_en, bounds)]
        return jsonify({"mermas": [row.to_dict() for row in rows]})

    @app.post("/api/admin/waste")
    def add_waste_record():
        error = admin_error()
        if error:
            return error
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("nombre", "")).strip()
        unit = payload.get("unidad", "kg")
        reason = str(payload.get("motivo", "")).strip()
        try:
            quantity = float(payload.get("cantidad"))
        except (TypeError, ValueError):
            quantity = 0
        if not name or len(name) > 120 or not math.isfinite(quantity) or quantity <= 0:
            return jsonify({"error": "Indica insumo y una cantidad de merma mayor que cero."}), 400
        if unit not in UNIDADES_INVENTARIO:
            return jsonify({"error": "La unidad de medida no es válida."}), 400
        record = MermaDB(nombre=name, cantidad=quantity, unidad=unit, motivo=reason[:240])
        db.session.add(record)
        db.session.commit()
        return jsonify({"merma": record.to_dict()}), 201

    @app.patch("/api/admin/orders/<codigo>")
    def update_admin_order(codigo):
        error = admin_error()
        if error:
            return error
        order = PedidoDB.query.filter_by(codigo=codigo).first()
        if order is None:
            return jsonify({"error": "No se encontró ese pedido."}), 404
        next_state = ORDER_TRANSITIONS.get(order.estado)
        requested_state = (request.get_json(silent=True) or {}).get("estado")
        if requested_state != next_state:
            return jsonify({"error": "El pedido debe avanzar al siguiente estado disponible."}), 400
        order.estado = requested_state
        state_time = datetime.now(timezone.utc)
        if requested_state == "en_preparacion":
            order.preparacion_inicio_en = state_time
        elif requested_state == "listo":
            if order.preparacion_inicio_en is None:
                order.preparacion_inicio_en = order.creado_en
            order.listo_en = state_time
        elif requested_state == "entregado":
            order.entregado_en = state_time
        elif requested_state == "pagado":
            order.pagado_en = state_time
        db.session.commit()
        return jsonify({"pedido": order.to_dict()})

    @app.get("/api/admin/inventory")
    def admin_inventory():
        error = admin_error()
        if error:
            return error
        items = InventarioDB.query.filter_by(tipo="ingrediente").order_by(
            InventarioDB.categoria, InventarioDB.nombre
        ).all()
        categories = list(INVENTORY_CATEGORIES)
        if any(item.categoria == "Otros" for item in items):
            categories.append("Otros")
        return jsonify({"categorias": categories, "ingredientes": [item.to_dict() for item in items]})

    @app.post("/api/admin/inventory")
    def add_inventory_item():
        error = admin_error()
        if error:
            return error
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("nombre", "")).strip()
        unit = payload.get("unidad", "kg")
        category = payload.get("categoria", "Otros")
        try:
            quantity = float(payload.get("cantidad", 0))
        except (TypeError, ValueError):
            quantity = -1
        if not name or len(name) > 120:
            return jsonify({"error": "Escribe un nombre de ingrediente válido."}), 400
        if not math.isfinite(quantity) or quantity < 0:
            return jsonify({"error": "La cantidad debe ser un número igual o mayor que cero."}), 400
        if unit not in UNIDADES_INVENTARIO:
            return jsonify({"error": "La unidad de medida no es válida."}), 400
        if category not in {*INVENTORY_CATEGORIES, "Otros"}:
            return jsonify({"error": "La categoría de inventario no es válida."}), 400
        item = InventarioDB(
            tipo="ingrediente",
            item_id=f"custom-{uuid.uuid4().hex[:12]}",
            nombre=name,
            categoria=category,
            cantidad=quantity,
            unidad=unit,
        )
        db.session.add(item)
        db.session.commit()
        return jsonify({"item": item.to_dict()}), 201

    @app.put("/api/admin/inventory/<item_type>/<item_id>")
    def update_inventory_item(item_type, item_id):
        error = admin_error()
        if error:
            return error
        if item_type not in {"pizza", "ingrediente"}:
            return jsonify({"error": "Tipo de inventario no válido."}), 400
        item = InventarioDB.query.filter_by(tipo=item_type, item_id=item_id).first()
        if item is None:
            return jsonify({"error": "No se encontró ese artículo de inventario."}), 404
        payload = request.get_json(silent=True) or {}
        try:
            quantity = float(payload.get("cantidad"))
        except (TypeError, ValueError):
            quantity = -1
        if not math.isfinite(quantity) or quantity < 0:
            return jsonify({"error": "La cantidad debe ser un número igual o mayor que cero."}), 400
        unit = "unidad" if item_type == "pizza" else payload.get("unidad")
        if unit not in UNIDADES_INVENTARIO:
            return jsonify({"error": "La unidad de medida no es válida."}), 400
        item.cantidad = quantity
        item.unidad = unit
        db.session.commit()
        return jsonify({"item": item.to_dict()})

    @app.put("/api/admin/pizzas/<pizza_id>")
    def update_admin_pizza(pizza_id):
        error = admin_error()
        if error:
            return error
        pizza = db.session.get(PizzaDB, pizza_id)
        if pizza is None:
            return jsonify({"error": "No se encontró esa pizza."}), 404

        payload = request.get_json(silent=True) or {}
        form_values = request.form.to_dict() if request.form else {}
        if form_values:
            payload = {**payload, **form_values}
        image = request.files.get("imagen") if request.files else None

        name = str(payload.get("nombre", "")).strip()
        description = str(payload.get("descripcion", "")).strip()
        prices = payload.get("precios", {}) if isinstance(payload.get("precios"), dict) else {}

        if not prices and form_values:
            prices = {
                "personal": form_values.get("precio_personal"),
                "mediana": form_values.get("precio_mediana"),
                "familiar": form_values.get("precio_familiar"),
            }

        if not name or len(name) > 120:
            return jsonify({"error": "Escribe un nombre de pizza válido."}), 400
        try:
            personal = float(prices.get("personal") or payload.get("precio_personal") or pizza.precio_personal)
            mediana = float(prices.get("mediana") or payload.get("precio_mediana") or pizza.precio_mediana)
            familiar = float(prices.get("familiar") or payload.get("precio_familiar") or pizza.precio_familiar)
        except (TypeError, ValueError):
            return jsonify({"error": "Completa los precios de los tres tamaños."}), 400
        if any(not math.isfinite(price) or price < 0 for price in (personal, mediana, familiar)):
            return jsonify({"error": "Los precios deben ser números iguales o mayores que cero."}), 400

        if image and image.filename:
            extension = image.filename.rsplit(".", 1)[-1].lower() if "." in image.filename else ""
            if extension not in ALLOWED_IMAGE_EXTENSIONS:
                return jsonify({"error": "La imagen debe ser JPG, PNG o WEBP."}), 400
            filename = f"{uuid.uuid4().hex}.{extension}"
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            pizza.imagen = f"/api/uploads/{filename}"
        elif payload.get("imagen"):
            pizza.imagen = str(payload["imagen"]).strip()

        pizza.nombre = name
        pizza.descripcion = description
        pizza.precio_personal = personal
        pizza.precio_mediana = mediana
        pizza.precio_familiar = familiar
        inventory_row = InventarioDB.query.filter_by(tipo="pizza", item_id=pizza_id).first()
        if inventory_row:
            inventory_row.nombre = name
        db.session.commit()
        cargar_desde_bd()
        return jsonify({"pizza": pizza.to_dict()})

    @app.put("/api/admin/menu-items/<menu_item_id>")
    def update_menu_item(menu_item_id):
        error = admin_error()
        if error:
            return error
        item = db.session.get(MenuItemDB, menu_item_id)
        if item is None:
            return jsonify({"error": "No se encontró ese producto."}), 404

        payload = request.get_json(silent=True) or {}
        form_values = request.form.to_dict() if request.form else {}
        if form_values:
            payload = {**payload, **form_values}
        image = request.files.get("imagen") if request.files else None

        name = str(payload.get("nombre", "")).strip()
        description = str(payload.get("descripcion", "")).strip()
        price_value = payload.get("precio")
        if price_value is None and "precio_unitario" in payload:
            price_value = payload.get("precio_unitario")

        if not name or len(name) > 160:
            return jsonify({"error": "Escribe un nombre de producto válido."}), 400
        try:
            price = float(price_value if price_value is not None else item.precio)
        except (TypeError, ValueError):
            return jsonify({"error": "El precio del producto no es válido."}), 400
        if not math.isfinite(price) or price < 0:
            return jsonify({"error": "El precio debe ser un número mayor o igual que cero."}), 400

        if image and image.filename:
            extension = image.filename.rsplit(".", 1)[-1].lower() if "." in image.filename else ""
            if extension not in ALLOWED_IMAGE_EXTENSIONS:
                return jsonify({"error": "La imagen debe ser JPG, PNG o WEBP."}), 400
            filename = f"{uuid.uuid4().hex}.{extension}"
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            item.imagen = f"/api/uploads/{filename}"
        elif payload.get("imagen"):
            item.imagen = str(payload["imagen"]).strip()

        item.nombre = name
        item.descripcion = description
        item.precio = price
        if item.es_pizza:
            item.precio_mediana = payload.get("precio_mediana")
            item.precio_familiar = payload.get("precio_familiar")
        db.session.commit()
        return jsonify({"item": item.to_dict()})

    @app.patch("/api/admin/pizzas/<pizza_id>/visibility")
    def set_pizza_visibility(pizza_id):
        error = admin_error()
        if error:
            return error
        pizza = db.session.get(PizzaDB, pizza_id)
        if pizza is None:
            return jsonify({"error": "No se encontró esa pizza."}), 404
        payload = request.get_json(silent=True) or {}
        active = payload.get("activo")
        if not isinstance(active, bool):
            return jsonify({"error": "Indica si la pizza debe estar activa u oculta."}), 400
        pizza.activo = active
        db.session.commit()
        cargar_desde_bd()
        return jsonify({"pizza": pizza.to_dict()})

    @app.patch("/api/admin/menu-items/<menu_item_id>/visibility")
    def set_menu_item_visibility(menu_item_id):
        error = admin_error()
        if error:
            return error
        item = db.session.get(MenuItemDB, menu_item_id)
        if item is None:
            return jsonify({"error": "No se encontró ese producto."}), 404
        payload = request.get_json(silent=True) or {}
        active = payload.get("activo")
        if not isinstance(active, bool):
            return jsonify({"error": "Indica si el producto debe estar activo u oculto."}), 400
        item.activo = active
        db.session.commit()
        return jsonify({"item": item.to_dict()})

    @app.delete("/api/admin/menu-items/<menu_item_id>")
    def delete_menu_item(menu_item_id):
        error = admin_error()
        if error:
            return error
        item = db.session.get(MenuItemDB, menu_item_id)
        if item is None:
            return jsonify({"error": "No se encontró ese producto."}), 404
        db.session.delete(item)
        db.session.commit()
        return jsonify({"ok": True})

    @app.delete("/api/admin/pizzas/<pizza_id>")
    def delete_admin_pizza(pizza_id):
        error = admin_error()
        if error:
            return error
        pizza = db.session.get(PizzaDB, pizza_id)
        if pizza is None:
            return jsonify({"error": "No se encontró esa pizza."}), 404
        inventory_row = InventarioDB.query.filter_by(tipo="pizza", item_id=pizza_id).first()
        if inventory_row:
            db.session.delete(inventory_row)
        db.session.delete(pizza)
        db.session.commit()
        cargar_desde_bd()
        return jsonify({"ok": True})

    @app.post("/api/quote")
    def quote():
        payload = request.get_json(silent=True) or {}
        pizza_id = payload.get("pizza_id") or None
        tamano_id = payload.get("tamano_id", "mediana")
        ingredient_ids = payload.get("ingredientes", [])
        if not isinstance(ingredient_ids, list) or any(not isinstance(item, str) for item in ingredient_ids):
            return jsonify({"error": "La lista de ingredientes no es válida."}), 400
        if pizza_id and (not obtener_pizza(pizza_id) or not obtener_pizza(pizza_id).get("activo", True)):
            return jsonify({"error": "La pizza ya no está disponible."}), 404
        if tamano_id not in {size["id"] for size in TAMANOS}:
            return jsonify({"error": "El tamaño seleccionado no existe."}), 400
        if any(not any(ingredient["id"] == item for ingredient in INGREDIENTES) for item in ingredient_ids):
            return jsonify({"error": "Uno o más ingredientes ya no están disponibles."}), 400

        revision = validar_combinacion(ingredient_ids)
        return jsonify({
            "ok": not revision["errores"],
            "errores": revision["errores"],
            "advertencias": revision["advertencias"],
            "bloqueados": ingredientes_bloqueados(ingredient_ids),
            **cotizar(pizza_id, ingredient_ids, tamano_id),
        }), 200 if not revision["errores"] else 422

    @app.post("/api/orders")
    def create_order():
        if not has_valid_session():
            return jsonify({"error": "Inicia sesión o continúa como invitado para pedir."}), 401
        payload = request.get_json(silent=True) or {}
        customer = payload.get("cliente") or {}
        customer, customer_error = normalize_customer(customer)
        if customer_error:
            return jsonify({"error": customer_error}), 400
        name = customer["nombre"]
        phone = customer["telefono"]
        delivery_type = customer["tipo_entrega"]
        payment_method = payload.get("metodo_pago", "efectivo")
        requested_items = payload.get("items", [])

        if payment_method not in {"efectivo", "tarjeta", "yape"}:
            return jsonify({"error": "El método de pago no es válido."}), 400
        if not isinstance(requested_items, list) or not requested_items:
            return jsonify({"error": "Agrega al menos una pizza al carrito."}), 400

        items = []
        subtotal = 0.0
        for requested in requested_items:
            if not isinstance(requested, dict):
                return jsonify({"error": "Hay un producto no válido en el carrito."}), 400
            menu_item_id = requested.get("menu_item_id")
            pizza_id = requested.get("pizza_id") or None
            if menu_item_id and pizza_id:
                return jsonify({"error": "El producto del menú no puede ser también una pizza personalizada."}), 400
            try:
                quantity = int(requested.get("cantidad", 1))
            except (TypeError, ValueError):
                quantity = 0
            if quantity < 1 or quantity > 20:
                return jsonify({"error": "La cantidad debe estar entre 1 y 20."}), 400
            if menu_item_id:
                menu_item = MenuItemDB.query.filter_by(id=menu_item_id, activo=True).first()
                if menu_item is None:
                    return jsonify({"error": "Un producto del menú ya no está disponible."}), 400
                requested_size = requested.get("tamano_id", "personal")
                menu_prices = {
                    "personal": menu_item.precio,
                    "mediana": menu_item.precio_mediana,
                    "familiar": menu_item.precio_familiar,
                }
                has_size_prices = menu_item.es_pizza and menu_item.precio_mediana is not None and menu_item.precio_familiar is not None
                if has_size_prices and requested_size not in menu_prices:
                    return jsonify({"error": "El tamaño seleccionado no existe."}), 400
                unit_price = menu_prices[requested_size] if has_size_prices else menu_item.precio
                size_name = {"personal": "Personal", "mediana": "Mediana", "familiar": "Familiar"}.get(requested_size, menu_item.subcategoria)
                line = {
                    "menu_item_id": menu_item.id,
                    "nombre": menu_item.nombre,
                    "tamano": size_name,
                    "tamano_id": requested_size if has_size_prices else None,
                    "ingredientes": json.loads(menu_item.ingredientes_json or "[]"),
                    "extras": [],
                    "descripcion": menu_item.descripcion,
                    "es_pizza": menu_item.es_pizza,
                    "cantidad": quantity,
                    "precio_unitario": unit_price,
                    "total": round(unit_price * quantity, 2),
                }
            else:
                ingredient_ids = requested.get("ingredientes", [])
                size_id = requested.get("tamano_id", "mediana")
                if not isinstance(ingredient_ids, list) or any(not isinstance(item, str) for item in ingredient_ids):
                    return jsonify({"error": "La receta de una pizza no es válida."}), 400
                if size_id not in {size["id"] for size in TAMANOS}:
                    return jsonify({"error": "El tamaño de una pizza no existe."}), 400
                pizza = obtener_pizza(pizza_id) if pizza_id else None
                if pizza_id and (not pizza or not pizza.get("activo", True)):
                    return jsonify({"error": "Una pizza del carrito ya no está disponible."}), 400
                if any(not any(ingredient["id"] == item for ingredient in INGREDIENTES) for item in ingredient_ids):
                    return jsonify({"error": "Un ingrediente del carrito ya no está disponible."}), 400
                revision = validar_combinacion(ingredient_ids)
                if revision["errores"]:
                    return jsonify({"error": revision["errores"][0]["detalle"]}), 422

                priced = cotizar(pizza_id, ingredient_ids, size_id)
                line = {
                    "nombre": str(requested.get("nombre") or (pizza["nombre"] if pizza else "Pizza personalizada")),
                    "tamano": priced["tamano_nombre"],
                    "tamano_id": size_id,
                    "ingredientes": [item["nombre"] for item in priced["detalle"]],
                    "extras": [item["nombre"] for item in priced["detalle"] if not item["incluido"]],
                    "es_pizza": True,
                    "cantidad": quantity,
                    "precio_unitario": priced["total"],
                    "total": round(priced["total"] * quantity, 2),
                }
            items.append(line)
            subtotal += line["total"]

        subtotal = round(subtotal, 2)
        delivery = COSTO_DELIVERY if delivery_type == "delivery" and subtotal < DELIVERY_GRATIS_DESDE else 0.0
        total = round(subtotal + delivery, 2)
        if payment_method == "efectivo":
            try:
                paid_amount = float(payload.get("paga_con"))
            except (TypeError, ValueError):
                paid_amount = -1
            if not math.isfinite(paid_amount) or paid_amount < total:
                return jsonify({"error": f"El monto en efectivo debe ser igual o mayor que S/ {total:.2f}."}), 400
            change = round(paid_amount - total, 2)
        else:
            paid_amount = total
            change = 0.0
        code = f"PP-{uuid.uuid4().hex[:7].upper()}"
        order = PedidoDB(
            codigo=code,
            cliente=name,
            telefono=phone,
            tipo_entrega=delivery_type,
            direccion=customer["direccion"],
            referencia=customer["referencia"],
            dni_ruc=customer["dni_ruc"],
            numero_mesa=customer["numero_mesa"],
            metodo_pago=payment_method,
            items_json=json.dumps(items, ensure_ascii=False),
            subtotal=subtotal,
            delivery=delivery,
            total=total,
            paga_con=paid_amount,
            vuelto=change,
        )
        consume_soft_inventory(requested_items)
        db.session.add(order)
        db.session.commit()
        active_orders = PedidoDB.query.filter(PedidoDB.estado.in_(ACTIVE_ORDER_STATES)).all()
        estimate = estimate_order_queue(active_orders).get(order.id)
        order_data = order.to_dict()
        order_data["estimado_minutos"] = estimate
        return jsonify({"pedido": order_data}), 201

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Ruta no encontrada."}), 404

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
