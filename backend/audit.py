"""HU14: historial transaccional con una lista explícita de campos permitidos."""

import json

from flask import current_app, g, has_app_context, has_request_context
from sqlalchemy import event, inspect

from modelos import MenuItemDB, PizzaDB, db
from backend.models import InventarioDB, MermaDB, PedidoDB, UsuarioDB
from backend.inventory_models import MovimientoStockDB, PagoDB, RecetaConsumoDB
from backend.operations_models import AuditoriaDB, MedicionDB, PilotoDB, ResultadoPilotoDB, utcnow


AUDITED_FIELDS = {
    RecetaConsumoDB: ("nombre", "componentes_json", "origen", "revision"),
    MovimientoStockDB: ("pedido_id", "insumo_id", "tipo", "cantidad", "unidad", "saldo_anterior", "saldo_posterior"),
    PagoDB: ("pedido_id", "importe", "metodo", "registrado_en", "usuario_id", "origen"),
    PizzaDB: ("nombre", "descripcion", "precio_personal", "precio_mediana", "precio_familiar", "imagen", "activo"),
    MenuItemDB: ("nombre", "descripcion", "precio", "precio_mediana", "precio_familiar", "imagen", "activo", "ingredientes_json"),
    InventarioDB: ("item_id", "nombre", "cantidad", "unidad", "categoria", "stock_minimo", "costo_unitario"),
    PedidoDB: ("codigo", "estado", "total", "metodo_pago", "preparacion_inicio_en", "listo_en", "entregado_en", "pagado_en", "stock_estado", "anulado_en", "motivo_anulacion"),
    MermaDB: ("nombre", "cantidad", "unidad", "motivo"),
    UsuarioDB: ("nombre", "rol", "activo", "session_version"),
    PilotoDB: ("nombre", "responsable", "casos_json", "estado", "acta_json"),
    ResultadoPilotoDB: ("piloto_id", "caso_id", "participante", "resultado", "evidencia", "defecto", "responsable_correccion", "resuelto", "evidencia_correccion"),
    MedicionDB: ("codigo", "fase", "fecha", "turno", "modalidad", "condiciones", "pedidos", "errores", "completos", "minutos_totales", "pedidos_cronometrados", "insumos_revisados", "insumos_exactos", "excluida", "motivo_exclusion", "limitaciones"),
}


def actor_values():
    if has_request_context():
        return getattr(g, "audit_actor", {"usuario_id": None, "actor": "visitante", "rol": "publico"})
    return {"usuario_id": None, "actor": "sistema", "rol": "sistema"}


def _json_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def write_audit(operation, entity, entity_id, changes):
    """Eventos de operación fuera de los cambios ORM, como creación de una copia."""
    db.session.add(AuditoriaDB(**actor_values(), operacion=operation, entidad=entity,
                              entidad_id=str(entity_id), cambios_json=json.dumps(changes, ensure_ascii=False)))


def _record(mapper, connection, target, operation):
    if has_app_context() and current_app.config.get("INITIALIZING"):
        return
    fields = AUDITED_FIELDS[type(target)]
    state = inspect(target)
    changes = {}
    for name in fields:
        value = _json_value(getattr(target, name))
        history = state.attrs[name].history
        if operation == "crear":
            changes[name] = {"antes": None, "despues": value}
        elif operation == "eliminar":
            changes[name] = {"antes": value, "despues": None}
        elif history.has_changes():
            changes[name] = {"antes": _json_value(history.deleted[0]) if history.deleted else None, "despues": value}
    if not changes:
        return
    identifier = getattr(target, "codigo", None) or getattr(target, "item_id", None) or getattr(target, "clave", None) or target.id
    connection.execute(AuditoriaDB.__table__.insert().values(
        **actor_values(), fecha=utcnow(), operacion=operation, entidad=target.__tablename__,
        entidad_id=str(identifier), cambios_json=json.dumps(changes, ensure_ascii=False)))


def _created(mapper, connection, target):
    _record(mapper, connection, target, "crear")


def _updated(mapper, connection, target):
    _record(mapper, connection, target, "actualizar")


def _deleted(mapper, connection, target):
    _record(mapper, connection, target, "eliminar")


for audited_model in AUDITED_FIELDS:
    event.listen(audited_model, "after_insert", _created)
    event.listen(audited_model, "after_update", _updated)
    event.listen(audited_model, "after_delete", _deleted)
