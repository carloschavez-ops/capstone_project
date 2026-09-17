import json
import os
import re
import uuid

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename

from data import PIZZAS, obtener_pizza

app = Flask(__name__)
app.secret_key = "clave-secreta-pizza-pronto-dev"  # Cambia esto en producción

# --- "Base de datos" de usuarios (por ahora fija, en memoria) ---
USUARIO_VALIDO = {
    "email": "pizzapronto@gmail.com",
    "password": "pizzapronto"
}

# --- Configuración para subir fotos de pizzas ---
CARPETA_SUBIDAS = os.path.join(app.root_path, "static", "img", "uploads")
os.makedirs(CARPETA_SUBIDAS, exist_ok=True)
EXTENSIONES_PERMITIDAS = {"png", "jpg", "jpeg", "webp", "gif"}


def extension_valida(nombre_archivo):
    return "." in nombre_archivo and nombre_archivo.rsplit(".", 1)[1].lower() in EXTENSIONES_PERMITIDAS


def generar_id(nombre):
    base = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-") or "pizza"
    return f"{base}-{uuid.uuid4().hex[:6]}"


def puede_ver_carta():
    """Tanto un usuario logueado como uno en modo invitado pueden ver el menú."""
    return session.get("logueado") or session.get("invitado")


# ---------------------------------------------------------
# Rutas de acceso
# ---------------------------------------------------------
@app.route("/")
def index():
    # La app siempre abre en el login, no directo al menú.
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        recordar = request.form.get("recordar")

        if email == USUARIO_VALIDO["email"] and password == USUARIO_VALIDO["password"]:
            session["logueado"] = True
            session["invitado"] = False
            session["email"] = email
            session.permanent = bool(recordar)
            session.setdefault("carrito", [])
            return redirect(url_for("carta"))
        else:
            flash("Correo o contraseña incorrectos. Intenta de nuevo.")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/invitado")
def modo_invitado():
    """Acceso rápido de solo lectura al menú, sin necesidad de cuenta."""
    session["invitado"] = True
    session["logueado"] = False
    session["email"] = None
    session.setdefault("carrito", [])
    return redirect(url_for("carta"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------
# Carta digital
# ---------------------------------------------------------
@app.route("/carta")
def carta():
    if not puede_ver_carta():
        return redirect(url_for("login"))

    pizzas_visibles = [p for p in PIZZAS if p.get("activo", True)]

    return render_template(
        "carta.html",
        email=session.get("email"),
        invitado=bool(session.get("invitado")) and not session.get("logueado"),
        pizzas=pizzas_visibles,
        pizzas_json=json.dumps(pizzas_visibles, ensure_ascii=False),
    )


@app.route("/carrito/agregar", methods=["POST"])
def agregar_al_carrito():
    """Recibe la receta personalizada desde el JS de la carta y la guarda en la sesión."""
    if not puede_ver_carta():
        return jsonify({"error": "no_autenticado"}), 401

    datos = request.get_json(silent=True) or {}
    pizza_id = datos.get("pizza_id")
    pizza = obtener_pizza(pizza_id)
    if not pizza:
        return jsonify({"error": "pizza_no_encontrada"}), 400

    item = {
        "pizza_id": pizza_id,
        "nombre": pizza["nombre"],
        "tamano_id": datos.get("tamano_id"),
        "queso_id": datos.get("queso_id"),
        "toppings": datos.get("toppings", []),
        "total": datos.get("total", pizza["precio_base"]),
    }

    carrito = session.get("carrito", [])
    carrito.append(item)
    session["carrito"] = carrito

    return jsonify({"cantidad": len(carrito), "item": item})


# ---------------------------------------------------------
# Agregar una pizza nueva al menú (solo usuarios con sesión iniciada)
# ---------------------------------------------------------
@app.route("/agregar-pizza", methods=["GET", "POST"])
def agregar_pizza():
    if not session.get("logueado"):
        flash("Inicia sesión para poder agregar pizzas al menú.")
        return redirect(url_for("login"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        categoria = request.form.get("categoria", "tradicionales")

        def a_float(campo):
            valor = request.form.get(campo, "").strip().replace(",", ".")
            try:
                return float(valor) if valor else 0.0
            except ValueError:
                return None

        precio_personal = a_float("precio_personal")
        precio_mediana = a_float("precio_mediana")
        precio_familiar = a_float("precio_familiar")

        if precio_personal is None or precio_mediana is None or precio_familiar is None:
            flash("Los precios deben ser números válidos, por ejemplo 18.50.")
            return render_template("agregar_pizza.html", valores=request.form)

        if not nombre or precio_personal <= 0:
            flash("Escribe al menos el nombre de la pizza y el Precio Personal.")
            return render_template("agregar_pizza.html", valores=request.form)

        precio_mediana = precio_mediana or precio_personal
        precio_familiar = precio_familiar or precio_mediana

        # --- Imagen (opcional) ---
        imagen_url = None
        archivo = request.files.get("imagen")
        if archivo and archivo.filename and extension_valida(archivo.filename):
            nombre_archivo = secure_filename(f"{uuid.uuid4().hex[:8]}_{archivo.filename}")
            archivo.save(os.path.join(CARPETA_SUBIDAS, nombre_archivo))
            imagen_url = f"/static/img/uploads/{nombre_archivo}"

        # --- Etiquetas especiales ---
        es_picante = request.form.get("picante") == "on"
        es_vegetariana = request.form.get("vegetariana") == "on"
        es_recomendada = request.form.get("recomendada") == "on"
        activa = request.form.get("activa") == "on"

        tags = []
        if es_picante:
            tags.append("🌶️ Picante")
        if es_vegetariana:
            tags.append("🥦 Vegetariana")
        if es_recomendada:
            tags.append("⭐ Recomendación del Chef")

        if es_recomendada:
            badge, badge_tipo = "Recomendación del Chef", "autor"
        elif es_picante:
            badge, badge_tipo = "Picante", "picante"
        else:
            badge, badge_tipo = "Nueva en la Carta", "dop"

        nueva_pizza = {
            "id": generar_id(nombre),
            "categoria": categoria,
            "badge": badge,
            "badge_tipo": badge_tipo,
            "nombre": nombre,
            "descripcion": descripcion or "Deliciosa pizza artesanal preparada con ingredientes frescos.",
            "tags": tags,
            "precio_base": precio_personal,
            "meta": "Agregada recientemente",
            "activo": activa,
            "imagen": imagen_url,
            "dieta": {"vegano": es_vegetariana, "sin_gluten": False, "sin_lactosa": False},
            "personalizacion": {
                "etiqueta": categoria.capitalize(),
                "tamanos": [
                    {"id": "personal", "nombre": "Personal 20cm", "desc": "Ideal para uno", "precio": precio_personal, "extra": 0},
                    {"id": "mediana", "nombre": "Mediana 30cm", "desc": "Para compartir en pareja", "precio": precio_mediana, "extra": round(precio_mediana - precio_personal, 2)},
                    {"id": "familiar", "nombre": "Familiar 40cm", "desc": "Para compartir en familia", "precio": precio_familiar, "extra": round(precio_familiar - precio_personal, 2)},
                ],
                "insumos_base": [
                    {"nombre": "Masa Artesanal Horneada a la Piedra", "detalle": "Receta de la casa"},
                    {"nombre": "Salsa de Tomate Casera", "detalle": "Receta tradicional"},
                ],
                "quesos": [
                    {"id": "queso_clasico", "nombre": "Queso Mozzarella Clásico", "extra": 0, "incluido": True},
                ],
                "toppings": [
                    {"id": "extra_queso", "nombre": "Extra Queso Mozzarella", "extra": 3.00},
                ],
                "tiempo_horneado": "~8 min",
                "kcal": "800 kcal aprox",
            },
        }

        PIZZAS.append(nueva_pizza)

        if activa:
            flash(f'"{nombre}" fue agregada al menú y ya es visible para los clientes.')
        else:
            flash(f'"{nombre}" se guardó como INACTIVA (no se muestra en la carta hasta que la actives).')

        return redirect(url_for("carta"))

    return render_template("agregar_pizza.html", valores={})


if __name__ == "__main__":
    app.run(debug=True)