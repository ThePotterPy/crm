import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding='utf-8')

from app import create_app
from models import db, SheetConfig, Case, user_sheet_assignments, is_light_color

app = create_app()

with app.app_context():
    print("=== PASO 1: DIAGNÓSTICO PREVIO A LA PURGA ===")
    all_sheets = SheetConfig.query.all()
    print(f"Total tipos de casos encontrados: {len(all_sheets)}")

    # Identificar duplicados o candidatos a purga
    # IDs 14 a 18 son GARANTIA PREMIUM BGH con 0 casos
    purge_ids = [s.id for s in all_sheets if s.id >= 14 or (s.cases.count() == 0 and "GARANTIA" in s.display_name.upper())]
    print(f"IDs a purgar: {purge_ids}")

    for sid in purge_ids:
        sheet = db.session.get(SheetConfig, sid)
        if sheet:
            cases_count = Case.query.filter_by(sheet_config_id=sheet.id).count()
            print(f"Purgando ID {sheet.id}: '{sheet.display_name}' ({sheet.sheet_name}) - Casos asociados: {cases_count}")
            assert cases_count == 0, f"SEGURIDAD: La tipología {sheet.id} tiene {cases_count} casos y no debe borrarse."
            
            # Limpiar asignaciones en user_sheet_assignments
            db.session.execute(
                user_sheet_assignments.delete().where(user_sheet_assignments.c.sheet_config_id == sheet.id)
            )
            # Eliminar la tipología
            db.session.delete(sheet)

    db.session.commit()
    print(f"✅ {len(purge_ids)} tipos de casos basura eliminados de forma limpia.")

    print("\n=== PASO 2: NORMALIZACIÓN Y REPARACIÓN DE TIPOLOGÍAS OFICIALES ===")
    remaining_sheets = SheetConfig.query.order_by(SheetConfig.id).all()
    print(f"Tipologías restantes: {len(remaining_sheets)}")

    for s in remaining_sheets:
        # Reparar caracteres corruptos
        if "Direcci" in s.display_name:
            s.display_name = "Cambio de Dirección 2026"
            s.badge_label = "Cambio Dirección"
        if "Direcci" in s.sheet_name:
            s.sheet_name = "CAMBIO DE DIRECCION 2026"

        # Asegurar colores válidos
        if not s.color or not s.color.startswith("#"):
            s.color = "#6366f1"
        if not s.badge_bg or not s.badge_bg.startswith("#"):
            s.badge_bg = s.color
        if not s.badge_text_color or not s.badge_text_color.startswith("#"):
            s.badge_text_color = "#0f172a" if is_light_color(s.badge_bg) else "#ffffff"
        if not s.badge_label:
            s.badge_label = s.display_name

        print(f"ID {s.id:2d} | Slug: {s.slug:25s} | Nombre: {s.display_name:32s} | BG: {s.badge_bg} | Text: {s.badge_text_color}")

    db.session.commit()
    print("✅ Todas las tipologías restantes normalizadas con colores y badges válidos.")
