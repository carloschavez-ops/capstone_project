import json
import time
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import backend.tests.test_operations as operation_fixtures
from backend.inventory import build_consumption_plan
from backend.inventory_models import MovimientoStockDB, PagoDB, RecetaConsumoDB
from backend.models import InventarioDB, PedidoDB
from modelos import IngredienteDB, MenuItemDB, db


class RemainingHuTests(unittest.TestCase):
    setUp = operation_fixtures.OperationsTests.setUp
    tearDown = operation_fixtures.OperationsTests.tearDown
    login = operation_fixtures.OperationsTests.login
    employee = operation_fixtures.OperationsTests.employee
    pilot = operation_fixtures.OperationsTests.pilot

    def place(self, items=None):
        response = self.client.post('/api/orders', json={
            'cliente': {'nombre': 'Prueba', 'telefono': '999111222', 'tipo_entrega': 'retiro_local'},
            'items': items or [{'menu_item_id': 'pan-ajo', 'cantidad': 2}],
            'metodo_pago': 'efectivo', 'paga_con': 1000})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['pedido']

    def advance(self, code, state, **values):
        return self.client.patch(f'/api/admin/orders/{code}', json={'estado': state, **values})

    def test_hu06_state_times_and_once_only_payment(self):
        self.app.config['PREPARATION_START_DELAY_SECONDS'] = 3600
        order = self.place()
        code = order['codigo']
        self.assertEqual(self.advance(code, 'pagado').status_code, 400)
        for state in ['en_preparacion', 'listo', 'entregado', 'pagado']:
            self.assertEqual(self.advance(code, state).status_code, 200)
            self.assertEqual(self.advance(code, state).status_code, 200)
        result = self.client.get(f'/api/orders/{code}').get_json()['pedido']
        self.assertTrue(all(result[key] for key in ['preparacion_inicio_en', 'listo_en', 'entregado_en', 'pagado_en']))
        self.assertTrue(all(result[key].endswith('+00:00') for key in ['preparacion_inicio_en', 'listo_en', 'entregado_en', 'pagado_en']))
        with self.app.app_context():
            self.assertEqual(PagoDB.query.count(), 1)
            self.assertEqual(MovimientoStockDB.query.filter_by(tipo='consumo').count(), 3)
        self.assertEqual(self.advance(code, 'anulado', motivo='Prueba').status_code, 400)

    def test_hu06_automatic_start_respects_configured_delay(self):
        order = self.place()
        self.assertEqual(self.client.put('/api/admin/order-settings', json={'inicio_segundos': 3600, 'minutos_por_pizza': 12}).status_code, 200)
        self.assertEqual(self.client.get('/api/admin/orders').get_json()['pedidos'][0]['estado'], 'recibido')
        with self.app.app_context():
            row = PedidoDB.query.filter_by(codigo=order['codigo']).first()
            row.creado_en = datetime.now(timezone.utc) - timedelta(seconds=3601)
            db.session.commit()
        response = self.client.get('/api/admin/orders').get_json()
        self.assertEqual(response['pedidos'][0]['estado'], 'en_preparacion')
        self.assertEqual(response['tiempos']['minutos_por_pizza'], 12)

    def test_hu08_compatible_conversion_and_rejection_without_change(self):
        inventory = self.client.get('/api/admin/inventory').get_json()['ingredientes']
        stock = next(row for row in inventory if row['nombre'] == 'Mantequilla')
        url = f"/api/admin/inventory/ingrediente/{stock['item_id']}"
        response = self.client.put(url, json={'cantidad': 500, 'unidad': 'g'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['item']['cantidad'], .5)
        self.assertEqual(response.get_json()['item']['unidad'], 'kg')
        for value, unit in [(1, 'ml'), (-2, 'kg'), ('abc', 'kg'), (True, 'kg'), (float('nan'), 'kg')]:
            self.assertEqual(self.client.put(url, json={'cantidad': value, 'unidad': unit}).status_code, 400)
        with self.app.app_context():
            self.assertEqual(InventarioDB.query.filter_by(item_id=stock['item_id']).first().cantidad, .5)

    def test_hu09_all_catalog_and_custom_ingredients_have_valid_recipes(self):
        with self.app.app_context():
            for item in MenuItemDB.query.all():
                sizes = ['personal', 'mediana', 'familiar'] if item.es_pizza and item.precio_mediana is not None and item.precio_familiar is not None else [None]
                for size in sizes:
                    plan = build_consumption_plan([{'menu_item_id': item.id, 'tamano_id': size, 'cantidad': 1}])
                    self.assertTrue(plan, item.id)
                    self.assertTrue(all(part['cantidad'] > 0 for part in plan))
            for ingredient in IngredienteDB.query.all():
                for size in ['personal', 'mediana', 'familiar']:
                    self.assertTrue(build_consumption_plan([{'ingredientes_ids': [ingredient.id], 'tamano_id': size, 'cantidad': 1}]))

    def test_hu09_insufficient_stock_never_partial_and_reversal_is_once(self):
        order = self.place()
        with self.app.app_context():
            row = PedidoDB.query.filter_by(codigo=order['codigo']).first()
            plan = json.loads(row.plan_consumo_json)
            identifiers = [entry['insumo_id'] for entry in plan]
            stock = InventarioDB.query.filter_by(item_id=identifiers[-1]).first()
            stock.cantidad = 0
            db.session.commit()
            initial = {item.item_id: item.cantidad for item in InventarioDB.query.filter(InventarioDB.item_id.in_(identifiers)).all()}
        self.assertEqual(self.advance(order['codigo'], 'en_preparacion').status_code, 409)
        with self.app.app_context():
            self.assertEqual(MovimientoStockDB.query.count(), 0)
            self.assertEqual(initial, {item.item_id: item.cantidad for item in InventarioDB.query.filter(InventarioDB.item_id.in_(identifiers)).all()})
            InventarioDB.query.filter_by(item_id=identifiers[-1]).first().cantidad = 100
            db.session.commit()
            initial[identifiers[-1]] = 100
        self.assertEqual(self.advance(order['codigo'], 'en_preparacion').status_code, 200)
        self.assertEqual(self.advance(order['codigo'], 'en_preparacion').status_code, 200)
        self.assertEqual(self.advance(order['codigo'], 'anulado', motivo='Cancelación de prueba').status_code, 200)
        self.assertEqual(self.advance(order['codigo'], 'anulado', motivo='Repetición').status_code, 200)
        with self.app.app_context():
            self.assertEqual(MovimientoStockDB.query.filter_by(tipo='consumo').count(), len(plan))
            self.assertEqual(MovimientoStockDB.query.filter_by(tipo='reversion').count(), len(plan))
            self.assertEqual(initial, {item.item_id: item.cantidad for item in InventarioDB.query.filter(InventarioDB.item_id.in_(identifiers)).all()})

    def test_hu09_order_keeps_recipe_snapshot_when_recipe_is_edited(self):
        order = self.place()
        with self.app.app_context():
            original = PedidoDB.query.filter_by(codigo=order['codigo']).first().plan_consumo_json
            recipe = db.session.get(RecetaConsumoDB, 'menu:pan-ajo:unico')
            part = json.loads(recipe.componentes_json)[0]
        response = self.client.put('/api/admin/recipes/menu:pan-ajo:unico', json={'componentes': [{**part, 'cantidad': 10}]})
        self.assertEqual(response.status_code, 200)
        self.advance(order['codigo'], 'en_preparacion')
        with self.app.app_context():
            self.assertEqual(PedidoDB.query.filter_by(codigo=order['codigo']).first().plan_consumo_json, original)
        self.assertEqual(self.client.put('/api/admin/recipes/menu:pan-ajo:unico', json={'componentes': [{**part, 'cantidad': 1, 'unidad': 'kg'}]}).status_code, 400)

    def test_hu09_competing_orders_cannot_overdraw_the_last_stock(self):
        first, second = self.place(), self.place()
        with self.app.app_context():
            bread = InventarioDB.query.filter_by(nombre='Pan baguette').first()
            bread.cantidad = 2
            db.session.commit()
        clients = [self.app.test_client(), self.app.test_client()]
        for client in clients:
            self.login(client)
        barrier, statuses = threading.Barrier(2), []
        def prepare(client, code):
            barrier.wait(timeout=10)
            statuses.append(client.patch(f'/api/admin/orders/{code}', json={'estado': 'en_preparacion'}).status_code)
        threads = [threading.Thread(target=prepare, args=(client, order['codigo'])) for client, order in zip(clients, [first, second])]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(statuses), [200, 409])
        with self.app.app_context():
            self.assertEqual(InventarioDB.query.filter_by(nombre='Pan baguette').first().cantidad, 0)
            self.assertEqual(PedidoDB.query.filter_by(estado='en_preparacion').count(), 1)

    def test_hu07_menu_pizza_prices_visibility_and_deletion_use_catalog_routes(self):
        product = self.client.get('/api/admin/catalog').get_json()['menu_items'][0]
        pizzas = [item for item in self.client.get('/api/admin/catalog').get_json()['menu_items'] if item['es_pizza']]
        product = pizzas[0]
        url = f"/api/admin/menu-items/{product['id']}"
        response = self.client.put(url, data={'nombre': 'Pizza editada', 'descripcion': 'Prueba', 'precio_personal': '20', 'precio_mediana': '30', 'precio_familiar': '40'})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['item']['precios'], {'personal': 20, 'mediana': 30, 'familiar': 40})
        self.assertEqual(self.client.put(url, data={'nombre': 'Pizza editada', 'precio_mediana': 'nan'}).status_code, 400)
        self.assertEqual(self.client.patch(url + '/visibility', json={'activo': False}).status_code, 200)
        self.assertNotIn(product['id'], [item['id'] for item in self.client.get('/api/catalog').get_json()['menu_items']])
        self.assertEqual(self.client.delete(url).status_code, 200)

    def test_hu05_guest_lookup_requires_the_original_guest_session(self):
        customer = {'nombre': 'Invitado de prueba', 'telefono': '999111222', 'tipo_entrega': 'retiro_local'}
        self.client.post('/api/auth/guest', json={'cliente': customer})
        order = self.place()
        other = self.app.test_client()
        other.post('/api/auth/guest', json={'cliente': customer})
        self.assertEqual(other.get(f"/api/orders/{order['codigo']}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/orders/{order['codigo']}").status_code, 200)

    def test_hu12_login_attempt_limit_window_and_success(self):
        self.app.config.update(LOGIN_MAX_ATTEMPTS=2, LOGIN_WINDOW_SECONDS=60)
        base = time.time()
        with patch('backend.security.time.time', return_value=base):
            for _ in range(2):
                self.assertEqual(self.login(password='clave-incorrecta').status_code, 401)
            limited = self.login()
            self.assertEqual(limited.status_code, 429)
            self.assertIn('Retry-After', limited.headers)
        with patch('backend.security.time.time', return_value=base + 61):
            self.assertEqual(self.login().status_code, 200)

    def test_hu12_absolute_and_idle_expiry_even_with_cookie(self):
        for setting in ['SESSION_IDLE_SECONDS', 'SESSION_ABSOLUTE_SECONDS']:
            self.login()
            with self.client.session_transaction() as values:
                values['emitida_en'] = time.time() - (40000 if setting == 'SESSION_ABSOLUTE_SECONDS' else 10)
                values['actividad_en'] = time.time() - (2000 if setting == 'SESSION_IDLE_SECONDS' else 1)
            response = self.client.get('/api/admin/orders')
            self.assertEqual(response.status_code, 401, setting)
            self.assertFalse(self.client.get('/api/auth/me').get_json()['authenticated'])

    def test_hu05_order_lookup_is_restricted_to_owner(self):
        order = self.place()
        other = self.app.test_client()
        other.post('/api/auth/register', json={'nombre': 'Otra persona', 'email': 'otra@example.com', 'password': 'otra-clave-personal'})
        self.assertEqual(other.get(f"/api/orders/{order['codigo']}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/orders/{order['codigo']}").status_code, 200)
        self.assertEqual(self.app.test_client().get(f"/api/orders/{order['codigo']}").status_code, 401)

    def test_hu13_reports_reconcile_orders_cancellations_and_payments(self):
        paid = self.place()
        cancelled = self.place()
        for state in ['en_preparacion', 'listo', 'entregado', 'pagado']:
            self.advance(paid['codigo'], state)
        self.advance(cancelled['codigo'], 'anulado', motivo='Prueba')
        report = self.client.get('/api/admin/reports').get_json()
        self.assertEqual(report['totales']['pedidos'], 2)
        self.assertEqual(report['totales']['anulaciones'], 1)
        self.assertEqual(report['totales']['cobrado'], paid['total'])
        self.assertEqual(report['totales']['pendiente_cobro'], 0)
        filtered = self.client.get('/api/admin/reports?estado=anulado').get_json()
        self.assertEqual(filtered['totales']['pedidos'], 1)
        self.assertEqual(filtered['totales']['cobrado'], 0)
        self.assertEqual(self.client.get('/api/admin/reports?desde=2000-01-01&hasta=2000-01-02').get_json()['totales']['pedidos'], 0)
        self.assertEqual(self.client.get('/api/admin/reports?desde=2026-10-02&hasta=2026-10-01').status_code, 400)
        self.assertEqual(self.client.get('/api/admin/dashboard?estado=anulado').get_json()['resumen']['anulaciones'], 1)

    def test_hu16_usability_percent_has_real_denominator_and_empty_state(self):
        pilot = self.pilot([{'id': 'P06', 'nombre': 'Pedido sin ayuda', 'criterio': 'Completar un pedido.'}])
        report = self.client.get(f'/api/admin/pilot/{pilot}').get_json()['piloto']
        self.assertIsNone(report['usabilidad']['porcentaje'])
        for index in range(5):
            response = self.client.post(f'/api/admin/pilot/{pilot}/results', json={'caso_id': 'P06', 'participante': f'P00{index}', 'resultado': 'aprobado', 'evidencia': 'Prueba automatizada, no participante real', 'sin_ayuda': index < 4})
            self.assertEqual(response.status_code, 201)
        usability = self.client.get(f'/api/admin/pilot/{pilot}').get_json()['piloto']['usabilidad']
        self.assertEqual(usability['participantes'], 5)
        self.assertEqual(usability['porcentaje'], 80)
        self.assertTrue(usability['cumple_meta'])


if __name__ == '__main__':
    unittest.main()
