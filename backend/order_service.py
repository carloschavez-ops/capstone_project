"""HU06 y HU09: transición, consumo, reversión y cobro en una transacción."""
from datetime import datetime, timezone
from backend.inventory import begin_write, consume_order, reverse_order
from backend.inventory_models import PagoDB
from backend.models import PedidoDB
from backend.permissions import current_user
from modelos import db

TRANSITIONS = {"recibido": "en_preparacion", "en_preparacion": "listo", "listo": "entregado", "entregado": "pagado"}


def transition_order(code, state, reason=""):
    begin_write()
    order = PedidoDB.query.filter_by(codigo=code).populate_existing().first()
    if order is None:
        raise LookupError("No se encontró ese pedido.")
    if state == order.estado:
        return order
    if state == "anulado":
        if order.estado not in {"recibido", "en_preparacion", "listo"}:
            raise ValueError("Solo se anulan pedidos anteriores a la entrega y al cobro.")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise ValueError("Indica el motivo de anulación (máximo 500 caracteres).")
        reverse_order(order)
        order.motivo_anulacion = reason.strip()
        order.anulado_en = datetime.now(timezone.utc)
        if order.stock_estado == "legacy":
            order.problema_preparacion = "Pedido histórico: conciliar manualmente los descuentos anteriores a esta versión."
    elif TRANSITIONS.get(order.estado) != state:
        raise ValueError("El pedido debe avanzar al siguiente estado disponible.")
    now = datetime.now(timezone.utc)
    if state == "en_preparacion":
        consume_order(order)
        order.preparacion_inicio_en = now
        order.problema_preparacion = ""
    elif state == "listo":
        order.listo_en = now
    elif state == "entregado":
        order.entregado_en = now
    elif state == "pagado":
        order.pagado_en = now
        actor = current_user()
        db.session.add(PagoDB(pedido_id=order.id, importe=order.total, metodo=order.metodo_pago, registrado_en=now, usuario_id=actor.id if actor else None))
    order.estado = state
    db.session.commit()
    return order
