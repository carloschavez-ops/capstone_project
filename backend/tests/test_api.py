import unittest

from backend.app import create_app
from backend.models import PedidoDB
from modelos import db


class PizzaApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("sqlite://")
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def test_catalog_and_invalid_recipe(self):
        catalog_response = self.client.get("/api/catalog")
        self.assertEqual(catalog_response.status_code, 200)
        self.assertTrue(catalog_response.get_json()["pizzas"])

        quote_response = self.client.post("/api/quote", json={"ingredientes": []})
        self.assertEqual(quote_response.status_code, 422)
        self.assertTrue(quote_response.get_json()["errores"])

    def test_order_is_persisted_and_price_is_server_calculated(self):
        pizza = self.client.get("/api/catalog").get_json()["pizzas"][0]
        response = self.client.post("/api/orders", json={
            "cliente": {
                "nombre": "Cliente de prueba",
                "telefono": "999111222",
                "tipo_entrega": "domicilio",
                "direccion": "Calle de prueba 123",
            },
            "metodo_pago": "efectivo",
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
        with self.app.app_context():
            self.assertIsNotNone(PedidoDB.query.filter_by(codigo=saved_order["codigo"]).first())


if __name__ == "__main__":
    unittest.main()