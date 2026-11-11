"""Cantidades ficticias de demostración autorizadas por el usuario.

Las porciones son aproximaciones técnicas; no representan recetas del negocio.
Las cantidades usan la unidad base del inventario indicado.
"""


def menu_portions(product):
    key, category = product.id, product.categoria
    if category == "Gaseosas":
        return [(f"{product.nombre} {product.subcategoria}".strip(), 1, "unidad")]
    if product.es_pizza:
        base = [("Masa de pizza", .25, "kg")]
        if "nutella" in key:
            return base + [("Nutella", .12, "kg"), ("Fresa", .06, "kg")]
        parts = base + [("Salsa de tomate", .06, "l"), ("Queso Mozzarella", .15, "kg")]
        toppings = {"hawaiana": [("Jamón", .06, "kg"), ("Piña", .2, "unidad")], "jamon": [("Jamón", .07, "kg")],
                    "pepperoni": [("Pepperoni", .07, "kg")], "cabanossi": [("Cabanossi", .07, "kg")],
                    "salami": [("Salami", .07, "kg")], "tropical": [("Jamón", .05, "kg"), ("Piña", .2, "unidad"), ("Durazno", .06, "kg")],
                    "margarita": [("Tomate", .06, "kg"), ("Albahaca", .03, "paquete")]}
        for token, values in toppings.items():
            if token in key:
                parts += values
        return parts
    if category == "Hamburguesas":
        parts = [("Pan de hamburguesa", 1, "unidad"), ("Carne de pollo" if "pollo" in key else "Carne de res", .15 if "doble" not in key else .3, "kg"), ("Lechuga", .05, "unidad"), ("Tomate", .04, "kg")]
        for token, part in {"especial": ("Huevo", 1, "unidad"), "hawaiana": ("Piña", .15, "unidad"), "choriburger": ("Chorizo", .08, "kg"), "pizza-burger": ("Queso Mozzarella", .05, "kg")}.items():
            if token in key:
                parts.append(part)
        return parts
    if category == "Sándwiches":
        parts = [("Pan de sándwich", .1, "paquete")]
        for token, part in {"huevo": ("Huevo", 1, "unidad"), "jamon": ("Jamón", .04, "kg"), "queso": ("Queso Edam", .04, "kg"), "pollo": ("Pollo deshilachado", .1, "kg"), "tocino": ("Tocino", .03, "kg"), "hot-dog": ("Hot dog", .1, "paquete")}.items():
            if token in key:
                parts.append(part)
        return parts
    if category == "Salchipapas":
        return [("Papa para freír", .25, "kg"), ("Hot dog", .15, "paquete")] + ([] if "simple" in key else [("Huevo", 1, "unidad"), ("Carne de pollo", .1, "kg")])
    if category in {"Alitas", "Broasters"}:
        return [("Alitas de pollo" if category == "Alitas" else "Presas de pollo (para freír/broaster)", 6 if category == "Alitas" else 1, "unidad"), ("Papa para freír", .25, "kg")] + ([("Salsa BBQ", .04, "l")] if "bbq" in key else [("Salsa de maracuyá", .04, "l")] if "maracuya" in key else [])
    if category == "Entradas":
        if "pan-yuca" in key:
            return [("Pan de yuca", 5, "unidad")]
        if "tequenos" in key:
            return [("Masa de wantán", .2, "paquete"), ("Queso Mozzarella", .12, "kg")]
        if "ensalada" in key:
            return [("Lechuga", .25, "unidad"), ("Tomate", .12, "kg"), ("Zanahoria", .06, "kg")] + ([("Atún en conserva", .5, "unidad")] if "especial" in key else [])
        return [("Pan baguette", 1, "unidad"), ("Mantequilla", .02, "kg"), ("Ajo", .005, "kg")] + ([("Queso Mozzarella", .08, "kg")] if any(token in key for token in ("especial", "mozzarella")) else [])
    if category == "Adicionales":
        for token, item, amount, unit in [("carne", "Carne de res", .15, "kg"), ("hot-dog", "Hot dog", .1, "paquete"), ("huevo", "Huevo", 1, "unidad"), ("cheddar", "Queso Cheddar", .03, "kg"), ("presa", "Presas de pollo (para freír/broaster)", 1, "unidad"), ("papas", "Papa para freír", .2, "kg"), ("arroz", "Arroz", .1, "kg"), ("anchoas", "Anchoas", .25, "unidad")]:
            if token in key:
                return [(item, amount, unit)]
        return [("Queso Mozzarella", .08, "kg")]
    if category == "Cócteles":
        spirit = "Vodka" if "caipiroska" in key else "Tequila" if "margarita" in key else "Ron" if any(t in key for t in ("mojito", "cuba", "daiquiri", "colada")) else "Pisco"
        return [(spirit, .06, "l"), ("Limón", .04, "kg"), ("Jarabe de goma", .025, "l")]
    if category == "Jugos, batidos y café":
        if "infusion" in key:
            return [("Té" if "te-" in key else "Infusiones", .05, "paquete"), ("Agua para preparación", .25, "l")]
        if "cafe" in key:
            return [("Café instantáneo", .02, "paquete")] if "instantaneo" in key else [("Café en grano", .012, "kg")] + ([("Leche", .15, "l")] if any(t in key for t in ("leche", "cappuccino")) else [])
        if "chocolate" in key or key == "taza-leche":
            return [("Leche", .25, "l")] + ([("Chocolate puro", .025, "kg")] if "chocolate" in key else [])
        fruits = {"papaya": ("Papaya", .2, "unidad"), "pina": ("Piña", .2, "unidad"), "fresa": ("Fresa", .15, "kg"), "mango": ("Mango", .5, "unidad"), "lucuma": ("Lúcuma", .15, "kg"), "durazno": ("Durazno", .15, "kg"), "arandano": ("Arándanos", .12, "kg"), "platano": ("Plátano", 1, "unidad"), "limonada": ("Limón", .1, "kg"), "maracuya": ("Maracuyá", 1, "unidad")}
        parts = [part for token, part in fruits.items() if token in key]
        if "maracumango" in key:
            parts = [("Maracuyá", .5, "unidad"), ("Mango", .5, "unidad")]
        if not parts:
            parts = [("Papaya", .15, "unidad"), ("Fresa", .08, "kg")]
        parts += [("Leche", .2, "l")] if "batido" in key else [("Agua para preparación", .2, "l")]
        factor = 2.5 if "litro-" in key else 1
        return [(name, round(amount * factor, 5), unit) for name, amount, unit in parts]
    return []
