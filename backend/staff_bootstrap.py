"""Cuentas operativas iniciales para instalaciones persistentes."""

import os
import re
import secrets
import tempfile
from pathlib import Path

from werkzeug.security import generate_password_hash

from backend.inventory import begin_write
from backend.models import UsuarioDB
from modelos import db


DEFAULT_STAFF = (
    ("cocina", "Cocina", "cocina@pizzapronto.test"),
    ("caja", "Caja", "caja@pizzapronto.test"),
)


def _initial_password(role, directory):
    variable = f"PIZZA_PRONTO_{role.upper()}_PASSWORD"
    password = os.environ.get(variable)
    if password is not None:
        if not 12 <= len(password) <= 256 or password != password.strip():
            raise RuntimeError(f"Configura {variable} con una clave privada de 12 a 256 caracteres y sin espacios en los extremos.")
        return password, None

    path = directory / f".{role}-password"
    if path.is_file():
        password = path.read_text(encoding="utf-8").strip()
        if not 12 <= len(password) <= 256:
            raise RuntimeError(f"La clave inicial de {role} guardada en {path} no es válida. Configura {variable}.")
        return password, path

    password = secrets.token_urlsafe(24)
    # El archivo temporal se crea con permisos privados y se mueve completo.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(password + "\n")
            handle.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return password, path


def ensure_staff_accounts(directory, logger):
    """Crea un acceso inicial para cada rol sin cuentas registradas."""
    begin_write()
    created = []
    try:
        pending = []
        for role, name, default_email in DEFAULT_STAFF:
            if UsuarioDB.query.filter_by(rol=role).first() is not None:
                continue
            variable = f"PIZZA_PRONTO_{role.upper()}_EMAIL"
            email = os.environ.get(variable, default_email).strip().lower()
            if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                raise RuntimeError(f"Configura un correo válido en {variable}.")
            if UsuarioDB.query.filter(db.func.lower(UsuarioDB.email) == email).first() or any(entry[2] == email for entry in pending):
                raise RuntimeError(f"El correo inicial de {role} ya está asignado. Configura otro en {variable}.")
            pending.append((role, name, email))

        for role, name, email in pending:
            password, path = _initial_password(role, directory)
            db.session.add(UsuarioDB(nombre=name, email=email, rol=role, password_hash=generate_password_hash(password)))
            created.append((role, email, path))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    for role, email, path in created:
        if path:
            logger.info("Cuenta inicial de %s creada (%s). Clave privada en %s.", role, email, path)
        else:
            logger.info("Cuenta inicial de %s creada (%s) con su clave configurada.", role, email)
