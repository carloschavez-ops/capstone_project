import json
from datetime import datetime, timezone

from modelos import db


class PedidoDB(db.Model):
    __tablename__ = "pedidos"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False, index=True)
    cliente = db.Column(db.String(120), nullable=False)
    telefono = db.Column(db.String(40), nullable=False)
    tipo_entrega = db.Column(db.String(20), nullable=False)
    direccion = db.Column(db.String(300), nullable=False, default="")
    metodo_pago = db.Column(db.String(30), nullable=False)
    items_json = db.Column(db.Text, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    delivery = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="recibido")
    creado_en = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "codigo": self.codigo,
            "cliente": self.cliente,
            "telefono": self.telefono,
            "tipo_entrega": self.tipo_entrega,
            "direccion": self.direccion,
            "metodo_pago": self.metodo_pago,
            "items": json.loads(self.items_json),
            "subtotal": self.subtotal,
            "delivery": self.delivery,
            "total": self.total,
            "estado": self.estado,
            "creado_en": self.creado_en.isoformat(),
        }