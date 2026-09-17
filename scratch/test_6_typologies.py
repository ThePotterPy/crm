import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User, SheetConfig, Case

app = create_app()

def test_typologies():
    with app.app_context():
        print("=== PROBANDO LAS 6 TIPOLOGÍAS ===")
        typology_names = [
            "Retiro arrepentimiento",
            "SEGUIMIENTO",
            "Otros",
            "NC POR FACTURA B",
            "CAMBIO INCORRECTO",
            "CAMBIO DEFECTUOSO"
        ]

        front_user = User.query.filter_by(username="front").first()
        back_user = User.query.filter_by(username="jorge").first()

        for name in typology_names:
            sheet = SheetConfig.query.filter_by(display_name=name).first()
            assert sheet is not None, f"No se encontró la hoja con display_name: {name}"
            badge = sheet.badge_style
            print(f"[HOJA] {name} -> Label: '{badge['label']}', BG: {badge['bg']}, Class: {badge['css_class']}")

            # Crear caso simulado
            c = Case(
                sheet_config_id=sheet.id,
                pedido_id=f"TEST-{name[:3].upper()}-999",
                solicitud=name,
                tienda="BGH Tienda Online",
                agente_front="Agente Front Test",
                created_by=front_user.id if front_user else None,
                assigned_to=back_user.id if back_user else None,
                status="nuevo"
            )
            case_badge = c.typology_badge
            assert case_badge["label"] == name, f"Esperaba label {name}, obtuve {case_badge['label']}"
            print(f"  -> Caso Badge OK: {case_badge}")

        print("\n[EXITO] TODAS LAS 6 TIPOLOGIAS TIENEN SU BADGE Y ESTILO EXACTO.")

if __name__ == "__main__":
    test_typologies()
