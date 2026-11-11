# Verificación técnica de HU01 a HU18

Fecha: 11 de noviembre de 2026, hora de Perú.

Se revisaron las tres hojas del Excel original. Sus estados se conservan: 6 Implementada, 6 En desarrollo y 6 Pendiente. Se reutilizaron los flujos existentes y se completaron las brechas funcionales. El Excel no se marca como aceptado por el negocio.

## Resultados ejecutados

- Suite completa: **48 pruebas aprobadas**, 0 fallos y 0 errores. Son las 34 anteriores más 14 de backend/tests/test_remaining_hu.py.
- Dos pruebas focalizadas se repitieron después de normalizar las fechas de estados a UTC y aprobaron.
- Compilación React correcta. Vite conserva el aviso de archivo JavaScript principal mayor de 500 kB.
- scripts/check_ui.mjs: **9 comprobaciones aprobadas** en una instancia WSGI local aislada con CSRF activo. Editor de recetas en escritorio, reporte vacío por fechas, carta móvil sin desbordamiento, foco inicial del carrito, Tab, Shift+Tab, Escape con devolución del foco, compra móvil completa y ausencia de errores JavaScript.
- Capturas internas revisadas de carta móvil, checkout y confirmación. Anchos probados: 375 y 1280 píxeles.
- compileall de backend y git diff --check: correctos.

Las pruebas usaron Python 3.12, Node.js 24 y Chrome con perfil temporal. Las bases, imágenes, cuentas, pedidos y participantes son temporales; no se insertan en la base real del usuario.

## Cobertura por historia

| HU | Evidencia técnica |
| --- | --- |
| HU01 | Registro, ingreso y cierre existentes; protección de sesiones completada en HU12. |
| HU02 | Tres modalidades de invitado existentes; compra móvil probada con retiro local. |
| HU03 | Catálogo, búsqueda e imágenes alternativas existentes; ocultación comprobada. |
| HU04 | Cotización y validación existentes; configuración e instantánea de consumo conservadas. |
| HU05 | Precio del servidor y persistencia; consulta propia por código para cuenta o sesión de invitado. |
| HU06 | Estados, tiempos configurables, marcas UTC, inicio con stock, anulación y solicitudes idempotentes. |
| HU07 | Mantenimiento existente; corrección de rutas de pizzas del menú, precios por tamaño, ocultación, borrado y rechazo de NaN. |
| HU08 | Conversión de unidades compatibles; rechazo de valores inválidos sin modificar el saldo. |
| HU09 | Todas las recetas y tamaños, plan conservado, consumo único, insuficiencia sin cambios parciales, reversión y competencia por el último stock. |
| HU10 | Cuentas individuales, roles, sesiones revocadas y migración sin perder pedidos. |
| HU11 | Copia y recuperación SQLite/imágenes, integridad, RPO/RTO de prueba y rollback ante fallo de disco. |
| HU12 | CSRF, cookies protegidas, secretos individuales, vencimiento y límites persistentes de intentos. |
| HU13 | Fechas y estado, pagos únicos, conciliación, periodo vacío y CSV. |
| HU14 | Actor, cambios y saldos antes/después; rollback y exclusión de credenciales. Incluye recetas, movimientos y pagos. |
| HU15 | Protocolo, evidencia, defectos, responsables, corrección y acta conservada. |
| HU16 | Compra móvil, foco, teclado y fórmula de tareas sin ayuda. La prueba temporal 4 de 5 produce 80%; sin datos no se inventa una tasa. |
| HU17 | WSGI, frontend compilado, persistencia, depurador desactivado y manual. |
| HU18 | Mediciones anónimas, denominadores, comparación por condiciones, exclusiones y exportación. |

## Demostración y aceptación del negocio

El usuario autorizó cantidades ficticias aproximadas para las recetas. Se guardan como estimacion_demo, son editables y deben reemplazarse con recetas reales para controlar inventario operativo. No se presentan como datos entregados por la pizzería.

Los pedidos anteriores se identifican como legacy: no se repite un descuento antiguo ni se inventan sus movimientos de devolución. Si se anulan, requieren conciliación manual.

La implementación cubre las funciones de HU01 a HU18. Las pruebas automatizadas no equivalen a aceptación con personal ni demuestran la meta real del 80%. Se deben realizar las pruebas con participantes, decisiones del negocio, mediciones de campo y configuración del dominio/certificado y las copias diarias en el equipo de destino.

La conversión para comprobar visualmente el Word no está disponible en este entorno. El informe se valida estructuralmente y sus referencias de línea se generan desde el código actual.
