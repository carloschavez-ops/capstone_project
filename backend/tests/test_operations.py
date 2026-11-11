import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backend.app import create_app
from backend.backups import create_backup, maintenance_lock, restore_backup, verify_backup
from backend.models import InventarioDB, PedidoDB, UsuarioDB
from backend.operations_models import AuditoriaDB
from modelos import MenuItemDB, db


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "pizza_pronto.db"
        self.uploads = self.root / "uploads"
        self.backups = self.root / "backups"
        self.app = create_app(f"sqlite:///{self.database.as_posix()}", {
            "TESTING": True, "CSRF_ENABLED": False, "UPLOAD_FOLDER": str(self.uploads),
            "BACKUP_FOLDER": str(self.backups), "FRONTEND_DIST": str(self.root / "dist")})
        self.client = self.app.test_client()
        self.login()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp.cleanup()

    def login(self, client=None, email="pizzapronto@gmail.com", password=None):
        return (client or self.client).post("/api/auth/login", json={"email": email, "password": password or self.app.config["BOOTSTRAP_ADMIN_PASSWORD"]})

    def employee(self, role):
        response = self.client.post("/api/admin/staff", json={"nombre": role.title(), "email": f"{role}@example.com", "password": "clave-personal-123", "rol": role})
        self.assertEqual(response.status_code, 201, response.get_json())
        client = self.app.test_client()
        self.assertEqual(self.login(client, f"{role}@example.com", "clave-personal-123").status_code, 200)
        return client, response.get_json()["usuario"]

    def order(self):
        with self.app.app_context():
            row = PedidoDB(codigo="PP-TEST", cliente="Prueba", telefono="999111222", tipo_entrega="retiro_local",
                           metodo_pago="efectivo", items_json="[]", subtotal=10, delivery=0, total=10,
                           estado="en_preparacion", preparacion_inicio_en=datetime.now(timezone.utc))
            db.session.add(row)
            db.session.commit()

    def pilot(self, cases=None):
        response = self.client.post("/api/admin/pilot", json={"nombre": "Piloto de prueba", "responsable": "Responsable prueba",
            "casos": cases or [{"id": "P01", "nombre": "Cobro", "criterio": "El cobro se registra una vez."}]})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["piloto"]["id"]

    def observation(self, **changes):
        values = {"fase": "antes", "fecha": "2026-10-01", "turno": "tarde", "modalidad": "retiro_local",
                  "condiciones": "dos personas", "pedidos": 10, "errores": 2, "completos": 8,
                  "minutos_totales": 50, "pedidos_cronometrados": 10, "insumos_revisados": 5, "insumos_exactos": 4}
        values.update(changes)
        return self.client.post("/api/admin/indicators", json=values)

    def test_hu10_role_matrix_and_individual_accounts(self):
        self.order()
        kitchen, _ = self.employee("cocina")
        cashier, _ = self.employee("caja")
        self.assertEqual(kitchen.get("/api/admin/inventory").status_code, 200)
        stock = kitchen.get("/api/admin/inventory").get_json()["ingredientes"][0]
        self.assertEqual(kitchen.put(f"/api/admin/inventory/ingrediente/{stock['item_id']}", json={"cantidad": 10, "unidad": stock["unidad"]}).status_code, 403)
        self.assertEqual(cashier.get("/api/admin/inventory").status_code, 403)
        self.assertEqual(kitchen.get("/api/admin/orders").status_code, 200)
        self.assertEqual(cashier.patch("/api/admin/orders/PP-TEST", json={"estado": "listo"}).status_code, 403)
        self.assertEqual(kitchen.patch("/api/admin/orders/PP-TEST", json={"estado": "pagado"}).status_code, 403)
        self.assertEqual(kitchen.patch("/api/admin/orders/PP-TEST", json={"estado": "listo"}).status_code, 200)
        self.assertEqual(cashier.patch("/api/admin/orders/PP-TEST", json={"estado": "pagado"}).status_code, 400)
        self.assertEqual(cashier.patch("/api/admin/orders/PP-TEST", json={"estado": "entregado"}).status_code, 200)
        self.assertEqual(cashier.patch("/api/admin/orders/PP-TEST", json={"estado": "pagado"}).status_code, 200)
        for worker in (kitchen, cashier):
            for endpoint in ("staff", "audit", "backups", "pilot", "indicators", "catalog", "dashboard"):
                self.assertEqual(worker.get(f"/api/admin/{endpoint}").status_code, 403, endpoint)

    def test_hu10_disable_and_password_change_revoke_sessions(self):
        worker, user = self.employee("cocina")
        response = self.client.patch(f"/api/admin/staff/{user['id']}", json={"activo": False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(worker.get("/api/admin/orders").status_code, 401)
        self.assertEqual(self.login(worker, user["email"], "clave-personal-123").status_code, 401)
        self.client.patch(f"/api/admin/staff/{user['id']}", json={"activo": True})
        self.login(worker, user["email"], "clave-personal-123")
        self.client.patch(f"/api/admin/staff/{user['id']}", json={"password": "otra-clave-segura-456"})
        self.assertEqual(worker.get("/api/admin/orders").status_code, 401)
        self.assertEqual(self.login(worker, user["email"], "otra-clave-segura-456").status_code, 200)

    def test_hu10_reject_escalation_and_invalid_accounts(self):
        for changes in ({"rol": "admin"}, {"password": "corta"}, {"email": "correo-invalido"}):
            data = {"nombre": "Prueba", "email": "prueba@example.com", "password": "clave-personal-123", "rol": "caja", **changes}
            self.assertEqual(self.client.post("/api/admin/staff", json=data).status_code, 400)
        _, user = self.employee("caja")
        self.assertEqual(self.client.patch(f"/api/admin/staff/{user['id']}", json={"rol": "admin"}).status_code, 400)
        self.assertEqual(self.client.patch(f"/api/admin/staff/{user['id']}", json={"activo": "false"}).status_code, 400)
        duplicate = {"nombre": "Duplicado", "email": user["email"], "password": "clave-personal-123", "rol": "caja"}
        self.assertEqual(self.client.post("/api/admin/staff", json=duplicate).status_code, 409)

    def test_hu10_legacy_user_schema_migrates_without_losing_orders(self):
        self.order()
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("ALTER TABLE usuarios DROP COLUMN activo")
            connection.execute("ALTER TABLE usuarios DROP COLUMN session_version")
        migrated = create_app(f"sqlite:///{self.database.as_posix()}", {"TESTING": True, "CSRF_ENABLED": False})
        client = migrated.test_client()
        self.assertEqual(self.login(client).status_code, 200)
        self.assertEqual(client.get("/api/admin/orders").get_json()["pedidos"][0]["codigo"], "PP-TEST")
        with migrated.app_context():
            self.assertTrue(UsuarioDB.query.first().activo)
            db.session.remove()
            db.engine.dispose()

    def test_hu14_inventory_actor_before_after_and_atomic_rollback(self):
        item = self.client.get("/api/admin/inventory").get_json()["ingredientes"][0]
        url = f"/api/admin/inventory/ingrediente/{item['item_id']}"
        self.assertEqual(self.client.put(url, json={"cantidad": 45, "unidad": item["unidad"]}).status_code, 200)
        rows = self.client.get(f"/api/admin/audit?entidad=inventario&entidad_id={item['item_id']}").get_json()["registros"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cambios"]["cantidad"], {"antes": 100.0, "despues": 45.0})
        self.assertIsNotNone(rows[0]["usuario_id"])
        self.assertEqual(rows[0]["rol"], "admin")
        self.assertEqual(self.client.put(url, json={"cantidad": -1, "unidad": item["unidad"]}).status_code, 400)
        self.assertEqual(len(self.client.get(f"/api/admin/audit?entidad=inventario&entidad_id={item['item_id']}").get_json()["registros"]), 1)
        with self.app.app_context():
            before = AuditoriaDB.query.count()
            stock = InventarioDB.query.filter_by(item_id=item["item_id"]).first()
            stock.cantidad = 12
            db.session.flush()
            db.session.rollback()
            self.assertEqual(AuditoriaDB.query.count(), before)
            self.assertEqual(InventarioDB.query.filter_by(item_id=item["item_id"]).first().cantidad, 45)

    def test_hu14_catalog_states_and_credentials_excluded(self):
        self.order()
        kitchen, _ = self.employee("cocina")
        kitchen.patch("/api/admin/orders/PP-TEST", json={"estado": "listo"})
        catalog = self.client.get("/api/admin/catalog").get_json()
        pizza_id = catalog["pizzas"][0]["id"]
        self.client.patch(f"/api/admin/pizzas/{pizza_id}/visibility", json={"activo": False})
        rows = self.client.get("/api/admin/audit").get_json()["registros"]
        self.assertTrue(any(row["entidad"] == "pizzas" for row in rows))
        changed = next(row for row in rows if row["entidad"] == "pedidos" and row["operacion"] == "actualizar")
        self.assertEqual(changed["rol"], "cocina")
        serialized = json.dumps(rows)
        for secret in ("password", "password_hash", "clave-personal-123", "csrf_token", "secret_key"):
            self.assertNotIn(secret, serialized.lower())
        self.assertEqual(self.client.delete(f"/api/admin/audit/{rows[0]['id']}").status_code, 405)

    def test_hu15_protocol_results_defects_and_frozen_decision(self):
        pilot = self.pilot()
        decision = {"decision": "aceptado", "representante_negocio": "Representante de prueba", "conclusion": "Prueba técnica automatizada"}
        self.assertEqual(self.client.post(f"/api/admin/pilot/{pilot}/decision", json=decision).status_code, 409)
        result = {"caso_id": "P01", "participante": "P001", "resultado": "fallido", "evidencia": "Evidencia de prueba", "defecto": "Pago duplicado", "responsable_correccion": "Responsable de prueba"}
        response = self.client.post(f"/api/admin/pilot/{pilot}/results", json=result)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.post(f"/api/admin/pilot/{pilot}/decision", json=decision).status_code, 409)
        identifier = response.get_json()["resultado"]["id"]
        self.assertEqual(self.client.patch(f"/api/admin/pilot/results/{identifier}", json={"evidencia_correccion": "Repetición correcta del caso"}).status_code, 200)
        closed = self.client.post(f"/api/admin/pilot/{pilot}/decision", json=decision)
        self.assertEqual(closed.status_code, 200)
        self.assertTrue(closed.get_json()["piloto"]["acta"]["resultados"][0]["resuelto"])
        self.assertEqual(self.client.post(f"/api/admin/pilot/{pilot}/decision", json=decision).status_code, 409)
        self.assertEqual(self.client.post(f"/api/admin/pilot/{pilot}/results", json=result).status_code, 409)

    def test_hu15_requires_evidence_and_correction_owner(self):
        pilot = self.pilot()
        base = {"caso_id": "P01", "participante": "P001", "resultado": "fallido", "evidencia": "", "defecto": "Fallo"}
        self.assertEqual(self.client.post(f"/api/admin/pilot/{pilot}/results", json=base).status_code, 400)
        base.update(evidencia="Prueba", responsable_correccion="Responsable")
        base["caso_id"] = "INEXISTENTE"
        self.assertEqual(self.client.post(f"/api/admin/pilot/{pilot}/results", json=base).status_code, 400)
        self.assertEqual(self.client.post(f"/api/admin/pilot/{pilot}/decision", json={"decision": "rechazado", "conclusion": "Falla", "representante_negocio": "Prueba"}).status_code, 400)

    def test_hu18_weighted_indicators_denominators_and_comparison(self):
        self.assertEqual(self.observation().status_code, 201)
        self.assertEqual(self.observation(pedidos=30, errores=3, completos=27, minutos_totales=60, pedidos_cronometrados=20).status_code, 201)
        self.assertEqual(self.observation(fase="despues", fecha="2026-10-02", errores=1, completos=9, minutos_totales=20).status_code, 201)
        report = self.client.get("/api/admin/indicators").get_json()
        before = report["comparacion"]["antes"]
        self.assertEqual(before["tasa_errores"], {"numerador": 5, "denominador": 40, "valor": 12.5})
        self.assertEqual(before["tiempo_medio_minutos"]["valor"], 3.67)
        self.assertEqual(report["comparacion"]["diferencias"]["tasa_errores"], -2.5)
        self.assertEqual(report["comparacion"]["muestras_sin_par"], 0)

    def test_hu18_exclusions_unmatched_strata_and_empty_denominators(self):
        response = self.observation()
        identifier = response.get_json()["medicion"]["id"]
        self.observation(fase="despues", turno="noche")
        report = self.client.get("/api/admin/indicators").get_json()
        self.assertEqual(report["comparacion"]["muestras_sin_par"], 2)
        self.assertIsNone(report["comparacion"]["diferencias"]["completitud"])
        self.assertEqual(self.client.patch(f"/api/admin/indicators/{identifier}/exclusion", json={"excluida": True, "motivo_exclusion": "Muestra incompleta"}).status_code, 200)
        report = self.client.get("/api/admin/indicators").get_json()
        self.assertEqual(report["excluidas"], 1)
        self.assertEqual(report["total"], 2)
        self.assertIsNone(report["fases"]["antes"]["tasa_errores"]["valor"])

    def test_hu18_reject_invalid_denominators_nan_and_preserve_anonymous_export(self):
        for values in ({"errores": 11}, {"insumos_exactos": 8}, {"minutos_totales": float("nan")}, {"pedidos": True}, {"pedidos_cronometrados": 0}, {"excluida": True}):
            self.assertEqual(self.observation(**values).status_code, 400, values)
        self.assertEqual(self.observation(condiciones="=SUM(A1)").status_code, 201)
        response = self.client.get("/api/admin/indicators/export")
        csv = response.data.decode("utf-8-sig")
        self.assertIn("'=sum(a1)", csv)
        self.assertNotIn("registrado_por", csv)
        self.assertNotIn("password", csv)

    def test_hu11_backup_and_trial_restore_include_orders_catalog_and_images(self):
        self.order()
        self.uploads.mkdir()
        (self.uploads / "prueba.png").write_bytes(b"imagen-prueba")
        with self.app.app_context():
            item = MenuItemDB.query.first()
            item.imagen = "/api/uploads/prueba.png"
            db.session.commit()
        response = self.client.post("/api/admin/backups")
        self.assertEqual(response.status_code, 201, response.get_json())
        filename = response.get_json()["copia"]["archivo"]
        result = self.client.post(f"/api/admin/backups/{filename}/verify").get_json()["verificacion"]
        self.assertEqual(result["conteos"]["pedidos"], 1)
        self.assertEqual(result["imagenes"], 1)
        self.assertTrue(result["cumple_rpo"] and result["cumple_rto"])
        with self.client.get(f"/api/admin/backups/{filename}/download") as downloaded:
            self.assertEqual(downloaded.status_code, 200)
        self.assertIsNotNone(self.client.get("/api/admin/backups").get_json()["copias"][0]["verificacion"])

    def test_hu11_restore_recovers_data_preserves_originals_and_revokes_sessions(self):
        self.order()
        copy = create_backup(self.database, self.uploads, self.backups)
        with self.app.app_context():
            order = PedidoDB.query.first()
            order.estado = "pagado"
            db.session.commit()
            version = UsuarioDB.query.filter_by(rol="admin").first().session_version
            db.session.remove()
            db.engine.dispose()
        result = restore_backup(self.backups / copy["archivo"], self.root, self.database, self.uploads)
        self.assertTrue(result["restaurada"])
        self.assertTrue(Path(result["original_sqlite"]).is_file())
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT estado FROM pedidos").fetchone()[0], "en_preparacion")
            self.assertGreater(connection.execute("SELECT session_version FROM usuarios WHERE rol='admin'").fetchone()[0], version)
        self.assertEqual(self.client.get("/api/admin/orders").status_code, 401)

    def test_hu11_corrupt_zip_missing_image_and_active_server_are_rejected(self):
        broken = self.root / "corrupt.zip"
        broken.write_bytes(b"no-es-zip")
        with self.assertRaises(ValueError):
            verify_backup(broken)
        with self.app.app_context():
            row = MenuItemDB.query.first()
            row.imagen = "/api/uploads/ausente.png"
            db.session.commit()
        with self.assertRaises(ValueError):
            create_backup(self.database, self.uploads, self.backups)
        with maintenance_lock(self.root):
            with self.assertRaises(ValueError):
                restore_backup(broken, self.root, self.database, self.uploads)

    def test_hu11_zip_traversal_and_altered_checksum_are_rejected(self):
        copy = create_backup(self.database, self.uploads, self.backups)
        original = self.backups / copy["archivo"]
        with zipfile.ZipFile(original) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        damaged = self.root / "altered.zip"
        entries["database.sqlite3"] += b"alterado"
        with zipfile.ZipFile(damaged, "w") as archive:
            for name, contents in entries.items():
                archive.writestr(name, contents)
        with self.assertRaises(ValueError):
            verify_backup(damaged)
        manifest = {"version": 1, "creado_en": datetime.now(timezone.utc).isoformat(), "archivos": {"../escape": {}, "database.sqlite3": {}}}
        with zipfile.ZipFile(damaged, "w") as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            archive.writestr("database.sqlite3", b"falso")
            archive.writestr("../escape", b"escape")
        with self.assertRaises(ValueError):
            verify_backup(damaged)
        self.assertFalse((self.root.parent / "escape").exists())

    def test_hu11_failed_install_returns_original_database_and_images(self):
        self.uploads.mkdir()
        (self.uploads / "original.png").write_bytes(b"original")
        copy = create_backup(self.database, self.uploads, self.backups)
        (self.uploads / "posterior.png").write_bytes(b"posterior")
        original_replace = os.replace
        def fail_new_images(source, destination):
            if ".staged-" in str(source) and Path(destination) == self.uploads:
                raise OSError("Fallo de disco simulado")
            return original_replace(source, destination)
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        with patch("backend.backups.os.replace", side_effect=fail_new_images):
            with self.assertRaises(OSError):
                restore_backup(self.backups / copy["archivo"], self.root, self.database, self.uploads)
        self.assertTrue(self.database.is_file())
        self.assertEqual((self.uploads / "posterior.png").read_bytes(), b"posterior")
        self.assertEqual(self.client.get("/api/admin/orders").status_code, 200)

    def test_hu18_zero_denominators_remain_unavailable_and_filters_apply(self):
        response = self.observation(pedidos=0, errores=0, completos=0, pedidos_cronometrados=0, minutos_totales=0)
        self.assertEqual(response.status_code, 201)
        report = self.client.get("/api/admin/indicators?desde=2026-10-01&hasta=2026-10-01&turno=tarde").get_json()
        self.assertIsNone(report["fases"]["antes"]["tasa_errores"]["valor"])
        self.assertEqual(report["fases"]["antes"]["exactitud_inventario"]["valor"], 80)
        self.assertEqual(self.client.get("/api/admin/indicators?desde=2026-10-02").get_json()["total"], 0)

    def test_security_csrf_protects_existing_and_new_writes(self):
        self.app.config["CSRF_ENABLED"] = True
        self.assertEqual(self.client.post("/api/admin/staff", json={}).status_code, 403)
        token = self.client.get("/api/auth/csrf").get_json()["csrf_token"]
        response = self.client.post("/api/admin/staff", json={"nombre": "Prueba", "email": "csrf@example.com", "password": "contraseña-larga-prueba", "rol": "caja"}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(self.client.get("/api/admin/staff").headers["Cache-Control"], "no-store")

    def test_hu17_wsgi_frontend_and_persistent_restart(self):
        dist = self.root / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<h1>Pizza Pronto</h1>", encoding="utf-8")
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/missing").status_code, 404)
        self.employee("caja")
        removed = self.client.delete("/api/admin/menu-items/pan-ajo")
        self.assertEqual(removed.status_code, 200)
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        other = create_app(f"sqlite:///{self.database.as_posix()}", {"TESTING": True, "CSRF_ENABLED": False})
        with other.app_context():
            self.assertIsNotNone(UsuarioDB.query.filter_by(email="caja@example.com").first())
            self.assertIsNone(db.session.get(MenuItemDB, "pan-ajo"))
            db.session.remove()
            db.engine.dispose()

    def test_hu17_production_requires_private_secret(self):
        with patch.dict(os.environ, {"PIZZA_PRONTO_ENV": "production", "PIZZA_PRONTO_SECRET_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
                create_app("sqlite://")

    def test_hu17_production_cookie_and_no_default_password(self):
        values = {"PIZZA_PRONTO_ENV": "production", "PIZZA_PRONTO_SECRET_KEY": "s" * 64, "FLASK_DEBUG": "1",
                  "PIZZA_PRONTO_ADMIN_PASSWORD": "clave-privada-productiva", "PIZZA_PRONTO_ADMIN_EMAIL": "prod@example.com"}
        with patch.dict(os.environ, values):
            productive = create_app("sqlite://", {"CSRF_ENABLED": True})
            client = productive.test_client()
            response = client.get("/api/auth/csrf", base_url="https://localhost")
            cookie = response.headers["Set-Cookie"]
            self.assertIn("HttpOnly", cookie)
            self.assertIn("Secure", cookie)
            self.assertIn("SameSite=Lax", cookie)
            self.assertFalse(productive.debug)
            self.assertEqual(client.post("/api/auth/login", json={}).status_code, 403)
            with productive.app_context():
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
