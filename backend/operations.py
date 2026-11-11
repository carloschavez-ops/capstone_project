"""Pantallas y API de las seis historias pendientes del backlog T2."""

import csv
import io
import json
import math
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from modelos import db
from backend.audit import write_audit
from backend.models import UsuarioDB
from backend.operations_models import AuditoriaDB, MedicionDB, PilotoDB, ResultadoPilotoDB, iso, utcnow
from backend.permissions import ROLE_PERMISSIONS, current_user, permission_error
from backend.backups import backup_path, create_backup, list_backups, verify_backup


operations = Blueprint("operations", __name__, url_prefix="/api/admin")

PILOT_CASES = [
    {"id": "P01", "nombre": "Acceso individual y permisos", "criterio": "Cocina y caja acceden con cuentas distintas y la API rechaza una operación ajena al rol."},
    {"id": "P02", "nombre": "Pedido por modalidad", "criterio": "Registrar un pedido con datos válidos y comprobar precio, código y modalidad conservados."},
    {"id": "P03", "nombre": "Preparación y cobro", "criterio": "Cocina marca listo y caja confirma entrega y pago sin saltar estados."},
    {"id": "P04", "nombre": "Catálogo e inventario", "criterio": "Un cambio autorizado se conserva después de recargar y aparece en auditoría con actor y variación."},
    {"id": "P05", "nombre": "Recuperación", "criterio": "Verificar una copia y documentar una restauración de prueba con SQLite e imágenes, RPO y RTO medidos."},
    {"id": "P06", "nombre": "Pedido sin ayuda", "criterio": "Un participante completa la carta, formulario y carrito con teclado o móvil y se registra si necesitó ayuda."},
]


def requires(permission):
    def decorate(function):
        @wraps(function)
        def guarded(*args, **kwargs):
            error = permission_error(permission)
            return error if error else function(*args, **kwargs)
        return guarded
    return decorate


def payload():
    result = request.get_json(silent=True)
    if not isinstance(result, dict):
        raise ValueError("Envía un objeto JSON válido.")
    return result


def required_text(data, field, maximum=160):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValueError(f"Completa {field} con un texto de hasta {maximum} caracteres.")
    return value.strip()


def optional_text(data, field, maximum=1000):
    value = data.get(field, "")
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"Revisa {field} (máximo {maximum} caracteres).")
    return value.strip()


def boolean(data, field, default=False):
    value = data.get(field, default)
    if not isinstance(value, bool):
        raise ValueError(f"{field} debe ser verdadero o falso.")
    return value


def positive_id(value):
    try:
        identifier = int(value)
    except (TypeError, ValueError):
        raise ValueError("Identificador no válido.")
    if identifier < 1:
        raise ValueError("Identificador no válido.")
    return identifier


@operations.errorhandler(ValueError)
def validation_error(error):
    db.session.rollback()
    return jsonify({"error": str(error)}), 400


@operations.errorhandler(IntegrityError)
def conflict_error(error):
    db.session.rollback()
    return jsonify({"error": "Ya existe un registro con esos datos. Recarga e intenta de nuevo."}), 409


@operations.errorhandler(OSError)
def storage_error(error):
    db.session.rollback()
    current_app.logger.error("No se pudo completar una operación de almacenamiento", exc_info=error)
    return jsonify({"error": "No se pudo acceder al almacenamiento. Revisa espacio y permisos con el responsable técnico."}), 503


@operations.get("/permissions")
@requires("personal.gestionar")
def permission_matrix():
    return jsonify({"roles": ROLE_PERMISSIONS})


@operations.get("/staff")
@requires("personal.gestionar")
def staff_list():
    return jsonify({"usuarios": [user.to_dict() for user in UsuarioDB.query.filter(UsuarioDB.rol.in_(["admin", "cocina", "caja"])).order_by(UsuarioDB.id).all()], "roles": ROLE_PERMISSIONS})


@operations.post("/staff")
@requires("personal.gestionar")
def staff_create():
    data = payload()
    name = required_text(data, "nombre", 120)
    email = required_text(data, "email", 254).lower()
    password = required_text(data, "password", 256)
    role = data.get("rol")
    if role not in {"cocina", "caja"}:
        raise ValueError("Elige cocina o caja para la cuenta individual.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Escribe un correo válido.")
    if len(password) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres.")
    user = UsuarioDB(nombre=name, email=email, password_hash=generate_password_hash(password), rol=role)
    db.session.add(user)
    db.session.commit()
    return jsonify({"usuario": user.to_dict()}), 201


@operations.patch("/staff/<int:user_id>")
@requires("personal.gestionar")
def staff_update(user_id):
    user = db.session.get(UsuarioDB, user_id)
    if not user or user.rol not in {"cocina", "caja"}:
        return jsonify({"error": "Solo se modifican cuentas operativas de cocina y caja."}), 404
    data = payload()
    role = data.get("rol", user.rol)
    if role not in {"cocina", "caja"}:
        raise ValueError("El rol operativo debe ser cocina o caja.")
    user.nombre = required_text(data, "nombre", 120) if "nombre" in data else user.nombre
    user.rol = role
    user.activo = boolean(data, "activo", user.activo)
    if "password" in data:
        password = required_text(data, "password", 256)
        if len(password) < 12:
            raise ValueError("La contraseña debe tener al menos 12 caracteres.")
        user.password_hash = generate_password_hash(password)
    user.session_version += 1
    db.session.commit()
    return jsonify({"usuario": user.to_dict()})


@operations.get("/audit")
@requires("auditoria.ver")
def audit_list():
    query = AuditoriaDB.query
    if request.args.get("entidad"):
        query = query.filter_by(entidad=request.args["entidad"])
    if request.args.get("entidad_id"):
        query = query.filter_by(entidad_id=request.args["entidad_id"])
    if request.args.get("usuario_id"):
        query = query.filter_by(usuario_id=positive_id(request.args["usuario_id"]))
    for name, end in (("desde", False), ("hasta", True)):
        if request.args.get(name):
            value = date.fromisoformat(request.args[name])
            # Las fechas introducidas se interpretan en hora de Perú.
            instant = datetime.combine(value, datetime.min.time(), timezone(timedelta(hours=-5)))
            instant = instant.astimezone(timezone.utc).replace(tzinfo=None)
            query = query.filter(AuditoriaDB.fecha < instant + timedelta(days=1)) if end else query.filter(AuditoriaDB.fecha >= instant)
    page = positive_id(request.args.get("page", 1))
    total = query.count()
    rows = query.order_by(AuditoriaDB.id.desc()).offset((page - 1) * 50).limit(50).all()
    return jsonify({"registros": [row.to_dict() for row in rows], "total": total, "page": page, "page_size": 50})


@operations.get("/pilot")
@requires("piloto.gestionar")
def pilot_list():
    return jsonify({"pilotos": [row.to_dict() for row in PilotoDB.query.order_by(PilotoDB.id.desc()).all()], "casos_propuestos": PILOT_CASES})


@operations.post("/pilot")
@requires("piloto.gestionar")
def pilot_create():
    data = payload()
    cases = data.get("casos", PILOT_CASES)
    if not isinstance(cases, list) or not 1 <= len(cases) <= 30:
        raise ValueError("Define de 1 a 30 tareas antes de ejecutar el piloto.")
    normalized = []
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Revisa la definición de las tareas.")
        identifier = required_text(case, "id", 40)
        if identifier in seen:
            raise ValueError("Los identificadores de tareas no se repiten.")
        seen.add(identifier)
        normalized.append({"id": identifier, "nombre": required_text(case, "nombre", 160), "criterio": required_text(case, "criterio", 1000)})
    pilot = PilotoDB(nombre=required_text(data, "nombre"), responsable=required_text(data, "responsable", 120), casos_json=json.dumps(normalized, ensure_ascii=False))
    db.session.add(pilot)
    db.session.commit()
    return jsonify({"piloto": pilot.to_dict()}), 201


def pilot_detail(pilot):
    result = pilot.to_dict()
    result["resultados"] = [row.to_dict() for row in ResultadoPilotoDB.query.filter_by(piloto_id=pilot.id).order_by(ResultadoPilotoDB.id).all()]
    executed = {row["caso_id"] for row in result["resultados"]}
    result["tareas_sin_ejecutar"] = [case["id"] for case in result["casos"] if case["id"] not in executed]
    result["defectos_abiertos"] = sum(row["resultado"] == "fallido" and not row["resuelto"] for row in result["resultados"])
    usability = [row for row in result["resultados"] if row["caso_id"] == "P06"]
    independent = sum(row["resultado"] == "aprobado" and row["sin_ayuda"] for row in usability)
    result["usabilidad"] = {"participantes": len(usability), "completaron_sin_ayuda": independent,
                            "porcentaje": round(independent / len(usability) * 100, 2) if usability else None,
                            "meta_porcentaje": 80, "cumple_meta": independent / len(usability) >= .8 if usability else None}
    return result


@operations.get("/pilot/<int:pilot_id>")
@requires("piloto.gestionar")
def pilot_get(pilot_id):
    pilot = db.session.get(PilotoDB, pilot_id)
    return (jsonify({"piloto": pilot_detail(pilot)}) if pilot else (jsonify({"error": "Piloto no encontrado."}), 404))


@operations.post("/pilot/<int:pilot_id>/results")
@requires("piloto.gestionar")
def pilot_result_create(pilot_id):
    pilot = db.session.get(PilotoDB, pilot_id)
    if not pilot:
        return jsonify({"error": "Piloto no encontrado."}), 404
    if pilot.estado != "abierto":
        return jsonify({"error": "El acta cerrada conserva sus resultados. Crea una nueva ejecución."}), 409
    data = payload()
    case_id = required_text(data, "caso_id", 40)
    if case_id not in {case["id"] for case in json.loads(pilot.casos_json)}:
        raise ValueError("La tarea no pertenece al protocolo de este piloto.")
    result = data.get("resultado")
    if result not in {"aprobado", "fallido"}:
        raise ValueError("Registra aprobado o fallido después de ejecutar la tarea.")
    defect = optional_text(data, "defecto")
    owner = optional_text(data, "responsable_correccion", 120)
    if result == "fallido" and (not defect or not owner):
        raise ValueError("Un fallo requiere defecto y responsable de corrección.")
    participant = required_text(data, "participante", 40)
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,40}", participant):
        raise ValueError("Usa un código de participante sin nombres ni datos personales.")
    record = ResultadoPilotoDB(piloto_id=pilot.id, caso_id=case_id, participante=participant,
                               ejecutor_id=current_user().id, resultado=result,
                               evidencia=required_text(data, "evidencia", 1000), defecto=defect,
                               responsable_correccion=owner, sin_ayuda=boolean(data, "sin_ayuda"))
    db.session.add(record)
    db.session.commit()
    return jsonify({"resultado": record.to_dict()}), 201


@operations.patch("/pilot/results/<int:result_id>")
@requires("piloto.gestionar")
def pilot_resolve_defect(result_id):
    record = db.session.get(ResultadoPilotoDB, result_id)
    if not record:
        return jsonify({"error": "Resultado no encontrado."}), 404
    pilot = db.session.get(PilotoDB, record.piloto_id)
    if pilot.estado != "abierto" or record.resultado != "fallido" or record.resuelto:
        return jsonify({"error": "Solo se resuelven defectos abiertos de un piloto abierto."}), 409
    record.evidencia_correccion = required_text(payload(), "evidencia_correccion", 1000)
    record.resuelto = True
    db.session.commit()
    return jsonify({"resultado": record.to_dict()})


@operations.post("/pilot/<int:pilot_id>/decision")
@requires("piloto.gestionar")
def pilot_decision(pilot_id):
    pilot = db.session.get(PilotoDB, pilot_id)
    if not pilot:
        return jsonify({"error": "Piloto no encontrado."}), 404
    if pilot.estado != "abierto":
        return jsonify({"error": "El acta ya fue emitida y no se sobrescribe."}), 409
    data = payload()
    decision = data.get("decision")
    if decision not in {"aceptado", "rechazado", "condicionado"}:
        raise ValueError("La decisión debe ser aceptado, rechazado o condicionado.")
    detail = pilot_detail(pilot)
    if decision == "aceptado" and (detail["tareas_sin_ejecutar"] or detail["defectos_abiertos"]):
        return jsonify({"error": "No se puede aceptar con tareas sin ejecutar o defectos abiertos."}), 409
    impediments = optional_text(data, "impedimentos", 2000)
    if decision != "aceptado" and not impediments:
        raise ValueError("Documenta los impedimentos para la puesta en servicio.")
    pilot.acta_json = json.dumps({"decision": decision, "fecha": iso(utcnow()),
        "usabilidad": detail["usabilidad"],
        "registrado_por": current_user().id, "representante_negocio": required_text(data, "representante_negocio", 120),
        "conclusion": required_text(data, "conclusion", 2000), "impedimentos": impediments,
        "resultados": detail["resultados"], "tareas_sin_ejecutar": detail["tareas_sin_ejecutar"],
        "defectos_abiertos": detail["defectos_abiertos"]}, ensure_ascii=False)
    pilot.estado = "cerrado"
    db.session.commit()
    return jsonify({"piloto": pilot_detail(pilot)})


COUNT_FIELDS = ("pedidos", "errores", "completos", "pedidos_cronometrados", "insumos_revisados", "insumos_exactos")


def measurement_values(data):
    phase = data.get("fase")
    shift = data.get("turno")
    mode = data.get("modalidad")
    if phase not in {"antes", "despues"} or shift not in {"manana", "tarde", "noche"} or mode not in {"delivery", "retiro_local", "comer_local"}:
        raise ValueError("Revisa fase, turno y modalidad.")
    values = {"fase": phase, "turno": shift, "modalidad": mode,
              "fecha": date.fromisoformat(required_text(data, "fecha", 10)),
              "condiciones": required_text(data, "condiciones", 160).lower(),
              "limitaciones": optional_text(data, "limitaciones"),
              "excluida": boolean(data, "excluida"),
              "motivo_exclusion": optional_text(data, "motivo_exclusion", 500)}
    for field in COUNT_FIELDS:
        value = data.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1000000:
            raise ValueError(f"{field} debe ser un entero entre 0 y 1000000.")
        values[field] = value
    minutes = data.get("minutos_totales")
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or not 0 <= minutes <= 10000000:
        raise ValueError("Los minutos totales deben ser un número finito igual o mayor que cero.")
    values["minutos_totales"] = minutes
    if any(values[field] > values["pedidos"] for field in ("errores", "completos", "pedidos_cronometrados")):
        raise ValueError("Errores, completos y pedidos cronometrados no pueden superar los pedidos observados.")
    if values["insumos_exactos"] > values["insumos_revisados"]:
        raise ValueError("Los insumos exactos no pueden superar los revisados.")
    if not values["pedidos_cronometrados"] and minutes:
        raise ValueError("Indica los pedidos cronometrados que corresponden a esos minutos.")
    if not values["pedidos"] and not values["insumos_revisados"]:
        raise ValueError("Registra al menos un pedido o un insumo observado.")
    if values["excluida"] and not values["motivo_exclusion"]:
        raise ValueError("Una exclusión requiere su motivo.")
    return values


def measurement_query():
    query = MedicionDB.query
    for field in ("turno", "modalidad", "condiciones"):
        if request.args.get(field):
            query = query.filter(getattr(MedicionDB, field) == request.args[field].strip().lower())
    if request.args.get("desde"):
        query = query.filter(MedicionDB.fecha >= date.fromisoformat(request.args["desde"]))
    if request.args.get("hasta"):
        query = query.filter(MedicionDB.fecha <= date.fromisoformat(request.args["hasta"]))
    return query


def summarize_measurements(rows):
    totals = {field: sum(getattr(row, field) for row in rows) for field in (*COUNT_FIELDS, "minutos_totales")}
    def ratio(numerator, denominator, percent=False):
        n, d = totals[numerator], totals[denominator]
        return {"numerador": n, "denominador": d,
                "valor": round(n / d * (100 if percent else 1), 2) if d else None}
    return {"muestras": len(rows), "totales": totals,
            "tasa_errores": ratio("errores", "pedidos", True),
            "tiempo_medio_minutos": ratio("minutos_totales", "pedidos_cronometrados"),
            "completitud": ratio("completos", "pedidos", True),
            "exactitud_inventario": ratio("insumos_exactos", "insumos_revisados", True)}


@operations.post("/indicators")
@requires("indicadores.gestionar")
def measurement_create():
    record = MedicionDB(codigo=f"M-{uuid.uuid4().hex[:12]}", registrado_por=current_user().id,
                        **measurement_values(payload()))
    db.session.add(record)
    db.session.commit()
    return jsonify({"medicion": record.to_dict()}), 201


@operations.patch("/indicators/<int:measurement_id>/exclusion")
@requires("indicadores.gestionar")
def measurement_exclusion(measurement_id):
    record = db.session.get(MedicionDB, measurement_id)
    if not record:
        return jsonify({"error": "Medición no encontrada."}), 404
    data = payload()
    excluded = boolean(data, "excluida")
    reason = required_text(data, "motivo_exclusion", 500)
    record.excluida = excluded
    record.motivo_exclusion = reason
    db.session.commit()
    return jsonify({"medicion": record.to_dict()})


@operations.get("/indicators")
@requires("indicadores.gestionar")
def measurement_report():
    rows = measurement_query().order_by(MedicionDB.fecha, MedicionDB.id).all()
    included = [row for row in rows if not row.excluida]
    phases = {phase: [row for row in included if row.fase == phase] for phase in ("antes", "despues")}
    strata = {phase: {(row.turno, row.modalidad, row.condiciones) for row in phase_rows} for phase, phase_rows in phases.items()}
    matched = strata["antes"] & strata["despues"]
    comparable = {phase: [row for row in phase_rows if (row.turno, row.modalidad, row.condiciones) in matched] for phase, phase_rows in phases.items()}
    summaries = {phase: summarize_measurements(phase_rows) for phase, phase_rows in comparable.items()}
    differences = {}
    for metric in ("tasa_errores", "tiempo_medio_minutos", "completitud", "exactitud_inventario"):
        before, after = (summaries[phase][metric]["valor"] for phase in ("antes", "despues"))
        differences[metric] = round(after - before, 2) if before is not None and after is not None else None
    page = positive_id(request.args.get("page", 1))
    return jsonify({"mediciones": [row.to_dict() for row in rows[(page - 1) * 50:page * 50]], "page": page,
        "total": len(rows), "excluidas": sum(row.excluida for row in rows),
        "fases": {phase: summarize_measurements(phase_rows) for phase, phase_rows in phases.items()},
        "comparacion": {"antes": summaries["antes"], "despues": summaries["despues"], "diferencias": differences,
            "condiciones_comparables": [dict(zip(("turno", "modalidad", "condiciones"), key)) for key in sorted(matched)],
            "muestras_sin_par": len(included) - sum(len(v) for v in comparable.values()),
            "criterio": "Se comparan solo turnos, modalidades y condiciones presentes en ambas fases. Diferencia = después menos antes; porcentajes en puntos porcentuales.",
            "limitacion": "Comparación descriptiva ponderada por denominador. Diferencias de volumen y composición pueden influir; no demuestra causalidad."},
        "mensaje": "Sin mediciones registradas." if not rows else ("Faltan condiciones comparables en ambas fases." if not matched else "Comparación disponible.")})


def csv_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@operations.get("/indicators/export")
@requires("indicadores.gestionar")
def measurement_export():
    rows = measurement_query().order_by(MedicionDB.fecha, MedicionDB.id).all()
    fields = [column.name for column in MedicionDB.__table__.columns if column.name not in {"registrado_por", "id"}]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: csv_safe(value) for key, value in row.to_dict().items() if key in fields})
    return send_file(io.BytesIO(stream.getvalue().encode("utf-8-sig")), mimetype="text/csv; charset=utf-8", as_attachment=True, download_name="indicadores_anonimos.csv")


def app_database_path():
    if db.engine.url.drivername != "sqlite" or not db.engine.url.database or db.engine.url.database == ":memory:":
        raise ValueError("Los respaldos requieren una base SQLite en archivo.")
    return db.engine.url.database


@operations.get("/backups")
@requires("respaldos.gestionar")
def backups_list():
    copies = list_backups(current_app.config["BACKUP_FOLDER"])
    valid = [item for item in copies if "error" not in item]
    return jsonify({"copias": copies, "meta_rpo_horas": 24, "meta_rto_segundos": 7200,
                    "alerta": "No hay una copia válida con menos de 24 horas." if not valid or not valid[0]["cumple_rpo"] else None})


@operations.post("/backups")
@requires("respaldos.gestionar")
def backups_create():
    result = create_backup(app_database_path(), current_app.config["UPLOAD_FOLDER"], current_app.config["BACKUP_FOLDER"])
    write_audit("respaldar", "respaldo", result["archivo"], {"creado_en": result["creado_en"], "conteos": result["conteos"]})
    db.session.commit()
    return jsonify({"copia": result}), 201


@operations.get("/backups/<filename>/download")
@requires("respaldos.gestionar")
def backups_download(filename):
    path = backup_path(current_app.config["BACKUP_FOLDER"], filename)
    return send_file(path, mimetype="application/zip", as_attachment=True, download_name=path.name)


@operations.post("/backups/<filename>/verify")
@requires("respaldos.gestionar")
def backups_verify(filename):
    path = backup_path(current_app.config["BACKUP_FOLDER"], filename)
    result = verify_backup(path)
    write_audit("verificar", "respaldo", filename, result)
    db.session.commit()
    return jsonify({"verificacion": result})
