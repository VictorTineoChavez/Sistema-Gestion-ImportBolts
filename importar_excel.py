from app import app, db
from models import User, Product

# DATOS SIMULADOS (Como si vinieran de un Excel)
productos_excel = [
    # CATEGORIA: PERNOS
    {"sku": "PER-001", "cat": "Pernos", "nom": "Perno Hexagonal 1/2 x 2", "stock": 500, "unit": 2.50, "doc": 2.20, "caja": 1.80},
    {"sku": "PER-002", "cat": "Pernos", "nom": "Perno Carrocero 1/4 x 1", "stock": 1200, "unit": 1.50, "doc": 1.20, "caja": 0.90},
    {"sku": "PER-003", "cat": "Pernos", "nom": "Perno Estructural A325", "stock": 50, "unit": 8.50, "doc": 8.00, "caja": 7.50},
    
    # CATEGORIA: TUERCAS
    {"sku": "TUE-001", "cat": "Tuercas", "nom": "Tuerca Hexagonal 1/2", "stock": 2000, "unit": 0.50, "doc": 0.40, "caja": 0.20},
    {"sku": "TUE-002", "cat": "Tuercas", "nom": "Tuerca de Seguridad 1/4", "stock": 800, "unit": 0.80, "doc": 0.70, "caja": 0.50},
    
    # CATEGORIA: ARANDELAS
    {"sku": "ARA-001", "cat": "Arandelas", "nom": "Arandela Plana Zincada", "stock": 5000, "unit": 0.20, "doc": 0.15, "caja": 0.10},
    {"sku": "ARA-002", "cat": "Arandelas", "nom": "Arandela Presión Negra", "stock": 3000, "unit": 0.30, "doc": 0.25, "caja": 0.15},
    
    # OTRAS CATEGORIAS
    {"sku": "ABR-001", "cat": "Abrazaderas", "nom": "Abrazadera Tipo U 2 pulg", "stock": 150, "unit": 3.50, "doc": 3.00, "caja": 2.50},
    {"sku": "REM-001", "cat": "Remaches", "nom": "Remache Pop 3/16", "stock": 10000, "unit": 0.10, "doc": 0.08, "caja": 0.05},
]

with app.app_context():
    db.drop_all()   # Reiniciamos todo limpio
    db.create_all() # Creamos tablas nuevas con la columna categoria
    
    # Crear Admin
    admin = User(username='admin', password='123', role='admin')
    db.session.add(admin)
    
    # Cargar Productos Masivos
    print(">>> Cargando productos desde lista masiva...")
    for p in productos_excel:
        nuevo = Product(
            sku=p["sku"],
            nombre=p["nom"],
            categoria=p["cat"], # <--- Aqui guardamos la categoria
            stock_actual=p["stock"],
            unidades_por_caja=100,
            precio_unidad=p["unit"],
            precio_docena=p["doc"],
            precio_caja=p["caja"],
            costo_referencial=p["caja"] * 0.6 # Simulamos costo
        )
        db.session.add(nuevo)
    
    db.session.commit()
    print(f">>> ¡Éxito! Se cargaron {len(productos_excel)} productos y el usuario admin.")