import json
import os
import uuid

from flask import Flask, jsonify, request

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
from modelos import IngredienteDB, PizzaDB, db
from backend.models import PedidoDB


def create_app(database_uri=None):
    app = Flask(__name__)
    database_path = os.path.join(os.path.dirname(__file__), "pizza_pronto.sqlite3")
    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_uri or f"sqlite:///{database_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JSON_AS_ASCII=False,
    )
    db.init_app(app)

    with app.app_context():
        db.create_all()
        sembrar_si_hace_falta()
        cargar_desde_bd()

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "service": "pizza-pronto-api"})

    @app.get("/api/catalog")
    def catalog():
        return jsonify({
            "pizzas": [pizza for pizza in PIZZAS if pizza.get("activo", True)],
            "ingredientes": INGREDIENTES,
            "grupos": GRUPOS,
            "tamanos": TAMANOS,
            "delivery": {
                "costo": COSTO_DELIVERY,
                "gratis_desde": DELIVERY_GRATIS_DESDE,
            },
        })

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
        payload = request.get_json(silent=True) or {}
        customer = payload.get("cliente") or {}
        name = str(customer.get("nombre", "")).strip()
        phone = str(customer.get("telefono", "")).strip()
        delivery_type = customer.get("tipo_entrega", "domicilio")
        address = str(customer.get("direccion", "")).strip()
        payment_method = payload.get("metodo_pago", "efectivo")
        requested_items = payload.get("items", [])

        if not name or not phone:
            return jsonify({"error": "Completa tu nombre y teléfono."}), 400
        if delivery_type not in {"domicilio", "recojo"}:
            return jsonify({"error": "El tipo de entrega no es válido."}), 400
        if delivery_type == "domicilio" and not address:
            return jsonify({"error": "Escribe la dirección de entrega."}), 400
        if payment_method not in {"efectivo", "tarjeta", "yape"}:
            return jsonify({"error": "El método de pago no es válido."}), 400
        if not isinstance(requested_items, list) or not requested_items:
            return jsonify({"error": "Agrega al menos una pizza al carrito."}), 400

        items = []
        subtotal = 0.0
        for requested in requested_items:
            if not isinstance(requested, dict):
                return jsonify({"error": "Hay un producto no válido en el carrito."}), 400
            pizza_id = requested.get("pizza_id") or None
            ingredient_ids = requested.get("ingredientes", [])
            size_id = requested.get("tamano_id", "mediana")
            try:
                quantity = int(requested.get("cantidad", 1))
            except (TypeError, ValueError):
                quantity = 0
            if quantity < 1 or quantity > 20:
                return jsonify({"error": "La cantidad debe estar entre 1 y 20."}), 400
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
                "cantidad": quantity,
                "precio_unitario": priced["total"],
                "total": round(priced["total"] * quantity, 2),
            }
            items.append(line)
            subtotal += line["total"]

        subtotal = round(subtotal, 2)
        delivery = 0.0 if delivery_type == "recojo" or subtotal >= DELIVERY_GRATIS_DESDE else COSTO_DELIVERY
        total = round(subtotal + delivery, 2)
        code = f"PP-{uuid.uuid4().hex[:7].upper()}"
        order = PedidoDB(
            codigo=code,
            cliente=name,
            telefono=phone,
            tipo_entrega=delivery_type,
            direccion=address if delivery_type == "domicilio" else "",
            metodo_pago=payment_method,
            items_json=json.dumps(items, ensure_ascii=False),
            subtotal=subtotal,
            delivery=delivery,
            total=total,
        )
        db.session.add(order)
        db.session.commit()
        return jsonify({"pedido": order.to_dict()}), 201

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Ruta no encontrada."}), 404

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)