from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import db, User, Product, Client, Order, OrderDetail
from models import ProductMovement
from models import Payment
from models import Category
from datetime import datetime # Importante para la hora
import pandas as pd
from sqlalchemy.exc import IntegrityError # Para capturar el error del SKU
from sqlalchemy import or_
from sqlalchemy import func
from datetime import datetime, timedelta
from flask import send_file
from docxtpl import DocxTemplate # Importar librería de Word
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# --- CONFIGURACIÓN ---
# Esto crea un archivo 'importbolts.db' en tu carpeta automáticamente
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///importbolts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'tesis_secreta_123' # Necesario para login y mensajes

# Configuración de carpeta temporal para subidas (Agregalo después de app = Flask...)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Conectar la base de datos a la app
db.init_app(app)

# --- RUTAS BÁSICAS (VISTAS) ---

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    rol = session.get('role')
    user_id = session.get('user_id')
    hoy = datetime.now().date()
    
    # --- DATOS COMUNES (Alertas de Stock) ---
    # 1. Definir el límite de stock bajo
    UMBRAL_STOCK = 100 
    
    # 2. Contar el TOTAL REAL de productos bajos (Para el número grande en la tarjeta)
    total_alertas = Product.query.filter(Product.stock_actual < UMBRAL_STOCK).count()
    
    # 3. Traer solo una MUESTRA de 5 (Para la lista visual, no saturar)
    alertas_muestra = Product.query.filter(Product.stock_actual < UMBRAL_STOCK).limit(5).all()
    
    # ======================================================
    # VISTA 1: ADMIN Y ADMINISTRACIÓN (DASHBOARD BI GLOBAL)
    # ======================================================
    if rol in ['admin', 'administracion']:
        # A. KPIs Financieros (Ventas Hoy y Mes)
        ventas_hoy = db.session.query(func.sum(Order.total)).filter(func.date(Order.fecha) == hoy).scalar() or 0
        # SQLite usa strftime para extraer año-mes
        ventas_mes = db.session.query(func.sum(Order.total)).filter(func.strftime('%Y-%m', Order.fecha) == hoy.strftime('%Y-%m')).scalar() or 0
        pedidos_pendientes = Order.query.filter(Order.estado == 'Pendiente').count()
        
        # B. Ranking de Vendedores (Top 5)
        ranking = db.session.query(
            User.username, 
            User.nombre_completo, # Agregamos nombre real para que se vea mejor
            func.sum(Order.total).label('total_vendido'),
            func.count(Order.id).label('cantidad_ventas') # Dato extra: cuántos pedidos hizo
        ).join(Order).group_by(User.id).order_by(func.sum(Order.total).desc()).all()
        
        # C. Productos Más Vendidos (Top 5 para Gráfico)
        top_productos = db.session.query(
            Product.nombre,
            func.sum(OrderDetail.cantidad).label('total_qty')
        ).join(OrderDetail).group_by(Product.nombre).order_by(func.sum(OrderDetail.cantidad).desc()).limit(5).all()
        
        # D. ALGORITMO DE PREDICCIÓN (Proyección a fin de mes)
        dias_transcurridos = hoy.day
        # Evitar división por cero si es día 1
        promedio_diario = ventas_mes / dias_transcurridos if dias_transcurridos > 0 else 0
        dias_totales_mes = 30 
        prediccion_fin_mes = promedio_diario * dias_totales_mes
        
        return render_template('dashboard_admin.html', 
                               ventas_hoy=ventas_hoy,
                               ventas_mes=ventas_mes,
                               pedidos_pendientes=pedidos_pendientes,
                               ranking=ranking,
                               top_productos=top_productos,
                               prediccion=prediccion_fin_mes,
                               # Pasamos las alertas corregidas:
                               alertas=alertas_muestra,      
                               total_alertas=total_alertas)

    # ======================================================
    # VISTA 2: VENDEDOR (MI RENDIMIENTO PERSONAL)
    # ======================================================
    elif rol == 'vendedor':
        # Ventas filtradas por MI ID
        mis_ventas_hoy = db.session.query(func.sum(Order.total)).filter(Order.vendedor_id == user_id, func.date(Order.fecha) == hoy).scalar() or 0
        mis_ventas_mes = db.session.query(func.sum(Order.total)).filter(Order.vendedor_id == user_id, func.strftime('%Y-%m', Order.fecha) == hoy.strftime('%Y-%m')).scalar() or 0
        mis_pendientes = Order.query.filter_by(vendedor_id=user_id, estado='Pendiente').count()
        
        # Mis últimas 5 cotizaciones
        mis_ultimas = Order.query.filter_by(vendedor_id=user_id).order_by(Order.fecha.desc()).limit(5).all()
        
        return render_template('dashboard_vendedor.html', 
                               hoy=mis_ventas_hoy, 
                               mes=mis_ventas_mes, 
                               pendientes=mis_pendientes,
                               ultimas=mis_ultimas)

    # ======================================================
    # VISTA 3: ALMACÉN (LOGÍSTICA OPERATIVA)
    # ======================================================
    else: # Almacen
        # KPIs Logísticos
        por_despachar = Order.query.filter(Order.estado == 'Pendiente').count()
        en_ruta = Order.query.filter(Order.estado == 'Despachado').count()
        entregados_hoy = Order.query.filter(Order.estado == 'Entregado', func.date(Order.fecha) == hoy).count()
        
        # Lista Prioritaria (Ordenada por Fecha de Entrega más próxima)
        prioritarios = Order.query.filter(Order.estado == 'Pendiente').order_by(Order.fecha_entrega.asc()).limit(5).all()
        
        return render_template('dashboard_almacen.html', 
                               por_despachar=por_despachar,
                               en_ruta=en_ruta,
                               entregados=entregados_hoy,
                               prioritarios=prioritarios,
                               # Pasamos las alertas corregidas:
                               alertas=alertas_muestra,
                               total_alertas=total_alertas)
    
# 2. NUEVA RUTA: DESCARGAR REPORTE PREDICCIONES (EXCEL)
@app.route('/descargar_reporte_excel')
def descargar_reporte_excel():
    if session.get('role') not in ['admin', 'administracion']: return "Acceso denegado", 403
    
    # Replicamos la lógica de predicción
    productos_activos = db.session.query(
        Product.sku,
        Product.nombre, 
        Product.stock_actual,
        func.sum(ProductMovement.cantidad).label('total_vendido')
    ).join(ProductMovement).filter(
        ProductMovement.tipo == 'SALIDA',
        ProductMovement.fecha >= datetime.now() - timedelta(days=90)
    ).group_by(Product.id).all()
    
    data_excel = []
    
    for p in productos_activos:
        promedio_mensual = p.total_vendido / 3
        prediccion = promedio_mensual * 1.10
        
        estado = "OK"
        faltante = 0
        if prediccion > p.stock_actual:
            estado = "QUIEBRE DE STOCK"
            faltante = prediccion - p.stock_actual
            
        data_excel.append({
            'SKU': p.sku,
            'Producto': p.nombre,
            'Stock Actual': p.stock_actual,
            'Ventas 90 Días': p.total_vendido,
            'Velocidad (Mes)': round(promedio_mensual, 1),
            'Predicción Demanda': round(prediccion, 0),
            'Estado': estado,
            'Sugerencia Compra': round(faltante, 0) if faltante > 0 else 0
        })
    
    # Crear DataFrame y Excel
    df = pd.DataFrame(data_excel)
    
    # Guardar en memoria o temporal
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'Reporte_Predicciones_BI.xlsx')
    df.to_excel(path, index=False)
    
    return send_file(path, as_attachment=True)
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos')
            
    return render_template('login.html') # Crearemos esto luego

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/inventario')
def inventario():
    if session.get('user_id') is None: return redirect(url_for('login'))
    
    productos = Product.query.all()
    categorias = Category.query.all() # <--- Pasamos las categorías al HTML
    
    return render_template('inventario.html', productos=productos, categorias=categorias)

# --- API: OBTENER SIGUIENTE SKU (Magia Automática) ---
@app.route('/api/next_sku/<int:category_id>')
def get_next_sku(category_id):
    cat = Category.query.get_or_404(category_id)
    siguiente_num = cat.contador + 1
    # Genera formato: PER-005 (Rellena con ceros hasta 3 dígitos)
    sku_sugerido = f"{cat.prefijo}-{str(siguiente_num).zfill(3)}"
    return {'sku': sku_sugerido, 'prefijo': cat.prefijo}

@app.route('/api/productos_por_categoria/<int:category_id>')
def get_productos_por_categoria(category_id):
    try:
        cat = Category.query.get_or_404(category_id)
        
        # --- DEBUG: MIRA ESTO EN TU TERMINAL NEGRA CUANDO SELECCIONES UNA CATEGORÍA ---
        print(f"\n>>> BUSCANDO: Categoría ID={category_id} Nombre='{cat.nombre}'")
        
        # Usamos .ilike() en lugar de == para que 'Pernos' encuentre 'PERNOS' o 'pernos'
        productos = Product.query.filter(Product.categoria.ilike(f"{cat.nombre}")).all()
        
        print(f">>> RESULTADO: Se encontraron {len(productos)} productos.")
        
        lista = []
        for p in productos:
            lista.append({
                'id': p.id,
                'sku': p.sku,
                'nombre': p.nombre,
                'stock': p.stock_actual,
                'p_unidad': p.precio_unidad,
                'p_docena': p.precio_docena,
                'p_caja': p.precio_caja
            })
        return {'productos': lista}
        
    except Exception as e:
        print(f">>> ERROR API: {e}")
        return {'productos': []}
    

# --- GESTIÓN DE USUARIOS (ADMIN) ---

@app.route('/usuarios')
def gestion_usuarios():
    # Seguridad: Solo admin
    if session.get('role') != 'admin': 
        return "Acceso denegado", 403
    
    usuarios = User.query.all()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/usuarios/guardar', methods=['POST'])
def guardar_usuario():
    if session.get('role') != 'admin': return "Acceso denegado", 403
    
    user_id = request.form.get('user_id') # Si viene ID, es Edición. Si no, es Creación.
    username = request.form['username']
    nombre = request.form['nombre_completo']
    password = request.form['password']
    rol = request.form['role']
    
    try:
        if user_id:
            # --- MODO EDICIÓN ---
            usuario = User.query.get_or_404(user_id)
            usuario.username = username
            usuario.nombre_completo = nombre
            usuario.role = rol
            
            # Solo cambiamos la contraseña si el admin escribió algo nuevo
            if password:
                usuario.password = password
                flash(f'Usuario {username} actualizado (Contraseña cambiada).')
            else:
                flash(f'Usuario {username} actualizado (Contraseña mantenida).')
                
        else:
            # --- MODO CREACIÓN ---
            if not password:
                flash('Error: La contraseña es obligatoria para nuevos usuarios.')
                return redirect(url_for('gestion_usuarios'))
                
            nuevo = User(username=username, nombre_completo=nombre, password=password, role=rol)
            db.session.add(nuevo)
            flash(f'Usuario {username} creado exitosamente.')
            
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error: El nombre de usuario ya existe o hubo un problema.')
        
    return redirect(url_for('gestion_usuarios'))

@app.route('/usuarios/eliminar/<int:user_id>')
def eliminar_usuario(user_id):
    if session.get('role') != 'admin': return "Acceso denegado", 403
    
    # Protección: No te puedes borrar a ti mismo
    if user_id == session.get('user_id'):
        flash('Error: No puedes eliminar tu propia cuenta mientras estás conectado.')
        return redirect(url_for('gestion_usuarios'))
    
    usuario = User.query.get_or_404(user_id)
    db.session.delete(usuario)
    db.session.commit()
    flash('Usuario eliminado permanentemente.')
    
    return redirect(url_for('gestion_usuarios'))

# --- RUTA: CREAR NUEVA CATEGORÍA ---
@app.route('/categoria/nueva', methods=['POST'])
def nueva_categoria():
    nombre = request.form['cat_nombre']
    prefijo = request.form['cat_prefijo'].upper() # Siempre mayúscula
    
    nueva = Category(nombre=nombre, prefijo=prefijo, contador=0)
    db.session.add(nueva)
    db.session.commit()
    
    flash(f'Categoría "{nombre}" creada. Prefijo: {prefijo}')
    return redirect(url_for('inventario'))

@app.route('/nueva_venta', methods=['GET', 'POST'])
def nueva_venta():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            # 1. Validar Cliente
            cliente_doc = data.get('cliente_ruc')
            if not cliente_doc:
                return {'status': 'error', 'msg': 'Falta el RUC del cliente'}, 400

            # Buscar o Crear Cliente
            cliente = Client.query.filter_by(documento=cliente_doc).first()
            if not cliente:
                cliente = Client(
                    documento=cliente_doc,
                    nombre=data.get('cliente_nombre'),
                    telefono=data.get('cliente_tel'),
                    direccion=data.get('cliente_dir')
                )
                db.session.add(cliente)
            else:
                cliente.nombre = data.get('cliente_nombre')
                cliente.direccion = data.get('cliente_dir')
                
            db.session.flush() # Para obtener el ID del cliente si es nuevo

            # 2. Procesar Fecha de Entrega
            fecha_str = data.get('fecha_entrega')
            if not fecha_str:
                return {'status': 'error', 'msg': 'La fecha de entrega es obligatoria'}, 400
            
            # Convertimos texto "2025-11-24" a objeto Fecha real
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                
            # 3. Crear Orden (Cabecera)
            nueva_orden = Order(
                cliente_id=cliente.id, 
                vendedor_id=session['user_id'], 
                fecha=datetime.now(), # Fecha de creación (hoy)
                
                subtotal=float(data['subtotal']),
                igv=float(data['igv']),
                total=float(data['total']),
                
                tipo_entrega=data['tipo_entrega'],
                direccion_envio=data['direccion_entrega'],
                fecha_entrega=fecha_obj # <--- AQUÍ GUARDAMOS LA FECHA LÍMITE
            )
            db.session.add(nueva_orden)
            db.session.flush() # Para obtener el ID de la orden
            
            # 4. Guardar Detalles (Productos)
            for item in data['items']:
                prod = Product.query.get(item['id'])

                stock_antes = prod.stock_actual
                
                # Verificación final de stock
                if prod.stock_actual < int(item['cantidad']):
                    db.session.rollback()
                    return {'status': 'error', 'msg': f'Stock insuficiente para {prod.nombre}'}, 400
                
                # Restar stock
                prod.stock_actual -= int(item['cantidad']) # Restamos
                
                movimiento = ProductMovement(
                    product_id=prod.id,
                    user_id=session['user_id'],
                    tipo='SALIDA',
                    cantidad=int(item['cantidad']),
                    stock_anterior=stock_antes,
                    stock_nuevo=prod.stock_actual,
                    motivo=f"Venta COT-{nueva_orden.id:04d}" # Referencia automática
                )
                db.session.add(movimiento)
                
                detalle = OrderDetail(
                    order_id=nueva_orden.id,
                    product_id=prod.id,
                    cantidad=int(item['cantidad']),
                    precio_aplicado=float(item['precio']),
                    tipo_precio_usado=item['tipo_precio'],
                    subtotal=float(item['subtotal'])
                )
                db.session.add(detalle)
                
            db.session.commit()
            return {'status': 'success', 'order_id': nueva_orden.id}
            
        except Exception as e:
            db.session.rollback()
            print(f"ERROR EN SERVIDOR: {e}")
            return {'status': 'error', 'msg': str(e)}, 500

    # GET: Cargar la pantalla de venta
    productos = Product.query.all()
    categorias = Category.query.all() # <--- AGREGAR ESTO
    return render_template('nueva_venta.html', productos=productos, categorias=categorias) # <--- PASARLO AQUÍ

# --- ACTUALIZACIÓN: DESCARGAR WORD (Con nombre vendedor) ---
@app.route('/descargar_cotizacion/<int:order_id>')
def descargar_cotizacion(order_id):
    orden = Order.query.get_or_404(order_id)
    doc = DocxTemplate("plantilla_cotizacion.docx")
    
    lista_items = []
    for d in orden.details:
        lista_items.append({
            'cant': d.cantidad,
            'desc': d.product.nombre,
            'unit': f"S/ {d.precio_aplicado:.2f}",
            'subtotal': f"S/ {d.subtotal:.2f}"
        })

    context = {
        'fecha': orden.fecha.strftime("%d/%m/%Y"),
        'codigo_pedido': f"COT-{orden.id:04d}",
        'cliente_nombre': orden.cliente.nombre,
        'cliente_ruc': orden.cliente.documento,
        'direccion_entrega': orden.direccion_envio,
        'tipo_entrega': orden.tipo_entrega,
        'fecha_entrega': orden.fecha_entrega.strftime("%d/%m/%Y") if orden.fecha_entrega else "A coordinar",
        
        # --- NUEVO: DATOS DEL VENDEDOR ---
        'vendedor_nombre': orden.vendedor.nombre_completo, 
        
        'tbl_contents': lista_items,
        'item': lista_items,
        'subtotal': f"S/ {orden.subtotal:.2f}",
        'igv': f"S/ {orden.igv:.2f}",
        'total': f"S/ {orden.total:.2f}"
    }
    
    doc.render(context)
    nombre_archivo = f"Cotizacion_{orden.id}.docx"
    doc.save(nombre_archivo)
    return send_file(nombre_archivo, as_attachment=True)


# --- EN APP.PY (Reemplaza la función importar_excel completa) ---

@app.route('/producto/importar', methods=['POST'])
def importar_excel():
    if session.get('role') not in ['admin', 'almacen']: return "No autorizado", 403
    
    if 'archivo_excel' not in request.files:
        flash('No se seleccionó ningún archivo')
        return redirect(url_for('inventario'))
        
    archivo = request.files['archivo_excel']
    if archivo.filename == '':
        return redirect(url_for('inventario'))

    if archivo:
        filename = secure_filename(archivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        archivo.save(filepath)
        
        try:
            df = pd.read_excel(filepath)
            
            # Validar columnas
            cols = ['SKU', 'Nombre', 'Categoria', 'Stock', 'Precio Unidad', 'Precio Caja']
            if not all(col in df.columns for col in cols):
                flash('ERROR: Formato incorrecto. Use la plantilla.')
                return redirect(url_for('inventario'))
            
            nuevos = 0
            actualizados = 0
            
            for index, row in df.iterrows():
                sku = str(row['SKU']).strip()
                nombre_cat = str(row['Categoria']).strip()
                cantidad_excel = int(row['Stock'])
                
                # 1. BUSCAR O CREAR CATEGORÍA (CON LÓGICA ANTI-CHOQUE)
                cat = Category.query.filter_by(nombre=nombre_cat).first()
                
                if not cat:
                    # Generar prefijo base (Ej: PER)
                    prefijo_base = nombre_cat[:3].upper()
                    prefijo_final = prefijo_base
                    contador_sufijo = 1
                    
                    # BUCLE WHILE: Si 'PER' existe, prueba 'PE1', 'PE2', 'PE3'...
                    while Category.query.filter_by(prefijo=prefijo_final).first():
                        prefijo_final = f"{prefijo_base[:2]}{contador_sufijo}"
                        contador_sufijo += 1
                    
                    # Crear la categoría con el prefijo seguro
                    cat = Category(nombre=nombre_cat, prefijo=prefijo_final, contador=0)
                    db.session.add(cat)
                    db.session.flush() # Guardamos para obtener el ID y que el próximo loop lo vea

                # 2. BUSCAR O CREAR PRODUCTO
                prod = Product.query.filter_by(sku=sku).first()
                
                if prod:
                    # ACTUALIZAR EXISTENTE
                    if cantidad_excel > 0:
                        stock_anterior = prod.stock_actual
                        prod.stock_actual += cantidad_excel
                        prod.precio_unidad = float(row['Precio Unidad'])
                        prod.precio_caja = float(row['Precio Caja'])
                        
                        kardex = ProductMovement(
                            product_id=prod.id,
                            user_id=session['user_id'],
                            tipo='ENTRADA',
                            cantidad=cantidad_excel,
                            stock_anterior=stock_anterior,
                            stock_nuevo=prod.stock_actual,
                            motivo="Carga Masiva (Actualización)"
                        )
                        db.session.add(kardex)
                        actualizados += 1
                else:
                    # CREAR NUEVO
                    prod = Product(
                        sku=sku,
                        nombre=str(row['Nombre']),
                        categoria=cat.nombre,
                        stock_actual=cantidad_excel,
                        precio_unidad=float(row['Precio Unidad']),
                        precio_docena=float(row['Precio Unidad']) * 0.9,
                        precio_caja=float(row['Precio Caja']),
                        costo_referencial=float(row['Precio Caja']) * 0.6,
                        unidades_por_caja=100
                    )
                    db.session.add(prod)
                    db.session.flush()
                    
                    if cantidad_excel > 0:
                        kardex = ProductMovement(
                            product_id=prod.id,
                            user_id=session['user_id'],
                            tipo='ENTRADA',
                            cantidad=cantidad_excel,
                            stock_anterior=0,
                            stock_nuevo=cantidad_excel,
                            motivo="Carga Masiva (Inicial)"
                        )
                        db.session.add(kardex)
                    nuevos += 1
            
            db.session.commit()
            flash(f'Proceso terminado: {nuevos} nuevos, {actualizados} actualizados.')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error crítico en el archivo: {str(e)}')
        finally:
            if os.path.exists(filepath): os.remove(filepath)
            
    return redirect(url_for('inventario'))

# --- RUTA PARA DESCARGAR PLANTILLA ---
@app.route('/descargar_plantilla')
def descargar_plantilla():
    # Creamos un Excel en memoria
    df = pd.DataFrame(columns=['SKU', 'Nombre', 'Categoria', 'Stock', 'Precio Unidad', 'Precio Caja'])
    # Agregamos un ejemplo
    df.loc[0] = ['EJ-001', 'Producto Ejemplo', 'Pernos', 100, 2.50, 1.80]
    
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'plantilla_importacion.xlsx')
    df.to_excel(path, index=False)
    
    return send_file(path, as_attachment=True)

# --- RUTA: NUEVO PRODUCTO (Actualizada para sumar el contador) ---
@app.route('/producto/nuevo', methods=['POST'])
def nuevo_producto():
    # ... (validaciones de rol) ...
    if session.get('role') not in ['admin', 'almacen']: return "No autorizado", 403
    try:
        cat_id = request.form['categoria_id'] # Recibimos ID, no nombre
        cat = Category.query.get(cat_id)
        
        # Creamos producto
        nuevo = Product(
            sku=request.form['sku'],
            nombre=request.form['nombre'],
            categoria=cat.nombre, # Guardamos el nombre para los reportes
            stock_actual=int(request.form['stock']),
            # ... precios ...
            precio_unidad=float(request.form['p_unidad']),
            precio_docena=float(request.form['p_unidad']) * 0.9, # Auto-calculado si quieres
            precio_caja=float(request.form['p_caja']),
            costo_referencial=float(request.form['p_caja']) * 0.6,
            unidades_por_caja=100
        )
        db.session.add(nuevo)
        
        # ACTUALIZAMOS EL CONTADOR DE LA CATEGORÍA
        # Si el SKU usado coincide con el sugerido, aumentamos el contador
        if request.form['sku'].startswith(cat.prefijo):
            cat.contador += 1
            
        db.session.commit()
        flash('Producto creado exitosamente')
        
    except IntegrityError:
        db.session.rollback()
        flash('ERROR: El SKU ya existe.')
        
    return redirect(url_for('inventario'))

@app.route('/producto/editar', methods=['POST'])
def editar_producto():
    if session.get('role') != 'admin': return "Acceso denegado. Solo Gerencia edita precios.", 403
    
    prod_id = request.form['prod_id']
    prod = Product.query.get(prod_id)
    
    # Actualizar datos
    prod.nombre = request.form['nombre']
    prod.stock_actual = int(request.form['stock'])
    prod.precio_unidad = float(request.form['p_unidad'])
    prod.precio_caja = float(request.form['p_caja'])
    
    db.session.commit()
    flash('Producto actualizado')
    return redirect(url_for('inventario'))

@app.route('/producto/eliminar/<int:prod_id>')
def eliminar_producto(prod_id):
    if session.get('role') != 'admin': return "Acceso denegado", 403
    
    try:
        prod = Product.query.get_or_404(prod_id)
        db.session.delete(prod)
        db.session.commit()
        flash('Producto eliminado correctamente')
    except IntegrityError:
        db.session.rollback()
        flash('Error: No se puede eliminar porque tiene ventas asociadas.')
        
    return redirect(url_for('inventario'))

@app.route('/producto/ajustar_stock', methods=['POST'])
def ajustar_stock():
    # Solo Admin y Almacén mueven stock físico
    if session.get('role') not in ['admin', 'almacen']: return "No autorizado", 403
    
    prod_id = request.form['prod_id']
    tipo_ajuste = request.form['tipo'] # 'ingreso' o 'salida'
    cantidad = int(request.form['cantidad'])
    motivo_texto = request.form['motivo'] # <--- Agregaremos este campo en el HTML
    
    prod = Product.query.get(prod_id)
    stock_antes = prod.stock_actual
    
    tipo_kardex = ""
    
    if tipo_ajuste == 'ingreso':
        prod.stock_actual += cantidad
        tipo_kardex = "ENTRADA"
        flash(f'Ingreso registrado: +{cantidad} en {prod.sku}')
    else:
        prod.stock_actual -= cantidad
        tipo_kardex = "SALIDA"
        flash(f'Salida registrada: -{cantidad} en {prod.sku}')
        
    # REGISTRO KARDEX
    kardex = ProductMovement(
        product_id=prod.id,
        user_id=session['user_id'],
        tipo=tipo_kardex,
        cantidad=cantidad,
        stock_anterior=stock_antes,
        stock_nuevo=prod.stock_actual,
        motivo=motivo_texto # Ej: "Compra a proveedor X" o "Merma por óxido"
    )
    db.session.add(kardex)
    db.session.commit()
    return redirect(url_for('inventario'))

@app.route('/kardex')
def ver_kardex():
    if session.get('user_id') is None: return redirect(url_for('login'))
    
    # Unimos con Product para poder filtrar por nombre/categoría
    query = ProductMovement.query.join(Product)
    
    # 1. Filtro por Texto (Nombre, SKU o Motivo)
    busqueda = request.args.get('busqueda')
    if busqueda:
        query = query.filter(
            or_(
                Product.nombre.ilike(f"%{busqueda}%"),
                Product.sku.ilike(f"%{busqueda}%"),
                ProductMovement.motivo.ilike(f"%{busqueda}%")
            )
        )
    
    # 2. Filtro por Categoría
    cat_nombre = request.args.get('categoria')
    if cat_nombre and cat_nombre != 'todas':
        query = query.filter(Product.categoria == cat_nombre)

    # 3. NUEVO: Filtro por Tipo (Entrada/Salida)
    tipo_mov = request.args.get('tipo')
    if tipo_mov and tipo_mov in ['ENTRADA', 'SALIDA']:
        query = query.filter(ProductMovement.tipo == tipo_mov)

    # 4. Filtro por Rango de Fechas
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    if fecha_inicio and fecha_fin:
        start = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        end = datetime.strptime(fecha_fin + " 23:59:59", '%Y-%m-%d %H:%M:%S')
        query = query.filter(ProductMovement.fecha.between(start, end))
        
    # Ordenar: Más reciente primero y Limitar resultados para velocidad
    movimientos = query.order_by(ProductMovement.fecha.desc()).limit(1000).all()
    
    categorias = Category.query.all()
    
    return render_template('kardex.html', movimientos=movimientos, categorias=categorias)

@app.route('/historial_ventas')
def historial_ventas():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    query = Order.query
    
    # 1. FILTRO DE VENDEDOR (Si no es admin, solo ve lo suyo)
    if session['role'] == 'vendedor':
        query = query.filter_by(vendedor_id=session['user_id'])
        
    # 2. FILTRO POR RANGO DE FECHAS
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    if fecha_inicio and fecha_fin:
        start = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        end = datetime.strptime(fecha_fin + " 23:59:59", '%Y-%m-%d %H:%M:%S')
        query = query.filter(Order.fecha.between(start, end))

    # 3. NUEVO: FILTRO POR ESTADO
    estado = request.args.get('estado')
    if estado and estado != 'todos':
        query = query.filter(Order.estado == estado)

    # 4. NUEVO: BUSCADOR POR CLIENTE (Nombre o RUC)
    busqueda = request.args.get('busqueda')
    if busqueda:
        # Busca clientes que contengan el texto
        # Hacemos un JOIN para buscar en la tabla de clientes
        query = query.join(Client).filter(
            or_(
                Client.nombre.ilike(f"%{busqueda}%"),
                Client.documento.ilike(f"%{busqueda}%")
            )
        )
    
    # Ordenar: Más reciente primero
    ordenes = query.order_by(Order.fecha.desc()).all()
    
    # Pasamos 'hoy' para las alertas de colores en la tabla
    return render_template('historial_ventas.html', ordenes=ordenes, hoy=datetime.now().date())

@app.route('/despachos')
def despachos():
    if session.get('role') not in ['admin', 'almacen']: return "Acceso denegado", 403
    
    # Obtener el parámetro de ordenamiento de la URL (por defecto 'urgencia')
    modo_orden = request.args.get('ordenar_por', 'urgencia')
    
    # Consulta base: Solo pedidos que NO han sido entregados (Pendientes o Despachados)
    query = Order.query.filter(Order.estado != 'Entregado')
    
    # Lógica de Priorización
    if modo_orden == 'urgencia':
        # Ordenar por fecha de entrega ASCENDENTE (Lo más cercano a vencer primero)
        query = query.order_by(Order.fecha_entrega.asc())
    elif modo_orden == 'ganancia':
        # Ordenar por total DESCENDENTE (Las ventas más grandes primero)
        query = query.order_by(Order.total.desc())
    else:
        # Por defecto: Ordenar por fecha de creación (FIFO)
        query = query.order_by(Order.fecha.asc())
        
    ordenes_pendientes = query.all()
    
    # Pasamos 'hoy' para que la plantilla sepa pintar de rojo los vencidos
    return render_template(
        'despachos.html', 
        ordenes=ordenes_pendientes, 
        orden_actual=modo_orden, 
        hoy=datetime.now().date()
    )

@app.route('/cobranzas')
def cobranzas():
    # AHORA: Solo Admin y Administración (Vendedores NO, Almacén NO)
    if session.get('role') not in ['admin', 'administracion']: return "Acceso denegado", 403
    
    filtro = request.args.get('ver', 'deudas')
    query = Order.query
    if filtro == 'deudas':
        query = query.filter(Order.estado_pago != 'Pagado')
    ordenes = query.order_by(Order.fecha.asc()).all()
    return render_template('cobranzas.html', ordenes=ordenes)

@app.route('/registrar_pago', methods=['POST'])
def registrar_pago():
    if session.get('role') not in ['admin', 'administracion']: return "Acceso denegado", 403
    
    order_id = request.form['order_id']
    monto = float(request.form['monto'])
    metodo = request.form['metodo']
    nota = request.form['nota']
    
    orden = Order.query.get(order_id)
    
    # Validar que no pague más de la deuda
    deuda_actual = orden.total - orden.monto_pagado
    if monto > (deuda_actual + 0.1): # Margen de error 0.1 por decimales
        flash('Error: El monto excede la deuda actual.')
        return redirect(url_for('cobranzas'))
    
    # 1. Crear registro de pago
    nuevo_pago = Payment(
        order_id=orden.id,
        monto=monto,
        metodo=metodo,
        nota=nota,
        fecha=datetime.now()
    )
    db.session.add(nuevo_pago)
    
    # 2. Actualizar la Orden
    orden.monto_pagado += monto
    
    # Calcular nuevo estado
    if orden.monto_pagado >= (orden.total - 0.1):
        orden.estado_pago = 'Pagado'
        orden.monto_pagado = orden.total # Ajuste exacto
    elif orden.monto_pagado > 0:
        orden.estado_pago = 'Parcial'
    else:
        orden.estado_pago = 'Pendiente'
        
    db.session.commit()
    flash(f'Pago de S/ {monto} registrado correctamente.')
    return redirect(url_for('cobranzas'))

@app.route('/cambiar_estado/<int:order_id>/<nuevo_estado>')
def cambiar_estado(order_id, nuevo_estado):
    if session.get('role') not in ['admin', 'almacen']: return "Acceso denegado", 403
    
    orden = Order.query.get_or_404(order_id)
    orden.estado = nuevo_estado
    db.session.commit()
    flash(f'Pedido #{order_id} actualizado a {nuevo_estado}')
    return redirect(url_for('despachos'))

@app.route('/reportes_predicciones')
def reportes_predicciones():
    if session.get('role') not in ['admin', 'administracion']: return "Acceso denegado", 403
    
    # 1. CALCULO DE PREDICCIONES POR PRODUCTO
    # Obtenemos productos que han tenido movimiento de SALIDA (Ventas)
    productos_activos = db.session.query(
        Product.nombre, 
        Product.stock_actual,
        func.sum(ProductMovement.cantidad).label('total_vendido')
    ).join(ProductMovement).filter(
        ProductMovement.tipo == 'SALIDA',
        # Analizamos los últimos 90 días (Trimestre) para mejor precisión
        ProductMovement.fecha >= datetime.now() - timedelta(days=90)
    ).group_by(Product.id).all()
    
    reporte = []
    
    for p in productos_activos:
        # Promedio mensual real (basado en los ultimos 3 meses)
        promedio_mensual = p.total_vendido / 3 
        
        # Algoritmo Simple de Predicción:
        # Asumimos un crecimiento del 10% o estacionalidad
        prediccion = promedio_mensual * 1.10
        
        estado_proyeccion = "Estable"
        if prediccion > p.stock_actual:
            estado_proyeccion = "QUIEBRE DE STOCK (Comprar urgente)"
        
        reporte.append({
            'producto': p.nombre,
            'stock': p.stock_actual,
            'historico_trimestral': p.total_vendido,
            'promedio_mensual': round(promedio_mensual, 1),
            'prediccion_prox_mes': round(prediccion, 0),
            'estado': estado_proyeccion
        })
    
    # Ordenar por los que más se van a vender
    reporte = sorted(reporte, key=lambda k: k['prediccion_prox_mes'], reverse=True)
    
    return render_template('reportes_predicciones.html', data=reporte, hoy=datetime.now())

# API SECRETA PARA CONSULTAR PRECIO EN VIVO (AJAX)
@app.route('/api/check_precio/<int:product_id>/<int:cantidad>')
def check_precio(product_id, cantidad):
    p = Product.query.get_or_404(product_id)
    
    # --- LÓGICA DE TU TESIS (Validador de 3 niveles) ---
    precio_final = 0.0
    tipo_precio = ""
    
    mitad_caja = p.unidades_por_caja / 2
    
    if cantidad >= 1 and cantidad <= 11:
        precio_final = p.precio_unidad
        tipo_precio = "Precio Unidad"
    elif cantidad >= 12 and cantidad < mitad_caja:
        precio_final = p.precio_docena
        tipo_precio = "Precio Docena"
    else:
        precio_final = p.precio_caja
        tipo_precio = "Precio Caja Mayorista"
        
    # --- SEMÁFORO DE MARGEN (OK / WARN / BLOCK) ---
    # Simulamos cálculo de margen
    margen = precio_final - p.costo_referencial
    estado = "OK"
    mensaje = "Margen saludable."
    
    if margen <= 0:
        estado = "BLOCK"
        mensaje = "ERROR: Venta con pérdida. Aumente precio."
    elif margen < (p.costo_referencial * 0.15): # Si gana menos del 15%
        estado = "WARN"
        mensaje = "ADVERTENCIA: Margen muy bajo."
        
    return {
        "precio": precio_final,
        "tipo": tipo_precio,
        "total": precio_final * cantidad,
        "estado": estado,
        "mensaje": mensaje
    }

# --- ARRANQUE DE LA APLICACIÓN ---
if __name__ == '__main__':
    app.run(debug=True)

