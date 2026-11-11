# Operación de Pizza Pronto

Este manual cubre el arranque WSGI, las cuentas operativas, la persistencia, las copias, la recuperación y el registro del piloto. El responsable de mantenimiento es el administrador técnico designado por el negocio. Antes del piloto se debe registrar su nombre, contacto y reemplazo en el acta de transferencia del local.

## Recetas y stock de demostración

Por autorización del usuario, se incluyen cantidades ficticias aproximadas para todos los productos del catálogo y cada ingrediente/tamaño de pizza personalizable. La pestaña **Recetas** distingue `estimacion_demo` de una receta configurada por administración. Estas cantidades permiten demostrar el flujo; se deben reemplazar con las recetas reales del negocio antes de operar con inventario real. No se presentan como información proporcionada por la pizzería.

Al recibir un pedido se conserva una instantánea de su plan de consumo. El descuento ocurre **al iniciar preparación**, una sola vez, con bloqueo de escritura SQLite y validación completa de existencias. Si falta stock, el pedido permanece recibido, muestra el problema y no modifica ningún insumo. Después de ajustar existencias se puede reintentar. La anulación antes de entregar/cobrar exige motivo y revierte una sola vez los movimientos de consumo.

Los pedidos anteriores a esta versión se marcan `legacy`: no se aplica otro descuento ni se inventa una reversión de consumos antiguos desconocidos. Si se anulan, su aviso exige conciliar manualmente el inventario histórico.

En **Inventario**, las cantidades se pueden introducir en una unidad compatible: 500 g se guarda como 0,5 kg si la unidad base del insumo es kg. No se permite convertir kg a litros, unidades o paquetes. Se conserva la unidad base para mantener coherentes recetas y movimientos. Las cantidades de paquetes/unidades pueden representar fracciones de contenido; la receta debe documentar qué significa esa unidad.

## Estados y reportes

En **Pedidos**, administración configura la espera de inicio automático entre 0 y 3600 segundos y la estimación entre 1 y 120 minutos por pizza. Cocina puede iniciar preparación o marcar listo. Caja registra entrega y cobro. Se rechazan saltos y no se duplica un cobro si se repite la solicitud. Solo administración puede anular pedidos anteriores a la entrega.

En **Reportes**, seleccionar fechas inclusivas y estado. Las fechas se interpretan en hora de Perú y seleccionan los pedidos creados en ese intervalo. La tabla de pagos conserva los cobros de esos mismos pedidos y muestra su fecha real de registro; no es un reporte independiente de caja por fecha de cobro. Los totales separan importe de pedidos, anulaciones, importe vigente, cobrado y pendiente. El CSV incluye ambos tipos de registro con su fecha y código. Los pagos migrados desde pedidos antiguos se identifican como `migracion`.

## Sesiones y acceso inicial

Las instalaciones locales nuevas generan una contraseña administradora aleatoria en `instance/.admin-password`; no hay una contraseña compartida de desarrollo. Una base existente conserva sus cuentas. Definir las variables privadas de administrador antes del primer arranque permite establecer una contraseña propia. Producción exige 12 caracteres como mínimo y rechaza la credencial inicial antigua.

La sesión vence tras 30 minutos sin solicitudes o a las 8 horas desde el ingreso, aunque siga habiendo actividad. La API comprueba estos límites además de la validez de la cookie. Los formularios requieren CSRF y las respuestas de la API no se cachean. Cinco intentos fallidos por cuenta bloquean el acceso durante la ventana de 15 minutos; también existe un límite por dirección de origen. Los identificadores del control de intentos se guardan como HMAC, sin contraseñas. Una cuenta desactivada o cuya credencial cambia pierde sus sesiones anteriores.

## Uso con teclado y evaluación de facilidad

La carta y los formularios utilizan controles nativos con foco visible. Los diálogos capturan Tab y Shift+Tab, Escape cierra el diálogo y el foco vuelve al control que lo abrió. El fondo queda inactivo mientras el diálogo está abierto. El enlace Saltar al contenido evita recorrer toda la cabecera. Las tablas anchas tienen desplazamiento y los formularios se adaptan al ancho móvil.

La tarea P06 del piloto registra participantes con códigos anónimos. El porcentaje sin ayuda es participantes con resultado aprobado y sin ayuda dividido entre todas las ejecuciones P06 registradas. La pantalla muestra numerador, denominador, porcentaje y comparación con la meta del 80%; sin ejecuciones muestra Sin datos. Los resultados automatizados no se registran en la base real ni representan participantes del negocio.

## Instalación o actualización

Python 3.10 o superior y Node.js 20 o superior. Desde la raíz, en PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd install
cd frontend
npm.cmd install
npm.cmd run build
cd ..
```

Si `.venv` ya existe y funciona, omite su creación. El `npm install` de la raíz instala `recharts`, declarado por la estructura original del repositorio. El de `frontend` instala React y Vite. No se necesita un servidor de base de datos externo.

## Desarrollo

En una terminal de la raíz:

```powershell
.\.venv\Scripts\python.exe -m backend
```

En otra terminal:

```powershell
cd frontend
npm.cmd run dev
```

Abrir `http://127.0.0.1:5173`. La API escucha en `127.0.0.1:5000`. El depurador está desactivado y el proceso mantiene un bloqueo que evita restauraciones simultáneas. Detener con Ctrl+C.

## Configuración del servicio

| Variable | Uso |
| --- | --- |
| `PIZZA_PRONTO_ENV` | `production` exige una clave de sesión privada y activa cookies Secure. |
| `PIZZA_PRONTO_SECRET_KEY` | Secreto privado de al menos 32 caracteres en producción. No incluir en Git ni en el Word. En desarrollo se genera una clave local persistente en `instance/.session-key`. |
| `PIZZA_PRONTO_ADMIN_EMAIL` | Correo del administrador inicial. En una instalación nueva, definir el correo real antes de arrancar. |
| `PIZZA_PRONTO_ADMIN_PASSWORD` | Contraseña para crear al administrador en una instalación productiva nueva o para el comando de cambio de credencial. Mínimo 12 caracteres. No se imprime ni se guarda en código. |
| `PIZZA_PRONTO_DATA_DIR` | Directorio persistente para SQLite y copias. Predeterminado: `instance` en la raíz. |
| `PIZZA_PRONTO_UPLOAD_DIR` | Directorio persistente para imágenes subidas. Predeterminado: `backend/uploads`. |
| `PORT` | Puerto de Waitress, predeterminado `5000`. Solo escucha en la interfaz local. |

Las variables se leen del entorno del proceso. El proyecto no carga archivos `.env` automáticamente. Usar las mismas rutas al arrancar el servidor, programar copias y restaurar. Proteger el acceso a esos directorios y al almacén de secretos del servicio.

## Servicio WSGI y HTTPS

Compilar el frontend y ejecutar un proceso Waitress con cuatro hilos:

```powershell
$env:PIZZA_PRONTO_ENV = 'production'
$env:PIZZA_PRONTO_DATA_DIR = 'D:\PizzaPronto\data'
$env:PIZZA_PRONTO_UPLOAD_DIR = 'D:\PizzaPronto\uploads'
# Definir SECRET_KEY y ADMIN_PASSWORD mediante el almacén privado del servicio.
.\.venv\Scripts\python.exe -m backend.serve
```

`backend/serve.py` sirve la API y `frontend/dist` con WSGI y sin depurador. El archivo `deploy/Caddyfile` contiene la configuración de proxy HTTPS: reemplazar `pizza.example.com` por el dominio real, configurar su DNS e instalar Caddy en el servidor. El servicio público utiliza HTTPS y reenvía a `127.0.0.1:5000`. No publicar directamente el puerto interno. El certificado y el dominio deben comprobarse en el equipo donde se ejecute el piloto.

Para una base ya utilizada con la contraseña inicial, detener el servidor y cambiarla antes de activar producción:

```powershell
# Definir PIZZA_PRONTO_ADMIN_PASSWORD de forma privada, con al menos 12 caracteres.
.\.venv\Scripts\python.exe -m backend.maintenance set-admin-password
```

El comando usa `PIZZA_PRONTO_ADMIN_EMAIL`, actualiza el hash e invalida las sesiones de ese administrador. No poner una contraseña literal en un archivo versionado. Producción rechaza la contraseña inicial conocida.

El operador del servidor debe configurar el reinicio del proceso WSGI al iniciar Windows, por ejemplo con su gestor de servicios. Usar un proceso por base SQLite y el directorio de trabajo del proyecto. La configuración externa del servicio, el DNS y el certificado requieren el equipo y dominio reales del piloto; no se dan por desplegados por la existencia de estos archivos.

## Persistencia y actualización del esquema

La base activa es `<PIZZA_PRONTO_DATA_DIR>/pizza_pronto.db`, no el archivo `pizza_pronto.db` de la raíz. Las imágenes activas se guardan en `PIZZA_PRONTO_UPLOAD_DIR`. Al primer arranque se crean las nuevas tablas y se agregan `activo` y `session_version` a usuarios existentes sin borrar pedidos. La marca `configuracion.catalogo_inicial_v1` evita repetir la carga inicial del catálogo en arranques posteriores.

Antes de actualizar una instalación usada, detener el servicio y conservar una copia del SQLite y de las imágenes. En la primera actualización de una base antigua sin la marca de inicialización se aplica una vez la normalización y siembra histórica. Después, los productos eliminados ya no se recrean al reiniciar. No borrar `instance`, los uploads ni la marca de configuración al publicar una versión nueva.

## Cuentas y permisos

Iniciar sesión como administrador y abrir **Panel admin → Personal**. Crear una cuenta individual para cada trabajador, con rol cocina o caja y contraseña de al menos 12 caracteres. Comunicar las credenciales por un medio privado. No compartir la cuenta administradora.

| Operación | Administración | Cocina | Caja |
| --- | --- | --- | --- |
| Consultar pedidos | Sí | Sí | Sí |
| Marcar pedido listo | Sí | Sí | No |
| Confirmar entrega y pago | Sí | No | Sí |
| Consultar inventario | Sí | Sí | No |
| Ajustar inventario y catálogo | Sí | No | No |
| Personal, auditoría, copias y piloto | Sí | No | No |

El flujo de estados existente se mantiene: recibido pasa automáticamente a preparación, cocina marca listo y caja confirma entrega y pago. Registrar pago confirma un cobro realizado fuera del sistema; no procesa un pago bancario. La API verifica los permisos aunque se envíen solicitudes fuera de la interfaz. Cambiar el rol, la contraseña o el acceso de un trabajador invalida todas sus sesiones anteriores. El registro público de clientes no permite escoger roles operativos.

## Auditoría

En **Panel admin → Auditoría** se filtra por entidad, identificador, usuario y fechas de Perú. Cada evento contiene actor, rol, hora, operación, identificador y valores anteriores y posteriores. Los descuentos automáticos de stock y los ajustes manuales aparecen como movimientos de inventario. Los cambios se guardan en la misma transacción que su auditoría; si se revierte una operación, también se revierte el evento. La preparación automática se atribuye al sistema.

No hay rutas para editar o eliminar eventos. La lista de campos auditados excluye hashes, contraseñas y tokens. Los administradores del archivo SQLite mantienen acceso técnico directo al almacenamiento; la inmutabilidad de la pantalla no sustituye la protección del servidor.

## Copias y objetivo de recuperación

En **Panel admin → Respaldos**: crear una copia, verificar su recuperación y descargar el ZIP. La copia usa la API de backup de SQLite, incorpora las imágenes subidas y un manifiesto con fecha UTC, conteos y SHA256 por archivo. Los recursos estáticos del catálogo se conservan en el código y en la versión compilada, que también debe mantenerse disponible para desplegar la misma versión.

Una copia se rechaza si falta una imagen referenciada. Los ZIP se limitan a 512 MB descomprimidos y 10000 entradas. La verificación comprueba hashes, integridad SQLite, claves foráneas, pedidos, catálogo e imágenes, restaurando en un directorio temporal separado. No sustituye la base en uso.

Desde consola:

```powershell
.\.venv\Scripts\python.exe -m backend.maintenance backup
.\.venv\Scripts\python.exe -m backend.maintenance verify 'instance\backups\NOMBRE_REAL_DE_LA_COPIA.zip'
```

RPO propuesto: 24 horas. El panel alerta si no hay una copia reciente. RTO propuesto: 7200 segundos. El informe de prueba guarda `rpo_horas`, `rto_segundos`, conteos e imágenes recuperadas en un archivo `.verification.json`. El RPO medido es la antigüedad de la instantánea en la verificación. El RTO de prueba mide extracción, validación y consulta local; la recuperación completa de una falla real incluye equipo, acceso y reinicio y debe medirse en el piloto.

Programar `deploy/backup.ps1` diariamente en el Programador de tareas de Windows, con el usuario de mantenimiento. Acción de ejemplo:

```text
Programa: powershell.exe
Argumentos: -NoProfile -File "C:\ruta\capstone_project\deploy\backup.ps1" -ProjectRoot "C:\ruta\capstone_project" -DataDir "D:\PizzaPronto\data" -UploadDir "D:\PizzaPronto\uploads"
Frecuencia: diaria, por ejemplo 23:00 hora de Perú
```

Configurar las rutas reales y revisar el resultado de la tarea cada día. El script devuelve error si la copia falla. La tarea no queda instalada automáticamente. Mantener al menos una copia fuera del equipo y comprobar su descarga. El responsable del negocio define la retención según espacio y necesidad; no se borran copias automáticamente.

## Restaurar el servicio

1. Detener el proceso Waitress o Flask. Confirmar que el servidor no está atendiendo solicitudes. Todos los arranques documentados mantienen un bloqueo de mantenimiento.
2. Seleccionar la copia y ejecutar `verify`. Revisar integridad, fecha, conteos y la medición RPO/RTO.
3. Confirmar que las variables de datos e imágenes apuntan a la instalación que se recuperará.
4. Ejecutar la recuperación explícita:

```powershell
.\.venv\Scripts\python.exe -m backend.maintenance restore 'instance\backups\NOMBRE_REAL_DE_LA_COPIA.zip' --confirm-restore
```

5. La herramienta valida el ZIP antes de reemplazar archivos, invalida sesiones y conserva los originales con sufijo `.pre-restore-...`. Si falla la instalación de SQLite o imágenes, intenta devolver ambos originales. No borrar los originales hasta terminar la comprobación operativa.
6. Reiniciar con `python -m backend.serve`. Comprobar `/api/health`, iniciar sesión de nuevo, abrir catálogo y pedidos, revisar una imagen y comparar conteos. Registrar responsable, inicio, fin e incidencias en el piloto.

No ejecutar una restauración con otro servidor que omita el bloqueo ni contra una base conectada por herramientas externas. Para volver al estado anterior, detener de nuevo el servicio, preservar el intento fallido y recuperar la copia previa con el mismo procedimiento. La verificación automatizada del proyecto utiliza directorios temporales y no restaura sobre los datos del usuario.

## Piloto y acta

Abrir **Panel admin → Piloto**. Crear una ejecución con nombre, responsable y tareas/criterios revisados antes de realizar pruebas. Se proponen seis tareas que cubren permisos, pedido, preparación/cobro, catálogo/stock, recuperación y uso sin ayuda. Los criterios se pueden editar antes de guardar el protocolo.

Registrar cada ejecución real con código anónimo de participante, resultado, evidencia y necesidad de ayuda. Un fallo requiere defecto y responsable de corrección. Registrar evidencia de la corrección antes de resolverlo. El mismo participante no duplica la misma tarea en una ejecución; para repetir pruebas crear otra ejecución o registrar la corrección del defecto.

Emitir el acta con representante del negocio, conclusión, decisión e impedimentos. **Aceptado** requiere todas las tareas ejecutadas y ningún defecto abierto. **Condicionado** y **Rechazado** exigen impedimentos. El cierre conserva una instantánea de resultados y evita nuevas ediciones. Registrar una decisión en el sistema no equivale a una firma digital ni a una aceptación que no haya acordado el representante.

## Indicadores del piloto

Abrir **Panel admin → Indicadores**. Registrar observaciones de las fases antes y después, con fecha, turno, modalidad y condiciones comparables. No incluir nombres, teléfonos, documentos de identidad ni datos de pedidos individuales en esta base.

| Indicador | Numerador | Denominador |
| --- | --- | --- |
| Pedidos con errores | Pedidos que tuvieron al menos un error | Pedidos observados |
| Tiempo medio en minutos | Suma de minutos de atención | Pedidos cronometrados |
| Completitud | Pedidos con todos los datos definidos | Pedidos observados |
| Exactitud de inventario | Insumos cuyo conteo físico coincide con el sistema | Insumos revisados |

Definir previamente los errores, los campos obligatorios, el inicio/fin del cronometraje y el método de conteo. Mantener las mismas definiciones en ambas fases y consignarlas en el protocolo/evidencia. Los ceros son válidos; un denominador cero muestra **Sin datos** y no una tasa de cero por ciento.

Los totales se suman antes de calcular porcentajes y tiempos medios. La comparación usa solo combinaciones de turno, modalidad y condiciones que aparecen en ambas fases. Se muestran muestras sin par, numeradores y denominadores. La diferencia es después menos antes: en porcentajes se expresa en puntos porcentuales. Es una comparación descriptiva, afectada por volumen, composición y otras condiciones; no demuestra causalidad.

Las exclusiones requieren motivo y conservan el registro original. Anotar las limitaciones de cada observación. Exportar la base CSV anónima, que incluye fechas, condiciones, exclusiones y limitaciones, y excluye el identificador del operador. Conservar junto con el acta las definiciones y limitaciones del estudio.

## Verificación y entrega

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
cd frontend
npm.cmd run build
```

Antes de poner en servicio, el responsable debe comprobar HTTPS con el dominio real, la tarea diaria de copias, una recuperación en el equipo de destino y el acceso individual del personal. Validar las cantidades de las recetas y ejecutar el piloto con personas reales, completando el acta e indicadores. La disponibilidad de funciones y las pruebas automatizadas no sustituyen la aceptación del negocio ni demuestran por sí mismas la meta de facilidad de uso.
