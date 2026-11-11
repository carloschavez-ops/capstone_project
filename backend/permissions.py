"""HU10: permisos comprobados en la API, no solamente en los botones."""

from flask import g, jsonify, request, session

from backend.models import UsuarioDB
from modelos import db


ROLE_PERMISSIONS = {
    "admin": ["pedidos.ver", "pedidos.preparar", "pedidos.entregar", "pedidos.cobrar", "pedidos.anular",
              "inventario.ver", "inventario.editar", "catalogo.editar", "personal.gestionar",
              "auditoria.ver", "respaldos.gestionar", "piloto.gestionar", "indicadores.gestionar"],
    "cocina": ["pedidos.ver", "pedidos.preparar", "inventario.ver"],
    "caja": ["pedidos.ver", "pedidos.entregar", "pedidos.cobrar"],
    "cliente": [],
}


def current_user():
    identifier = session.get("user_id")
    user = db.session.get(UsuarioDB, identifier) if identifier else None
    if user and user.activo and session.get("session_version") == user.session_version:
        return user
    if identifier:
        session.clear()
    return None


def permission_error(permission):
    user = current_user()
    if user is None:
        return jsonify({"error": "Inicia sesión para continuar."}), 401
    if permission not in ROLE_PERMISSIONS.get(user.rol, []):
        return jsonify({"error": "Tu función no permite esta operación."}), 403
    return None


def operational_permission():
    if request.endpoint == "admin_orders":
        return "pedidos.ver"
    if request.endpoint == "admin_inventory":
        return "inventario.ver"
    if request.endpoint == "update_admin_order":
        state = (request.get_json(silent=True) or {}).get("estado")
        return {"en_preparacion": "pedidos.preparar", "listo": "pedidos.preparar",
                "entregado": "pedidos.entregar", "pagado": "pedidos.cobrar", "anulado": "pedidos.anular"}.get(state, "catalogo.editar")
    return "catalogo.editar"


def install_permissions(app):
    @app.before_request
    def identify_actor_and_protect_admin():
        user = current_user()
        g.audit_actor = {"usuario_id": user.id if user else None,
                         "actor": f"cuenta:{user.id} {user.nombre}" if user else "visitante",
                         "rol": user.rol if user else "publico"}
        # Defensa para cualquier ruta administrativa actual o futura.
        if request.path.startswith("/api/admin/") and request.method != "OPTIONS":
            if user is None:
                return jsonify({"error": "Inicia sesión para continuar."}), 401
            if user.rol != "admin" and request.endpoint not in {"admin_orders", "update_admin_order", "admin_inventory"}:
                return jsonify({"error": "Esta operación requiere administración."}), 403
            return permission_error(operational_permission()) if user.rol != "admin" else None
