import unittest
import tempfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

from backend.app import create_app
from backend.models import PedidoDB, UsuarioDB
from modelos import db


class PizzaApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("sqlite://")
        self.upload_dir = tempfile.TemporaryDirectory()
        self.app.config["UPLOAD_FOLDER"] = self.upload_dir.name
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.upload_dir.cleanup()

    def test_catalog_and_invalid_recipe(self):
        catalog_response = self.client.get("/api/catalog")
        self.assertEqual(catalog_response.status_code, 200)
        self.assertTrue(catalog_response.get_json()["pizzas"])
        menu_items = catalog_response.get_json()["menu_items"]
        self.assertEqual(len(menu_items), 118)
        menu_by_id = {item["id"]: item for item in menu_items}
        self.assertEqual(menu_by_id["pan-ajo"]["precio"], 8)
        self.assertEqual(menu_by_id["pizza-cuatro-estaciones"]["ingredientes"][-1], "Salami")
        self.assertEqual(menu_by_id["pizza-nutella"]["subcategoria"], "Italianas · 8 porciones")
        self.assertIn("Coca Cola", {item["nombre"] for item in menu_items if item["subcategoria"] == "300 ml"})
        self.assertNotIn("gaseosa-300ml", menu_by_id)
        soda_names = [item["nombre"] for item in menu_items if item["categoria"] == "Gaseosas"]
        self.assertEqual(soda_names[:4], ["Coca Cola", "Inca Kola", "Fanta", "Sprite"])
        doughs = [item for item in catalog_response.get_json()["ingredientes"] if item["grupo"] == "masa"]
        self.assertEqual([item["nombre"] for item in doughs], ["Masa italiana"])

        quote_response = self.client.post("/api/quote", json={"ingredientes": []})
        self.assertEqual(quote_response.status_code, 422)
        self.assertTrue(quote_response.get_json()["errores"])

    def test_register_login_guest_and_logout(self):
        registration = self.client.post("/api/auth/register", json={
            "nombre": "Ana Prueba",
            "email": "ANA@example.com",
            "password": "una-clave-segura",
        })
        self.assertEqual(registration.status_code, 201)
        self.assertEqual(registration.get_json()["user"]["email"], "ana@example.com")
        with self.app.app_context():
            user = UsuarioDB.query.filter_by(email="ana@example.com").first()
            self.assertIsNotNone(user)
            self.assertNotEqual(user.password_hash, "una-clave-segura")

        duplicate = self.client.post("/api/auth/register", json={
            "nombre": "Otra Ana",
            "email": "ana@example.com",
            "password": "otra-clave-segura",
        })
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)

        failed_login = self.client.post("/api/auth/login", json={
            "email": "ana@example.com",
            "password": "incorrecta",
        })
        self.assertEqual(failed_login.status_code, 401)
        login = self.client.post("/api/auth/login", json={
            "email": "ANA@example.com",
            "password": "una-clave-segura",
        })
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").get_json()["mode"], "account")

        self.client.post("/api/auth/logout")
        guest_customer = {
            "nombre": "Ana Invitada",
            "telefono": "999111222",
            "tipo_entrega": "delivery",
            "direccion": "Calle 1",
            "referencia": "Parque central",
        }
        guest = self.client.post("/api/auth/guest", json={"cliente": guest_customer})
        self.assertEqual(guest.status_code, 200)
        self.assertEqual(guest.get_json()["mode"], "guest")
        current_session = self.client.get("/api/auth/me").get_json()
        self.assertEqual(current_session["mode"], "guest")
        self.assertEqual(current_session["cliente"]["referencia"], "Parque central")
        self.client.post("/api/auth/logout")
        self.assertFalse(self.client.get("/api/auth/me").get_json()["authenticated"])

    def test_order_is_persisted_and_price_is_server_calculated(self):
        self.client.post("/api/auth/guest", json={"cliente": {
            "nombre": "Cliente de prueba",
            "telefono": "999111222",
            "tipo_entrega": "delivery",
            "direccion": "Calle de prueba 123",
            "referencia": "Frente al parque",
            "dni_ruc": "12345678",
        }})
        pizza = self.client.get("/api/catalog").get_json()["pizzas"][0]
        response = self.client.post("/api/orders", json={
            "cliente": {
                "nombre": "Cliente de prueba",
                "telefono": "999111222",
                "tipo_entrega": "delivery",
                "direccion": "Calle de prueba 123",
                "referencia": "Frente al parque",
                "dni_ruc": "12345678",
            },
            "metodo_pago": "efectivo",
            "paga_con": 100,
            "total": 0,
            "items": [{
                "pizza_id": pizza["id"],
                "tamano_id": "mediana",
                "ingredientes": pizza["ingredientes"],
                "cantidad": 1,
            }],
        })

        self.assertEqual(response.status_code, 201, response.get_json())
        saved_order = response.get_json()["pedido"]
        self.assertGreater(saved_order["total"], 0)
        self.assertEqual(saved_order["estimado_minutos"], 8)
        self.assertTrue(saved_order["creado_en"].endswith("+00:00"))
        self.assertEqual(saved_order["paga_con"], 100)
        self.assertEqual(saved_order["vuelto"], round(100 - saved_order["total"], 2))
        self.assertEqual(saved_order["referencia"], "Frente al parque")
        self.assertEqual(saved_order["dni_ruc"], "12345678")
        with self.app.app_context():
            self.assertIsNotNone(PedidoDB.query.filter_by(codigo=saved_order["codigo"]).first())

    def test_menu_item_order_uses_database_price_and_skips_oven_estimate(self):
        customer = {
            "nombre": "Pedido de entrada",
            "telefono": "999111222",
            "tipo_entrega": "retiro_local",
        }
        self.client.post("/api/auth/guest", json={"cliente": customer})
        response = self.client.post("/api/orders", json={
            "cliente": customer,
            "metodo_pago": "efectivo",
            "paga_con": 20,
            "items": [{
                "menu_item_id": "pan-ajo",
                "nombre": "Precio manipulado",
                "precio_unitario": 0.01,
                "cantidad": 2,
            }],
        })

        self.assertEqual(response.status_code, 201, response.get_json())
        order = response.get_json()["pedido"]
        self.assertEqual(order["subtotal"], 16)
        self.assertEqual(order["total"], 16)
        self.assertEqual(order["items"][0]["nombre"], "Pan al Ajo (5 unid.)")
        self.assertFalse(order["items"][0]["es_pizza"])
        self.assertIsNone(order["estimado_minutos"])

        pizza_response = self.client.post("/api/orders", json={
            "cliente": customer,
            "metodo_pago": "efectivo",
            "paga_con": 50,
            "items": [{"menu_item_id": "pizza-nutella", "cantidad": 1}],
        })
        self.assertEqual(pizza_response.status_code, 201, pizza_response.get_json())
        pizza_order = pizza_response.get_json()["pedido"]
        self.assertEqual(pizza_order["total"], 40)
        self.assertEqual(pizza_order["estimado_minutos"], 8)
        self.assertTrue(pizza_order["items"][0]["es_pizza"])

    def test_admin_adds_pizza_image_and_prices_by_size(self):
        login = self.client.post("/api/auth/login", json={
            "email": "pizzapronto@gmail.com",
            "password": "pizzapronto",
        })
        self.assertEqual(login.status_code, 200)
        created = self.client.post("/api/admin/pizzas", data={
            "nombre": "Pizza de prueba",
            "descripcion": "Tomate, mozzarella y albahaca.",
            "tipo": "Italianas · 8 porciones",
            "ingredientes": "Salsa de tomate\nMozzarella\nAlbahaca",
            "precio_personal": "30",
            "precio_mediana": "40",
            "precio_familiar": "50",
            "imagen": (BytesIO(b"\x89PNG\r\n\x1a\nreferential-image"), "pizza.png"),
        }, content_type="multipart/form-data")
        self.assertEqual(created.status_code, 201, created.get_json())
        pizza = created.get_json()["pizza"]
        self.assertEqual(pizza["precios"], {"personal": 30, "mediana": 40, "familiar": 50})
        image_response = self.client.get(pizza["imagen"])
        self.assertEqual(image_response.data, b"\x89PNG\r\n\x1a\nreferential-image")
        image_response.close()
        self.assertIn(pizza["id"], {item["id"] for item in self.client.get("/api/catalog").get_json()["menu_items"]})

        customer = {"nombre": "Cliente", "telefono": "999111222", "tipo_entrega": "retiro_local"}
        ordered = self.client.post("/api/orders", json={
            "cliente": customer,
            "metodo_pago": "efectivo",
            "paga_con": 60,
            "items": [{"menu_item_id": pizza["id"], "tamano_id": "familiar", "cantidad": 1}],
        })
        self.assertEqual(ordered.status_code, 201, ordered.get_json())
        self.assertEqual(ordered.get_json()["pedido"]["items"][0]["precio_unitario"], 50)

    def test_guest_requires_delivery_details_and_persists_local_modes(self):
        missing_details = self.client.post("/api/auth/guest", json={})
        self.assertEqual(missing_details.status_code, 400)

        pizza = self.client.get("/api/catalog").get_json()["pizzas"][0]
        order_items = [{
            "pizza_id": pizza["id"],
            "tamano_id": "mediana",
            "ingredientes": pizza["ingredientes"],
            "cantidad": 1,
        }]
        for customer, expected_type, expected_address in [
            ({"nombre": "Retiro", "telefono": "999111222", "tipo_entrega": "retiro_local"}, "retiro_local", "Av. Manco Cápac 618, Cajamarca 06004"),
            ({"nombre": "En mesa", "telefono": "999111222", "tipo_entrega": "comer_local", "numero_mesa": "8", "dni_ruc": "12345678"}, "comer_local", "Av. Manco Cápac 618, Cajamarca 06004"),
        ]:
            self.client.post("/api/auth/guest", json={"cliente": customer})
            response = self.client.post("/api/orders", json={
                "cliente": customer,
                "paga_con": 100,
                "items": order_items,
            })
            self.assertEqual(response.status_code, 201, response.get_json())
            saved_order = response.get_json()["pedido"]
            self.assertEqual(saved_order["tipo_entrega"], expected_type)
            self.assertEqual(saved_order["direccion"], expected_address)
            if expected_type == "comer_local":
                self.assertEqual(saved_order["numero_mesa"], "8")
                self.assertEqual(saved_order["dni_ruc"], "12345678")

    def test_cash_payment_requires_enough_and_returns_change(self):
        customer = {
            "nombre": "Pago efectivo",
            "telefono": "999111222",
            "tipo_entrega": "delivery",
            "direccion": "Calle de prueba",
            "referencia": "Frente al parque",
        }
        self.client.post("/api/auth/guest", json={"cliente": customer})
        pizza = self.client.get("/api/catalog").get_json()["pizzas"][0]
        items = [{
            "pizza_id": pizza["id"],
            "tamano_id": "personal",
            "ingredientes": pizza["ingredientes"],
            "cantidad": 1,
        }]
        insufficient = self.client.post("/api/orders", json={"cliente": customer, "items": items, "paga_con": 1})
        self.assertEqual(insufficient.status_code, 400)

        quote = self.client.post("/api/quote", json={
            "pizza_id": pizza["id"], "tamano_id": "personal", "ingredientes": pizza["ingredientes"],
        }).get_json()
        payment_amount = quote["total"] + 5
        accepted = self.client.post("/api/orders", json={
            "cliente": customer, "items": items, "paga_con": payment_amount,
        })
        self.assertEqual(accepted.status_code, 201, accepted.get_json())
        saved_order = accepted.get_json()["pedido"]
        self.assertEqual(saved_order["vuelto"], round(payment_amount - saved_order["total"], 2))

    def test_order_requires_a_session(self):
        response = self.client.post("/api/orders", json={})
        self.assertEqual(response.status_code, 401)

    def test_incomplete_legacy_guest_session_must_reenter_details(self):
        with self.client.session_transaction() as current_session:
            current_session["guest"] = True
        response = self.client.get("/api/auth/me")
        self.assertFalse(response.get_json()["authenticated"])

    def test_default_admin_can_manage_inventory_and_pizzas(self):
        login = self.client.post("/api/auth/login", json={
            "email": "pizzapronto@gmail.com",
            "password": "pizzapronto",
        })
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.get_json()["user"]["rol"], "admin")

        inventory = self.client.get("/api/admin/inventory").get_json()
        supply_names = {item["nombre"] for item in inventory["ingredientes"]}
        self.assertEqual(len(inventory["categorias"]), 7)
        self.assertTrue({"Carne de res", "Queso Mozzarella", "Pisco", "Amargo de angostura"}.issubset(supply_names))
        self.assertNotIn("Harina", supply_names)
        self.assertFalse(inventory.get("pizzas"))
        self.assertTrue(all(item["cantidad"] == 100 for item in inventory["ingredientes"]))
        beef = next(item for item in inventory["ingredientes"] if item["nombre"] == "Carne de res")
        self.assertEqual(beef["categoria"], "Carnes, Embutidos y Proteínas")
        updated_stock = self.client.put(
            f"/api/admin/inventory/ingrediente/{beef['item_id']}",
            json={"cantidad": 18.5, "unidad": "kg"},
        )
        self.assertEqual(updated_stock.status_code, 200)
        self.assertEqual(updated_stock.get_json()["item"]["cantidad"], 18.5)

        new_supply = self.client.post("/api/admin/inventory", json={
            "nombre": "Aceite de oliva",
            "cantidad": 4,
            "unidad": "l",
            "categoria": "Salsas, Condimentos e Insumos Secos",
        })
        self.assertEqual(new_supply.status_code, 201)
        self.assertEqual(new_supply.get_json()["item"]["categoria"], "Salsas, Condimentos e Insumos Secos")

        pizza = self.client.get("/api/admin/catalog").get_json()["pizzas"][0]
        pizza_id = pizza["id"]
        edited = self.client.put(f"/api/admin/pizzas/{pizza_id}", json={
            "nombre": "Pizza temporal editada",
            "descripcion": "Receta de prueba",
            "precios": {"personal": 20, "mediana": 30, "familiar": 40},
        })
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.get_json()["pizza"]["nombre"], "Pizza temporal editada")
        hidden = self.client.patch(f"/api/admin/pizzas/{pizza_id}/visibility", json={"activo": False})
        self.assertFalse(hidden.get_json()["pizza"]["activo"])
        public_ids = {item["id"] for item in self.client.get("/api/catalog").get_json()["pizzas"]}
        self.assertNotIn(pizza_id, public_ids)
        self.assertEqual(self.client.delete(f"/api/admin/pizzas/{pizza_id}").status_code, 200)

    def test_admin_can_update_pizza_image_and_public_catalog_reflects_it(self):
        login = self.client.post("/api/auth/login", json={
            "email": "pizzapronto@gmail.com",
            "password": "pizzapronto",
        })
        self.assertEqual(login.status_code, 200)

        pizza_id = self.client.get("/api/admin/catalog").get_json()["pizzas"][0]["id"]
        updated = self.client.put(
            f"/api/admin/pizzas/{pizza_id}",
            data={
                "nombre": "Pizza actualizada",
                "descripcion": "Nueva imagen para la carta",
                "precio_personal": "21",
                "precio_mediana": "31",
                "precio_familiar": "41",
                "imagen": (BytesIO(b"updated-image-data"), "pizza-edited.png"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(updated.status_code, 200, updated.get_json())
        updated_pizza = updated.get_json()["pizza"]
        self.assertEqual(updated_pizza["nombre"], "Pizza actualizada")
        self.assertIn("/api/uploads/", updated_pizza["imagen"])
        image_response = self.client.get(updated_pizza["imagen"])
        try:
            self.assertEqual(image_response.data, b"updated-image-data")
        finally:
            image_response.close()
        self.assertIn("Pizza actualizada", {item["nombre"] for item in self.client.get("/api/catalog").get_json()["pizzas"]})

    def test_customer_cannot_access_admin_routes(self):
        registration = self.client.post("/api/auth/register", json={
            "nombre": "Cliente",
            "email": "cliente@example.com",
            "password": "cliente-seguro",
        })
        self.assertEqual(registration.status_code, 201)
        self.assertEqual(self.client.get("/api/admin/inventory").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/orders").status_code, 403)

    def test_admin_order_queue_estimates_and_status_workflow(self):
        customer = {
            "nombre": "Pedido de prueba",
            "telefono": "999111222",
            "tipo_entrega": "retiro_local",
        }
        self.client.post("/api/auth/guest", json={"cliente": customer})
        pizza = self.client.get("/api/catalog").get_json()["pizzas"][0]
        first = self.client.post("/api/orders", json={
            "cliente": customer,
            "paga_con": 200,
            "items": [{
                "pizza_id": pizza["id"],
                "tamano_id": "personal",
                "ingredientes": pizza["ingredientes"],
                "cantidad": 1,
            }],
        }).get_json()["pedido"]
        second = self.client.post("/api/orders", json={
            "cliente": customer,
            "paga_con": 200,
            "items": [{
                "pizza_id": pizza["id"],
                "tamano_id": "personal",
                "ingredientes": pizza["ingredientes"],
                "cantidad": 1,
            }],
        }).get_json()["pedido"]

        reference_time = datetime.now(timezone.utc).replace(microsecond=0)
        with self.app.app_context():
            first_order = PedidoDB.query.filter_by(codigo=first["codigo"]).first()
            second_order = PedidoDB.query.filter_by(codigo=second["codigo"]).first()
            first_order.creado_en = reference_time - timedelta(seconds=5)
            second_order.creado_en = reference_time
            db.session.commit()

        self.client.post("/api/auth/login", json={
            "email": "pizzapronto@gmail.com",
            "password": "pizzapronto",
        })
        waiting = self.client.get("/api/admin/orders").get_json()["pedidos"]
        waiting_by_code = {order["codigo"]: order for order in waiting}
        self.assertEqual(waiting_by_code[first["codigo"]]["estado"], "recibido")

        with self.app.app_context():
            first_order = PedidoDB.query.filter_by(codigo=first["codigo"]).first()
            first_order.creado_en = reference_time - timedelta(minutes=6)
            db.session.commit()
        listed = self.client.get("/api/admin/orders").get_json()["pedidos"]
        by_code = {order["codigo"]: order for order in listed}
        self.assertEqual(by_code[first["codigo"]]["estado"], "en_preparacion")
        self.assertEqual(by_code[first["codigo"]]["estimado_minutos"], 3)
        self.assertEqual(by_code[second["codigo"]]["estimado_minutos"], 11)

        invalid_transition = self.client.patch(f"/api/admin/orders/{first['codigo']}", json={"estado": "pagado"})
        self.assertEqual(invalid_transition.status_code, 400)
        for state in ("listo", "entregado", "pagado"):
            response = self.client.patch(f"/api/admin/orders/{first['codigo']}", json={"estado": state})
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(response.get_json()["pedido"]["estado"], state)

        refreshed = self.client.get("/api/admin/orders").get_json()["pedidos"]
        remaining = next(order for order in refreshed if order["codigo"] == second["codigo"])
        self.assertEqual(remaining["estimado_minutos"], 8)


if __name__ == "__main__":
    unittest.main()
