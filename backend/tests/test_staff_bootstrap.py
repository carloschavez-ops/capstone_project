import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlalchemy.pool import NullPool
from werkzeug.security import generate_password_hash

from backend.app import create_app
from backend.models import UsuarioDB
from modelos import db


class StaffBootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)
        self.environment = {
            "PIZZA_PRONTO_ENV": "production",
            "PIZZA_PRONTO_SECRET_KEY": "s" * 64,
            "PIZZA_PRONTO_ADMIN_PASSWORD": "admin-prueba-privada",
            "PIZZA_PRONTO_DATA_DIR": str(self.data),
            "PIZZA_PRONTO_UPLOAD_DIR": str(self.data / "uploads"),
        }
        isolated = {key: value for key, value in os.environ.items() if not key.startswith("PIZZA_PRONTO_")}
        overrides = patch.dict(os.environ, {**isolated, **self.environment}, clear=True)
        overrides.start()
        self.addCleanup(overrides.stop)

    def start(self, database_uri=None):
        return create_app(database_uri, {"SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": NullPool}})

    def login(self, app, email, password):
        client = app.test_client()
        csrf = client.get("/api/auth/csrf", base_url="https://localhost").get_json()["csrf_token"]
        response = client.post("/api/auth/login", base_url="https://localhost",
                               headers={"X-CSRF-Token": csrf},
                               json={"email": email, "password": password})
        return client, response

    def test_fresh_production_install_creates_and_authenticates_all_three_roles(self):
        app = self.start()
        kitchen_password = (self.data / ".cocina-password").read_text(encoding="utf-8").strip()
        cashier_password = (self.data / ".caja-password").read_text(encoding="utf-8").strip()
        self.assertNotEqual(kitchen_password, cashier_password)
        admin, response = self.login(app, "pizzapronto@gmail.com", self.environment["PIZZA_PRONTO_ADMIN_PASSWORD"])
        self.assertEqual(response.status_code, 200)
        kitchen, response = self.login(app, "cocina@pizzapronto.test", kitchen_password)
        self.assertEqual(response.status_code, 200)
        cashier, response = self.login(app, "caja@pizzapronto.test", cashier_password)
        self.assertEqual(response.status_code, 200)
        with app.app_context():
            self.assertEqual({user.rol for user in UsuarioDB.query.all()}, {"admin", "cocina", "caja"})
        self.assertEqual(admin.get("/api/admin/staff", base_url="https://localhost").status_code, 200)
        self.assertEqual(kitchen.get("/api/admin/inventory", base_url="https://localhost").status_code, 200)
        self.assertEqual(cashier.get("/api/admin/orders", base_url="https://localhost").status_code, 200)
        self.assertEqual(cashier.get("/api/admin/inventory", base_url="https://localhost").status_code, 403)
        self.assertEqual(kitchen.get("/api/admin/staff", base_url="https://localhost").status_code, 403)

    def test_restart_preserves_credentials_and_disabled_accounts(self):
        app = self.start()
        kitchen_file = self.data / ".cocina-password"
        saved_password = kitchen_file.read_bytes()
        with app.app_context():
            kitchen = UsuarioDB.query.filter_by(rol="cocina").one()
            kitchen.activo = False
            kitchen.password_hash = generate_password_hash("clave-ya-actualizada")
            kitchen.session_version += 1
            db.session.commit()
            saved_state = kitchen.id, kitchen.activo, kitchen.password_hash, kitchen.session_version
        with patch.dict(os.environ, {"PIZZA_PRONTO_COCINA_PASSWORD": "clave-nueva-no-aplicada"}):
            restarted = self.start()
        with restarted.app_context():
            kitchen = UsuarioDB.query.filter_by(rol="cocina").one()
            self.assertEqual((kitchen.id, kitchen.activo, kitchen.password_hash, kitchen.session_version), saved_state)
            self.assertEqual(UsuarioDB.query.count(), 3)
        self.assertEqual(kitchen_file.read_bytes(), saved_password)

    def test_existing_accounts_stay_intact_and_only_missing_role_is_created(self):
        # Simula la base de una versión anterior con administrador y cocina.
        previous = self.start(f"sqlite:///{(self.data / 'pizza_pronto.db').as_posix()}")
        with previous.app_context():
            kitchen = UsuarioDB(nombre="Cocina del local", email="cocina@example.com", rol="cocina",
                                password_hash=generate_password_hash("clave-cocina-del-local"))
            db.session.add(kitchen)
            db.session.commit()
            original = kitchen.id, kitchen.password_hash
        with patch.dict(os.environ, {"PIZZA_PRONTO_CAJA_EMAIL": " CAJA@EXAMPLE.COM ",
                                     "PIZZA_PRONTO_CAJA_PASSWORD": "clave-caja-del-local"}):
            current = self.start()
        with current.app_context():
            kitchen = UsuarioDB.query.filter_by(rol="cocina").one()
            self.assertEqual((kitchen.id, kitchen.password_hash), original)
            self.assertEqual(UsuarioDB.query.filter_by(rol="caja").one().email, "caja@example.com")
        self.assertFalse((self.data / ".caja-password").exists())
        _, response = self.login(current, "caja@example.com", "clave-caja-del-local")
        self.assertEqual(response.status_code, 200)

    def test_existing_client_email_is_never_promoted(self):
        previous = self.start(f"sqlite:///{(self.data / 'pizza_pronto.db').as_posix()}")
        with previous.app_context():
            db.session.add(UsuarioDB(nombre="Cliente", email="Caja@PizzaPronto.test", rol="cliente",
                                     password_hash=generate_password_hash("clave-cliente-prueba")))
            db.session.commit()
        with self.assertRaisesRegex(RuntimeError, "PIZZA_PRONTO_CAJA_EMAIL"):
            self.start()
        with previous.app_context():
            self.assertEqual(UsuarioDB.query.filter_by(email="Caja@PizzaPronto.test").one().rol, "cliente")
            self.assertEqual(UsuarioDB.query.filter(UsuarioDB.rol.in_(("caja", "cocina"))).count(), 0)
