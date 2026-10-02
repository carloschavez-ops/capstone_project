import re
import unicodedata


INVENTORY_GROUPS = [
    ("Carnes, Embutidos y Proteínas", [
        ("Carne de res", "kg"), ("Carne de pollo", "kg"), ("Pollo deshilachado", "kg"),
        ("Presas de pollo (para freír/broaster)", "unidad"), ("Salchicha artesanal", "kg"),
        ("Hot dog", "paquete"), ("Tocino", "kg"), ("Jamón", "kg"), ("Salami", "kg"),
        ("Pepperoni", "kg"), ("Cabanossi", "kg"), ("Chorizo", "kg"),
        ("Atún en conserva", "unidad"), ("Huevo", "unidad"), ("Anchoas", "unidad"),
    ]),
    ("Lácteos y Quesos", [
        ("Queso Mozzarella", "kg"), ("Queso Edam", "kg"), ("Queso Cheddar", "kg"),
        ("Queso Provolone", "kg"), ("Queso Dambo", "kg"), ("Queso Gouda", "kg"),
        ("Queso Parmesano", "kg"), ("Queso fresco", "kg"), ("Leche", "l"),
        ("Leche evaporada", "unidad"), ("Crema de leche", "l"),
        ("Leche condensada", "unidad"), ("Crema de coco", "l"),
        ("Mantequilla", "kg"), ("Margarina", "kg"),
    ]),
    ("Panadería, Masas y Cereales", [
        ("Pan de hamburguesa", "unidad"), ("Pan de molde", "paquete"),
        ("Pan de sándwich", "paquete"), ("Pan baguette", "unidad"),
        ("Pan de yuca", "unidad"), ("Masa de pizza", "kg"), ("Masa de wantán", "paquete"),
        ("Arroz", "kg"), ("Papa entera", "kg"), ("Papa para freír", "kg"), ("Yuca", "kg"),
    ]),
    ("Verduras, Hortalizas y Hierbas", [
        ("Lechuga", "unidad"), ("Tomate", "kg"), ("Cebolla", "kg"), ("Zanahoria", "kg"),
        ("Pimiento", "kg"), ("Espinaca", "kg"), ("Champiñones", "kg"), ("Alcachofas", "unidad"),
        ("Aceitunas negras", "kg"), ("Aceitunas verdes", "kg"), ("Ajo", "kg"),
        ("Albahaca", "paquete"), ("Perejil", "paquete"), ("Hierbabuena", "paquete"),
        ("Menta", "paquete"),
    ]),
    ("Frutas", [
        ("Papaya", "unidad"), ("Piña", "unidad"), ("Fresa", "kg"), ("Mango", "unidad"),
        ("Lúcuma", "kg"), ("Durazno", "kg"), ("Arándanos", "kg"), ("Plátano", "unidad"),
        ("Manzana", "unidad"), ("Maracuyá", "unidad"), ("Limón", "kg"),
    ]),
    ("Gaseosas y Bebidas (Stock e Insumos)", [
        ("Coca Cola", "unidad"), ("Inca Kola", "unidad"), ("Fanta", "unidad"),
        ("Sprite", "unidad"), ("Agua natural", "unidad"), ("Agua con gas", "unidad"),
        ("Café en grano", "kg"), ("Café instantáneo", "paquete"), ("Cacao", "kg"),
        ("Chocolate puro", "kg"), ("Infusiones", "paquete"), ("Té", "paquete"),
        ("Pisco", "l"), ("Ron", "l"), ("Tequila", "l"), ("Vodka", "l"),
        ("Ginger ale", "unidad"), ("Licor de naranja", "l"), ("Algarrobina", "l"),
    ]),
    ("Salsas, Condimentos e Insumos Secos", [
        ("Salsa de tomate", "l"), ("Nutella", "kg"), ("Salsa BBQ", "l"),
        ("Salsa de tamarindo", "l"), ("Salsa de maracuyá", "l"), ("Salsa golf", "l"),
        ("Jarabe de goma", "l"), ("Amargo de angostura", "l"), ("Sal", "kg"),
        ("Pimienta negra", "kg"), ("Canela", "paquete"), ("Clavo", "paquete"),
        ("Azúcar", "kg"),
    ]),
]


def _slug(value):
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


INVENTORY_CATEGORIES = [category for category, _items in INVENTORY_GROUPS]
INVENTORY_ITEMS = [
    {
        "item_id": f"stock-{_slug(category)}-{index:02d}",
        "categoria": category,
        "nombre": name,
        "unidad": unit,
    }
    for category, items in INVENTORY_GROUPS
    for index, (name, unit) in enumerate(items, start=1)
]