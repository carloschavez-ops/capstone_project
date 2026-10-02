import json
import math
import os
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

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
from backend.models import InventarioDB, PedidoDB, UsuarioDB


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
                cantidad=0,
                unidad=item["unidad"],
            ))
        else:
            row.nombre = item["nombre"]
            row.categoria = item["categoria"]
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
    app = Flask(__name__)
    database_path = os.path.join(os.path.dirname(__file__), "pizza_pronto.sqlite3")
    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_uri or f"sqlite:///{database_path}",
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
        for column_name in ("referencia", "dni_ruc", "numero_mesa", "paga_con", "vuelto"):
            if column_name not in order_columns:
                with db.engine.begin() as connection:
                    column_type = "FLOAT" if column_name in {"paga_con", "vuelto"} else "VARCHAR(300)"
                    default = "0" if column_type == "FLOAT" else "''"
                    connection.execute(text(
                        f"ALTER TABLE pedidos ADD COLUMN {column_name} {column_type} NOT NULL DEFAULT {default}"
                    ))
        inventory_columns = {column["name"] for column in inspect(db.engine).get_columns("inventario")}
        if "categoria" not in inventory_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE inventario ADD COLUMN categoria VARCHAR(80) NOT NULL DEFAULT 'Otros'"))

        menu_columns = {column["name"] for column in inspect(db.engine).get_columns("menu_items")}
        menu_migrations = {
            "precio_mediana": "FLOAT",
            "precio_familiar": "FLOAT",
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
                    "ingredientes": json.loads(menu_item.ingredientes_json or "[]"),
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
                    "ingredientes": [item["nombre"] for item in priced["detalle"]],
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