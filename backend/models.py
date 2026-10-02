import json
from datetime import datetime, timezone

from modelos import db


class UsuarioDB(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default="cliente")
    creado_en = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre, "email": self.email, "rol": self.rol}


class InventarioDB(db.Model):
    __tablename__ = "inventario"
    __table_args__ = (db.UniqueConstraint("tipo", "item_id", name="uq_inventario_tipo_item"),)

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    item_id = db.Column(db.String(80), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    categoria = db.Column(db.String(80), nullable=False, default="Otros")
    cantidad = db.Column(db.Float, nullable=False, default=0)
    unidad = db.Column(db.String(20), nullable=False, default="unidad")

    def to_dict(self):
        return {
            "item_id": self.item_id,
            "nombre": self.nombre,
            "categoria": self.categoria,
            "cantidad": self.cantidad,
            "unidad": self.unidad,
        }


class PedidoDB(db.Model):
    __tablename__ = "pedidos"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False, index=True)
    cliente = db.Column(db.String(120), nullable=False)
    telefono = db.Column(db.String(40), nullable=False)
    tipo_entrega = db.Column(db.String(20), nullable=False)
    direccion = db.Column(db.String(300), nullable=False, default="")
    referencia = db.Column(db.String(300), nullable=False, default="")
    dni_ruc = db.Column(db.String(30), nullable=False, default="")
    numero_mesa = db.Column(db.String(20), nullable=False, default="")
    metodo_pago = db.Column(db.String(30), nullable=False)
    items_json = db.Column(db.Text, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    delivery = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    paga_con = db.Column(db.Float, nullable=False, default=0)
    vuelto = db.Column(db.Float, nullable=False, default=0)
    estado = db.Column(db.String(30), nullable=False, default="recibido")
    creado_en = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        created_at = self.creado_en
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return {
            "codigo": self.codigo,
            "cliente": self.cliente,
            "telefono": self.telefono,
            "tipo_entrega": self.tipo_entrega,
            "direccion": self.direccion,
            "referencia": self.referencia,
            "dni_ruc": self.dni_ruc,
            "numero_mesa": self.numero_mesa,
            "metodo_pago": self.metodo_pago,
            "items": json.loads(self.items_json),
            "subtotal": self.subtotal,
            "delivery": self.delivery,
            "total": self.total,
            "paga_con": self.paga_con,
            "vuelto": self.vuelto,
            "estado": self.estado,
            "creado_en": created_at.isoformat(),
        }