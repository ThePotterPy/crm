# CRM BGH — Service Cloud Enterprise Platform ⚡

Plataforma CRM moderna y autónoma desarrollada con arquitectura inspirada en **Salesforce Service Cloud**, diseñada para gestionar el ciclo operativo completo de atención al cliente, logística, re-verificaciones, devoluciones y calidad de forma 100% independiente sin depender de Google Sheets.

---

## 🚀 Características Principales

- **Base de Datos Transaccional Autónoma (Single Source of Truth)**:
  - Motor relacional SQLite / PostgreSQL (compatible con Railway, Render y Docker).
  - Eliminación de la dependencia de hojas de cálculo para la operación diaria.

- **Barra de Búsqueda Global Universal (Top Search estilo Salesforce)**:
  - Atajo rápido `/` o `Ctrl+K`.
  - Búsqueda exhaustiva por N° de Pedido, DNI/CUIT, Tracking, Código SAP, Caso Salesforce, Tienda, Cliente o palabras clave en atributos JSON dinámicos.

- **Vistas Segmentadas**:
  - `📋 Todos los Casos`: Visibilidad operativa global con métricas en tiempo real.
  - `👤 Casos Asignados`: Bandeja personal para cada agente con contador dinámico de tickets activos en la barra superior.

- **Jerarquía y Matriz Dinámica de Roles (`/admin/permisos`)**:
  - **Administrador (`admin`)**: Control y gobernanza total.
  - **Supervisor (`supervisor`)**: Balanceo de cargas, reasignación y auditorías.
  - **Agente Back Office (`agente_back`)**: Gestión operativa, resolución segura, solicitud de re-verificaciones y rechazos.
  - **Agente Front Office (`agente_front`)**: Formulario interactivo de alta, bandeja de devueltos y re-envío de correcciones.
  - **Calidad (`tyq`)**: Módulo Training & Quality con checklist de evaluación, scoring (0-100%) y coaching.

- **Circuito Completo de Retiro por Arrepentimiento y Seguimiento Logístico**:
  - **`Retiro por Arrepentimiento (Solicitud)`**: Alta de pedido de retiro por parte de Front Office.
  - **Handoff Automático**: Al resolver la solicitud en Back Office, el sistema crea automáticamente el caso en la cola de **`Seguimiento de Retiros (Arrepentimiento)`**.
  - **Control de Retiro & Reembolso**: Panel interactivo para verificar si fue retirado (`Pendiente`, `Retirado / En tránsito`, `Ingresado a depósito`, `No retirado`) y gestionar el estado del pago (`Reembolso no solicitado`, `Solicitado`, `Reembolsado`).

- **Línea de Tiempo 360° (`CaseEvent`)**:
  - Historial inmutable y cronológico de cada evento, cambio de estado, nota de re-verificación o auditoría.

- **Centro de Informes y Exportaciones (`/reportes`)**:
  - Filtros por rango de fechas, tipología, estado y agente.
  - Descargas directas en **Excel (.xlsx)** con estilo corporativo y **CSV**.

---

## 🛠️ Tecnologías

- **Backend**: Python 3.10+ / Flask / Flask-Login / Flask-SQLAlchemy
- **Frontend**: HTML5 Semántico, Vanilla CSS (Salesforce Lightning Dark Mode), JavaScript moderno
- **Reportes**: `openpyxl`
- **Despliegue**: Listo para Railway / Heroku (`Procfile`, `railway.toml`)

---

## ⚙️ Instalación Local

1. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/ThePotterPy/crm.git
   cd crm
   ```

2. **Crear y activar entorno virtual**:
   ```bash
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux/Mac:
   source venv/bin/activate
   ```

3. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Inicializar datos y usuarios semilla**:
   ```bash
   python seed.py
   ```

5. **Iniciar el servidor**:
   ```bash
   python app.py
   ```
   Acceder desde el navegador a `http://127.0.0.1:5000`.

---

## 🔑 Credenciales Iniciales de Prueba

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `admin123` | Administrador |
| `supervisor` | `super123` | Supervisor |
| `jorge` | `jorge123` | Agente Back Office |
| `front` | `front123` | Agente Front Office |
| `calidad` | `calidad123` | Calidad (TYQ) |

---

## 📄 Licencia

Uso interno BGH CRM. Todos los derechos reservados.
