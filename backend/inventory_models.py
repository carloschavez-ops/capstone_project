import json
from datetime import datetime, timezone

from modelos import db


class RecetaConsumoDB(db.Model):
    __tablename__ = "recetas_consumo"
    clave = db.Column(db.String(160), primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    componentes_json = db.Column(db.Text, nullable=False)
    origen = db.Column(db.String(40), nullable=False, default="estimacion_demo")
    revision = db.Column(db.Integer, nullable=False, default=1)

    def to_dict(self):
        return {"clave": self.clave, "nombre": self.nombre, "componentes": json.loads(self.componentes_json), "origen": self.origen, "revision": self.revision}


class MovimientoStockDB(db.Model):
    __tablename__ = "movimientos_stock"
    __table_args__ = (db.UniqueConstraint("pedido_id", "insumo_id", "tipo", name="uq_movimiento_pedido_insumo_tipo"),)
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), nullable=False, index=True)
    insumo_id = db.Column(db.String(80), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    cantidad = db.Column(db.Float, nullable=False)
    unidad = db.Column(db.String(20), nullable=False)
    saldo_anterior = db.Column(db.Float, nullable=False)
    saldo_posterior = db.Column(db.Float, nullable=False)
    creado_en = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class PagoDB(db.Model):
    __tablename__ = "pagos"
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), unique=True, nullable=False, index=True)
    importe = db.Column(db.Float, nullable=False)
    metodo = db.Column(db.String(30), nullable=False)
    registrado_en = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    usuario_id = db.Column(db.Integer, nullable=True)
    origen = db.Column(db.String(20), nullable=False, default="caja")
