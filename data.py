# -*- coding: utf-8 -*-
"""
Datos del menú de Pizza Pronto.
Por ahora viven aquí como una lista de diccionarios en memoria.
Más adelante esto se puede mover a una base de datos real.
"""

PIZZAS = [
    {
        "id": "margherita",
        "categoria": "clasica",
        "badge": "D.O.P Certificada",
        "badge_tipo": "dop",
        "nombre": "Margherita Verace D.O.P",
        "descripcion": (
            "Tomate San Marzano D.O.P, Fior di Latte de Agerola, albahaca fresca "
            "del huerto y aceite de oliva virgen extra. Horneada 90s a 450°C."
        ),
        "tags": ["Fermentación 72h", "Harina Caputo Tipo 00"],
        "precio_base": 14.50,
        "meta": "Horneada al momento en horno de leña",
        "dieta": {"vegano": False, "sin_gluten": False, "sin_lactosa": False},
        "personalizacion": {
            "etiqueta": "Estándar AVPN",
            "tamanos": [
                {"id": "mediana", "nombre": "Mediana 30cm", "desc": "Individual napolitana", "precio": 14.50, "extra": 0},
                {"id": "familiar", "nombre": "Familiar 35cm", "desc": "Para compartir (2-3)", "precio": 18.50, "extra": 4.00},
            ],
            "insumos_base": [
                {"nombre": "Masa Napolitana 72h Fermentación", "detalle": "100% Hidratación"},
                {"nombre": "Pomodoro San Marzano D.O.P", "detalle": "Agro Sarnese"},
            ],
            "quesos": [
                {"id": "fior_original", "nombre": "Fior di Latte Agerola (Original)", "extra": 0, "incluido": True},
                {"id": "mozz_sin_lactosa", "nombre": "Mozzarella Sin Lactosa", "extra": 1.50},
                {"id": "doble_fior", "nombre": "Doble Fior di Latte Rallado Fino", "extra": 2.00},
            ],
            "toppings": [
                {"id": "prosciutto", "nombre": "Prosciutto di Parma 24m (añadido en crudo)", "extra": 1.50, "defecto": True},
                {"id": "rucula", "nombre": "Rúcula Fresca & Gotas de Limón de Amalfi", "extra": 1.00},
            ],
            "tiempo_horneado": "~8 min",
            "kcal": "840 kcal aprox",
        },
    },
    {
        "id": "diavola",
        "categoria": "especialidad",
        "badge": "Picante Suave",
        "badge_tipo": "picante",
        "nombre": "Diávola Calabresa & 'Nduja",
        "descripcion": (
            "Spianata piccante calabrese, 'nduja artesanal, fior di latte ahumado "
            "y miel infusionada con chiles de Calabria sobre masa rústica."
        ),
        "tags": ["Embutido Calabrés D.O.P", "Miel Picante Casera"],
        "precio_base": 17.00,
        "meta": "Tiempo estándar: 9-11 min",
        "dieta": {"vegano": False, "sin_gluten": False, "sin_lactosa": False},
        "personalizacion": {
            "etiqueta": "Nivel Picante Ajustable",
            "tamanos": [
                {"id": "mediana", "nombre": "Mediana 30cm", "desc": "Individual napolitana", "precio": 17.00, "extra": 0},
                {"id": "familiar", "nombre": "Familiar 35cm", "desc": "Para compartir (2-3)", "precio": 21.50, "extra": 4.50},
            ],
            "insumos_base": [
                {"nombre": "Masa Rústica 48h Fermentación", "detalle": "78% Hidratación"},
                {"nombre": "Spianata Piccante Calabrese", "detalle": "Denominación Calabria"},
            ],
            "quesos": [
                {"id": "fior_ahumado", "nombre": "Fior di Latte Ahumado (Original)", "extra": 0, "incluido": True},
                {"id": "provola", "nombre": "Provola Affumicata", "extra": 1.80},
            ],
            "toppings": [
                {"id": "nduja_extra", "nombre": "'Nduja Extra Artesanal", "extra": 2.00, "defecto": True},
                {"id": "miel_picante", "nombre": "Miel Picante Casera Doble", "extra": 1.20},
            ],
            "tiempo_horneado": "~9 min",
            "kcal": "910 kcal aprox",
        },
    },
    {
        "id": "tartufo",
        "categoria": "especialidad",
        "badge": "Especialidad de Autor",
        "badge_tipo": "autor",
        "nombre": "Tartufo & Funghi Porcini",
        "descripcion": (
            "Crema de trufa negra de Umbría, setas porcini salteadas al sarmiento, "
            "mozzarella di bufala campana y finas láminas de parmesano 24 meses."
        ),
        "tags": ["Trufa Negra de Umbría", "Bufala D.O.P"],
        "precio_base": 21.50,
        "meta": "Recomendado con Vino Chianti Classico",
        "dieta": {"vegano": False, "sin_gluten": False, "sin_lactosa": False},
        "personalizacion": {
            "etiqueta": "Selección de Chef",
            "tamanos": [
                {"id": "mediana", "nombre": "Mediana 30cm", "desc": "Individual napolitana", "precio": 21.50, "extra": 0},
                {"id": "familiar", "nombre": "Familiar 35cm", "desc": "Para compartir (2-3)", "precio": 26.50, "extra": 5.00},
            ],
            "insumos_base": [
                {"nombre": "Masa Napolitana 72h Fermentación", "detalle": "100% Hidratación"},
                {"nombre": "Crema de Trufa Negra de Umbría", "detalle": "Cosecha de Temporada"},
            ],
            "quesos": [
                {"id": "bufala_original", "nombre": "Mozzarella di Bufala Campana (Original)", "extra": 0, "incluido": True},
                {"id": "parmesano_extra", "nombre": "Parmesano 24 Meses Extra", "extra": 2.20},
            ],
            "toppings": [
                {"id": "porcini_extra", "nombre": "Setas Porcini Extra Salteadas", "extra": 2.50, "defecto": True},
                {"id": "trufa_extra", "nombre": "Láminas de Trufa Negra Extra", "extra": 3.50},
            ],
            "tiempo_horneado": "~8 min",
            "kcal": "870 kcal aprox",
        },
    },
]


def obtener_pizza(pizza_id):
    for pizza in PIZZAS:
        if pizza["id"] == pizza_id:
            return pizza
    return None
