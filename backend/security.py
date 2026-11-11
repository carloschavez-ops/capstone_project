"""CSRF para los nuevos formularios y para las operaciones existentes."""

import secrets
import hashlib
import hmac
import time

from flask import current_app, jsonify, request, session
from modelos import db


class IntentoAccesoDB(db.Model):
    __tablename__ = "intentos_acceso"
    clave = db.Column(db.String(80), primary_key=True)
    inicio = db.Column(db.Float, nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=0)


def start_session():
    session["emitida_en"] = time.time()
    session["actividad_en"] = session["emitida_en"]
    session.permanent = True


def login_keys(email):
    secret = current_app.secret_key.encode()
    return ["cuenta:" + hmac.new(secret, email.encode(), hashlib.sha256).hexdigest(),
            "red:" + hmac.new(secret, (request.remote_addr or "local").encode(), hashlib.sha256).hexdigest()]


def login_limit(email):
    from backend.inventory import begin_write
    begin_write()
    now, window = time.time(), current_app.config["LOGIN_WINDOW_SECONDS"]
    for key in login_keys(email):
        row = db.session.get(IntentoAccesoDB, key)
        limit = current_app.config["LOGIN_MAX_ATTEMPTS"] * (4 if key.startswith("red:") else 1)
        if row and row.inicio + window > now and row.cantidad >= limit:
            db.session.rollback()
            return jsonify({"error": "Demasiados intentos. Espera antes de volver a ingresar."}), 429, {"Retry-After": str(max(1, int(row.inicio + window - now)))}
    return None


def record_login(email, successful):
    now, window = time.time(), current_app.config["LOGIN_WINDOW_SECONDS"]
    for key in login_keys(email):
        row = db.session.get(IntentoAccesoDB, key)
        if successful:
            if row and key.startswith("cuenta:"):
                db.session.delete(row)
            continue
        if row is None:
            db.session.add(IntentoAccesoDB(clave=key, inicio=now, cantidad=1))
        elif row.inicio + window <= now:
            row.inicio, row.cantidad = now, 1
        else:
            row.cantidad += 1
    # No retener identificadores de intentos fuera de la ventana de observación.
    IntentoAccesoDB.query.filter(IntentoAccesoDB.inicio < now - window).delete(synchronize_session=False)
    db.session.commit()


def install_security(app):
    @app.before_request
    def expire_session():
        if not (session.get("user_id") or session.get("guest")):
            return None
        now = time.time()
        issued, active = session.get("emitida_en"), session.get("actividad_en")
        if issued is None or active is None or now - issued >= app.config["SESSION_ABSOLUTE_SECONDS"] or now - active >= app.config["SESSION_IDLE_SECONDS"]:
            session.clear()
            if request.path.startswith("/api/") and request.path not in {"/api/auth/me", "/api/auth/csrf", "/api/auth/login"}:
                return jsonify({"error": "Tu sesión venció. Vuelve a ingresar.", "code": "session_expired"}), 401
        else:
            session["actividad_en"] = now

    @app.get("/api/auth/csrf")
    def csrf_token():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return jsonify({"csrf_token": token})

    @app.before_request
    def validate_csrf():
        if app.config["CSRF_ENABLED"] and request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = session.get("csrf_token", "")
            supplied = request.headers.get("X-CSRF-Token", "")
            if not expected or not secrets.compare_digest(expected, supplied):
                return jsonify({"error": "La sesión del formulario venció. Intenta de nuevo.", "code": "csrf_invalid"}), 403
        if request.is_json and request.method in {"POST", "PUT", "PATCH"} and not isinstance(request.get_json(silent=True), dict):
            return jsonify({"error": "Envía un objeto JSON válido."}), 400

    @app.after_request
    def security_headers(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if app.config.get("PRODUCTION"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response
