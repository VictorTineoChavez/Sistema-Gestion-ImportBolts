# Plataforma Web de Gestión Comercial y Logística - ImportBolts SAC

Este proyecto es parte del Trabajo de Investigación.

**Título de Tesis:** "Plataforma web para optimizar la gestión de ventas y pedidos del área comercial de la empresa ImportBolts SAC, Lima, 2025"

## 📋 Descripción
Sistema web integral (ERP) desarrollado para automatizar el flujo comercial y logístico. La solución permite gestionar cotizaciones, inventarios, despachos y cobranzas, integrando herramientas de **Inteligencia de Negocios (BI)** para la predicción de demanda.

## 🚀 Módulos Principales
1.  **Seguridad:** Gestión de usuarios con roles (Admin, Vendedor, Almacén, Administración).
2.  **Inventario Inteligente:**
    * Carga Masiva de productos vía Excel.
    * Kardex digital auditado.
    * Generación automática de SKUs y Categorías.
3.  **Gestión Comercial:**
    * Cotizador web con validación de precios en tiempo real.
    * Generación de documentos PDF/Word.
4.  **Logística:** Control de despachos y semáforo de priorización por fecha de entrega.
5.  **Finanzas:** Módulo de Cuentas por Cobrar y control de pagos parciales.
6.  **Business Intelligence:** Dashboard gerencial con algoritmos de predicción de ventas.

## 🛠️ Tecnologías Utilizadas
* **Backend:** Python 3.11, Flask.
* **Base de Datos:** SQLite (SQLAlchemy ORM).
* **Frontend:** HTML5, Bootstrap 5, JavaScript (Chart.js, Select2).
* **Análisis de Datos:** Pandas (Python).

## 🔧 Instalación y Despliegue

1. Clonar el repositorio:
   ```bash
   git clone [https://github.com/VictorTineoChavez/Sistema-Gestion-ImportBolts.git](https://github.com/VictorTineoChavez/Sistema-Gestion-ImportBolts.git)

2. Instalar dependencias:

Bash

pip install -r requirements.txt

3. Inicializar la Base de Datos (con datos de prueba):

Bash

python setup_db.py

4. Ejecutar el sistema:

Bash

python app.py


5. Acceder en el navegador: http://127.0.0.1:5000
