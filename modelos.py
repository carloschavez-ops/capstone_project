# -*- coding: utf-8 -*-
"""
Tablas de la base de datos: una fila por pizza y una fila por ingrediente.

Guardamos "tags" e "ingredientes" como texto JSON dentro de una sola columna
en vez de crear más tablas de relación — para el tamaño de este proyecto es
más simple de mantener y de leer, y sigue siendo un solo archivo pizza_pronto.db.
"""
import json

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class IngredienteDB(db.Model):
    __tablename__ = "ingredientes"

    id = db.Column(db.String(50), primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    emoji = db.Column(db.String(10), default="🍕")
    grupo = db.Column(db.String(30), nullable=False)
    precio = db.Column(db.Float, default=0.0)
    color = db.Column(db.String(10), default="#cccccc")
    kcal = db.Column(db.Integer, default=30)
    vegano = db.Column(db.Boolean, default=True)
    sin_gluten = db.Column(db.Boolean, default=True)
    sin_lactosa = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "emoji": self.emoji,
            "grupo": self.grupo,
            "precio": self.precio,
            "color": self.color,
            "kcal": self.kcal,
            "vegano": self.vegano,
            "sin_gluten": self.sin_gluten,
            "sin_lactosa": self.sin_lactosa,
        }


class PizzaDB(db.Model):
    __tablename__ = "pizzas"

    id = db.Column(db.String(60), primary_key=True)
    categoria = db.Column(db.String(30), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    descripcion = db.Column(db.Text, default="")
    badge = db.Column(db.String(60), default="")
    badge_tipo = db.Column(db.String(20), default="dop")
    tags_json = db.Column(db.Text, default="[]")
    ingredientes_json = db.Column(db.Text, default="[]")
    precio_personal = db.Column(db.Float, nullable=False)
    precio_mediana = db.Column(db.Float, nullable=False)
    precio_familiar = db.Column(db.Float, nullable=False)
    meta = db.Column(db.String(120), default="Lista en 25 min")
    imagen = db.Column(db.String(300), nullable=True)
    activo = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "categoria": self.categoria,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "badge": self.badge,
            "badge_tipo": self.badge_tipo,
            "tags": json.loads(self.tags_json or "[]"),
            "precios": {
                "personal": self.precio_personal,
                "mediana": self.precio_mediana,
                "familiar": self.precio_familiar,
            },
            "precio_base": self.precio_personal,
            "ingredientes": json.loads(self.ingredientes_json or "[]"),
            "meta": self.meta,
            "imagen": self.imagen,
            "activo": self.activo,
        }


class MenuItemDB(db.Model):
    __tablename__ = "menu_items"
    __table_args__ = (db.Index("ix_menu_items_category_order", "categoria_orden", "orden"),)

    id = db.Column(db.String(80), primary_key=True)
    categoria = db.Column(db.String(60), nullable=False, index=True)
    subcategoria = db.Column(db.String(80), nullable=False, default="")
    nombre = db.Column(db.String(160), nullable=False)
    descripcion = db.Column(db.Text, nullable=False, default="")
    ingredientes_json = db.Column(db.Text, nullable=False, default="[]")
    precio = db.Column(db.Float, nullable=False)
    precio_mediana = db.Column(db.Float, nullable=True)
    precio_familiar = db.Column(db.Float, nullable=True)
    imagen = db.Column(db.String(300), nullable=False, default="")
    es_pizza = db.Column(db.Boolean, nullable=False, default=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    categoria_orden = db.Column(db.Integer, nullable=False, default=0)
    orden = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "categoria": self.categoria,
            "subcategoria": self.subcategoria,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "ingredientes": json.loads(self.ingredientes_json or "[]"),
            "precio": self.precio,
            "precios": {
                "personal": self.precio,
                "mediana": self.precio_mediana,
                "familiar": self.precio_familiar,
            } if self.es_pizza and self.precio_mediana is not None and self.precio_familiar is not None else None,
            "imagen": self.imagen,
            "es_pizza": self.es_pizza,
            "activo": self.activo,
        }