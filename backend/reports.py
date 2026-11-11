"""HU13: reportes conciliables de pedidos, anulaciones y cobros."""
import csv
import io
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, send_file
from backend.inventory_models import PagoDB
from backend.models import PedidoDB
from backend.operations import csv_safe, requires
from modelos import db

reports = Blueprint("reports", __name__, url_prefix="/api/admin")
STATES = {"recibido", "en_preparacion", "listo", "entregado", "pagado", "anulado"}


def report_filters(args):
    selected = args.get("estado", "")
    if selected and selected not in STATES:
        raise ValueError("Estado de pedido no válido.")
    bounds = []
    for name in ("desde", "hasta"):
        raw = args.get(name)
        bounds.append(datetime.combine(date.fromisoformat(raw), datetime.min.time(), timezone(timedelta(hours=-5))).astimezone(timezone.utc).replace(tzinfo=None) if raw else None)
    if all(bounds) and bounds[1] < bounds[0]:
        raise ValueError("La fecha final debe ser igual o posterior a la inicial.")
    return selected, (bounds[0], bounds[1] + timedelta(days=1) if bounds[1] else None)


def selected_order(order, state, bounds):
    instant = order.creado_en.replace(tzinfo=None) if order.creado_en.tzinfo is None else order.creado_en.astimezone(timezone.utc).replace(tzinfo=None)
    return (not state or order.estado == state) and (bounds[0] is None or instant >= bounds[0]) and (bounds[1] is None or instant < bounds[1])


def build_report(args):
    state, bounds = report_filters(args)
    orders = [row for row in PedidoDB.query.order_by(PedidoDB.creado_en.desc(), PedidoDB.id.desc()).all() if selected_order(row, state, bounds)]
    identifiers = {order.id for order in orders}
    payments = [row for row in PagoDB.query.order_by(PagoDB.registrado_en.desc()).all() if row.pedido_id in identifiers]
    by_id = {order.id: order for order in orders}
    cancelled = [row for row in orders if row.estado == "anulado"]
    charged = round(sum(row.importe for row in payments), 2)
    current_total = round(sum(row.total for row in orders if row.estado != "anulado"), 2)
    return {"criterio_fecha": "Pedidos creados en las fechas seleccionadas, hora de Perú. Cobros de esos mismos pedidos, con su fecha de registro visible.",
            "filtros": dict(args), "pedidos": [row.to_dict() for row in orders],
            "pagos": [{"id": row.id, "codigo": by_id[row.pedido_id].codigo, "importe": row.importe, "metodo": row.metodo, "registrado_en": row.registrado_en.replace(tzinfo=timezone.utc).isoformat(), "origen": row.origen} for row in payments],
            "totales": {"pedidos": len(orders), "importe_pedidos": round(sum(row.total for row in orders), 2),
                        "anulaciones": len(cancelled), "importe_anulado": round(sum(row.total for row in cancelled), 2),
                        "importe_vigente": current_total, "pagos_registrados": len(payments), "cobrado": charged,
                        "pendiente_cobro": round(current_total - charged, 2)},
            "mensaje": "Sin operaciones para estos filtros." if not orders else f"{len(orders)} pedidos incluidos."}


@reports.get("/reports")
@requires("auditoria.ver")
def reports_get():
    try:
        return jsonify(build_report(request.args))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@reports.get("/reports/export")
@requires("auditoria.ver")
def reports_export():
    try:
        report = build_report(request.args)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["tipo", "codigo", "fecha", "estado_o_metodo", "importe"])
    for row in report["pedidos"]:
        writer.writerow(["pedido", csv_safe(row["codigo"]), row["creado_en"], row["estado"], row["total"]])
    for row in report["pagos"]:
        writer.writerow(["pago", csv_safe(row["codigo"]), row["registrado_en"], row["metodo"], row["importe"]])
    return send_file(io.BytesIO(stream.getvalue().encode("utf-8-sig")), as_attachment=True, download_name="operaciones.csv", mimetype="text/csv")
