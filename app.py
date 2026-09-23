import json
import os
import re
import uuid
from modelos import db

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename

from data import (
    PIZZAS, INGREDIENTES, TAMANOS, GRUPOS,
    COSTO_DELIVERY, DELIVERY_GRATIS_DESDE,
    obtener_pizza, obtener_ingrediente, obtener_tamano,
    ingredientes_por_grupo, ingredientes_bloqueados,
    validar_combinacion, pizzas_similares, cotizar, calcular_dieta,
    sembrar_si_hace_falta, cargar_desde_bd,
    crear_pizza, eliminar_pizza, eliminar_ingrediente,
)
app = Flask(__name__)
app.secret_key = "clave-secreta-pizza-pronto-dev"  # Cambia esto en producción
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.root_path, "pizza_pronto.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()
    sembrar_si_hace_falta()
    cargar_desde_bd()

# --- "Base de datos" de usuarios (por ahora fija, en memoria) ---
USUARIO_VALIDO = {
    "email": "pizzapronto@gmail.com",
    "password": "pizzapronto"
}

# Usuarios que se registran ellos mismos. Nunca son administradores.
USUARIOS_REGISTRADOS = {}  # correo -> {"nombre": ..., "password": ...}

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


# Un item del carrito guardado en la sesión tiene que traer estas claves.
# Si falta alguna, viene de una versión anterior de la app y lo descartamos.
CLAVES_ITEM = {
    "linea", "pizza_id", "nombre", "origen", "tamano_id", "tamano_nombre",
    "ingredientes", "quitados", "kcal", "minutos", "dieta",
    "precio_base", "precio_unitario", "cantidad",
}


def _leer_carrito():
    """
    Devuelve el carrito de la sesión, descartando items con formato viejo.
    Así una cookie antigua nunca tumba la página: simplemente se limpia sola.
    """
    guardado = session.get("carrito") or []
    limpio = [i for i in guardado
              if isinstance(i, dict) and CLAVES_ITEM.issubset(i.keys())]

    if len(limpio) != len(guardado):
        session["carrito"] = limpio
        session.modified = True

    return limpio


def _guardar_carrito(carrito):
    session["carrito"] = carrito
    session.modified = True


def contexto_base():
    """Datos que aparecen en la navbar de todas las páginas."""
    return {
        "email": session.get("email"),
        "nombre_cliente": session.get("nombre"),
        "es_admin": bool(session.get("es_admin")),
        "invitado": bool(session.get("invitado")) and not session.get("logueado"),
        "items_carrito": sum(i["cantidad"] for i in _leer_carrito()),
        "datos_cliente": session.get("datos_cliente"),
    }


# Páginas a las que un invitado puede entrar aunque todavía no haya
# completado sus datos de entrega (si no, nunca podría llegar a llenarlos).
RUTAS_SIN_DATOS_INVITADO = {"login", "registrarse", "logout", "modo_invitado", "datos_invitado", "static", "index"}


@app.before_request
def exigir_datos_de_entrega():
    """
    A un invitado nuevo lo mandamos primero a completar nombre, teléfono y
    forma de entrega. Así, cuando llegue un pedido, sabemos a quién y dónde
    entregarlo. Un usuario logueado (el admin) no pasa por aquí.
    """
    if request.endpoint in RUTAS_SIN_DATOS_INVITADO or request.endpoint is None:
        return
    if session.get("invitado") and not session.get("logueado") and not session.get("datos_cliente"):
        return redirect(url_for("datos_invitado"))


def soles(valor):
    return f"S/ {valor:.2f}"


app.jinja_env.filters["soles"] = soles


# ---------------------------------------------------------
# Rutas de acceso
# ---------------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        recordar = request.form.get("recordar")

        if email == USUARIO_VALIDO["email"] and password == USUARIO_VALIDO["password"]:
            session["logueado"] = True
            session["es_admin"] = True
            session["invitado"] = False
            session["email"] = email
            session["nombre"] = "Administrador"
            session.permanent = bool(recordar)
            session.setdefault("carrito", [])
            return redirect(url_for("carta"))

        usuario = USUARIOS_REGISTRADOS.get(email)
        if usuario and usuario["password"] == password:
            session["logueado"] = True
            session["es_admin"] = False
            session["invitado"] = False
            session["email"] = email
            session["nombre"] = usuario["nombre"]
            session.permanent = bool(recordar)
            session.setdefault("carrito", [])
            return redirect(url_for("carta"))

        flash("Correo o contraseña incorrectos. Intenta de nuevo.")
        return redirect(url_for("login"))

    return render_template("login.html", modo="login", valores={}, **contexto_base())


@app.route("/registrarse", methods=["GET", "POST"])
def registrarse():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        correo = request.form.get("correo", "").strip().lower()
        contrasena = request.form.get("contrasena", "")
        confirmar = request.form.get("confirmar_contrasena", "")

        error = None
        if not nombre:
            error = "Escribe tu nombre."
        elif not correo or "@" not in correo:
            error = "Escribe un correo electrónico válido."
        elif len(contrasena) < 4:
            error = "La contraseña debe tener al menos 4 caracteres."
        elif contrasena != confirmar:
            error = "Las contraseñas no coinciden."
        elif correo == USUARIO_VALIDO["email"] or correo in USUARIOS_REGISTRADOS:
            error = "Ya existe una cuenta con ese correo."

        if error:
            flash(error)
            return render_template("login.html", modo="registro", valores=request.form, **contexto_base())

        # Se guarda como usuario normal. Jamás como administrador.
        USUARIOS_REGISTRADOS[correo] = {"nombre": nombre, "password": contrasena}

        session["logueado"] = True
        session["es_admin"] = False
        session["invitado"] = False
        session["email"] = correo
        session["nombre"] = nombre
        session.setdefault("carrito", [])

        return redirect(url_for("carta"))

    return render_template("login.html", modo="registro", valores={}, **contexto_base())


@app.route("/invitado")
def modo_invitado():
    session["invitado"] = True
    session["logueado"] = False
    session["es_admin"] = False
    session["email"] = None
    session.setdefault("carrito", [])
    if session.get("datos_cliente"):
        return redirect(url_for("carta"))
    return redirect(url_for("datos_invitado"))


@app.route("/datos-invitado", methods=["GET", "POST"])
def datos_invitado():
    """
    Nombre, teléfono y forma de entrega del cliente en modo invitado.
    Con esto sabemos a quién y dónde llevarle la pizza.
    """
    if session.get("logueado") or not session.get("invitado"):
        return redirect(url_for("login"))

    siguiente = request.values.get("siguiente") or url_for("carta")

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        tipo_entrega = request.form.get("tipo_entrega", "domicilio")
        direccion = request.form.get("direccion", "").strip()
        mesa = request.form.get("mesa", "").strip()
        dni_ruc = request.form.get("dni_ruc", "").strip()

        if not nombre:
            flash("Escribe tu nombre para saber a quién entregarle el pedido.")
        elif not telefono:
            flash("Déjanos un teléfono por si necesitamos contactarte.")
        elif tipo_entrega == "domicilio" and not direccion:
            flash("Escribe la dirección donde quieres recibir tu pedido.")
        elif tipo_entrega == "mesa" and not mesa:
            flash("Indica el número de mesa en la que estás.")
        else:
            session["datos_cliente"] = {
                "nombre": nombre,
                "telefono": telefono,
                "tipo_entrega": tipo_entrega,
                "direccion": direccion if tipo_entrega == "domicilio" else "",
                "mesa": mesa if tipo_entrega == "mesa" else "",
                "dni_ruc": dni_ruc,
            }
            session.modified = True
            return redirect(siguiente)

        return render_template(
            "datos_invitado.html", valores=request.form, siguiente=siguiente, **contexto_base()
        )

    valores = session.get("datos_cliente", {})
    return render_template("datos_invitado.html", valores=valores, siguiente=siguiente, **contexto_base())


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

    admin = bool(session.get("es_admin"))
    pizzas_visibles = list(PIZZAS) if admin else [p for p in PIZZAS if p.get("activo", True)]
    # Para cada pizza mandamos su receta ya "traducida" a nombres legibles.
    

    return render_template(
        "carta.html",
        pizzas=pizzas_visibles,
        tamanos=TAMANOS,
        pizzas_json=json.dumps(pizzas_visibles, ensure_ascii=False),
        ingredientes_json=json.dumps(INGREDIENTES, ensure_ascii=False),
        **contexto_base(),
    )


# ---------------------------------------------------------
# Constructor de pizzas: crear desde cero o personalizar una receta
# ---------------------------------------------------------
@app.route("/crear-mi-pizza")
def crear_mi_pizza():
    if not puede_ver_carta():
        return redirect(url_for("login"))

    seleccion = ["masa_clasica", "salsa_tomate", "mozzarella"]
    return render_template(
        "constructor.html",
        modo="crear",
        pizza=None,
        titulo="Crear mi pizza",
        bajada="Empieza por la masa y ve armando tu receta. Te avisamos si dos ingredientes no funcionan juntos.",
        nombre_sugerido="Mi pizza a medida",
        seleccion_inicial=seleccion,
        tamano_inicial="mediana",
        **_contexto_constructor(),
    )


@app.route("/personalizar/<pizza_id>")
def personalizar(pizza_id):
    if not puede_ver_carta():
        return redirect(url_for("login"))

    pizza = obtener_pizza(pizza_id)
    if not pizza:
        flash("Esa pizza ya no está en la carta.")
        return redirect(url_for("carta"))

    return render_template(
        "constructor.html",
        modo="personalizar",
        pizza=pizza,
        titulo=f"Personalizar {pizza['nombre']}",
        bajada="Quita o agrega lo que quieras. Lo que ya viene en la receta no te cuesta nada extra.",
        nombre_sugerido=f"{pizza['nombre']} a mi gusto",
        seleccion_inicial=list(pizza["ingredientes"]),
        tamano_inicial="mediana",
        **_contexto_constructor(),
    )


def _contexto_constructor():
    """Todo lo que el formulario del constructor necesita (es el mismo para ambos modos)."""
    return {
        "grupos": ingredientes_por_grupo(),
        "tamanos": TAMANOS,
        "ingredientes_json": json.dumps(INGREDIENTES, ensure_ascii=False),
        "tamanos_json": json.dumps(TAMANOS, ensure_ascii=False),
        "grupos_json": json.dumps(GRUPOS, ensure_ascii=False),
        **contexto_base(),
    }


@app.route("/api/cotizar", methods=["POST"])
def api_cotizar():
    """
    El constructor llama aquí cada vez que el cliente toca algo.
    Todo el cálculo vive en el servidor, así el precio del carrito y el que se
    ve en pantalla nunca se pueden desincronizar.
    """
    datos = request.get_json(silent=True) or {}
    pizza_id = datos.get("pizza_id") or None
    tamano_id = datos.get("tamano_id", "mediana")
    ids = datos.get("ingredientes", [])

    cotizacion = cotizar(pizza_id, ids, tamano_id)
    revision = validar_combinacion(ids)

    return jsonify({
        "ok": len(revision["errores"]) == 0,
        "errores": revision["errores"],
        "advertencias": revision["advertencias"],
        "bloqueados": ingredientes_bloqueados(ids),
        "similares": pizzas_similares(ids, excluir_id=pizza_id),
        **cotizacion,
    })


# ---------------------------------------------------------
# Carrito
# ---------------------------------------------------------
def _resumen_carrito(carrito):
    subtotal = round(sum(i["precio_unitario"] * i["cantidad"] for i in carrito), 2)
    delivery = 0.0 if (subtotal >= DELIVERY_GRATIS_DESDE or subtotal == 0) else COSTO_DELIVERY
    return {
        "subtotal": subtotal,
        "delivery": delivery,
        "total": round(subtotal + delivery, 2),
        "falta_para_envio_gratis": max(0.0, round(DELIVERY_GRATIS_DESDE - subtotal, 2)),
        "unidades": sum(i["cantidad"] for i in carrito),
    }


@app.route("/carrito/agregar", methods=["POST"])
def agregar_al_carrito():
    """Recibe una receta (de la carta o del constructor) y la guarda en la sesión."""
    if not puede_ver_carta():
        return jsonify({"error": "no_autenticado"}), 401

    datos = request.get_json(silent=True) or {}
    pizza_id = datos.get("pizza_id") or None
    tamano_id = datos.get("tamano_id", "mediana")
    ids = datos.get("ingredientes", [])
    cantidad = max(1, int(datos.get("cantidad", 1)))

    if pizza_id and not obtener_pizza(pizza_id):
        return jsonify({"error": "pizza_no_encontrada",
                        "mensaje": "Esa pizza ya no está en la carta."}), 400

    # Revalidamos en el servidor: nadie agrega una combinación prohibida.
    revision = validar_combinacion(ids)
    if revision["errores"]:
        return jsonify({
            "error": "combinacion_invalida",
            "mensaje": revision["errores"][0]["detalle"],
            "errores": revision["errores"],
        }), 400

    cotizacion = cotizar(pizza_id, ids, tamano_id)
    pizza = obtener_pizza(pizza_id) if pizza_id else None

    nombre = (datos.get("nombre") or "").strip()
    if not nombre:
        nombre = pizza["nombre"] if pizza else "Mi pizza a medida"

    item = {
        "linea": uuid.uuid4().hex[:10],
        "pizza_id": pizza_id,
        "nombre": nombre,
        "origen": "carta" if pizza and not cotizacion["quitados"] and not any(
            not d["incluido"] for d in cotizacion["detalle"]) else ("modificada" if pizza else "creada"),
        "tamano_id": cotizacion["tamano_id"],
        "tamano_nombre": cotizacion["tamano_nombre"],
        "ingredientes": cotizacion["detalle"],
        "quitados": cotizacion["quitados"],
        "kcal": cotizacion["kcal"],
        "minutos": cotizacion["minutos"],
        "dieta": cotizacion["dieta"],
        "precio_base": cotizacion["base"],
        "precio_unitario": cotizacion["total"],
        "cantidad": cantidad,
    }

    carrito = _leer_carrito()
    carrito.append(item)
    _guardar_carrito(carrito)

    resumen = _resumen_carrito(carrito)
    return jsonify({"ok": True, "item": item, "cantidad": resumen["unidades"], "resumen": resumen})


@app.route("/carrito")
def ver_carrito():
    if not puede_ver_carta():
        return redirect(url_for("login"))

    carrito = _leer_carrito()
    return render_template(
        "carrito.html",
        carrito=carrito,
        resumen=_resumen_carrito(carrito),
        costo_delivery=COSTO_DELIVERY,
        delivery_gratis_desde=DELIVERY_GRATIS_DESDE,
        **contexto_base(),
    )


@app.route("/carrito/cantidad", methods=["POST"])
def cambiar_cantidad():
    linea = request.form.get("linea")
    accion = request.form.get("accion", "sumar")

    carrito = _leer_carrito()
    for item in carrito:
        if item["linea"] == linea:
            if accion == "sumar":
                item["cantidad"] = min(20, item["cantidad"] + 1)
            else:
                item["cantidad"] -= 1
            break

    carrito = [i for i in carrito if i["cantidad"] > 0]
    _guardar_carrito(carrito)
    return redirect(url_for("ver_carrito"))


@app.route("/carrito/eliminar", methods=["POST"])
def eliminar_del_carrito():
    linea = request.form.get("linea")
    carrito = [i for i in _leer_carrito() if i["linea"] != linea]
    _guardar_carrito(carrito)
    flash("Quitamos esa pizza de tu pedido.")
    return redirect(url_for("ver_carrito"))


@app.route("/carrito/vaciar", methods=["POST"])
def vaciar_carrito():
    _guardar_carrito([])
    flash("Tu carrito quedó vacío.")
    return redirect(url_for("ver_carrito"))


@app.route("/carrito/confirmar", methods=["POST"])
def confirmar_pedido():
    carrito = _leer_carrito()
    if not carrito:
        flash("Agrega al menos una pizza antes de confirmar.")
        return redirect(url_for("ver_carrito"))

    resumen = _resumen_carrito(carrito)
    metodo = request.form.get("metodo_pago", "efectivo")

    vuelto = None
    if metodo == "efectivo":
        try:
            paga_con = float(request.form.get("paga_con", "0").replace(",", "."))
        except ValueError:
            paga_con = 0.0
        if paga_con < resumen["total"]:
            flash(f"Con {soles(paga_con)} no alcanza. El total es {soles(resumen['total'])}.")
            return redirect(url_for("ver_carrito"))
        vuelto = round(paga_con - resumen["total"], 2)

    session["ultimo_pedido"] = {
        "codigo": "PP-" + uuid.uuid4().hex[:6].upper(),
        "total": resumen["total"],
        "metodo": metodo,
        "vuelto": vuelto,
        "unidades": resumen["unidades"],
        "cliente": session.get("datos_cliente"),
    }
    _guardar_carrito([])
    return redirect(url_for("pedido_confirmado"))


@app.route("/pedido-confirmado")
def pedido_confirmado():
    pedido = session.get("ultimo_pedido")
    if not pedido:
        return redirect(url_for("carta"))
    return render_template("confirmacion.html", pedido=pedido, **contexto_base())


# ---------------------------------------------------------
# ---------------------------------------------------------
# Administración del menú (solo la cuenta administradora)
# ---------------------------------------------------------
CATEGORIAS_VALIDAS = {"tradicionales", "premium", "veganas", "dulces"}


def _guardar_imagen(archivo):
    """Guarda la foto subida y devuelve su URL, o None si no subieron nada válido."""
    if archivo and archivo.filename and extension_valida(archivo.filename):
        nombre_archivo = secure_filename(f"{uuid.uuid4().hex[:8]}_{archivo.filename}")
        archivo.save(os.path.join(CARPETA_SUBIDAS, nombre_archivo))
        return f"/static/img/uploads/{nombre_archivo}"
    return None


def _leer_formulario_pizza(pizza=None):
    """
    Lee y valida el formulario de pizza. Devuelve (datos, error).
    Si viene `pizza`, estamos editando: se conserva su receta y su foto
    cuando el admin no sube una nueva.
    """
    form = request.form
    nombre = form.get("nombre", "").strip()
    descripcion = form.get("descripcion", "").strip()
    categoria = form.get("categoria", "tradicionales")
    if categoria not in CATEGORIAS_VALIDAS:
        categoria = "tradicionales"

    def a_float(campo):
        valor = form.get(campo, "").strip().replace(",", ".")
        try:
            return float(valor) if valor else 0.0
        except ValueError:
            return None

    precio_personal = a_float("precio_personal")
    precio_mediana = a_float("precio_mediana")
    precio_familiar = a_float("precio_familiar")

    if precio_personal is None or precio_mediana is None or precio_familiar is None:
        return None, "Los precios deben ser números válidos, por ejemplo 18.50."
    if not nombre:
        return None, "Escribe el nombre de la pizza."
    if precio_personal <= 0:
        return None, "El Precio Personal tiene que ser mayor que cero."

    precio_mediana = precio_mediana or round(precio_personal * 1.35, 2)
    precio_familiar = precio_familiar or round(precio_mediana * 1.25, 2)

    es_picante = form.get("picante") == "on"
    es_vegetariana = form.get("vegetariana") == "on"
    es_recomendada = form.get("recomendada") == "on"
    activa = form.get("activa") == "on"

    tags = []
    if es_picante:
        tags.append("🌶️ Picante")
    if es_vegetariana:
        tags.append("🥦 Vegetariana")
    if es_recomendada:
        tags.append("⭐ Recomendación del chef")

    if es_recomendada:
        badge, badge_tipo = "Recomendación del Chef", "autor"
    elif es_picante:
        badge, badge_tipo = "Picante", "picante"
    elif pizza:
        badge, badge_tipo = pizza.get("badge", "Clásica"), pizza.get("badge_tipo", "dop")
    else:
        badge, badge_tipo = "Nueva en la carta", "dop"

    # La receta solo se genera al crear. Al editar se respeta la que ya tiene,
    # porque el dueño la afina desde "Personalizar".
    if pizza:
        receta = list(pizza["ingredientes"])
    else:
        receta = ["masa_clasica", "salsa_tomate"]
        receta.append("queso_vegano" if es_vegetariana else "mozzarella")
        if es_picante:
            receta.append("jalapeno")

    # Imagen: nueva > la que ya tenía > ninguna
    imagen = _guardar_imagen(request.files.get("imagen"))
    if imagen is None and pizza:
        imagen = None if form.get("quitar_imagen") == "on" else pizza.get("imagen")

    datos = {
        "categoria": categoria,
        "badge": badge,
        "badge_tipo": badge_tipo,
        "nombre": nombre,
        "descripcion": descripcion or "Pizza artesanal preparada con ingredientes frescos del día.",
        "tags": tags,
        "precios": {
            "personal": precio_personal,
            "mediana": precio_mediana,
            "familiar": precio_familiar,
        },
        "precio_base": precio_personal,
        "ingredientes": receta,
        "dieta": calcular_dieta(receta),
        "activo": activa,
        "imagen": imagen,
    }
    return datos, None


def _valores_desde_pizza(p):
    """Convierte una pizza guardada en los valores que espera el formulario."""
    tags = " ".join(p.get("tags", []))
    return {
        "nombre": p["nombre"],
        "descripcion": p["descripcion"],
        "categoria": p["categoria"],
        "precio_personal": p["precios"]["personal"],
        "precio_mediana": p["precios"]["mediana"],
        "precio_familiar": p["precios"]["familiar"],
        "picante": "on" if "Picante" in tags else "",
        "vegetariana": "on" if "Vegetariana" in tags else "",
        "recomendada": "on" if "Recomendación" in tags else "",
        "activa": "on" if p.get("activo", True) else "",
    }


@app.route("/agregar-pizza", methods=["GET", "POST"])
def agregar_pizza():
    if not session.get("es_admin"):
        flash("Esta opción es solo para el equipo de Pizza Pronto.")
        return redirect(url_for("login"))

    if request.method == "POST":
        datos, error = _leer_formulario_pizza()
        if error:
            flash(error)
            return render_template("agregar_pizza.html", modo="crear", pizza=None,
                                   accion=url_for("agregar_pizza"),
                                   valores=request.form, **contexto_base())

        nueva_pizza = {"id": generar_id(datos["nombre"]), "meta": "Recién agregada", **datos}
        crear_pizza(nueva_pizza)

        if datos["activo"]:
            flash(f'"{datos["nombre"]}" ya aparece en la carta. Entra a Personalizar para ajustar su receta.')
        else:
            flash(f'"{datos["nombre"]}" quedó guardada como inactiva. Actívala cuando quieras venderla.')
        return redirect(url_for("carta"))

    return render_template("agregar_pizza.html", modo="crear", pizza=None,
                           accion=url_for("agregar_pizza"),
                           valores={"activa": "on"}, **contexto_base())


@app.route("/editar-pizza/<pizza_id>", methods=["GET", "POST"])
def editar_pizza(pizza_id):
    if not session.get("es_admin"):
        flash("Esta opción es solo para el equipo de Pizza Pronto.")
        return redirect(url_for("login"))

    pizza = obtener_pizza(pizza_id)
    if not pizza:
        flash("Esa pizza ya no existe en el menú.")
        return redirect(url_for("carta"))

    if request.method == "POST":
        datos, error = _leer_formulario_pizza(pizza)
        if error:
            flash(error)
            return render_template("agregar_pizza.html", modo="editar", pizza=pizza,
                                   accion=url_for("editar_pizza", pizza_id=pizza_id),
                                   valores=request.form, **contexto_base())

        pizza.update(datos)          # el id y la receta se mantienen
        pizza["meta"] = "Actualizada recién"
        flash(f'Guardamos los cambios de "{pizza["nombre"]}".')
        return redirect(url_for("carta"))

    return render_template("agregar_pizza.html", modo="editar", pizza=pizza,
                           accion=url_for("editar_pizza", pizza_id=pizza_id),
                           valores=_valores_desde_pizza(pizza), **contexto_base())


@app.route("/pizza/<pizza_id>/alternar", methods=["POST"])
def alternar_pizza(pizza_id):
    """Muestra u oculta una pizza de la carta sin borrarla."""
    if not session.get("es_admin"):
        return redirect(url_for("login"))

    pizza = obtener_pizza(pizza_id)
    if pizza:
        pizza["activo"] = not pizza.get("activo", True)
        estado = "visible en la carta" if pizza["activo"] else "oculta"
        flash(f'"{pizza["nombre"]}" quedó {estado}.')
    return redirect(url_for("carta"))


@app.route("/pizza/<pizza_id>/eliminar", methods=["POST"])
def eliminar_pizza(pizza_id):
    if not session.get("es_admin"):
        return redirect(url_for("login"))

    pizza = obtener_pizza(pizza_id)
    if pizza:
        PIZZAS.remove(pizza)
        flash(f'Eliminamos "{pizza["nombre"]}" del menú.')
    return redirect(url_for("carta"))
@app.route("/admin/menu")
def admin_menu():
    if not session.get("es_admin"):
        flash("Esta opción es solo para el equipo de Pizza Pronto.")
        return redirect(url_for("login"))
    return render_template(
        "admin_menu.html", pizzas=PIZZAS, ingredientes=INGREDIENTES, **contexto_base()
    )


@app.route("/admin/pizza/<pizza_id>/eliminar", methods=["POST"])
def admin_eliminar_pizza(pizza_id):
    if not session.get("es_admin"):
        return redirect(url_for("login"))
    if eliminar_pizza(pizza_id):
        flash("Pizza eliminada del menú.")
    else:
        flash("No encontramos esa pizza.")
    return redirect(url_for("admin_menu"))


@app.route("/admin/ingrediente/<ing_id>/eliminar", methods=["POST"])
def admin_eliminar_ingrediente(ing_id):
    if not session.get("es_admin"):
        return redirect(url_for("login"))
    ok, en_uso = eliminar_ingrediente(ing_id)
    if ok:
        flash("Ingrediente eliminado.")
    elif en_uso:
        flash("No se puede eliminar: lo usan estas pizzas → " + ", ".join(en_uso))
    else:
        flash("No encontramos ese ingrediente.")
    return redirect(url_for("admin_menu"))

if __name__ == "__main__":
    app.run(debug=True)