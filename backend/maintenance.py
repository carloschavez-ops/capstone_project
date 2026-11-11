"""HU11 y HU17: comandos repetibles de respaldo, recuperación y credenciales."""

import argparse
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from backend.backups import create_backup, maintenance_lock, restore_backup, runtime_paths, verify_backup


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mantenimiento de Pizza Pronto")
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup", help="Copia SQLite e imágenes; puede ejecutarse con el servicio activo")
    backup.add_argument("--output", type=Path, help="Carpeta de copias; por defecto instance/backups")
    verify = sub.add_parser("verify", help="Restaura en una carpeta temporal y mide RPO/RTO")
    verify.add_argument("archive", type=Path)
    restore = sub.add_parser("restore", help="Restaura con el servicio detenido y conserva los originales")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--confirm-restore", action="store_true", required=True, help="Confirma el reemplazo de SQLite e imágenes")
    sub.add_parser("set-admin-password", help="Actualiza al administrador desde PIZZA_PRONTO_ADMIN_PASSWORD con el servicio detenido")
    args = parser.parse_args(argv)
    data, database, uploads, backups = runtime_paths()
    try:
        if args.command == "backup":
            result = create_backup(database, uploads, args.output or backups)
        elif args.command == "verify":
            result = verify_backup(args.archive)
        elif args.command == "restore":
            result = restore_backup(args.archive, data, database, uploads)
        else:
            from werkzeug.security import generate_password_hash
            password = os.environ.get("PIZZA_PRONTO_ADMIN_PASSWORD", "")
            if len(password) < 12 or password == "pizzapronto":
                raise ValueError("Configura PIZZA_PRONTO_ADMIN_PASSWORD con una clave privada de al menos 12 caracteres.")
            with maintenance_lock(data), closing(sqlite3.connect(database)) as connection, connection:
                email = os.environ.get("PIZZA_PRONTO_ADMIN_EMAIL", "pizzapronto@gmail.com").lower()
                user = connection.execute("SELECT id,nombre FROM usuarios WHERE email=? AND rol='admin'", (email,)).fetchone()
                if user is None:
                    raise ValueError("No existe ese administrador; inicia la aplicación para crearlo.")
                connection.execute("UPDATE usuarios SET password_hash=?,session_version=session_version+1 WHERE id=?", (generate_password_hash(password), user[0]))
                connection.execute("INSERT INTO auditoria (usuario_id,actor,rol,fecha,operacion,entidad,entidad_id,cambios_json) VALUES (?,?,?,?,?,?,?,?)",
                                   (user[0], "mantenimiento offline", "sistema", datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), "cambiar_credencial", "usuarios", str(user[0]), '{"sesiones_invalidadas":true}'))
                result = {"administrador_actualizado": True, "sesiones_invalidadas": True}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.DatabaseError) as error:
        parser.exit(1, f"Error de mantenimiento: {error}\n")


if __name__ == "__main__":
    main()
