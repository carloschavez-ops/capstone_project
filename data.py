# -*- coding: utf-8 -*-
"""
Datos y reglas de negocio de Pizza Pronto.

Las pizzas y los ingredientes ahora viven en la base de datos (pizza_pronto.db).
Al arrancar la app, se cargan en las listas PIZZAS e INGREDIENTES para que el
resto del código (cotizar, validar_combinacion, el constructor, etc.) siga
funcionando exactamente igual que antes — esa lógica no cambió ni una línea,
solo cambió de dónde vienen los datos.

Tamaños, grupos y reglas de combinación siguen siendo configuración fija del
negocio (no algo que cambie fila por fila), así que se quedan como estaban.
"""
import json

from modelos import db, IngredienteDB, PizzaDB

# ---------------------------------------------------------
# Tamaños
# ---------------------------------------------------------
TAMANOS = [
    {"id": "personal", "nombre": "Personal 20 cm", "desc": "1 persona · 4 porciones",
     "factor": 1.0, "minutos": 6},
    {"id": "mediana", "nombre": "Mediana 30 cm", "desc": "2 personas · 6 porciones",
     "factor": 1.4, "minutos": 8},
    {"id": "familiar", "nombre": "Familiar 40 cm", "desc": "4 personas · 8 porciones",
     "factor": 1.8, "minutos": 11},
]

# Precio de la masa + horneado cuando el cliente crea su pizza desde cero.
BASE_PERSONALIZADA = {"personal": 10.00, "mediana": 14.00, "familiar": 18.00}

# Costo de delivery
COSTO_DELIVERY = 5.00
DELIVERY_GRATIS_DESDE = 60.00


# ---------------------------------------------------------
# Grupos de ingredientes
# ---------------------------------------------------------
GRUPOS = [
    {"id": "masa", "nombre": "Masa", "ayuda": "Elige una sola masa.", "seleccion": "unica", "max": 1},
    {"id": "salsa", "nombre": "Salsa base", "ayuda": "Elige una sola salsa.", "seleccion": "unica", "max": 1},
    {"id": "queso", "nombre": "Quesos", "ayuda": "Hasta 3 quesos.", "seleccion": "multiple", "max": 3},
    {"id": "carne", "nombre": "Carnes y embutidos", "ayuda": "Hasta 4 carnes.", "seleccion": "multiple", "max": 4},
    {"id": "vegetal", "nombre": "Vegetales y frutas", "ayuda": "Hasta 6 vegetales.", "seleccion": "multiple", "max": 6},
    {"id": "dulce", "nombre": "Línea dulce", "ayuda": "Solo para pizzas de postre.", "seleccion": "multiple", "max": 4},
    {"id": "extra", "nombre": "Toques finales", "ayuda": "Se agregan al salir del horno.", "seleccion": "multiple", "max": 5},
]


def _ing(id, nombre, emoji, grupo, precio, color, vegano=True, sin_gluten=True, sin_lactosa=True, kcal=45):
    return {
        "id": id, "nombre": nombre, "emoji": emoji, "grupo": grupo,
        "precio": precio, "color": color, "kcal": kcal,
        "vegano": vegano, "sin_gluten": sin_gluten, "sin_lactosa": sin_lactosa,
    }


def _pizza(id, categoria, nombre, descripcion, badge, badge_tipo, tags, precios, ingredientes,
           meta="Lista en 25 min", imagen=None, activo=True):
    return {
        "id": id, "categoria": categoria, "nombre": nombre, "descripcion": descripcion,
        "badge": badge, "badge_tipo": badge_tipo, "tags": tags,
        "precios": precios, "ingredientes": ingredientes, "meta": meta,
        "imagen": imagen, "activo": activo,
    }


# ---------------------------------------------------------
# Semilla: el catálogo inicial, solo se usa la PRIMERA vez que se crea
# la base de datos (si ya existe pizza_pronto.db con datos, no se toca).
# ---------------------------------------------------------
SEMILLA_INGREDIENTES = [
    # --- Masas ---
    _ing("masa_clasica", "Masa clásica napolitana", "🫓", "masa", 0.00, "#e0b177", sin_gluten=False, kcal=220),
    _ing("masa_delgada", "Masa delgada crocante", "🫓", "masa", 1.50, "#d9a463", sin_gluten=False, kcal=180),
    _ing("masa_integral", "Masa integral", "🌾", "masa", 2.50, "#b98c55", sin_gluten=False, kcal=200),
    _ing("masa_sin_gluten", "Masa sin gluten", "🌽", "masa", 5.00, "#e8c48d", kcal=210),

    # --- Salsas ---
    _ing("salsa_tomate", "Salsa de tomate San Marzano", "🍅", "salsa", 0.00, "#c0392b", kcal=40),
    _ing("salsa_picante", "Salsa picante de rocoto", "🌶️", "salsa", 2.00, "#a5321f", kcal=45),
    _ing("salsa_bbq", "Salsa BBQ ahumada", "🍖", "salsa", 2.50, "#7a3b1d", kcal=70),
    _ing("salsa_pesto", "Pesto de albahaca", "🌿", "salsa", 3.50, "#4f7d3a", kcal=90),
    _ing("salsa_blanca", "Salsa blanca de la casa", "🥛", "salsa", 3.00, "#f2ead8", sin_lactosa=False, vegano=False, kcal=95),
    _ing("crema_chocolate", "Crema de chocolate", "🍫", "salsa", 4.00, "#4a2b1b", sin_lactosa=False, vegano=False, kcal=180),

    # --- Quesos ---
    _ing("mozzarella", "Mozzarella fior di latte", "🧀", "queso", 4.00, "#fbf3dd", vegano=False, sin_lactosa=False, kcal=150),
    _ing("mozzarella_bufala", "Mozzarella de búfala D.O.P", "🧀", "queso", 7.00, "#fdfaf0", vegano=False, sin_lactosa=False, kcal=160),
    _ing("parmesano", "Parmesano en lascas", "🧀", "queso", 4.50, "#f0dfae", vegano=False, sin_lactosa=False, kcal=120),
    _ing("gorgonzola", "Gorgonzola", "🧀", "queso", 5.50, "#e8e3c4", vegano=False, sin_lactosa=False, kcal=140),
    _ing("cheddar", "Cheddar madurado", "🧀", "queso", 3.50, "#e8a33d", vegano=False, sin_lactosa=False, kcal=140),
    _ing("queso_vegano", "Queso vegano de anacardos", "🌱", "queso", 5.00, "#f3e7c9", kcal=110),

    # --- Carnes ---
    _ing("pepperoni", "Pepperoni artesanal", "🍕", "carne", 5.00, "#b5342b", vegano=False, kcal=180),
    _ing("jamon", "Jamón del país", "🥓", "carne", 4.50, "#e28f8f", vegano=False, kcal=120),
    _ing("tocino", "Tocino crocante", "🥓", "carne", 5.00, "#c1553d", vegano=False, kcal=190),
    _ing("pollo", "Pollo marinado", "🍗", "carne", 5.00, "#d9a86c", vegano=False, kcal=140),
    _ing("chorizo", "Chorizo parrillero", "🌭", "carne", 5.00, "#9c3722", vegano=False, kcal=200),
    _ing("carne_molida", "Carne molida especiada", "🥩", "carne", 5.50, "#82412a", vegano=False, kcal=180),
    _ing("salchicha_italiana", "Salchicha italiana", "🌭", "carne", 5.50, "#a8543a", vegano=False, kcal=195),
    _ing("anchoas", "Anchoas del Cantábrico", "🐟", "carne", 6.50, "#8a7f6a", vegano=False, kcal=90),

    # --- Vegetales ---
    _ing("champinones", "Champiñones frescos", "🍄", "vegetal", 3.00, "#c8b39a", kcal=25),
    _ing("pimiento", "Pimiento asado", "🫑", "vegetal", 2.50, "#3f8f4a", kcal=25),
    _ing("cebolla", "Cebolla roja", "🧅", "vegetal", 2.00, "#b07fb5", kcal=20),
    _ing("cebolla_caramelizada", "Cebolla caramelizada", "🧅", "vegetal", 3.00, "#a6763f", kcal=60),
    _ing("aceituna", "Aceitunas negras", "🫒", "vegetal", 3.00, "#3d3a33", kcal=45),
    _ing("tomate_cherry", "Tomate cherry", "🍅", "vegetal", 3.00, "#d24a3d", kcal=20),
    _ing("rucula", "Rúcula fresca", "🥬", "vegetal", 3.50, "#4f8f42", kcal=15),
    _ing("albahaca", "Albahaca fresca", "🌿", "vegetal", 2.00, "#3f7a35", kcal=5),
    _ing("espinaca", "Espinaca baby", "🥬", "vegetal", 3.00, "#417a3c", kcal=15),
    _ing("alcachofa", "Corazones de alcachofa", "🌵", "vegetal", 4.00, "#8fa36a", kcal=35),
    _ing("maiz", "Choclo dulce", "🌽", "vegetal", 2.50, "#e8c14a", kcal=50),
    _ing("jalapeno", "Jalapeños en rodajas", "🌶️", "vegetal", 2.50, "#3f8f4a", kcal=10),
    _ing("pina", "Piña en trozos", "🍍", "vegetal", 3.00, "#e8c246", kcal=45),
    _ing("aji_amarillo", "Ají amarillo", "🌶️", "vegetal", 2.50, "#e0a02a", kcal=15),

    # --- Dulces ---
    _ing("platano", "Plátano en rodajas", "🍌", "dulce", 3.00, "#e8d05a", kcal=70),
    _ing("fresa", "Fresas frescas", "🍓", "dulce", 4.00, "#d63b52", kcal=35),
    _ing("manjar", "Manjar blanco", "🍮", "dulce", 4.00, "#c99147", vegano=False, sin_lactosa=False, kcal=180),
    _ing("marshmallow", "Marshmallows", "☁️", "dulce", 3.00, "#f7e6ea", vegano=False, kcal=120),

    # --- Toques finales ---
    _ing("oregano", "Orégano", "🌿", "extra", 0.50, "#5c7a3f", kcal=2),
    _ing("aceite_oliva", "Aceite de oliva extra virgen", "🫒", "extra", 1.50, "#9aa63f", kcal=60),
    _ing("ajo_confitado", "Ajo confitado", "🧄", "extra", 2.00, "#efe3c2", kcal=30),
    _ing("miel", "Hilo de miel", "🍯", "extra", 2.00, "#e0a72a", kcal=60),
    _ing("nueces", "Nueces tostadas", "🌰", "extra", 4.00, "#8a5a33", kcal=110),
    _ing("chiflis", "Chifles de plátano", "🍟", "extra", 2.50, "#e0b24a", kcal=90),
]

SEMILLA_PIZZAS = [
    _pizza(
        "margherita-dop", "tradicionales", "Margherita Verace D.O.P",
        "La receta protegida: tomate San Marzano, mozzarella de búfala y albahaca fresca del huerto.",
        "Certificada AVPN", "dop", ["🌿 Vegetariana", "⭐ La más pedida"],
        {"personal": 22.00, "mediana": 31.00, "familiar": 39.00},
        ["masa_clasica", "salsa_tomate", "mozzarella_bufala", "albahaca", "aceite_oliva"],
        meta="Lista en 20 min",
    ),
    _pizza(
        "diavola-rocoto", "tradicionales", "Diavola de Rocoto",
        "Pepperoni artesanal, salsa de rocoto y jalapeños. Para quienes piden picante de verdad.",
        "Picante", "picante", ["🌶️ Picante", "🔥 Nivel 3"],
        {"personal": 25.00, "mediana": 34.00, "familiar": 43.00},
        ["masa_clasica", "salsa_picante", "mozzarella", "pepperoni", "jalapeno", "oregano"],
    ),
    _pizza(
        "quattro-formaggi", "premium", "Cuatro Quesos de Autor",
        "Mozzarella, parmesano, gorgonzola y cheddar madurado, terminada con un hilo de miel.",
        "Recomendación del Chef", "autor", ["🧀 Intensa", "🍯 Con miel"],
        {"personal": 29.00, "mediana": 39.00, "familiar": 49.00},
        ["masa_clasica", "salsa_blanca", "mozzarella", "parmesano", "gorgonzola", "cheddar", "miel"],
        meta="Lista en 25 min",
    ),
    _pizza(
        "criolla-aji", "premium", "Criolla de Ají Amarillo",
        "Pollo marinado en ají amarillo, cebolla roja, choclo y chifles crocantes encima.",
        "Sabor peruano", "autor", ["🇵🇪 De la casa", "🌶️ Suave"],
        {"personal": 27.00, "mediana": 36.00, "familiar": 45.00},
        ["masa_clasica", "salsa_tomate", "mozzarella", "pollo", "cebolla", "maiz", "aji_amarillo", "chiflis"],
    ),
    _pizza(
        "huerto-vegana", "veganas", "Huerto Vegano",
        "Queso de anacardos, alcachofa, espinaca, champiñones y tomate cherry sobre masa integral.",
        "100% vegetal", "dop", ["🌱 Vegana", "🥬 Sin lactosa"],
        {"personal": 26.00, "mediana": 35.00, "familiar": 44.00},
        ["masa_integral", "salsa_tomate", "queso_vegano", "alcachofa", "espinaca", "champinones", "tomate_cherry"],
    ),
    _pizza(
        "libre-gluten", "veganas", "Jardín sin Gluten",
        "Masa de maíz sin gluten con pesto, rúcula, tomate cherry y aceitunas negras.",
        "Sin gluten", "dop", ["🌾 Sin gluten", "🌱 Vegana"],
        {"personal": 28.00, "mediana": 37.00, "familiar": 46.00},
        ["masa_sin_gluten", "salsa_pesto", "queso_vegano", "rucula", "tomate_cherry", "aceituna"],
    ),
    _pizza(
        "dulce-nutella", "dulces", "Pizza Chocolate y Fresa",
        "Masa delgada con crema de chocolate, fresas frescas y marshmallows tostados al horno.",
        "Postre", "autor", ["🍫 Dulce", "🍓 Para compartir"],
        {"personal": 24.00, "mediana": 32.00, "familiar": 40.00},
        ["masa_delgada", "crema_chocolate", "fresa", "marshmallow", "platano"],
        meta="Lista en 15 min",
    ),
]


# ---------------------------------------------------------
# Reglas de compatibilidad entre ingredientes (config fija del negocio)
# ---------------------------------------------------------
REGLAS_COMBINACION = [
    {"tipo": "bloquea", "a": ["anchoas"], "b": ["pina", "grupo:dulce", "miel"],
     "motivo": "Las anchoas son muy saladas y se pelean con lo dulce. La cocina no las hornea juntas."},
    {"tipo": "bloquea", "a": ["crema_chocolate"], "b": ["grupo:carne", "grupo:queso", "aceituna", "cebolla", "jalapeno", "ajo_confitado", "oregano"],
     "motivo": "La crema de chocolate solo va en pizzas dulces, sin ingredientes salados."},
    {"tipo": "bloquea", "a": ["grupo:dulce"], "b": ["grupo:carne", "salsa_picante", "salsa_bbq", "aji_amarillo"],
     "motivo": "La línea dulce no se combina con carnes ni salsas picantes."},
    {"tipo": "bloquea", "a": ["gorgonzola"], "b": ["fresa", "manjar", "marshmallow"],
     "motivo": "El gorgonzola tapa por completo el sabor de la fruta y el manjar."},
    {"tipo": "bloquea", "a": ["salsa_pesto"], "b": ["pina", "maiz"],
     "motivo": "El pesto pierde su aroma al hornearse con frutas dulces."},

    {"tipo": "advierte", "a": ["queso_vegano"], "b": ["grupo:carne", "salsa_blanca", "manjar"],
     "motivo": "Con queso vegano más carne, la pizza deja de ser vegana."},
    {"tipo": "advierte", "a": ["pina"], "b": ["grupo:carne"],
     "motivo": "Piña con carne: combinación clásica, pero no le gusta a todo el mundo."},
    {"tipo": "advierte", "a": ["rucula", "albahaca", "espinaca"], "b": ["salsa_bbq"],
     "motivo": "Las hojas frescas se marchitan con el ahumado del BBQ. Las ponemos al final."},
    {"tipo": "advierte", "a": ["salsa_picante", "jalapeno", "aji_amarillo"], "b": ["mozzarella_bufala"],
     "motivo": "El picante domina a la búfala. Si quieres sentirla, baja el picante."},
    {"tipo": "advierte", "a": ["anchoas"], "b": ["chorizo", "tocino", "pepperoni"],
     "motivo": "Demasiada sal junta. Te recomendamos elegir solo una de las dos."},
    {"tipo": "advierte", "a": ["masa_sin_gluten"], "b": ["nueces"],
     "motivo": "Preparamos en cocina compartida: las nueces pueden ser un problema de alergias."},
]


# ---------------------------------------------------------
# Listas en memoria — se llenan desde la base de datos al arrancar
# (siguen siendo listas de verdad, con este mismo nombre, para que todo el
# resto del código que ya funciona no tenga que cambiar nada).
# ---------------------------------------------------------
INGREDIENTES = []
INGREDIENTES_POR_ID = {}
PIZZAS = []


def calcular_dieta(ids):
    """Marca si una combinación es vegana / sin gluten / sin lactosa."""
    items = [obtener_ingrediente(i) for i in ids]
    items = [i for i in items if i]
    if not items:
        return {"vegano": False, "sin_gluten": False, "sin_lactosa": False}
    return {
        "vegano": all(i["vegano"] for i in items),
        "sin_gluten": all(i["sin_gluten"] for i in items),
        "sin_lactosa": all(i["sin_lactosa"] for i in items),
    }


def sembrar_si_hace_falta():
    """La primera vez que se crea la base de datos, la llenamos con el catálogo inicial."""
    if IngredienteDB.query.count() == 0:
        for i in SEMILLA_INGREDIENTES:
            db.session.add(IngredienteDB(
                id=i["id"], nombre=i["nombre"], emoji=i["emoji"], grupo=i["grupo"],
                precio=i["precio"], color=i["color"], kcal=i["kcal"],
                vegano=i["vegano"], sin_gluten=i["sin_gluten"], sin_lactosa=i["sin_lactosa"],
            ))

    if PizzaDB.query.count() == 0:
        for p in SEMILLA_PIZZAS:
            db.session.add(PizzaDB(
                id=p["id"], categoria=p["categoria"], nombre=p["nombre"],
                descripcion=p["descripcion"], badge=p["badge"], badge_tipo=p["badge_tipo"],
                tags_json=json.dumps(p["tags"], ensure_ascii=False),
                ingredientes_json=json.dumps(p["ingredientes"]),
                precio_personal=p["precios"]["personal"],
                precio_mediana=p["precios"]["mediana"],
                precio_familiar=p["precios"]["familiar"],
                meta=p["meta"], imagen=p.get("imagen"), activo=p.get("activo", True),
            ))

    db.session.commit()


def cargar_desde_bd():
    """Refresca INGREDIENTES y PIZZAS con lo que haya ahora mismo en la base de datos."""
    ingredientes = [fila.to_dict() for fila in IngredienteDB.query.order_by(IngredienteDB.grupo, IngredienteDB.nombre).all()]
    INGREDIENTES.clear()
    INGREDIENTES.extend(ingredientes)
    INGREDIENTES_POR_ID.clear()
    INGREDIENTES_POR_ID.update({i["id"]: i for i in INGREDIENTES})

    pizzas = [fila.to_dict() for fila in PizzaDB.query.all()]
    for p in pizzas:
        p["dieta"] = calcular_dieta(p["ingredientes"])
    PIZZAS.clear()
    PIZZAS.extend(pizzas)


# ---------------------------------------------------------
# Escritura: crear / eliminar (las usa el panel de administración)
# ---------------------------------------------------------
def crear_pizza(datos):
    """
    datos: dict con id, categoria, nombre, descripcion, badge, badge_tipo,
    tags (lista), precios (dict personal/mediana/familiar), ingredientes
    (lista de ids), meta, imagen, activo.
    """
    fila = PizzaDB(
        id=datos["id"],
        categoria=datos["categoria"],
        nombre=datos["nombre"],
        descripcion=datos.get("descripcion", ""),
        badge=datos.get("badge", ""),
        badge_tipo=datos.get("badge_tipo", "dop"),
        tags_json=json.dumps(datos.get("tags", []), ensure_ascii=False),
        ingredientes_json=json.dumps(datos.get("ingredientes", [])),
        precio_personal=datos["precios"]["personal"],
        precio_mediana=datos["precios"]["mediana"],
        precio_familiar=datos["precios"]["familiar"],
        meta=datos.get("meta", "Lista en 25 min"),
        imagen=datos.get("imagen"),
        activo=datos.get("activo", True),
    )
    db.session.add(fila)
    db.session.commit()
    cargar_desde_bd()


def eliminar_pizza(pizza_id):
    fila = db.session.get(PizzaDB, pizza_id)
    if not fila:
        return False
    db.session.delete(fila)
    db.session.commit()
    cargar_desde_bd()
    return True


def crear_ingrediente(datos):
    fila = IngredienteDB(
        id=datos["id"], nombre=datos["nombre"], emoji=datos.get("emoji", "🍕"),
        grupo=datos["grupo"], precio=datos.get("precio", 0.0), color=datos.get("color", "#cccccc"),
        kcal=datos.get("kcal", 30), vegano=datos.get("vegano", True),
        sin_gluten=datos.get("sin_gluten", True), sin_lactosa=datos.get("sin_lactosa", True),
    )
    db.session.add(fila)
    db.session.commit()
    cargar_desde_bd()


def eliminar_ingrediente(ing_id):
    """
    Si alguna pizza de la carta todavía usa este ingrediente, no lo borramos
    (dejaría esa pizza con una receta rota) — avisamos cuáles son.
    Devuelve (ok, lista_de_pizzas_que_lo_usan).
    """
    en_uso = [p["nombre"] for p in PIZZAS if ing_id in p["ingredientes"]]
    if en_uso:
        return False, en_uso

    fila = db.session.get(IngredienteDB, ing_id)
    if not fila:
        return False, []

    db.session.delete(fila)
    db.session.commit()
    cargar_desde_bd()
    return True, []


# ---------------------------------------------------------
# Helpers de consulta (sin cambios respecto a la versión anterior)
# ---------------------------------------------------------
def obtener_pizza(pizza_id):
    for p in PIZZAS:
        if p["id"] == pizza_id:
            return p
    return None


def obtener_ingrediente(ing_id):
    return INGREDIENTES_POR_ID.get(ing_id)


def obtener_tamano(tamano_id):
    for t in TAMANOS:
        if t["id"] == tamano_id:
            return t
    return TAMANOS[0]


def ingredientes_por_grupo():
    """Devuelve [(grupo, [ingredientes...]), ...] en el orden de GRUPOS."""
    salida = []
    for g in GRUPOS:
        items = [i for i in INGREDIENTES if i["grupo"] == g["id"]]
        salida.append((g, items))
    return salida


# ---------------------------------------------------------
# Validación de combinaciones
# ---------------------------------------------------------
def _expandir(referencias, seleccionados):
    """Convierte ['grupo:carne', 'pina'] en los ids realmente seleccionados."""
    encontrados = []
    for ref in referencias:
        if ref.startswith("grupo:"):
            grupo = ref.split(":", 1)[1]
            encontrados += [i for i in seleccionados
                            if obtener_ingrediente(i) and obtener_ingrediente(i)["grupo"] == grupo]
        elif ref in seleccionados:
            encontrados.append(ref)
    return encontrados


def validar_combinacion(ids):
    """
    Revisa una lista de ingredientes y devuelve:
      errores      -> impiden agregar al carrito
      advertencias -> solo informan al cliente
    """
    ids = [i for i in ids if obtener_ingrediente(i)]
    errores, advertencias = [], []

    for g in GRUPOS:
        del_grupo = [i for i in ids if obtener_ingrediente(i)["grupo"] == g["id"]]
        if len(del_grupo) > g["max"]:
            errores.append({
                "titulo": f"Demasiados ingredientes en {g['nombre'].lower()}",
                "detalle": f"El máximo es {g['max']}. Tienes {len(del_grupo)}.",
                "ingredientes": del_grupo,
            })

    if not any(obtener_ingrediente(i)["grupo"] == "masa" for i in ids):
        errores.append({"titulo": "Falta elegir la masa",
                        "detalle": "Toda pizza necesita una masa.", "ingredientes": []})
    if not any(obtener_ingrediente(i)["grupo"] == "salsa" for i in ids):
        errores.append({"titulo": "Falta elegir la salsa base",
                        "detalle": "Elige al menos una salsa para la base.", "ingredientes": []})

    for regla in REGLAS_COMBINACION:
        lado_a = _expandir(regla["a"], ids)
        lado_b = _expandir(regla["b"], ids)
        pares = [(a, b) for a in lado_a for b in lado_b if a != b]
        if not pares:
            continue
        a, b = pares[0]
        item = {
            "titulo": f"{obtener_ingrediente(a)['nombre']} + {obtener_ingrediente(b)['nombre']}",
            "detalle": regla["motivo"],
            "ingredientes": sorted({p for par in pares for p in par}),
        }
        if regla["tipo"] == "bloquea":
            errores.append(item)
        else:
            advertencias.append(item)

    return {"errores": errores, "advertencias": advertencias}


def ingredientes_bloqueados(ids):
    """
    Dado lo ya seleccionado, dice qué ingredientes quedarían bloqueados si se
    agregan. Sirve para apagar las tarjetas en pantalla antes de que el cliente
    cometa el error.
    """
    bloqueados = {}
    for candidato in INGREDIENTES:
        if candidato["id"] in ids:
            continue
        prueba = list(ids) + [candidato["id"]]
        for regla in REGLAS_COMBINACION:
            if regla["tipo"] != "bloquea":
                continue
            lado_a = _expandir(regla["a"], prueba)
            lado_b = _expandir(regla["b"], prueba)
            pares = [(a, b) for a in lado_a for b in lado_b if a != b]
            choca = any(candidato["id"] in par for par in pares)
            if choca:
                bloqueados[candidato["id"]] = regla["motivo"]
                break
    return bloqueados


# ---------------------------------------------------------
# Pizzas parecidas
# ---------------------------------------------------------
def pizzas_similares(ids, excluir_id=None, minimo=0.5):
    """
    Compara la receta que está armando el cliente con las pizzas de la carta
    (índice de Jaccard) y devuelve las más parecidas.
    """
    seleccion = set(ids)
    if len(seleccion) < 3:
        return []

    resultados = []
    for p in PIZZAS:
        if not p.get("activo", True) or p["id"] == excluir_id:
            continue
        receta = set(p["ingredientes"])
        union = seleccion | receta
        if not union:
            continue
        coincidencia = len(seleccion & receta) / len(union)
        if coincidencia >= minimo:
            faltan = [obtener_ingrediente(i)["nombre"] for i in receta - seleccion]
            sobran = [obtener_ingrediente(i)["nombre"] for i in seleccion - receta]
            resultados.append({
                "id": p["id"], "nombre": p["nombre"], "descripcion": p["descripcion"],
                "precio": p["precios"]["personal"], "imagen": p.get("imagen"),
                "coincidencia": round(coincidencia * 100),
                "faltan": faltan, "sobran": sobran,
            })

    resultados.sort(key=lambda r: r["coincidencia"], reverse=True)
    return resultados[:1]


# ---------------------------------------------------------
# Cotización de una receta
# ---------------------------------------------------------
def cotizar(pizza_id, ids, tamano_id):
    """
    Calcula precio, desglose, calorías y tiempo de horneado.
    Si pizza_id viene con valor, los ingredientes originales van incluidos en el
    precio de carta y solo se cobran los que el cliente agregó.
    """
    tam = obtener_tamano(tamano_id)
    factor = tam["factor"]
    pizza = obtener_pizza(pizza_id) if pizza_id else None

    ids = [i for i in ids if obtener_ingrediente(i)]
    desglose = []

    if pizza:
        base = pizza["precios"].get(tamano_id, pizza["precios"]["personal"])
        incluidos = set(pizza["ingredientes"])
        desglose.append({"etiqueta": f"{pizza['nombre']} · {tam['nombre']}",
                         "valor": base, "tipo": "base"})
    else:
        base = BASE_PERSONALIZADA.get(tamano_id, BASE_PERSONALIZADA["personal"])
        incluidos = set()
        desglose.append({"etiqueta": f"Masa y horneado · {tam['nombre']}",
                         "valor": base, "tipo": "base"})

    total = base
    detalle = []
    kcal = 120

    for iid in ids:
        ing = obtener_ingrediente(iid)
        kcal += ing["kcal"]
        if iid in incluidos:
            detalle.append({"id": iid, "nombre": ing["nombre"], "emoji": ing["emoji"],
                            "grupo": ing["grupo"], "precio": 0.0, "incluido": True})
        else:
            precio = round(ing["precio"] * factor, 2)
            total += precio
            detalle.append({"id": iid, "nombre": ing["nombre"], "emoji": ing["emoji"],
                            "grupo": ing["grupo"], "precio": precio, "incluido": False})
            if precio > 0:
                desglose.append({"etiqueta": f"Extra: {ing['nombre']}",
                                 "valor": precio, "tipo": "extra"})

    quitados = []
    if pizza:
        for iid in pizza["ingredientes"]:
            if iid not in ids:
                quitados.append({"id": iid, "nombre": obtener_ingrediente(iid)["nombre"]})

    return {
        "total": round(total, 2),
        "base": round(base, 2),
        "desglose": desglose,
        "detalle": detalle,
        "quitados": quitados,
        "kcal": int(kcal * factor),
        "minutos": tam["minutos"],
        "tamano_id": tam["id"],
        "tamano_nombre": tam["nombre"],
        "dieta": calcular_dieta(ids),
    }