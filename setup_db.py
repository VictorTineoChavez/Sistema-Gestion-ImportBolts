from app import app, db
from models import User, Product, Category

with app.app_context():
    # 1. Borrar todo y crear de nuevo
    db.drop_all()
    db.create_all()
    print(">>> Base de datos reiniciada.")
    
    # 2. CREAR USUARIOS (Con Nombres Completos)
    admin = User(
        username='admin', 
        password='123', 
        nombre_completo='Administrador General', # <--- Nuevo Campo
        role='admin'
    )
    
    jefe_ventas = User(
        username='jefe', 
        password='123', 
        nombre_completo='Roberto Gómez (Jefe Ventas)', 
        role='administracion'
    )
    
    vendedor = User(
        username='juan', 
        password='123', 
        nombre_completo='Juan Pérez (Vendedor)', 
        role='vendedor'
    )
    
    almacen = User(
        username='pedro', 
        password='123', 
        nombre_completo='Pedro Castillo (Almacén)', 
        role='almacen'
    )
    
    db.session.add_all([admin, jefe_ventas, vendedor, almacen])
    
    # 3. CREAR CATEGORÍAS INICIALES
    cats = [
        Category(nombre='Pernos', prefijo='PER', contador=0),
        Category(nombre='Tuercas', prefijo='TUE', contador=0),
        Category(nombre='Arandelas', prefijo='ARA', contador=0),
        Category(nombre='Abrazaderas', prefijo='ABR', contador=0),
        Category(nombre='Remaches', prefijo='REM', contador=0),
        Category(nombre='Clavos', prefijo='CLA', contador=0)
    ]
    db.session.add_all(cats)
    
    db.session.commit()
    print(">>> Usuarios y Categorías creadas exitosamente.")