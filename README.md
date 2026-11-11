# Pizza Pronto

Aplicación de pedidos con frontend React y API Flask. El catálogo, los ingredientes y los pedidos se guardan en SQLite.

## Estructura

- `backend/`: API Flask, servidor WSGI y herramientas de mantenimiento.
- `instance/pizza_pronto.db`: base SQLite activa, creada al iniciar (ruta configurable).
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
npm.cmd install
cd frontend
npm.cmd install
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

En una instalación local nueva, el administrador usa `pizzapronto@gmail.com` y una contraseña aleatoria guardada en `instance/.admin-password`. También puedes definir `PIZZA_PRONTO_ADMIN_EMAIL` y `PIZZA_PRONTO_ADMIN_PASSWORD` antes del primer arranque. Las cuentas de una base existente se conservan; producción rechaza la contraseña inicial antigua.

La carta tiene búsqueda por nombre, categoría, descripción e ingredientes. El panel admin permite crear pizzas con imagen JPG/PNG/WEBP (máximo 5 MB), ingredientes, tipo y precios personal/mediana/familiar. La API expone `POST /api/admin/pizzas` para ese alta. Cocina puede consultar pedidos/stock y marcar pedidos listos; caja puede consultar pedidos y registrar entrega/pago. Las demás funciones administrativas requieren el rol administrador. La receta personalizable ofrece únicamente masa italiana; la normalización inicial se aplica una vez.

La API también expone `GET /api/health`, `GET /api/catalog`, `POST /api/quote`, `GET /api/auth/me`, `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/guest`, `POST /api/auth/logout` y `POST /api/orders`. Las rutas de `/api/admin/` permiten editar, ocultar o eliminar pizzas y mantener cantidades/unidades de inventario. Las cuentas se guardan en SQLite con contraseñas hasheadas; los pedidos requieren una sesión activa. Los precios y la validación de recetas se calculan en el servidor.

Antes de ver la carta, los invitados completan nombre, teléfono y modalidad: delivery (dirección, referencia y DNI/RUC opcional), retiro en local o consumo en local (mesa y DNI/RUC). La dirección para retiro y consumo es Av. Manco Cápac 618, Cajamarca 06004. Los pedidos guardan estos datos en SQLite.

## Funciones añadidas del backlog T2

Se revisaron las 18 historias. Se conservaron las funciones existentes y se completaron las brechas pendientes:

- **HU06**: estados y tiempos configurables, inicio manual/automático y anulación con motivo.
- **HU08**: ajustes con conversión de unidades compatibles y rechazo de saldos inválidos.
- **HU09**: recetas para todo el catálogo y todos los ingredientes/tamaños, consumo único al preparar, transacciones y reversión trazable. La pestaña Recetas permite editarlas.
- **HU12**: CSRF, expiración absoluta y por inactividad, límite persistente de intentos, secretos individuales y configuración HTTPS.
- **HU13**: reportes por fechas y estado, cobros registrados, anulaciones y CSV conciliable, en Reportes.
- **HU16**: foco atrapado y restaurado en diálogos, Escape, navegación con teclado, estilos móviles y cálculo de la meta del 80% sin ayuda en el piloto.

- **HU10**: cuentas individuales de cocina/caja y matriz de permisos, en la pestaña Personal.
- **HU11**: ZIP de SQLite e imágenes, descarga, verificación aislada y restauración offline, en Respaldos y `backend.maintenance`.
- **HU14**: auditoría transaccional con actor, fecha, entidad y valores anteriores/posteriores, en Auditoría.
- **HU15**: protocolo del piloto, resultados, defectos, responsables y acta conservada, en Piloto.
- **HU17**: servidor Waitress, frontend compilado, rutas persistentes y manual de operación.
- **HU18**: base anónima antes/después, denominadores, comparación por condiciones y exportación CSV, en Indicadores.

Consulta [el manual de operación](docs/MANUAL_OPERACION.md) para configuración, arranque, permisos, respaldo, recuperación y registro de evidencias. El registro público continúa creando solo clientes. Los formularios utilizan protección CSRF.

Para servir la versión compilada localmente:

```powershell
cd frontend
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe -m backend.serve
```

Abre `http://127.0.0.1:5000`. En producción, configurar `PIZZA_PRONTO_ENV=production`, un secreto privado de al menos 32 caracteres y HTTPS mediante el proxy descrito en el manual. La contraseña inicial se rechaza en producción. La clave de desarrollo se genera localmente y no está incorporada al código.

Las recetas iniciales utilizan **cantidades ficticias aproximadas autorizadas para la demostración**. Se identifican como `estimacion_demo` y no sustituyen las recetas del negocio. Los productos nuevos también reciben recetas de demostración editables. Los pedidos históricos se identifican como `legacy` para no descontar nuevamente un consumo previo desconocido.

La implementación cubre las funciones de HU01 a HU18. La aceptación del negocio, las observaciones antes/después, la configuración del dominio y la programación diaria de copias requieren ejecución en el entorno real. No se precargan resultados del piloto ni se modifica el Excel para marcar historias como aceptadas.

## Pruebas

Desde la raíz, con el entorno Python activo:

```powershell
python -m unittest discover -s backend/tests -v
```
