# Despliegue de Pizza Pronto Italiana en Render

El servicio sirve la carta y la API desde la misma URL HTTPS. El primer arranque crea las cuentas iniciales de administración, cocina y caja. El archivo `render.yaml` configura el servicio y un disco persistente para SQLite, las imágenes subidas y las copias.

## Instalación con Blueprint y disco persistente

1. Descomprime el ZIP. Sube **el contenido** de `capstone_project` a un repositorio Git conectado a Render. En la raíz del repositorio deben quedar `render.yaml`, `requirements.txt`, `backend` y `frontend`.
2. En el panel de Render, elige **New → Blueprint** y selecciona el repositorio.
3. Introduce tres contraseñas privadas distintas, de al menos 12 caracteres, en los campos `PIZZA_PRONTO_ADMIN_PASSWORD`, `PIZZA_PRONTO_COCINA_PASSWORD` y `PIZZA_PRONTO_CAJA_PASSWORD`. Render genera automáticamente `PIZZA_PRONTO_SECRET_KEY`.
4. Revisa el plan y el disco que muestra el panel antes de crear el servicio. El Blueprint usa un plan de pago y monta 1 GB en `/var/data`.
5. Cuando el servicio esté en línea, abre la URL HTTPS de Render. Comprueba que `/api/health` devuelve HTTP 200 e inicia sesión con cada rol.

| Rol | Correo inicial | Acceso |
| --- | --- | --- |
| Administración | `pizzapronto@gmail.com` | Panel admin |
| Cocina | `cocina@pizzapronto.test` | Panel de trabajo |
| Caja | `caja@pizzapronto.test` | Panel de trabajo |

Los tres correos son identificadores de inicio de sesión. Si necesitas otros, establece `PIZZA_PRONTO_ADMIN_EMAIL`, `PIZZA_PRONTO_COCINA_EMAIL` o `PIZZA_PRONTO_CAJA_EMAIL` antes del primer arranque. Las variables de contraseña se aplican a la creación inicial. Para cambiar una cuenta de cocina o caja ya creada, usa **Panel admin → Personal**. El disco mantiene las cuentas y el estado del negocio al reiniciar o publicar otra versión.

## Demostración en plan gratuito

Crea un **Web Service** manual con el entorno **Python**, elige el plan **Free** y deja vacío el directorio raíz si subiste el contenido del ZIP según el paso 1.

| Campo | Valor |
| --- | --- |
| Build Command | `pip install -r requirements.txt && npm ci && npm ci --prefix frontend --include=dev && npm run build --prefix frontend` |
| Start Command | `python -m backend.serve` |
| Health Check Path | `/api/health` |

En **Environment**, define `PIZZA_PRONTO_ENV=production`, `PIZZA_PRONTO_SECRET_KEY` con un valor aleatorio de al menos 32 caracteres y las tres variables de contraseña del paso 3. Las versiones de Python y Node que usa el Blueprint se pueden copiar desde `render.yaml`. Deja sin definir `PIZZA_PRONTO_DATA_DIR` y `PIZZA_PRONTO_UPLOAD_DIR`.

En el plan gratuito los archivos son temporales. Al reconstruirse la instancia, las tres cuentas iniciales vuelven a crearse con los valores de Render. Se pierden los pedidos, los ajustes, las imágenes subidas y las cuentas o cambios de clave hechos desde el panel.

[Servicios web de Render](https://render.com/docs/web-services) · [Discos persistentes](https://render.com/docs/disks) · [Plan gratuito](https://render.com/docs/free)
