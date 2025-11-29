import pandas as pd
import random

# CONFIGURACIÓN
CANTIDAD_PRODUCTOS = 500 # Puedes subirlo a 2000 si quieres probar límites

categorias = [
    ("Abrazaderas", "ABR"),
    ("Pernos", "PER"),
    ("Tuercas", "TUE"),
    ("Arandelas", "ARA"),
    ("Espárragos", "ESP"),
    ("Pernería a medida", "PME"),
    ("Eclisas", "ECL"),
    ("Pasadores", "PAS"),
    ("Remaches", "REM"),
    ("Clavos", "CLA")
]

medidas = ["1/2 x 1", "1/4 x 2", "3/8 x 1.5", "1 pulgada", "5mm", "10mm", "Grande", "Pequeño"]
materiales = ["Zincado", "Acero Inox", "Galvanizado", "Negro", "Grado 5", "Grado 8"]

data = []

print(f"Generando {CANTIDAD_PRODUCTOS} productos de prueba...")

for i in range(1, CANTIDAD_PRODUCTOS + 1):
    cat_nombre, cat_prefijo = random.choice(categorias)
    medida = random.choice(medidas)
    material = random.choice(materiales)
    
    # Generar Datos Realistas
    sku = f"{cat_prefijo}-{str(i).zfill(4)}"
    nombre = f"{cat_nombre[:-1]} {material} {medida}" # Quita la 's' final para singular aprox
    stock = random.randint(0, 500) # Stock aleatorio entre 0 y 500
    
    # Precios lógicos
    precio_base = round(random.uniform(0.50, 25.00), 2)
    precio_caja = round(precio_base * 0.7, 2) # Caja es 30% más barato
    
    data.append({
        "SKU": sku,
        "Nombre": nombre,
        "Categoria": cat_nombre,
        "Stock": stock,
        "Precio Unidad": precio_base,
        "Precio Caja": precio_caja
    })

# Crear DataFrame y Guardar Excel
df = pd.DataFrame(data)
nombre_archivo = "datos_masivos_importbolts.xlsx"
df.to_excel(nombre_archivo, index=False)

print(f"¡Listo! Archivo creado: {nombre_archivo}")
print("Ahora ve a tu sistema -> Inventario -> Importar Excel y sube este archivo.")