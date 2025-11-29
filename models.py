from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# --- 1. CATEGORÍAS (NUEVO) ---
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    prefijo = db.Column(db.String(5), unique=True, nullable=False) # Ej: PER
    contador = db.Column(db.Integer, default=0) # Para el SKU automático

# --- 2. USUARIOS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False) # Para loguearse
    password = db.Column(db.String(100), nullable=False)
    nombre_completo = db.Column(db.String(100), nullable=False) # Para documentos (Ej: Juan Pérez)
    role = db.Column(db.String(20), nullable=False) # admin, administracion, almacen, vendedor

# --- 3. PRODUCTOS ---
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), nullable=False) 
    stock_actual = db.Column(db.Integer, default=0)
    
    # Precios
    unidades_por_caja = db.Column(db.Integer, default=100)
    precio_unidad = db.Column(db.Float, nullable=False)
    precio_docena = db.Column(db.Float, nullable=False)
    precio_caja = db.Column(db.Float, nullable=False)
    costo_referencial = db.Column(db.Float, nullable=False)

# --- 4. KARDEX ---
class ProductMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.now)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tipo = db.Column(db.String(10)) 
    cantidad = db.Column(db.Integer, nullable=False)
    stock_anterior = db.Column(db.Integer)
    stock_nuevo = db.Column(db.Integer)
    motivo = db.Column(db.String(200))

    product = db.relationship('Product', backref='movements')
    user = db.relationship('User', backref='movements')

# --- 5. CLIENTES ---
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    documento = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))

# --- 6. ORDENES ---
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.now)
    cliente_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    estado = db.Column(db.String(20), default='Pendiente')
    
    subtotal = db.Column(db.Float, default=0.0)
    igv = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    
    tipo_entrega = db.Column(db.String(20)) 
    direccion_envio = db.Column(db.String(200))
    fecha_entrega = db.Column(db.Date)
    
    monto_pagado = db.Column(db.Float, default=0.0)
    estado_pago = db.Column(db.String(20), default='Pendiente') 
    
    cliente = db.relationship('Client', backref='orders')
    vendedor = db.relationship('User', backref='orders')

class OrderDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_aplicado = db.Column(db.Float, nullable=False)
    tipo_precio_usado = db.Column(db.String(50))
    subtotal = db.Column(db.Float, nullable=False)
    
    product = db.relationship('Product')
    order = db.relationship('Order', backref='details')

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.now)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    metodo = db.Column(db.String(50))
    nota = db.Column(db.String(200))
    
    order = db.relationship('Order', backref='payments')