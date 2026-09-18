"""
Script de datos iniciales para el CRM BGH.
Crea el admin, las 8 hojas configuradas y un usuario agente de ejemplo.

Uso:
    python seed.py
"""
import json
from models import db, User, SheetConfig


SHEETS = [
    {
        "slug": "retiro_arrepentimiento",
        "sheet_name": "SOLICITUDES BGH 2026 - Retiro arrepentimiento",
        "display_name": "Retiro por Arrepentimiento (Solicitud)",
        "header_row": 1,
        "color": "#0052cc",
        "badge_label": "Retiro arrepentimiento",
        "badge_bg": "#0052cc",
        "badge_text_color": "#ffffff",
        "badge_css_class": "badge-retiro-arrepentimiento",
        "input_columns": [
            {"key": "id_pedido", "name": "ID Pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
            {"key": "fecha", "name": "Fecha", "column": "B", "index": 1, "maps_to": "fecha"},
            {"key": "agente_carga", "name": "Agente carga", "column": "C", "index": 2, "maps_to": "agente_front"},
            {"key": "sku", "name": "SKU", "column": "D", "index": 3},
            {"key": "caso_id_wise", "name": "CASO ID WISE", "column": "E", "index": 4},
            {"key": "tienda", "name": "Tienda", "column": "F", "index": 5, "maps_to": "tienda"},
            {"key": "solicitud", "name": "Solicitud", "column": "G", "index": 6, "type": "select", "maps_to": "solicitud", "options": ["Retiro arrepentimiento", "SEGUIMIENTO", "Otros", "NC POR FACTURA B", "CAMBIO INCORRECTO", "CAMBIO DEFECTUOSO"]},
            {"key": "motivos", "name": "Motivos - Retiros Arrepentimiento", "column": "H", "index": 7, "type": "select", "options": ["", "Arrepentimiento de compra", "Demora en entrega", "Producto no era lo esperado", "Compró por error", "Encontró mejor precio", "Otro motivo"]},
            {"key": "observacion_detalle", "name": "Observación - Detalle del inconveniente", "column": "I", "index": 8},
            {"key": "direccion_datos", "name": "Dirección/Teléfono/Datos (Gestión Front)", "column": "J", "index": 9},
        ],
        "output_columns": [
            {"key": "referencia_bo", "name": "Referencia (Gestión BACK OFFICE)", "column": "K", "index": 10, "type": "text"},
            {"key": "caso_salesforce", "name": "Caso SALESFORCE", "column": "L", "index": 11, "type": "text", "maps_to": "caso_salesforce"},
            {"key": "agente_back", "name": "Agente Back", "column": "M", "index": 12, "type": "text"},
            {"key": "resuelto", "name": "Resuelto", "column": "N", "index": 13, "type": "select", "options": ["", "Si", "No", "Rechazado", "No corresponde"]},
            {"key": "observaciones", "name": "Observaciones", "column": "O", "index": 14, "type": "textarea"},
        ],
    },
    {
        "slug": "seguimiento",
        "sheet_name": "SOLICITUDES BGH 2026 - SEGUIMIENTO",
        "display_name": "SEGUIMIENTO",
        "header_row": 1,
        "color": "#fef08a",
        "badge_label": "SEGUIMIENTO",
        "badge_bg": "#fef08a",
        "badge_text_color": "#713f12",
        "badge_css_class": "badge-seguimiento",
        "input_columns": [
            {"key": "id_pedido", "name": "ID Pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
            {"key": "fecha", "name": "Fecha", "column": "B", "index": 1, "maps_to": "fecha"},
            {"key": "agente_carga", "name": "Agente carga", "column": "C", "index": 2, "maps_to": "agente_front"},
            {"key": "sku", "name": "SKU", "column": "D", "index": 3},
            {"key": "caso_id_wise", "name": "CASO ID WISE", "column": "E", "index": 4},
            {"key": "tienda", "name": "Tienda", "column": "F", "index": 5, "maps_to": "tienda"},
            {"key": "solicitud", "name": "Solicitud", "column": "G", "index": 6, "type": "select", "maps_to": "solicitud", "options": ["Retiro arrepentimiento", "SEGUIMIENTO", "Otros", "NC POR FACTURA B", "CAMBIO INCORRECTO", "CAMBIO DEFECTUOSO"]},
            {"key": "motivos", "name": "Motivos - Retiros Arrepentimiento", "column": "H", "index": 7},
            {"key": "observacion_detalle", "name": "Observación - Detalle del inconveniente", "column": "I", "index": 8},
            {"key": "direccion_datos", "name": "Dirección/Teléfono/Datos (Gestión Front)", "column": "J", "index": 9},
        ],
        "output_columns": [
            {"key": "referencia_bo", "name": "Referencia (Gestión BACK OFFICE)", "column": "K", "index": 10, "type": "text"},
            {"key": "caso_salesforce", "name": "Caso SALESFORCE", "column": "L", "index": 11, "type": "text", "maps_to": "caso_salesforce"},
            {"key": "agente_back", "name": "Agente Back", "column": "M", "index": 12, "type": "text"},
            {"key": "resuelto", "name": "Resuelto", "column": "N", "index": 13, "type": "select", "options": ["", "Si", "No", "Rechazado", "No corresponde"]},
            {"key": "observaciones", "name": "Observaciones", "column": "O", "index": 14, "type": "textarea"},
        ],
    },
    {
        "slug": "otros",
        "sheet_name": "SOLICITUDES BGH 2026 - Otros",
        "display_name": "Otros",
        "header_row": 1,
        "color": "#581c87",
        "badge_label": "Otros",
        "badge_bg": "#581c87",
        "badge_text_color": "#ffffff",
        "badge_css_class": "badge-otros",
        "input_columns": [
            {"key": "id_pedido", "name": "ID Pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
            {"key": "fecha", "name": "Fecha", "column": "B", "index": 1, "maps_to": "fecha"},
            {"key": "agente_carga", "name": "Agente carga", "column": "C", "index": 2, "maps_to": "agente_front"},
            {"key": "sku", "name": "SKU", "column": "D", "index": 3},
            {"key": "caso_id_wise", "name": "CASO ID WISE", "column": "E", "index": 4},
            {"key": "tienda", "name": "Tienda", "column": "F", "index": 5, "maps_to": "tienda"},
            {"key": "solicitud", "name": "Solicitud", "column": "G", "index": 6, "type": "select", "maps_to": "solicitud", "options": ["Retiro arrepentimiento", "SEGUIMIENTO", "Otros", "NC POR FACTURA B", "CAMBIO INCORRECTO", "CAMBIO DEFECTUOSO"]},
            {"key": "motivos", "name": "Motivos - Retiros Arrepentimiento", "column": "H", "index": 7},
            {"key": "observacion_detalle", "name": "Observación - Detalle del inconveniente", "column": "I", "index": 8},
            {"key": "direccion_datos", "name": "Dirección/Teléfono/Datos (Gestión Front)", "column": "J", "index": 9},
        ],
        "output_columns": [
            {"key": "referencia_bo", "name": "Referencia (Gestión BACK OFFICE)", "column": "K", "index": 10, "type": "text"},
            {"key": "caso_salesforce", "name": "Caso SALESFORCE", "column": "L", "index": 11, "type": "text", "maps_to": "caso_salesforce"},
            {"key": "agente_back", "name": "Agente Back", "column": "M", "index": 12, "type": "text"},
            {"key": "resuelto", "name": "Resuelto", "column": "N", "index": 13, "type": "select", "options": ["", "Si", "No", "Rechazado", "No corresponde"]},
            {"key": "observaciones", "name": "Observaciones", "column": "O", "index": 14, "type": "textarea"},
        ],
    },
    {
        "slug": "nc_factura_b",
        "sheet_name": "SOLICITUDES BGH 2026 - NC POR FACTURA B",
        "display_name": "NC POR FACTURA B",
        "header_row": 1,
        "color": "#991b1b",
        "badge_label": "NC POR FACTURA B",
        "badge_bg": "#991b1b",
        "badge_text_color": "#ffffff",
        "badge_css_class": "badge-nc-factura-b",
        "input_columns": [
            {"key": "id_pedido", "name": "ID Pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
            {"key": "fecha", "name": "Fecha", "column": "B", "index": 1, "maps_to": "fecha"},
            {"key": "agente_carga", "name": "Agente carga", "column": "C", "index": 2, "maps_to": "agente_front"},
            {"key": "sku", "name": "SKU", "column": "D", "index": 3},
            {"key": "caso_id_wise", "name": "CASO ID WISE", "column": "E", "index": 4},
            {"key": "tienda", "name": "Tienda", "column": "F", "index": 5, "maps_to": "tienda"},
            {"key": "solicitud", "name": "Solicitud", "column": "G", "index": 6, "type": "select", "maps_to": "solicitud", "options": ["Retiro arrepentimiento", "SEGUIMIENTO", "Otros", "NC POR FACTURA B", "CAMBIO INCORRECTO", "CAMBIO DEFECTUOSO"]},
            {"key": "motivos", "name": "Motivos - Retiros Arrepentimiento", "column": "H", "index": 7},
            {"key": "observacion_detalle", "name": "Observación - Detalle del inconveniente", "column": "I", "index": 8},
            {"key": "direccion_datos", "name": "Dirección/Teléfono/Datos (Gestión Front)", "column": "J", "index": 9},
        ],
        "output_columns": [
            {"key": "referencia_bo", "name": "Referencia (Gestión BACK OFFICE)", "column": "K", "index": 10, "type": "text"},
            {"key": "caso_salesforce", "name": "Caso SALESFORCE", "column": "L", "index": 11, "type": "text", "maps_to": "caso_salesforce"},
            {"key": "agente_back", "name": "Agente Back", "column": "M", "index": 12, "type": "text"},
            {"key": "resuelto", "name": "Resuelto", "column": "N", "index": 13, "type": "select", "options": ["", "Si", "No", "Rechazado", "No corresponde"]},
            {"key": "observaciones", "name": "Observaciones", "column": "O", "index": 14, "type": "textarea"},
        ],
    },
    {
        "slug": "cambio_incorrecto",
        "sheet_name": "SOLICITUDES BGH 2026 - CAMBIO INCORRECTO",
        "display_name": "CAMBIO INCORRECTO",
        "header_row": 1,
        "color": "#fecdd3",
        "badge_label": "CAMBIO INCORRECTO",
        "badge_bg": "#fecdd3",
        "badge_text_color": "#991b1b",
        "badge_css_class": "badge-cambio-incorrecto",
        "input_columns": [
            {"key": "id_pedido", "name": "ID Pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
            {"key": "fecha", "name": "Fecha", "column": "B", "index": 1, "maps_to": "fecha"},
            {"key": "agente_carga", "name": "Agente carga", "column": "C", "index": 2, "maps_to": "agente_front"},
            {"key": "sku", "name": "SKU", "column": "D", "index": 3},
            {"key": "caso_id_wise", "name": "CASO ID WISE", "column": "E", "index": 4},
            {"key": "tienda", "name": "Tienda", "column": "F", "index": 5, "maps_to": "tienda"},
            {"key": "solicitud", "name": "Solicitud", "column": "G", "index": 6, "type": "select", "maps_to": "solicitud", "options": ["Retiro arrepentimiento", "SEGUIMIENTO", "Otros", "NC POR FACTURA B", "CAMBIO INCORRECTO", "CAMBIO DEFECTUOSO"]},
            {"key": "motivos", "name": "Motivos - Retiros Arrepentimiento", "column": "H", "index": 7},
            {"key": "observacion_detalle", "name": "Observación - Detalle del inconveniente", "column": "I", "index": 8},
            {"key": "direccion_datos", "name": "Dirección/Teléfono/Datos (Gestión Front)", "column": "J", "index": 9},
        ],
        "output_columns": [
            {"key": "referencia_bo", "name": "Referencia (Gestión BACK OFFICE)", "column": "K", "index": 10, "type": "text"},
            {"key": "caso_salesforce", "name": "Caso SALESFORCE", "column": "L", "index": 11, "type": "text", "maps_to": "caso_salesforce"},
            {"key": "agente_back", "name": "Agente Back", "column": "M", "index": 12, "type": "text"},
            {"key": "resuelto", "name": "Resuelto", "column": "N", "index": 13, "type": "select", "options": ["", "Si", "No", "Rechazado", "No corresponde"]},
            {"key": "observaciones", "name": "Observaciones", "column": "O", "index": 14, "type": "textarea"},
        ],
    },
    {
        "slug": "cambio_defectuoso",
        "sheet_name": "SOLICITUDES BGH 2026 - CAMBIO DEFECTUOSO",
        "display_name": "CAMBIO DEFECTUOSO",
        "header_row": 1,
        "color": "#065f46",
        "badge_label": "CAMBIO DEFECTUOSO",
        "badge_bg": "#065f46",
        "badge_text_color": "#dcfce7",
        "badge_css_class": "badge-cambio-defectuoso",
        "input_columns": [
            {"key": "id_pedido", "name": "ID Pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
            {"key": "fecha", "name": "Fecha", "column": "B", "index": 1, "maps_to": "fecha"},
            {"key": "agente_carga", "name": "Agente carga", "column": "C", "index": 2, "maps_to": "agente_front"},
            {"key": "sku", "name": "SKU", "column": "D", "index": 3},
            {"key": "caso_id_wise", "name": "CASO ID WISE", "column": "E", "index": 4},
            {"key": "tienda", "name": "Tienda", "column": "F", "index": 5, "maps_to": "tienda"},
            {"key": "solicitud", "name": "Solicitud", "column": "G", "index": 6, "type": "select", "maps_to": "solicitud", "options": ["Retiro arrepentimiento", "SEGUIMIENTO", "Otros", "NC POR FACTURA B", "CAMBIO INCORRECTO", "CAMBIO DEFECTUOSO"]},
            {"key": "motivos", "name": "Motivos - Retiros Arrepentimiento", "column": "H", "index": 7},
            {"key": "observacion_detalle", "name": "Observación - Detalle del inconveniente", "column": "I", "index": 8},
            {"key": "direccion_datos", "name": "Dirección/Teléfono/Datos (Gestión Front)", "column": "J", "index": 9},
        ],
        "output_columns": [
            {"key": "referencia_bo", "name": "Referencia (Gestión BACK OFFICE)", "column": "K", "index": 10, "type": "text"},
            {"key": "caso_salesforce", "name": "Caso SALESFORCE", "column": "L", "index": 11, "type": "text", "maps_to": "caso_salesforce"},
            {"key": "agente_back", "name": "Agente Back", "column": "M", "index": 12, "type": "text"},
            {"key": "resuelto", "name": "Resuelto", "column": "N", "index": 13, "type": "select", "options": ["", "Si", "No", "Rechazado", "No corresponde"]},
            {"key": "observaciones", "name": "Observaciones", "column": "O", "index": 14, "type": "textarea"},
        ],
    },
    {
        "slug": "cancelaciones",
        "sheet_name": "Cancelaciones 2026",
        "display_name": "Cancelaciones 2026",
        "header_row": 3,
        "color": "#ef4444",
        "badge_label": "Cancelaciones",
        "badge_bg": "#ef4444",
        "badge_text_color": "#ffffff",
        "badge_css_class": "badge-cancelaciones",
        "input_columns": [
            {"key": "numero_pedido", "name": "Numero de pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
            {"key": "agente", "name": "Agente", "column": "B", "index": 1, "maps_to": "agente_front"},
            {"key": "id_caso_asunto", "name": "ID CASO / ASUNTO", "column": "C", "index": 2},
            {"key": "fecha", "name": "FECHA", "column": "D", "index": 3, "maps_to": "fecha"},
            {"key": "solicitud", "name": "SOLICITUD", "column": "E", "index": 4, "maps_to": "solicitud"},
            {"key": "sku_producto", "name": "SKU Producto", "column": "F", "index": 5},
            {"key": "tienda", "name": "Tienda", "column": "G", "index": 6, "maps_to": "tienda"},
            {"key": "motivo_cancelacion", "name": "MOTIVO DE CANCELACIÓN", "column": "H", "index": 7},
            {"key": "observaciones_front", "name": "Observaciones", "column": "I", "index": 8},
        ],
        "output_columns": [
            {"key": "estado", "name": "ESTADO", "column": "J", "index": 9, "type": "select", "options": ["", "Frenado", "Cancelado", "Rechazado", "Pendiente"]},
            {"key": "reembolso", "name": "REEMBOLSO", "column": "K", "index": 10, "type": "select", "options": ["", "Reembolsado", "Pendiente", "No solicitado"]},
            {"key": "codigo_sap", "name": "CODIGO SAP (Gestión Back Office)", "column": "L", "index": 11, "type": "text", "maps_to": "codigo_sap"},
            {"key": "observaciones_bo", "name": "OBSERVACIONES", "column": "M", "index": 12, "type": "textarea"},
            {"key": "agente_back", "name": "AGENTE BACK", "column": "N", "index": 13, "type": "text"},
            {"key": "estado_final", "name": "ESTADO FINAL", "column": "O", "index": 14, "type": "select", "options": ["", "Resuelto", "Cerrado", "Rechazado", "Pendiente"]},
        ],
    },
    {
        "slug": "cambio_direccion",
        "sheet_name": "CAMBIO DE DIRECCION 2026",
        "display_name": "Cambio de Dirección 2026",
        "header_row": 2,
        "color": "#8b5cf6",
        "badge_label": "Cambio Dirección",
        "badge_bg": "#8b5cf6",
        "badge_text_color": "#ffffff",
        "badge_css_class": "badge-cambio-direccion",
        "input_columns": [
            {"key": "numero_pedido", "name": "Número de pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
            {"key": "fecha", "name": "Fecha", "column": "B", "index": 1, "maps_to": "fecha"},
            {"key": "numero_caso", "name": "Numero de Caso", "column": "C", "index": 2},
            {"key": "agente_carga", "name": "Agente carga", "column": "D", "index": 3, "maps_to": "agente_front"},
            {"key": "solicitud", "name": "Solicitud", "column": "E", "index": 4, "maps_to": "solicitud"},
            {"key": "direccion", "name": "DIRECCION", "column": "F", "index": 5},
            {"key": "zeco_andreani", "name": "ZECO / ANDREANI", "column": "G", "index": 6},
            {"key": "chequeo_celular", "name": "Chequeo celular", "column": "H", "index": 7},
            {"key": "observaciones_front", "name": "Observaciones", "column": "I", "index": 8},
        ],
        "output_columns": [
            {"key": "asunto_mail", "name": "Asunto Mail", "column": "J", "index": 9, "type": "text"},
            {"key": "agente_back", "name": "Agente Back", "column": "K", "index": 10, "type": "text"},
            {"key": "estado_resuelto", "name": "Estado / Resuelto", "column": "L", "index": 11, "type": "select", "options": ["", "Si", "No", "Rechazado", "Pendiente"]},
            {"key": "observaciones_bo", "name": "Observaciones", "column": "M", "index": 12, "type": "textarea"},
        ],
    },
    {
        "slug": "seguimiento_entregas",
        "sheet_name": "SEGUIMIENTO ENTREGAS 2026",
        "display_name": "Seguimiento Entregas 2026",
        "header_row": 3,
        "color": "#f59e0b",
        "badge_label": "Seg. Entregas",
        "badge_bg": "#f59e0b",
        "badge_text_color": "#0f172a",
        "badge_css_class": "badge-seguimiento-entregas",
        "input_columns": [
            {"key": "fecha_compra", "name": "Fecha de compra/carga", "column": "A", "index": 0, "maps_to": "fecha"},
            {"key": "numero_pedido", "name": "Número de pedido", "column": "B", "index": 1, "maps_to": "pedido_id", "required": True},
            {"key": "tienda", "name": "Tienda", "column": "C", "index": 2, "maps_to": "tienda"},
            {"key": "dni_cuit", "name": "DNI / CUIT", "column": "D", "index": 3, "maps_to": "dni_cuit"},
            {"key": "nombre_completo", "name": "Nombre completo", "column": "E", "index": 4, "maps_to": "nombre_cliente"},
            {"key": "id_wise_origen", "name": "ID Wise / Origen", "column": "F", "index": 5},
            {"key": "tracking", "name": "Tracking", "column": "G", "index": 6, "maps_to": "tracking"},
            {"key": "incidencia", "name": "Incidencia", "column": "H", "index": 7, "maps_to": "solicitud"},
            {"key": "agente_front", "name": "Agente", "column": "I", "index": 8, "maps_to": "agente_front"},
            {"key": "observaciones_front", "name": "Observaciones", "column": "J", "index": 9},
        ],
        "output_columns": [
            {"key": "gestion_realizar", "name": "Gestión a realizar", "column": "K", "index": 10, "type": "text"},
            {"key": "estado_caso", "name": "Estado del caso/entrega", "column": "L", "index": 11, "type": "select", "options": ["", "Cancelado", "Reenvío", "Entregado", "En tránsito", "Rechazado", "Pendiente"]},
            {"key": "asunto_mail", "name": "Asunto Mail", "column": "M", "index": 12, "type": "text"},
            {"key": "observaciones_bo", "name": "Observaciones", "column": "N", "index": 13, "type": "textarea"},
            {"key": "resolucion_final", "name": "Resolución final", "column": "O", "index": 14, "type": "text"},
            {"key": "agente_bo", "name": "Agente BO", "column": "P", "index": 15, "type": "text"},
        ],
    },
    {
        "slug": "reclamo_abierto",
        "sheet_name": "SOLICITUDES CON RECLAMO ABIERTO",
        "display_name": "Solicitudes con Reclamo",
        "header_row": 1,
        "color": "#ec4899",
        "badge_label": "Reclamo Abierto",
        "badge_bg": "#ec4899",
        "badge_text_color": "#ffffff",
        "badge_css_class": "badge-reclamo-abierto",
        "input_columns": [
            {"key": "numero_pedido", "name": "Numero de pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
            {"key": "fecha", "name": "Fecha", "column": "B", "index": 1, "maps_to": "fecha"},
            {"key": "solicitud", "name": "Solicitud", "column": "C", "index": 2, "maps_to": "solicitud"},
            {"key": "direccion_datos", "name": "Dirección/Datos", "column": "D", "index": 3},
        ],
        "output_columns": [
            {"key": "referencia", "name": "Referencia", "column": "E", "index": 4, "type": "text"},
            {"key": "caso_salesforce", "name": "Nº de caso en Salesforce", "column": "F", "index": 5, "type": "text", "maps_to": "caso_salesforce"},
            {"key": "agente", "name": "Agente", "column": "G", "index": 6, "type": "text"},
            {"key": "resuelto", "name": "Resuelto", "column": "H", "index": 7, "type": "select", "options": ["", "Si", "No", "Rechazado"]},
            {"key": "observaciones", "name": "Observaciones", "column": "I", "index": 8, "type": "textarea"},
        ],
    },
    {
        "slug": "reembolsos",
        "sheet_name": "REEMBOLSOS",
        "display_name": "Reembolsos",
        "header_row": 1,
        "color": "#10b981",
        "badge_label": "Reembolsos",
        "badge_bg": "#10b981",
        "badge_text_color": "#ffffff",
        "badge_css_class": "badge-reembolsos",
        "input_columns": [
            {"key": "numero_pedido", "name": "Número de pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
            {"key": "agente_front", "name": "Agente (Front)", "column": "B", "index": 1, "maps_to": "agente_front"},
            {"key": "fecha_compra", "name": "Fecha de compra", "column": "C", "index": 2, "maps_to": "fecha"},
            {"key": "tienda", "name": "Tienda", "column": "D", "index": 3, "maps_to": "tienda"},
            {"key": "motivo_reembolso", "name": "Motivo de reembolso", "column": "E", "index": 4, "maps_to": "solicitud"},
            {"key": "zre", "name": "ZRE2 / ZRE4", "column": "F", "index": 5, "maps_to": "codigo_sap"},
            {"key": "tipo_reembolso", "name": "Tipo de reembolso", "column": "G", "index": 6},
            {"key": "tarjeta_tid", "name": "Tarjeta / TID", "column": "H", "index": 7},
            {"key": "correo_cliente", "name": "Correo del cliente", "column": "I", "index": 8, "maps_to": "email_cliente"},
        ],
        "output_columns": [
            {"key": "gestion_back", "name": "Gestión Back", "column": "J", "index": 9, "type": "textarea"},
            {"key": "agente_back", "name": "Agente (Back/TL)", "column": "K", "index": 10, "type": "text"},
            {"key": "observacion_adicional", "name": "Observación adicional", "column": "L", "index": 11, "type": "textarea"},
        ],
    },
    {
        "slug": "casos_salesforce",
        "sheet_name": "CASOS SALESFORCE - FRONT BGH",
        "display_name": "Casos Salesforce",
        "header_row": 1,
        "color": "#0ea5e9",
        "badge_label": "Casos Salesforce",
        "badge_bg": "#0ea5e9",
        "badge_text_color": "#ffffff",
        "badge_css_class": "badge-casos-salesforce",
        "input_columns": [
            {"key": "fecha", "name": "Fecha", "column": "A", "index": 0, "maps_to": "fecha"},
            {"key": "nro_pedido", "name": "Nro de Pedido", "column": "B", "index": 1, "maps_to": "pedido_id", "required": True},
            {"key": "caso_wise", "name": "Caso en Wise", "column": "C", "index": 2},
            {"key": "caso_salesforce", "name": "Caso en Salesforce", "column": "D", "index": 3, "maps_to": "caso_salesforce"},
            {"key": "factura", "name": "Cuenta con Factura?", "column": "E", "index": 4},
            {"key": "agente", "name": "Agente", "column": "F", "index": 5, "maps_to": "agente_front"},
            {"key": "motivo", "name": "Motivo", "column": "G", "index": 6, "maps_to": "solicitud"},
            {"key": "comentarios", "name": "Comentarios adicionales", "column": "H", "index": 7},
        ],
        "output_columns": [
            {"key": "back_office", "name": "Back Office", "column": "I", "index": 8, "type": "textarea"},
        ],
    },
    {
        "slug": "seguimiento_retiros",
        "sheet_name": "No tocar Retiros arrepentimient",
        "display_name": "Seguimiento de Retiros (Arrepentimiento)",
        "header_row": 1,
        "color": "#0891b2",
        "badge_label": "Seguimiento de Retiros",
        "badge_bg": "#0891b2",
        "badge_text_color": "#ffffff",
        "badge_css_class": "badge-seguimiento-retiros",
        "input_columns": [
            {"key": "numero_pedido", "name": "Numero de pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
            {"key": "fecha", "name": "Fecha", "column": "B", "index": 1, "maps_to": "fecha"},
            {"key": "agente", "name": "Agente", "column": "C", "index": 2, "maps_to": "agente_front"},
            {"key": "caso", "name": "Caso", "column": "D", "index": 3},
            {"key": "tienda", "name": "Tienda", "column": "E", "index": 4, "maps_to": "tienda"},
            {"key": "tipo", "name": "Tipo", "column": "F", "index": 5, "maps_to": "solicitud"},
            {"key": "estado_retiro", "name": "Estado de retiro", "column": "G", "index": 6},
            {"key": "reembolso", "name": "Reembolso", "column": "H", "index": 7},
            {"key": "zre2", "name": "ZRE2", "column": "I", "index": 8, "maps_to": "codigo_sap"},
            {"key": "ultimo_estado", "name": "Ultimo estado", "column": "J", "index": 9},
        ],
        "output_columns": [
            {"key": "obs", "name": "OBS", "column": "K", "index": 10, "type": "textarea"},
        ],
    },
]


def run_seed():
    """Inicializa usuarios base y tipologías si no existen."""
    # ── Admin ──
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(username="admin", display_name="Administrador", role="admin")
        admin.set_password("admin123")
        admin.is_active_user = True
        db.session.add(admin)
        print("[OK] Admin creado (admin / admin123)")
    else:
        admin.role = "admin"
        admin.is_active_user = True

    # ── Supervisor ──
    supervisor = User.query.filter_by(username="supervisor").first()
    if not supervisor:
        supervisor = User(username="supervisor", display_name="Mariana Valdez (Supervisora)", role="supervisor")
        supervisor.set_password("super123")
        supervisor.is_active_user = True
        db.session.add(supervisor)
        print("[OK] Supervisor creado (supervisor / super123)")
    else:
        supervisor.role = "supervisor"
        supervisor.is_active_user = True

    # ── Usuario Jorge (Back Office) ──
    jorge = User.query.filter_by(username="jorge").first()
    if not jorge:
        jorge = User(username="jorge", display_name="Jorge Zolabarrieta", role="agente_back")
        jorge.set_password("jorge123")
        jorge.is_active_user = True
        db.session.add(jorge)
        print("[OK] Usuario Jorge creado (jorge / jorge123)")
    else:
        jorge.role = "agente_back"
        jorge.is_active_user = True

    # ── Usuario Front ──
    front1 = User.query.filter_by(username="front").first()
    if not front1:
        front1 = User(username="front", display_name="Agustina Gómez (Front)", role="agente_front")
        front1.set_password("front123")
        front1.is_active_user = True
        db.session.add(front1)
        print("[OK] Usuario Front creado (front / front123)")
    else:
        front1.role = "agente_front"
        front1.is_active_user = True

    # ── Usuario TYQ (Calidad) ──
    calidad1 = User.query.filter_by(username="calidad").first()
    if not calidad1:
        calidad1 = User(username="calidad", display_name="Lucas Pereyra (Calidad TYQ)", role="tyq")
        calidad1.set_password("calidad123")
        calidad1.is_active_user = True
        db.session.add(calidad1)
        print("[OK] Usuario TYQ creado (calidad / calidad123)")
    else:
        calidad1.role = "tyq"
        calidad1.is_active_user = True

    # ── Migrar usuarios con rol fantasma "agent" a "agente_back" ──
    ghost_agents = User.query.filter_by(role="agent").all()
    for u in ghost_agents:
        u.role = "agente_back"
        print(f"[MIGRATED] Usuario '{u.username}' migrado de 'agent' a 'agente_back'")

    db.session.commit()

    # ── Hojas / Tipologías ──
    for sheet_data in SHEETS:
        existing = SheetConfig.query.filter_by(sheet_name=sheet_data["sheet_name"]).first()
        if not existing:
            sheet = SheetConfig(
                slug=sheet_data["slug"],
                sheet_name=sheet_data["sheet_name"],
                display_name=sheet_data["display_name"],
                header_row=sheet_data["header_row"],
                color=sheet_data["color"],
                badge_label=sheet_data.get("badge_label"),
                badge_bg=sheet_data.get("badge_bg"),
                badge_text_color=sheet_data.get("badge_text_color"),
                badge_css_class=sheet_data.get("badge_css_class"),
                input_columns=json.dumps(sheet_data["input_columns"], ensure_ascii=False),
                output_columns=json.dumps(sheet_data["output_columns"], ensure_ascii=False),
                is_active=True,
            )
            db.session.add(sheet)
            print(f"[OK] Hoja '{sheet_data['display_name']}' configurada (slug: {sheet_data['slug']})")
        else:
            # Actualizar campos existentes incluyendo los nuevos
            existing.slug = sheet_data["slug"]
            existing.input_columns = json.dumps(sheet_data["input_columns"], ensure_ascii=False)
            existing.output_columns = json.dumps(sheet_data["output_columns"], ensure_ascii=False)
            existing.header_row = sheet_data["header_row"]
            existing.color = sheet_data["color"]
            existing.badge_label = sheet_data.get("badge_label")
            existing.badge_bg = sheet_data.get("badge_bg")
            existing.badge_text_color = sheet_data.get("badge_text_color")
            existing.badge_css_class = sheet_data.get("badge_css_class")

    db.session.commit()

    # ── Asignar hojas a administradores, supervisores y Jorge ──
    for u in User.query.filter(User.role.in_(["admin", "supervisor", "agente_back"])).all():
        for s in SheetConfig.query.all():
            if s not in u.assigned_sheets.all():
                u.assigned_sheets.append(s)

    db.session.commit()


def seed():
    from app import create_app
    app = create_app()
    with app.app_context():
        db.create_all()
        run_seed()
        print("\n[OK] Seed completado con éxito.")
        print("   Admin:       admin / admin123")
        print("   Supervisor:  supervisor / super123")
        print("   Back Office: jorge / jorge123")
        print("   Front:       front / front123")
        print("   Calidad TYQ: calidad / calidad123")


if __name__ == "__main__":
    seed()
