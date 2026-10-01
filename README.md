# Pizza Pronto

Aplicación de pedidos con frontend React y API Flask. El catálogo, los ingredientes y los pedidos se guardan en SQLite.

## Estructura

- `backend/`: API Flask y base `pizza_pronto.sqlite3` (se crea y se siembra al iniciar).
- `frontend/`: aplicación React con Vite.
- `data.py` y `modelos.py`: catálogo inicial, reglas de cocina y modelos del catálogo reutilizados por la API.
- `backend/models.py`: persistencia de pedidos.

Los archivos de la aplicación anterior se conservan, pero el nuevo flujo se inicia desde `backend/` y `frontend/`.

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

La API expone `GET /api/health`, `GET /api/catalog`, `POST /api/quote` y `POST /api/orders`. Los precios y la validación de recetas se calculan en el servidor al cotizar y antes de guardar un pedido.

## Pruebas

Desde la raíz, con el entorno Python activo:

```powershell
python -m unittest discover -s backend/tests -v
```