"""HU08 y HU09. Unidades compatibles y consumo atómico al iniciar preparación."""
import json
import math
import unicodedata
from decimal import Decimal

from flask import Blueprint, current_app, jsonify, request
from modelos import IngredienteDB, MenuItemDB, db
from backend.models import ConfiguracionDB, InventarioDB, PedidoDB
from backend.inventory_models import MovimientoStockDB, RecetaConsumoDB
from backend.operations import requires, payload
from backend.demo_recipes import menu_portions


recipes = Blueprint("recipes", __name__, url_prefix="/api/admin")
UNITS = {"kg": ("masa", 1000), "g": ("masa", 1), "l": ("volumen", 1000), "ml": ("volumen", 1), "unidad": ("unidad", 1), "paquete": ("paquete", 1)}

class StockError(ValueError):
    pass


@recipes.errorhandler(ValueError)
def recipe_validation_error(error):
    db.session.rollback()
    return jsonify({"error": str(error)}), 400


def convert_quantity(value, source, destination):
    if isinstance(value, bool):
        raise ValueError("La cantidad debe ser numérica.")
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ValueError("La cantidad debe ser numérica.")
    if not math.isfinite(number) or number < 0:
        raise ValueError("La cantidad debe ser finita y no negativa.")
    if not isinstance(source, str) or not isinstance(destination, str) or source not in UNITS or destination not in UNITS or UNITS[source][0] != UNITS[destination][0]:
        raise ValueError("Unidades incompatibles: no se convierte masa, volumen, unidades o paquetes entre sí.")
    converted = number * UNITS[source][1] / UNITS[destination][1]
    if not math.isfinite(converted) or converted > 1000000000:
        raise ValueError("La cantidad supera el límite de inventario de 1000000000 unidades base.")
    return round(converted, 6)


def begin_write():
    connection = db.session.connection()
    if db.engine.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")


def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFD", value.lower()) if not unicodedata.combining(c)).strip()


def demo_stock(name, group="otros", unit=None):
    aliases = {"mozzarella": "Queso Mozzarella", "masa italiana": "Masa de pizza", "salsa de tomate": "Salsa de tomate", "champinones": "Champiñones", "tomate cherry": "Tomate", "aceitunas": "Aceitunas negras", "pollo": "Carne de pollo", "pina": "Piña"}
    wanted = normalized(aliases.get(normalized(name), name))
    stock = next((item for item in InventarioDB.query.filter_by(tipo="ingrediente").all() if normalized(item.nombre) == wanted), None)
    if stock is None:
        import hashlib
        identifier = "demo-" + hashlib.sha256(wanted.encode()).hexdigest()[:16]
        stock = InventarioDB.query.filter_by(tipo="ingrediente", item_id=identifier).first()
        if stock is None:
            stock = InventarioDB(tipo="ingrediente", item_id=identifier, nombre=name[:120], categoria="Otros", cantidad=100, unidad=unit or ("l" if "salsa" in group else "kg"))
            db.session.add(stock)
            db.session.flush()
    return stock


def demo_component(stock, scale=1, group="otros"):
    # Cantidades ficticias autorizadas para demostración, no recetas del negocio.
    if stock.unidad == "unidad":
        quantity = max(1, round(scale))
    elif stock.unidad == "paquete":
        quantity = round(.05 * scale, 4)
    elif stock.unidad == "l":
        quantity = round((.06 if "salsa" in group else .15) * scale, 4)
    else:
        quantity = round((.25 if group == "masa" else .12 if group == "queso" else .06) * scale, 4)
    return {"insumo_id": stock.item_id, "cantidad": quantity, "unidad": stock.unidad}


def ensure_demo_recipes():
    """Cubre catálogo y cada ingrediente/tamaño, sin sobrescribir recetas editadas."""
    for ingredient in IngredienteDB.query.all():
        known = {"masa_clasica": "Masa de pizza", "salsa_tomate": "Salsa de tomate", "salsa_bbq": "Salsa BBQ", "mozzarella": "Queso Mozzarella", "parmesano": "Queso Parmesano", "cheddar": "Queso Cheddar", "pepperoni": "Pepperoni", "jamon": "Jamón", "tocino": "Tocino", "pollo": "Carne de pollo", "chorizo": "Chorizo", "carne_molida": "Carne de res", "champinones": "Champiñones", "cebolla": "Cebolla", "pimiento": "Pimiento", "albahaca": "Albahaca", "espinaca": "Espinaca", "pina": "Piña", "fresa": "Fresa"}
        stock = demo_stock(known.get(ingredient.id, ingredient.nombre), ingredient.grupo)
        for size, factor in (("personal", .6), ("mediana", 1), ("familiar", 1.6)):
            key = f"ingrediente:{ingredient.id}:{size}"
            if db.session.get(RecetaConsumoDB, key) is None:
                db.session.add(RecetaConsumoDB(clave=key, nombre=f"{ingredient.nombre} · {size}", componentes_json=json.dumps([demo_component(stock, factor, ingredient.grupo)])))
    for product in MenuItemDB.query.all():
        sized = product.es_pizza and product.precio_mediana is not None and product.precio_familiar is not None
        for size, factor in (("personal", .6), ("mediana", 1), ("familiar", 1.6)) if sized else (("unico", 1),):
            key = f"menu:{product.id}:{size}"
            if db.session.get(RecetaConsumoDB, key):
                continue
            parts = {}
            portions = menu_portions(product)
            # Ingredientes declarados en las pizzas italianas se añaden a su base.
            for name in json.loads(product.ingredientes_json or "[]"):
                if normalized(name) in {"salsa de tomate", "mozzarella"}:
                    continue
                stock = demo_stock(name)
                portions.append((stock.nombre, .03 if stock.unidad == "kg" else .05 if stock.unidad in {"l", "paquete"} else .25, stock.unidad))
            for name, amount, unit in portions:
                stock = demo_stock(name, unit=unit)
                part = {"insumo_id": stock.item_id, "cantidad": round(amount * factor, 5), "unidad": stock.unidad}
                parts[stock.item_id] = part
            db.session.add(RecetaConsumoDB(clave=key, nombre=f"{product.nombre} · {size}"[:200], componentes_json=json.dumps(list(parts.values()))))
    db.session.commit()


def build_consumption_plan(items):
    totals = {}
    for line in items:
        size = line.get("tamano_id") or "unico"
        keys = [f"menu:{line['menu_item_id']}:{size}"] if line.get("menu_item_id") else [f"ingrediente:{item}:{size}" for item in line.get("ingredientes_ids", [])]
        if not keys:
            raise ValueError("El pedido no conserva una receta válida.")
        for key in keys:
            recipe = db.session.get(RecetaConsumoDB, key)
            if recipe is None:
                raise ValueError(f"Configura la receta de consumo {key} antes de recibir el pedido.")
            for part in json.loads(recipe.componentes_json):
                stock = InventarioDB.query.filter_by(tipo="ingrediente", item_id=part["insumo_id"]).first()
                if stock is None:
                    raise ValueError("La receta utiliza un insumo inexistente.")
                amount = convert_quantity(part["cantidad"], part["unidad"], stock.unidad)
                entry = totals.setdefault(stock.item_id, {"insumo_id": stock.item_id, "unidad": stock.unidad, "cantidad": Decimal(0)})
                entry["cantidad"] += Decimal(str(amount)) * line["cantidad"]
    return [{**entry, "cantidad": float(entry["cantidad"])} for entry in totals.values()]


def consume_order(order):
    if order.stock_estado in {"consumido", "legacy"}:
        return
    if order.stock_estado != "pendiente":
        raise StockError("El consumo de este pedido ya fue revertido.")
    plan = json.loads(order.plan_consumo_json)
    if not plan:
        # Solo pedidos antiguos de pruebas o importaciones, nunca pedidos nuevos.
        raise StockError("El pedido no conserva su plan de consumo; requiere revisión.")
    checked = []
    for part in plan:
        stock = InventarioDB.query.filter_by(tipo="ingrediente", item_id=part["insumo_id"]).populate_existing().first()
        if stock is None or stock.unidad != part["unidad"]:
            raise StockError("Un insumo del plan cambió o no existe.")
        if stock.cantidad < part["cantidad"]:
            raise StockError(f"Stock insuficiente de {stock.nombre}: requiere {part['cantidad']} {stock.unidad}; disponible {stock.cantidad}.")
        checked.append((stock, part["cantidad"]))
    for stock, amount in checked:
        before = stock.cantidad
        stock.cantidad = round(before - amount, 6)
        db.session.add(MovimientoStockDB(pedido_id=order.id, insumo_id=stock.item_id, tipo="consumo", cantidad=-amount, unidad=stock.unidad, saldo_anterior=before, saldo_posterior=stock.cantidad))
    order.stock_estado = "consumido"


def reverse_order(order):
    if order.stock_estado != "consumido":
        return
    movements = MovimientoStockDB.query.filter_by(pedido_id=order.id, tipo="consumo").all()
    checked = []
    for movement in movements:
        stock = InventarioDB.query.filter_by(tipo="ingrediente", item_id=movement.insumo_id).populate_existing().first()
        if stock is None or stock.unidad != movement.unidad:
            raise StockError("No se puede revertir: falta un insumo o cambió su unidad.")
        checked.append((stock, movement))
    for stock, movement in checked:
        before = stock.cantidad
        stock.cantidad = round(before - movement.cantidad, 6)
        db.session.add(MovimientoStockDB(pedido_id=order.id, insumo_id=stock.item_id, tipo="reversion", cantidad=-movement.cantidad, unidad=stock.unidad, saldo_anterior=before, saldo_posterior=stock.cantidad))
    order.stock_estado = "revertido"


@recipes.get("/recipes")
@requires("inventario.editar")
def recipe_list():
    return jsonify({"recetas": [row.to_dict() for row in RecetaConsumoDB.query.order_by(RecetaConsumoDB.nombre).all()], "nota": "Las recetas estimacion_demo contienen cantidades ficticias para demostración; reemplázalas con las reales del negocio."})


@recipes.put("/recipes/<path:key>")
@requires("inventario.editar")
def recipe_update(key):
    recipe = db.session.get(RecetaConsumoDB, key)
    if recipe is None:
        return jsonify({"error": "Receta no encontrada."}), 404
    data = payload()
    parts = data.get("componentes")
    if not isinstance(parts, list) or not 1 <= len(parts) <= 50:
        return jsonify({"error": "La receta debe tener entre 1 y 50 insumos."}), 400
    validated, seen = [], set()
    try:
        for part in parts:
            if not isinstance(part, dict) or not isinstance(part.get("insumo_id"), str) or part["insumo_id"] in seen:
                raise ValueError("Los insumos deben ser válidos y no repetirse.")
            stock = InventarioDB.query.filter_by(tipo="ingrediente", item_id=part.get("insumo_id")).first()
            if not stock:
                raise ValueError("Insumo inexistente.")
            amount = convert_quantity(part.get("cantidad"), part.get("unidad"), stock.unidad)
            if amount <= 0:
                raise ValueError("Cada consumo debe ser mayor que cero.")
            validated.append({"insumo_id": stock.item_id, "cantidad": amount, "unidad": stock.unidad})
            seen.add(stock.item_id)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    recipe.componentes_json = json.dumps(validated)
    recipe.origen = "configurada_admin"
    recipe.revision += 1
    db.session.commit()
    return jsonify({"receta": recipe.to_dict()})


@recipes.put("/order-settings")
@requires("catalogo.editar")
def update_order_settings():
    values = payload()
    delay, minutes = values.get("inicio_segundos"), values.get("minutos_por_pizza")
    if type(delay) is not int or type(minutes) is not int or not 0 <= delay <= 3600 or not 1 <= minutes <= 120:
        return jsonify({"error": "Inicio: 0 a 3600 segundos. Preparación: 1 a 120 minutos por pizza."}), 400
    settings = {"PREPARATION_START_DELAY_SECONDS": delay, "MINUTOS_POR_PIZZA": minutes}
    record = db.session.get(ConfiguracionDB, "tiempos_pedidos_v1")
    if record is None:
        record = ConfiguracionDB(clave="tiempos_pedidos_v1", valor="")
        db.session.add(record)
    record.valor = json.dumps(settings)
    db.session.commit()
    current_app.config.update(settings)
    return jsonify({"tiempos": values})
