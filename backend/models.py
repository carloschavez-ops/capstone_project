import json
from datetime import datetime, timezone

from modelos import db


def utc_iso(value):
    if value is None:
        return None
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()


class ConfiguracionDB(db.Model):
    __tablename__ = "configuracion"
    clave = db.Column(db.String(80), primary_key=True)
    valor = db.Column(db.String(240), nullable=False)


class UsuarioDB(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default="cliente")
    activo = db.Column(db.Boolean, nullable=False, default=True)
    session_version = db.Column(db.Integer, nullable=False, default=1)
    creado_en = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre, "email": self.email, "rol": self.rol, "activo": self.activo}


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
    stock_minimo = db.Column(db.Float, nullable=False, default=0)
    costo_unitario = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            "item_id": self.item_id,
            "nombre": self.nombre,
            "categoria": self.categoria,
            "cantidad": self.cantidad,
            "unidad": self.unidad,
            "stock_minimo": self.stock_minimo,
            "costo_unitario": self.costo_unitario,
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
    canal = db.Column(db.String(30), nullable=False, default="sitio_web")
    creado_en = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    preparacion_inicio_en = db.Column(db.DateTime, nullable=True)
    listo_en = db.Column(db.DateTime, nullable=True)
    entregado_en = db.Column(db.DateTime, nullable=True)
    pagado_en = db.Column(db.DateTime, nullable=True)
    usuario_id = db.Column(db.Integer, nullable=True, index=True)
    invitado_token = db.Column(db.String(80), nullable=True)
    stock_estado = db.Column(db.String(20), nullable=False, default="pendiente")
    plan_consumo_json = db.Column(db.Text, nullable=False, default="[]")
    problema_preparacion = db.Column(db.String(500), nullable=False, default="")
    anulado_en = db.Column(db.DateTime, nullable=True)
    motivo_anulacion = db.Column(db.String(500), nullable=False, default="")

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
            "canal": self.canal,
            "creado_en": created_at.isoformat(),
            "preparacion_inicio_en": utc_iso(self.preparacion_inicio_en),
            "listo_en": utc_iso(self.listo_en),
            "entregado_en": utc_iso(self.entregado_en),
            "pagado_en": utc_iso(self.pagado_en),
            "stock_estado": self.stock_estado,
            "problema_preparacion": self.problema_preparacion,
            "anulado_en": utc_iso(self.anulado_en),
            "motivo_anulacion": self.motivo_anulacion,
        }


class MermaDB(db.Model):
    __tablename__ = "mermas"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    cantidad = db.Column(db.Float, nullable=False)
    unidad = db.Column(db.String(20), nullable=False)
    motivo = db.Column(db.String(240), nullable=False, default="")
    creado_en = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        created_at = self.creado_en
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return {
            "id": self.id,
            "nombre": self.nombre,
            "cantidad": self.cantidad,
            "unidad": self.unidad,
            "motivo": self.motivo,
            "creado_en": created_at.isoformat(),
        }
