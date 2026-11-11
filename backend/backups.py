"""HU11: copias consistentes de SQLite, imágenes, verificación y restauración offline."""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
import uuid
import zipfile
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_FILES = 10000
CORE_TABLES = {"usuarios", "ingredientes", "pizzas", "menu_items", "inventario", "pedidos", "auditoria", "pilotos", "resultados_piloto", "mediciones_piloto"}


def runtime_paths():
    root = Path(__file__).resolve().parents[1]
    data = Path(os.environ.get("PIZZA_PRONTO_DATA_DIR", root / "instance")).resolve()
    uploads = Path(os.environ.get("PIZZA_PRONTO_UPLOAD_DIR", root / "backend" / "uploads")).resolve()
    return data, data / "pizza_pronto.db", uploads, data / "backups"


@contextmanager
def maintenance_lock(data_dir):
    """El servidor y el restaurador se excluyen incluso tras cierres inesperados."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / ".service.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("El servicio está en ejecución o hay otro mantenimiento. Detén el servidor antes de restaurar.") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def open_readonly(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        yield connection


def snapshot_details(database_path):
    with open_readonly(database_path) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("La integridad de SQLite no es válida.")
        if connection.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("La copia contiene referencias inconsistentes.")
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not CORE_TABLES.issubset(tables):
            raise ValueError("La copia no corresponde al esquema actual de Pizza Pronto.")
        counted = CORE_TABLES | ({"recetas_consumo", "movimientos_stock", "pagos"} & tables)
        counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in sorted(counted)}
        images = set()
        for table in ("pizzas", "menu_items"):
            for (image,) in connection.execute(f"SELECT imagen FROM {table}"):
                if image and image.startswith("/api/uploads/"):
                    name = image.removeprefix("/api/uploads/")
                    if not name or PurePosixPath(name).name != name or "\\" in name:
                        raise ValueError("La base contiene una referencia de imagen no válida.")
                    images.add(name)
        return {"conteos": counts, "imagenes_referenciadas": sorted(images)}


def create_backup(database_path, uploads_dir, backup_dir):
    started = time.monotonic()
    database_path, uploads_dir, backup_dir = map(Path, (database_path, uploads_dir, backup_dir))
    if not database_path.is_file():
        raise ValueError("No existe la base SQLite. Inicia la aplicación primero.")
    backup_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    name = f"pizza-pronto-{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}.zip"
    destination = backup_dir / name
    with tempfile.TemporaryDirectory(prefix="pizza-backup-") as directory:
        staging = Path(directory)
        snapshot = staging / "database.sqlite3"
        # SQLite backup API produce una instantánea transaccional aun con el servidor activo.
        with open_readonly(database_path) as source, closing(sqlite3.connect(snapshot)) as target:
            source.backup(target)
        details = snapshot_details(snapshot)
        images = staging / "uploads"
        images.mkdir()
        # Los uploads tienen nombres UUID y no se sobrescriben. Se copian todos los
        # archivos presentes; se exige que cada referencia de la instantánea exista.
        if uploads_dir.exists():
            for source in uploads_dir.iterdir():
                if source.is_symlink() or (not source.is_file()):
                    raise ValueError("La carpeta de imágenes debe contener solo archivos regulares.")
                shutil.copy2(source, images / source.name)
        for filename in details["imagenes_referenciadas"]:
            if not (images / filename).is_file():
                raise ValueError(f"Falta la imagen referenciada {filename}; no se creó una copia incompleta.")
        files = {path.relative_to(staging).as_posix(): {"sha256": sha256(path), "bytes": path.stat().st_size}
                 for path in [snapshot, *sorted(images.iterdir())]}
        if sum(item["bytes"] for item in files.values()) > MAX_ARCHIVE_BYTES or len(files) > MAX_ARCHIVE_FILES - 1:
            raise ValueError("La copia supera el límite de 512 MB o 9999 archivos.")
        manifest = {"version": 1, "creado_en": now.isoformat(), "archivos": files, **details}
        (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary = backup_dir / (name + ".part")
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                for relative in ["manifest.json", *files]:
                    archive.write(staging / relative, relative)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    return {"archivo": name, "creado_en": manifest["creado_en"], "bytes": destination.stat().st_size,
            "duracion_segundos": round(time.monotonic() - started, 3), "conteos": details["conteos"]}


def backup_path(backup_dir, filename):
    if not isinstance(filename, str) or Path(filename).name != filename or not filename.startswith("pizza-pronto-") or not filename.endswith(".zip") or "\\" in filename:
        raise ValueError("Nombre de copia no válido.")
    path = Path(backup_dir) / filename
    if path.is_symlink() or not path.is_file():
        raise ValueError("Copia no encontrada.")
    return path


def unpack_verified(archive_path, staging):
    """No usa extractall: rechaza traversal, duplicados y archivos ZIP excesivos."""
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(entries) > MAX_ARCHIVE_FILES or len(set(names)) != len(names) or sum(entry.file_size for entry in entries) > MAX_ARCHIVE_BYTES:
                raise ValueError("El ZIP excede los límites o contiene entradas duplicadas.")
            if "manifest.json" not in names or "database.sqlite3" not in names:
                raise ValueError("El ZIP no contiene manifiesto y base de datos.")
            if archive.getinfo("manifest.json").file_size > 2 * 1024 * 1024:
                raise ValueError("Manifiesto demasiado grande.")
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict):
                raise ValueError("El manifiesto debe ser un objeto JSON.")
            files = manifest.get("archivos")
            if manifest.get("version") != 1 or not isinstance(files, dict) or set(names) != {"manifest.json", *files}:
                raise ValueError("El manifiesto no coincide con los archivos del ZIP.")
            created = datetime.fromisoformat(manifest["creado_en"])
            if created.tzinfo is None or created > datetime.now(timezone.utc):
                raise ValueError("Fecha de respaldo no válida.")
            for name, metadata in files.items():
                parts = PurePosixPath(name).parts
                allowed = name == "database.sqlite3" or (len(parts) == 2 and parts[0] == "uploads")
                if not allowed or ".." in parts or "\\" in name or ":" in name:
                    raise ValueError("El ZIP contiene una ruta no permitida.")
                output = staging / name
                output.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, output.open("wb") as target:
                    shutil.copyfileobj(source, target, 1024 * 1024)
                if output.stat().st_size != metadata["bytes"] or sha256(output) != metadata["sha256"]:
                    raise ValueError(f"La huella de {name} no coincide; copia alterada o dañada.")
            details = snapshot_details(staging / "database.sqlite3")
            if details["conteos"] != manifest.get("conteos") or details["imagenes_referenciadas"] != manifest.get("imagenes_referenciadas"):
                raise ValueError("Los conteos o las imágenes no coinciden con el manifiesto.")
            for name in details["imagenes_referenciadas"]:
                if f"uploads/{name}" not in files:
                    raise ValueError("El respaldo omite una imagen del catálogo.")
            (staging / "uploads").mkdir(exist_ok=True)
            return manifest
    except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError, sqlite3.DatabaseError) as error:
        raise ValueError("El respaldo está dañado o tiene un formato incompatible.") from error


def verify_backup(archive_path, record=True):
    """Restaura realmente en un directorio aislado y consulta SQLite e imágenes."""
    started = time.monotonic()
    archive_path = Path(archive_path)
    with tempfile.TemporaryDirectory(prefix="pizza-restore-check-") as directory:
        manifest = unpack_verified(archive_path, Path(directory))
        details = snapshot_details(Path(directory) / "database.sqlite3")
    elapsed = time.monotonic() - started
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(manifest["creado_en"])).total_seconds() / 3600
    result = {"archivo": archive_path.name, "verificado_en": datetime.now(timezone.utc).isoformat(),
              "restauracion_prueba": True, "integridad": "ok", "conteos": details["conteos"],
              "imagenes": len(manifest["archivos"]) - 1,
              "rpo_horas": round(age, 4), "rto_segundos": round(elapsed, 3),
              "meta_rpo_horas": 24, "meta_rto_segundos": 7200,
              "cumple_rpo": age <= 24, "cumple_rto": elapsed <= 7200,
              "alcance": "Restauración aislada local; el RTO de un incidente también depende del equipo, despliegue y operación."}
    if record:
        archive_path.with_suffix(".verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def list_backups(backup_dir):
    results = []
    folder = Path(backup_dir)
    if not folder.exists():
        return results
    for path in sorted(folder.glob("pizza-pronto-*.zip"), reverse=True):
        try:
            with zipfile.ZipFile(path) as archive:
                if archive.getinfo("manifest.json").file_size > 2 * 1024 * 1024:
                    raise ValueError("Manifiesto inválido")
                manifest = json.loads(archive.read("manifest.json"))
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(manifest["creado_en"])).total_seconds() / 3600
            verification = path.with_suffix(".verification.json")
            results.append({"archivo": path.name, "creado_en": manifest["creado_en"], "bytes": path.stat().st_size,
                            "antiguedad_horas": round(age, 2), "cumple_rpo": 0 <= age <= 24,
                            "verificacion": json.loads(verification.read_text(encoding="utf-8")) if verification.is_file() else None})
        except (OSError, ValueError, KeyError, zipfile.BadZipFile):
            results.append({"archivo": path.name, "error": "Copia o manifiesto no válido; no usar para restaurar."})
    return results


def restore_backup(archive_path, data_dir, database_path, uploads_dir):
    """Reemplazo offline con originales conservados y rollback ante fallo de instalación."""
    started = time.monotonic()
    data_dir, database_path, uploads_dir = map(Path, (data_dir, database_path, uploads_dir))
    with maintenance_lock(data_dir), tempfile.TemporaryDirectory(prefix="pizza-restore-") as directory:
        stage = Path(directory)
        manifest = unpack_verified(archive_path, stage)
        # Invalida sesiones anteriores a la recuperación, incluidas las cuentas
        # deshabilitadas después de la copia que ahora podrían reaparecer.
        old_version = 0
        if database_path.is_file():
            with open_readonly(database_path) as connection:
                old_version = connection.execute("SELECT COALESCE(MAX(session_version),0) FROM usuarios").fetchone()[0]
        with closing(sqlite3.connect(stage / "database.sqlite3")) as connection, connection:
            restored_version = connection.execute("SELECT COALESCE(MAX(session_version),0) FROM usuarios").fetchone()[0]
            connection.execute("UPDATE usuarios SET session_version=?", (max(old_version, restored_version) + 1,))
            connection.execute("INSERT INTO auditoria (actor,rol,fecha,operacion,entidad,entidad_id,cambios_json) VALUES (?,?,?,?,?,?,?)",
                               ("mantenimiento offline", "sistema", datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), "restaurar", "respaldo", Path(archive_path).name,
                                json.dumps({"copia_creada_en": manifest["creado_en"], "sesiones_invalidadas": True})))
        database_path.parent.mkdir(parents=True, exist_ok=True)
        uploads_dir.parent.mkdir(parents=True, exist_ok=True)
        suffix = uuid.uuid4().hex[:12]
        saved_db = database_path.with_name(f"{database_path.name}.pre-restore-{suffix}")
        saved_uploads = uploads_dir.with_name(f"{uploads_dir.name}.pre-restore-{suffix}")
        new_db = database_path.with_name(f"{database_path.name}.staged-{suffix}")
        new_uploads = uploads_dir.with_name(f"{uploads_dir.name}.staged-{suffix}")
        shutil.copy2(stage / "database.sqlite3", new_db)
        shutil.copytree(stage / "uploads", new_uploads)
        moved_db = moved_images = installed_db = installed_images = False
        try:
            if database_path.exists():
                os.replace(database_path, saved_db)
                moved_db = True
            if uploads_dir.exists():
                os.replace(uploads_dir, saved_uploads)
                moved_images = True
            os.replace(new_db, database_path)
            installed_db = True
            os.replace(new_uploads, uploads_dir)
            installed_images = True
        except OSError:
            if installed_db:
                database_path.unlink()
            if installed_images:
                shutil.rmtree(uploads_dir)
            if moved_db:
                os.replace(saved_db, database_path)
            if moved_images:
                os.replace(saved_uploads, uploads_dir)
            raise
        finally:
            new_db.unlink(missing_ok=True)
            if new_uploads.exists():
                shutil.rmtree(new_uploads)
        # Los sidecars de una base anterior no deben reaplicarse a la restaurada.
        for extension in ("-wal", "-shm", "-journal"):
            sidecar = Path(str(database_path) + extension)
            if sidecar.exists():
                os.replace(sidecar, Path(str(saved_db) + extension))
        elapsed = time.monotonic() - started
        return {"restaurada": True, "archivo": Path(archive_path).name,
                "rto_segundos": round(elapsed, 3), "cumple_rto": elapsed <= 7200,
                "original_sqlite": str(saved_db) if moved_db else None,
                "original_imagenes": str(saved_uploads) if moved_images else None}
