# Pizza Pronto

Aplicación de pedidos con frontend React y API Flask. El catálogo, los ingredientes y los pedidos se guardan en SQLite.

## Estructura

- `backend/`: API Flask y base `pizza_pronto.sqlite3` (se crea y se siembra al iniciar).
- `frontend/`: aplicación React con Vite.
- `menu_data.py`: semilla idempotente de los artículos de la carta, agrupados por categoría.
- `data.py` y `modelos.py`: recetas personalizables, ingredientes, reglas de cocina y modelos SQLite del catálogo.
- `backend/models.py`: persistencia de pedidos.

La antigua interfaz Flask y sus templates se retiraron. `data.py` y `modelos.py` permanecen en la raíz porque la API los usa para el catálogo y sus reglas.

## Requisitos

- Python 3.10 o superior.
- Node.js 20 o superior, que incluye npm.

## Instalación

Desde la raíz del proyecto, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd frontend
npm install
```

## Desarrollo

Abre dos terminales desde la raíz del proyecto.

Terminal 1, API:

```powershell
.\.venv\Scripts\Activate.ps1
python -m backend
```

Terminal 2, React:

```powershell
cd frontend
npm run dev
```

Abre la URL que muestra Vite, normalmente `http://127.0.0.1:5173`. Vite redirige las llamadas `/api` al backend en `http://127.0.0.1:5000`.

Cuenta admin inicial: `pizzapronto@gmail.com` / `pizzapronto`. Se crea automáticamente al iniciar el backend; cambia esa contraseña antes de exponer la aplicación fuera de desarrollo.

La carta tiene búsqueda por nombre, categoría, descripción e ingredientes. El panel admin permite crear pizzas con imagen JPG/PNG/WEBP (máximo 5 MB), ingredientes, tipo y precios personal/mediana/familiar. La API expone `POST /api/admin/pizzas` para ese alta; las rutas de `/api/admin/` requieren el rol administrador. La receta personalizable ofrece únicamente masa italiana; al iniciar se normalizan las recetas anteriores a esa masa y se retiran las otras opciones de masa.

La API también expone `GET /api/health`, `GET /api/catalog`, `POST /api/quote`, `GET /api/auth/me`, `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/guest`, `POST /api/auth/logout` y `POST /api/orders`. Las rutas de `/api/admin/` permiten editar, ocultar o eliminar pizzas y mantener cantidades/unidades de inventario. Las cuentas se guardan en SQLite con contraseñas hasheadas; los pedidos requieren una sesión activa. Los precios y la validación de recetas se calculan en el servidor.

Antes de ver la carta, los invitados completan nombre, teléfono y modalidad: delivery (dirección, referencia y DNI/RUC opcional), retiro en local o consumo en local (mesa y DNI/RUC). La dirección para retiro y consumo es Av. Manco Cápac 618, Cajamarca 06004. Los pedidos guardan estos datos en SQLite.

Para despliegue, configura `PIZZA_PRONTO_SECRET_KEY` con un valor aleatorio y privado. La clave incluida por defecto es solo para desarrollo local.

## Pruebas

Desde la raíz, con el entorno Python activo:

```powershell
python -m unittest discover -s backend/tests -v
```