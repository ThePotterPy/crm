import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, SheetConfig, User, Case

app = create_app()

TYPOLOGIES = [
    {
        "display_name": "Retiro arrepentimiento",
        "sheet_name": "SOLICITUDES BGH 2026 - Retiro arrepentimiento",
        "color": "#0052cc",
        "default_solicitud": "Retiro arrepentimiento"
    },
    {
        "display_name": "SEGUIMIENTO",
        "sheet_name": "SOLICITUDES BGH 2026 - SEGUIMIENTO",
        "color": "#facc15",
        "default_solicitud": "SEGUIMIENTO"
    },
    {
        "display_name": "Otros",
        "sheet_name": "SOLICITUDES BGH 2026 - Otros",
        "color": "#581c87",
        "default_solicitud": "Otros"
    },
    {
        "display_name": "NC POR FACTURA B",
        "sheet_name": "SOLICITUDES BGH 2026 - NC POR FACTURA B",
        "color": "#991b1b",
        "default_solicitud": "NC POR FACTURA B"
    },
    {
        "display_name": "CAMBIO INCORRECTO",
        "sheet_name": "SOLICITUDES BGH 2026 - CAMBIO INCORRECTO",
        "color": "#f87171",
        "default_solicitud": "CAMBIO INCORRECTO"
    },
    {
        "display_name": "CAMBIO DEFECTUOSO",
        "sheet_name": "SOLICITUDES BGH 2026 - CAMBIO DEFECTUOSO",
        "color": "#065f46",
        "default_solicitud": "CAMBIO DEFECTUOSO"
    },
]

INPUT_COLUMNS = [
    {"key": "id_pedido", "name": "ID Pedido", "column": "A", "index": 0},
    {"key": "fecha", "name": "Fecha", "column": "B", "index": 1},
    {"key": "agente_carga", "name": "Agente carga", "column": "C", "index": 2},
    {"key": "sku", "name": "SKU", "column": "D", "index": 3},
    {"key": "caso_id_wise", "name": "CASO ID WISE", "column": "E", "index": 4},
    {"key": "tienda", "name": "Tienda", "column": "F", "index": 5},
    {
        "key": "solicitud",
        "name": "Solicitud",
        "column": "G",
        "index": 6,
        "type": "select",
        "options": ["Retiro arrepentimiento", "SEGUIMIENTO", "Otros", "NC POR FACTURA B", "CAMBIO INCORRECTO", "CAMBIO DEFECTUOSO"]
    },
    {
        "key": "motivos",
        "name": "Motivos - Retiros Arrepentimiento",
        "column": "H",
        "index": 7,
        "type": "select",
        "options": ["", "Arrepentimiento de compra", "Demora en entrega", "Producto no era lo esperado", "Compró por error", "Encontró mejor precio", "Otro motivo"]
    },
    {"key": "observacion_detalle", "name": "Observación - Detalle del inconveniente", "column": "I", "index": 8},
    {"key": "direccion_datos", "name": "Dirección/Teléfono/Datos (Gestión Front)", "column": "J", "index": 9},
]

OUTPUT_COLUMNS = [
    {"key": "referencia_bo", "name": "Referencia (Gestión BACK OFFICE)", "column": "K", "index": 10, "type": "text"},
    {"key": "caso_salesforce", "name": "Caso SALESFORCE", "column": "L", "index": 11, "type": "text"},
    {"key": "agente_back", "name": "Agente Back", "column": "M", "index": 12, "type": "text"},
    {"key": "resuelto", "name": "Resuelto", "column": "N", "index": 13, "type": "select", "options": ["", "Si", "No", "Rechazado", "No corresponde"]},
    {"key": "observaciones", "name": "Observaciones", "column": "O", "index": 14, "type": "textarea"},
]

def migrate():
    with app.app_context():
        print("Migrando 'SOLICITUDES BGH 2026' a las 6 tipologias exactas...")

        # Buscar si existe la hoja 1 'SOLICITUDES BGH 2026'
        old_sheet = SheetConfig.query.filter(
            (SheetConfig.sheet_name == "SOLICITUDES BGH 2026") | 
            (SheetConfig.display_name == "Solicitudes BGH 2026")
        ).first()

        users_to_assign = User.query.filter(User.role.in_(["admin", "supervisor", "agente_back"])).all()

        typology_configs = []
        for i, t in enumerate(TYPOLOGIES):
            if i == 0 and old_sheet:
                # Actualizar la hoja #1 existente a "Retiro arrepentimiento"
                old_sheet.sheet_name = t["sheet_name"]
                old_sheet.display_name = t["display_name"]
                old_sheet.color = t["color"]
                old_sheet.input_columns = json.dumps(INPUT_COLUMNS, ensure_ascii=False)
                old_sheet.output_columns = json.dumps(OUTPUT_COLUMNS, ensure_ascii=False)
                sc = old_sheet
                print(f"[OK] Hoja existente #{old_sheet.id} actualizada a '{t['display_name']}'")
            else:
                # Buscar si ya existe
                sc = SheetConfig.query.filter_by(sheet_name=t["sheet_name"]).first()
                if not sc:
                    sc = SheetConfig(
                        sheet_name=t["sheet_name"],
                        display_name=t["display_name"],
                        header_row=1,
                        color=t["color"],
                        input_columns=json.dumps(INPUT_COLUMNS, ensure_ascii=False),
                        output_columns=json.dumps(OUTPUT_COLUMNS, ensure_ascii=False),
                    )
                    db.session.add(sc)
                    db.session.flush()
                    print(f"[OK] Creada tipología '{t['display_name']}' con color {t['color']}")
                else:
                    sc.display_name = t["display_name"]
                    sc.color = t["color"]
                    sc.input_columns = json.dumps(INPUT_COLUMNS, ensure_ascii=False)
                    sc.output_columns = json.dumps(OUTPUT_COLUMNS, ensure_ascii=False)
                    print(f"[OK] Actualizada tipología existente '{t['display_name']}'")

            # Asignar a los agentes back y admin
            for u in users_to_assign:
                if sc not in u.assigned_sheets.all():
                    u.assigned_sheets.append(sc)
            typology_configs.append(sc)

        db.session.commit()
        print("\n[MIGRACION EXITOSA] Las 6 tipologías fueron configuradas y asignadas.")

if __name__ == "__main__":
    migrate()
