"""Persistencia de HU14, HU15 y HU18. No contiene datos de prueba precargados."""

import json
from datetime import datetime, timezone

from modelos import db


def utcnow():
    return datetime.now(timezone.utc)


def iso(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()


class AuditoriaDB(db.Model):
    __tablename__ = "auditoria"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, nullable=True, index=True)
    actor = db.Column(db.String(140), nullable=False)
    rol = db.Column(db.String(20), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    operacion = db.Column(db.String(40), nullable=False)
    entidad = db.Column(db.String(80), nullable=False, index=True)
    entidad_id = db.Column(db.String(120), nullable=False)
    cambios_json = db.Column(db.Text, nullable=False, default="{}")

    def to_dict(self):
        return {"id": self.id, "usuario_id": self.usuario_id, "actor": self.actor,
                "rol": self.rol, "fecha": iso(self.fecha), "operacion": self.operacion,
                "entidad": self.entidad, "entidad_id": self.entidad_id,
                "cambios": json.loads(self.cambios_json)}


class PilotoDB(db.Model):
    __tablename__ = "pilotos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(160), nullable=False)
    responsable = db.Column(db.String(120), nullable=False)
    creado_en = db.Column(db.DateTime, nullable=False, default=utcnow)
    casos_json = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="abierto")
    acta_json = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre, "responsable": self.responsable,
                "creado_en": iso(self.creado_en), "estado": self.estado,
                "casos": json.loads(self.casos_json),
                "acta": json.loads(self.acta_json) if self.acta_json else None}


class ResultadoPilotoDB(db.Model):
    __tablename__ = "resultados_piloto"
    __table_args__ = (db.UniqueConstraint("piloto_id", "caso_id", "participante", name="uq_resultado_piloto"),)

    id = db.Column(db.Integer, primary_key=True)
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=False, index=True)
    caso_id = db.Column(db.String(40), nullable=False)
    participante = db.Column(db.String(40), nullable=False)
    ejecutor_id = db.Column(db.Integer, nullable=False)
    resultado = db.Column(db.String(20), nullable=False)
    evidencia = db.Column(db.String(1000), nullable=False)
    defecto = db.Column(db.String(1000), nullable=False, default="")
    responsable_correccion = db.Column(db.String(120), nullable=False, default="")
    resuelto = db.Column(db.Boolean, nullable=False, default=False)
    evidencia_correccion = db.Column(db.String(1000), nullable=False, default="")
    sin_ayuda = db.Column(db.Boolean, nullable=False, default=False)
    fecha = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {key: iso(value) if key == "fecha" else value for key, value in
                ((column.name, getattr(self, column.name)) for column in self.__table__.columns)}


class MedicionDB(db.Model):
    __tablename__ = "mediciones_piloto"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(40), unique=True, nullable=False)
    fase = db.Column(db.String(10), nullable=False, index=True)
    fecha = db.Column(db.Date, nullable=False, index=True)
    turno = db.Column(db.String(20), nullable=False)
    modalidad = db.Column(db.String(20), nullable=False)
    condiciones = db.Column(db.String(160), nullable=False)
    pedidos = db.Column(db.Integer, nullable=False)
    errores = db.Column(db.Integer, nullable=False)
    completos = db.Column(db.Integer, nullable=False)
    minutos_totales = db.Column(db.Float, nullable=False)
    pedidos_cronometrados = db.Column(db.Integer, nullable=False)
    insumos_revisados = db.Column(db.Integer, nullable=False)
    insumos_exactos = db.Column(db.Integer, nullable=False)
    excluida = db.Column(db.Boolean, nullable=False, default=False)
    motivo_exclusion = db.Column(db.String(500), nullable=False, default="")
    limitaciones = db.Column(db.String(1000), nullable=False, default="")
    registrado_por = db.Column(db.Integer, nullable=False)
    creado_en = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        result = {column.name: getattr(self, column.name) for column in self.__table__.columns}
        result["fecha"] = self.fecha.isoformat()
        result["creado_en"] = iso(self.creado_en)
        return result
