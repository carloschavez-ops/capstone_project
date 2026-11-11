"""Genera el Word de trazabilidad a partir del Excel y de líneas reales del código.

Herramienta de documentación: ejecutar con python-docx y openpyxl disponibles.
No forma parte de las dependencias de ejecución de la aplicación.
"""

import argparse
from pathlib import Path

import openpyxl
from report_remaining_data import FEATURES as REMAINING_FEATURES
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]


def line_for(filename, anchor):
    lines = (ROOT / filename).read_text(encoding="utf-8-sig").splitlines()
    for number, line in enumerate(lines, 1):
        if anchor in line:
            return number
    raise ValueError(f"No se encontró {anchor!r} en {filename}")


def location(doc, filename, anchor, description):
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(f"{filename}:{line_for(filename, anchor)}")
    run.bold = True
    run.font.size = Pt(10)
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.space_after = Pt(2)
    doc.add_paragraph(description)


def table(doc, headers, rows, widths):
    result = doc.add_table(rows=1, cols=len(headers))
    result.alignment = WD_TABLE_ALIGNMENT.CENTER
    result.autofit = False
    for column, width in zip(result.columns, widths):
        column.width = Inches(width)
    for cell, value, width in zip(result.rows[0].cells, headers, widths):
        cell.width = Inches(width)
        cell.text = value
    header = OxmlElement("w:tblHeader")
    result.rows[0]._tr.get_or_add_trPr().append(header)
    for row_values in rows:
        cells = result.add_row().cells
        for cell, value, width in zip(cells, row_values, widths):
            cell.width = Inches(width)
            cell.text = str(value)
    for index, row in enumerate(result.rows):
        no_split = OxmlElement("w:cantSplit")
        row._tr.get_or_add_trPr().append(no_split)
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            properties = cell._tc.get_or_add_tcPr()
            borders = OxmlElement("w:tcBorders")
            for edge in ("top", "left", "bottom", "right"):
                border = OxmlElement(f"w:{edge}")
                border.set(qn("w:val"), "single")
                border.set(qn("w:sz"), "4")
                border.set(qn("w:color"), "D9D9D9")
                borders.append(border)
            properties.append(borders)
            margins = OxmlElement("w:tcMar")
            for edge in ("top", "left", "bottom", "right"):
                item = OxmlElement(f"w:{edge}")
                item.set(qn("w:w"), "100")
                item.set(qn("w:type"), "dxa")
                margins.append(item)
            properties.append(margins)
            shade = OxmlElement("w:shd")
            shade.set(qn("w:fill"), "E7EDF3" if index == 0 else ("F6F7F8" if index % 2 == 0 else "FFFFFF"))
            properties.append(shade)
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                paragraph.paragraph_format.space_before = Pt(2)
                for run in paragraph.runs:
                    run.font.size = Pt(10)
                    run.bold = index == 0
                    run.font.color.rgb = RGBColor(0, 0, 0)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return result


FEATURES = [
    {
        "id": "HU10", "title": "Permisos operativos",
        "summary": "Se añadieron cuentas individuales de cocina y caja, una matriz de permisos y controles de acceso en la API. Cambiar rol, acceso o contraseña invalida las sesiones previas del trabajador.",
        "locations": [
            ("backend/permissions.py", "ROLE_PERMISSIONS =", "ROLE_PERMISSIONS define la matriz. Cocina consulta pedidos e inventario y marca listo. Caja consulta pedidos y registra entrega y pago. Administración conserva la gestión completa."),
            ("backend/permissions.py", "def install_permissions", "install_permissions protege todas las rutas administrativas antes de ejecutar su lógica. current_user comprueba que la cuenta siga activa y que su versión de sesión coincida."),
            ("backend/operations.py", "def staff_create", "staff_create y staff_update crean cuentas operativas, validan rol/correo/contraseña y permiten desactivar o cambiar credenciales sin conceder el rol administrador."),
            ("backend/models.py", "class UsuarioDB", "UsuarioDB conserva rol, activo y session_version. create_app migra los dos nuevos campos en bases existentes; login guarda la versión de sesión."),
            ("frontend/src/OperationsPanel.jsx", "function Staff()", "Staff ofrece alta y mantenimiento de cuentas y muestra la matriz. AdminPanel adapta pestañas, acciones de pedidos y lectura de inventario al rol conectado."),
        ],
        "test": ("test_hu10_role_matrix_and_individual_accounts", "Se probaron las acciones permitidas y prohibidas de cocina/caja, la protección del stock, la desactivación, el cambio de contraseña y el rechazo de escalada a administrador."),
        "use": "Entrar como administrador y abrir Panel admin → Personal. Cada trabajador entra con su cuenta y abre Panel de trabajo.",
        "limit": "El negocio debe asignar las cuentas reales y comunicar sus credenciales de forma privada. No se crearon trabajadores ficticios en la base del usuario.",
    },
    {
        "id": "HU11", "title": "Respaldo y recuperación",
        "summary": "Se añadieron copias ZIP de SQLite e imágenes, descarga, restauración aislada de prueba y recuperación offline con originales conservados. Cada copia contiene fecha, conteos y huellas SHA256.",
        "locations": [
            ("backend/backups.py", "def create_backup", "create_backup usa la API transaccional de SQLite y copia los uploads. snapshot_details verifica integridad, claves foráneas y referencias de imágenes antes de emitir una copia."),
            ("backend/backups.py", "def unpack_verified", "unpack_verified rechaza rutas inseguras, archivos duplicados, ZIP excesivos y huellas incorrectas. verify_backup restaura en una carpeta temporal y mide RPO y RTO locales."),
            ("backend/backups.py", "def restore_backup", "restore_backup exige exclusión con el servidor, valida antes de reemplazar, invalida sesiones y conserva archivos .pre-restore. Ante un fallo de instalación intenta devolver los originales."),
            ("backend/maintenance.py", "def main", "La consola expone backup, verify y restore. restore requiere --confirm-restore. El comando set-admin-password permite cambiar la credencial inicial con el servicio detenido."),
            ("backend/operations.py", "def backups_create", "Las rutas /api/admin/backups crean, listan, descargan y verifican copias. Solo administración accede. La verificación no reemplaza los datos en uso."),
            ("frontend/src/OperationsPanel.jsx", "function Backups()", "Backups muestra fecha, antigüedad, alertas, resultados de recuperación y descargas. deploy/backup.ps1 permite programar la copia diaria en el equipo de destino."),
        ],
        "test": ("test_hu11_backup_and_trial_restore_include_orders_catalog_and_images", "Se recuperaron pedidos, catálogo e imágenes de prueba; se rechazaron copias dañadas y servicio activo. Se probó la restauración real en una base temporal y el rollback ante un fallo de disco simulado."),
        "use": "Panel admin → Respaldos. Para recuperar el servicio, detenerlo y seguir docs/MANUAL_OPERACION.md antes de ejecutar backend.maintenance restore.",
        "limit": "Las metas son RPO de 24 horas y RTO de 2 horas. La prueba local no mide todo un incidente productivo. La tarea diaria y la copia externa deben configurarse en el equipo real.",
    },
    {
        "id": "HU14", "title": "Trazabilidad de cambios",
        "summary": "Se añadió un historial con usuario, rol, fecha, operación y entidad afectada. Para el inventario conserva cantidades anteriores y posteriores, incluidas las variaciones del consumo automático existente.",
        "locations": [
            ("backend/operations_models.py", "class AuditoriaDB", "AuditoriaDB guarda actor, usuario_id, fecha UTC, operación, entidad, identificador y cambios estructurados. Los registros se consultan con paginación."),
            ("backend/audit.py", "AUDITED_FIELDS =", "AUDITED_FIELDS limita qué valores se registran. Excluye contraseñas, hashes y tokens. Incluye catálogo, inventario, estados, cuentas y registros operativos del piloto."),
            ("backend/audit.py", "def _record", "Los eventos ORM de inserción, actualización y borrado escriben el historial usando la misma conexión y transacción de la operación. Un rollback revierte tanto el cambio como su evento."),
            ("backend/permissions.py", "def install_permissions", "El hook de petición identifica al actor. start_orders_after_delay en backend/app.py atribuye la preparación automática al sistema y conserva la atribución humana de las demás acciones."),
            ("backend/operations.py", "def audit_list", "audit_list filtra por entidad, identificador, usuario y fechas de Perú. Solo administración consulta el historial; no hay rutas para modificarlo o borrarlo."),
            ("frontend/src/OperationsPanel.jsx", "function Audit()", "Audit muestra los filtros, el actor, la entidad y el detalle anterior/posterior de cada cambio en la pestaña Auditoría."),
        ],
        "test": ("test_hu14_inventory_actor_before_after_and_atomic_rollback", "Se verificaron los valores 100 → 45 de un ajuste, el actor, la ausencia de evento ante rechazo o rollback, la atribución de cocina y la exclusión de secretos."),
        "use": "Panel admin → Auditoría. Filtrar por inventario y por el identificador del insumo para explicar sus movimientos.",
        "limit": "El historial empieza con esta versión y no reconstruye autores de cambios anteriores. Proteger el acceso al archivo SQLite sigue siendo responsabilidad del operador.",
    },
    {
        "id": "HU15", "title": "Aceptación del piloto",
        "summary": "Se añadió un flujo para definir tareas y criterios antes del piloto, registrar resultados y defectos, asignar responsables de corrección y conservar un acta con la decisión del negocio.",
        "locations": [
            ("backend/operations_models.py", "class PilotoDB", "PilotoDB conserva el protocolo, responsable y estado. ResultadoPilotoDB guarda código anónimo de participante, resultado, evidencia, defecto y corrección documentada."),
            ("backend/operations.py", "PILOT_CASES =", "PILOT_CASES propone seis tareas críticas. pilot_create copia los criterios revisados al protocolo; la interfaz permite editarlos antes de guardar la ejecución."),
            ("backend/operations.py", "def pilot_result_create", "pilot_result_create exige evidencia y, para fallos, defecto y responsable. Una restricción evita duplicar la misma tarea y participante en una ejecución."),
            ("backend/operations.py", "def pilot_resolve_defect", "pilot_resolve_defect conserva la evidencia de corrección. pilot_decision impide aceptar con tareas sin ejecutar o defectos abiertos, y exige impedimentos para decisiones condicionadas o rechazadas."),
            ("backend/operations.py", "def pilot_decision", "El acta guarda fecha, representante, conclusión, impedimentos y una instantánea de resultados. Después del cierre no se sobrescribe la decisión ni se agregan resultados."),
            ("frontend/src/OperationsPanel.jsx", "function Pilot()", "Pilot y PilotRun ofrecen creación del protocolo, registro de ejecución, resolución de defectos y consulta del acta en la pestaña Piloto."),
        ],
        "test": ("test_hu15_protocol_results_defects_and_frozen_decision", "Se rechazó la aceptación sin ejecutar tareas y con defectos abiertos; después de documentar la corrección se conservó el acta y se bloquearon nuevas escrituras."),
        "use": "Panel admin → Piloto. Revisar criterios, ejecutar con el personal y registrar evidencia real antes de emitir el acta.",
        "limit": "No se ejecutó un piloto con trabajadores ni se emitió una aceptación del negocio. El registro de una decisión no sustituye una firma digital.",
    },
    {
        "id": "HU17", "title": "Despliegue y transferencia",
        "summary": "Se añadió un arranque Waitress sin depurador, servicio del frontend compilado, rutas persistentes configurables y un manual de arranque, recuperación y mantenimiento.",
        "locations": [
            ("backend/serve.py", "def main", "main ejecuta Waitress con cuatro hilos, en un proceso y en la interfaz local. Mantiene el bloqueo compartido con el restaurador. requirements.txt incorpora Waitress."),
            ("backend/app.py", "def create_app", "create_app lee las rutas persistentes y las variables del servicio. Producción exige secreto privado, activa cookies Secure y rechaza la contraseña inicial conocida."),
            ("backend/app.py", 'def frontend(asset=', "frontend sirve index.html y los assets de frontend/dist. Las rutas API desconocidas no reciben la página de la aplicación."),
            ("backend/models.py", "class ConfiguracionDB", "ConfiguracionDB conserva la marca de carga inicial. El arranque deja de recrear productos eliminados después de inicializar el catálogo."),
            ("deploy/Caddyfile", "pizza.example.com", "Configuración de referencia para HTTPS y proxy al puerto local. El dominio real y su DNS se configuran en el servidor del piloto."),
            ("docs/MANUAL_OPERACION.md", "# Operación", "Manual con configuración, comandos, permisos, copias programadas, recuperación, pruebas y rol responsable del mantenimiento. README.md enlaza el manual y el nuevo arranque."),
        ],
        "test": ("test_hu17_wsgi_frontend_and_persistent_restart", "Se verificaron el frontend, la persistencia de cuentas, la eliminación conservada al reiniciar, los requisitos productivos y las cookies protegidas. Waitress respondió al health check en una base separada."),
        "use": "Compilar frontend y ejecutar python -m backend.serve. Para exposición pública, seguir el manual y configurar HTTPS con el dominio de destino.",
        "limit": "No se ha publicado un dominio, instalado un servicio de Windows ni entregado la operación a una persona real. El negocio debe designar al responsable y registrar la transferencia.",
    },
    {
        "id": "HU18", "title": "Evaluación de indicadores",
        "summary": "Se añadió una base anónima antes/después con fecha, turno, modalidad y condiciones, más exclusiones, limitaciones y exportación CSV. Los indicadores muestran sus denominadores.",
        "locations": [
            ("backend/operations_models.py", "class MedicionDB", "MedicionDB guarda fase, fecha, condiciones y los conteos de pedidos, errores, completitud, tiempos e inventario. No almacena nombres, teléfonos ni códigos de pedidos individuales."),
            ("backend/operations.py", "def measurement_values", "measurement_values valida enteros, finitud y relaciones entre numeradores y denominadores. Una exclusión requiere motivo y no borra la observación."),
            ("backend/operations.py", "def summarize_measurements", "summarize_measurements suma conteos antes de dividir. Calcula pedidos con errores, tiempo medio, completitud y exactitud de inventario. El denominador cero devuelve valor no disponible."),
            ("backend/operations.py", "def measurement_report", "measurement_report compara solo turnos, modalidades y condiciones que existen en ambas fases. Conserva muestras sin par y calcula diferencias después menos antes."),
            ("backend/operations.py", "def measurement_export", "measurement_export incluye observaciones, exclusiones y limitaciones en CSV sin ID del operador. csv_safe evita que texto exportado se interprete como una fórmula."),
            ("frontend/src/OperationsPanel.jsx", "function Indicators()", "Indicators permite registrar observaciones, filtrar fechas, turnos y modalidades, consultar numeradores/denominadores, excluir con motivo y descargar la base anónima."),
        ],
        "test": ("test_hu18_weighted_indicators_denominators_and_comparison", "Se verificaron agregación ponderada, diferencias, muestras sin par, exclusiones, filtros, denominador cero, entradas inconsistentes y exportación sin identificador de operador."),
        "use": "Panel admin → Indicadores. Definir el método de medición previamente y registrar observaciones reales con las mismas condiciones en ambas fases.",
        "limit": "No se cargaron mediciones ficticias ni se atribuyó una mejora al sistema. La comparación es descriptiva y depende de la comparabilidad de las muestras.",
    },
]


def build(source, output):
    features = sorted([*FEATURES, *REMAINING_FEATURES], key=lambda item: item["id"])
    workbook = openpyxl.load_workbook(source, data_only=False)
    sheet = workbook["Historias de Usuario"]
    stories = [{"id": sheet.cell(row, 2).value, "alias": sheet.cell(row, 4).value,
                "estado": sheet.cell(row, 5).value, "fila": row} for row in range(5, 23)]
    pending = [story for story in stories if story["estado"] in {"Pendiente", "En desarrollo"}]
    if {story["id"] for story in pending} != {feature["id"] for feature in features}:
        raise ValueError("Las historias pendientes del Excel no coinciden con el alcance del informe.")
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(.7)
    section.bottom_margin = Inches(.65)
    section.left_margin = Inches(.8)
    section.right_margin = Inches(.8)
    for style_name in ("Normal", "Title", "Subtitle", "Heading 1", "Heading 2", "Heading 3"):
        style = doc.styles[style_name]
        style.font.name = "Calibri"
        style.font.color.rgb = RGBColor(0, 0, 0)
    normal = doc.styles["Normal"]
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.05
    doc.styles["Title"].font.size = Pt(24)
    doc.styles["Title"].paragraph_format.space_after = Pt(12)
    doc.styles["Heading 1"].font.size = Pt(18)
    doc.styles["Heading 1"].paragraph_format.space_after = Pt(10)
    doc.styles["Heading 2"].font.size = Pt(12)
    doc.styles["Heading 2"].paragraph_format.space_before = Pt(9)
    doc.styles["Heading 2"].paragraph_format.space_after = Pt(5)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run("Pizza Pronto   ").font.size = Pt(9)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    doc.core_properties.title = "Implementación de historias de Pizza Pronto"
    doc.core_properties.subject = "Cobertura técnica y ubicación del código de HU01 a HU18"
    doc.core_properties.author = "Proyecto Pizza Pronto"

    doc.add_paragraph("Implementación de historias de Pizza Pronto", "Title")
    doc.add_paragraph("Ubicación del código y verificación técnica", "Subtitle")
    doc.add_paragraph("11 de noviembre de 2026")
    doc.add_paragraph("La revisión cubre las 18 historias del Excel. Se conservaron las funciones existentes y se completaron las brechas de las 12 historias originalmente pendientes o en desarrollo. Este informe identifica archivos, funciones, líneas y pruebas. La implementación técnica no sustituye la aceptación del negocio.")
    doc.add_heading("Revisión del Excel", 2)
    doc.add_paragraph(f"Fuente: {Path(source).name}. Se revisaron las hojas Historias de Usuario, Instructivo y Seguimiento T2. La primera contiene 18 historias: 6 Implementada, 6 En desarrollo y 6 Pendiente. El archivo original conserva sus estados y sus casillas de verificación.")
    table(doc, ["Historia", "Función pendiente", "Ubicación en el Excel"],
          [(story["id"], story["alias"], f"Historias de Usuario E{story['fila']} e I{story['fila']}") for story in pending], [.65, 3.4, 2.85])
    doc.add_heading("Cómo leer las referencias", 2)
    doc.add_paragraph("Cada referencia usa archivo:línea, seguida de la función o clase y su propósito. Las líneas corresponden a esta versión del proyecto; los nombres de las funciones ayudan a localizar el mismo código si futuras ediciones desplazan la numeración.")
    doc.add_paragraph("La hoja Seguimiento T2 conserva su verificación del negocio. Las recetas utilizan cantidades ficticias aproximadas autorizadas por el usuario para demostración. No se cargan participantes, resultados de campo ni decisiones de aceptación ficticias.")

    for feature in features:
        doc.add_page_break()
        doc.add_heading(f"{feature['id']} {feature['title']}", 1)
        doc.add_paragraph(feature["summary"])
        doc.add_heading("Ubicación del código", 2)
        for filename, anchor, description in feature["locations"]:
            location(doc, filename, anchor, description)
        doc.add_heading("Prueba técnica", 2)
        test_name, test_description = feature["test"]
        location(doc, feature.get("test_file", "backend/tests/test_operations.py"), f"def {test_name}", test_description)
        doc.add_heading("Uso y validación real", 2)
        doc.add_paragraph(feature["use"])
        doc.add_paragraph(feature["limit"])

    doc.add_page_break()
    doc.add_heading("Cambios compartidos y verificación", 1)
    doc.add_heading("Funciones existentes conservadas", 2)
    original = [("HU01", "Registro ingreso y cierre", "def register"),
                ("HU02", "Modalidades y datos de invitado", "def enter_as_guest"),
                ("HU03", "Carta y productos visibles", "def catalog"),
                ("HU04", "Personalización y cotización", "def quote"),
                ("HU05", "Pedidos y consulta propia", "def get_customer_order"),
                ("HU07", "Catálogo e imágenes", "def update_menu_item")]
    table(doc, ["HU", "Función", "Código"], [(code, name, f"backend/app.py:{line_for('backend/app.py', anchor)}") for code, name, anchor in original], [.6, 3.2, 3.1])
    doc.add_paragraph("Se reutilizaron estos flujos. Se corrigió la consulta privada por código de HU05 y las rutas de edición, ocultación y borrado de pizzas del menú de HU07, que estaban enviándose al catálogo antiguo.")
    location(doc, "frontend/src/AdminPanel.jsx", "export default function AdminPanel", "AdminPanel incorpora las cinco pestañas nuevas y adapta la vista para cocina y caja. App.jsx ofrece Panel de trabajo a los roles operativos. operations.css define formularios, tablas con desplazamiento y foco visible.")
    location(doc, "frontend/src/api.js", "export async function apiFetch", "apiFetch incorpora el token CSRF a las escrituras de App, AdminPanel, AdminDashboard y PizzaCreateForm. backend/security.py valida el token y añade cabeceras de seguridad y ausencia de caché en la API.")
    location(doc, "docs/VERIFICACION_BACKLOG.md", "# Verificación", "Registro de la verificación técnica y de sus límites. El manual de operación contiene los pasos de instalación, cuentas, HTTPS, programación de copias, recuperación y mediciones del piloto.")
    doc.add_heading("Resultados ejecutados", 2)
    table(doc, ["Comprobación", "Resultado"], [
        ("Pruebas de API y operaciones", "48 aprobadas, 0 fallos y 0 errores. Incluyen las 34 pruebas anteriores y 14 adicionales."),
        ("Compilación React", "npm run build finalizó. Vite avisó del tamaño del archivo JavaScript principal."),
        ("Navegador y servidor WSGI", "9 comprobaciones de escritorio, móvil, teclado y compra con CSRF en una instancia aislada."),
        ("Código Python y diff", "compileall correcto y git diff --check sin problemas de espacios."),
    ], [2.2, 4.7])
    doc.add_heading("Activación de los cambios", 2)
    doc.add_paragraph("Actualizar las dependencias con .venv\\Scripts\\python.exe -m pip install -r requirements.txt y reiniciar el backend. En desarrollo iniciar React con npm run dev dentro de frontend. Para WSGI compilar con npm run build y ejecutar .venv\\Scripts\\python.exe -m backend.serve desde la raíz.")
    doc.add_heading("Validaciones aún necesarias", 2)
    doc.add_paragraph("La aplicación fue probada en navegador con anchos de escritorio y móvil, incluyendo una compra completa y manejo del foco. Quedan por ejecutar las pruebas con personal, la aceptación del negocio, las mediciones de campo y la configuración productiva real de HTTPS y copias diarias.")
    doc.add_paragraph("HU01 a HU18 disponen de funciones en el proyecto. La base de pruebas y sus resultados automatizados no se presentan como un piloto realizado con el negocio. Las cantidades de demostración deben reemplazarse con recetas reales antes de usarse para controlar inventario operativo.")
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "Informe_Implementacion_Backlog_Pizza_Pronto.docx")
    args = parser.parse_args()
    build(args.excel, args.output)
