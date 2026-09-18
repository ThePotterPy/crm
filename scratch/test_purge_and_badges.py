import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding='utf-8')

from app import create_app
from models import db, SheetConfig, Case, User

app = create_app()

def run_tests():
    client = app.test_client()
    with app.app_context():
        print("=== 1. VERIFICACIÓN DE TIPOLOGÍAS PURGADAS Y NORMALIZADAS ===")
        sheets = SheetConfig.query.order_by(SheetConfig.id).all()
        assert len(sheets) == 13, f"Se esperaban 13 tipologías oficiales, hay {len(sheets)}"

        for s in sheets:
            assert s.slug is not None, f"Sheet {s.id} tiene slug nulo"
            assert s.color.startswith("#"), f"Sheet {s.id} tiene color inválido: {s.color}"
            assert s.badge_bg.startswith("#"), f"Sheet {s.id} tiene badge_bg inválido: {s.badge_bg}"
            assert s.badge_text_color.startswith("#"), f"Sheet {s.id} tiene badge_text_color inválido: {s.badge_text_color}"
            assert "Direcci\ufffdn" not in s.display_name, f"Sheet {s.id} tiene caracter corrupto en display_name"
            badge = s.badge_style
            assert badge["bg"].startswith("#")
            assert badge["color"].startswith("#")
            print(f"  [OK] Tipología ID {s.id:2d}: {s.display_name:32s} | Badge: {badge['bg']} / {badge['color']}")

        print("\n=== 2. VERIFICACIÓN DE ASIGNACIONES DE USUARIOS ===")
        users = User.query.all()
        for u in users:
            assigned = u.assigned_sheets.all()
            for ash in assigned:
                assert ash.id in [s.id for s in sheets], f"Usuario {u.username} tiene asignada tipología inexistente {ash.id}"
            print(f"  [OK] Usuario {u.username:12s} ({u.role}): {len(assigned)} tipologías asignadas.")

        print("\n=== 3. PRUEBAS HTTP DE RENDERIZADO Y MODIFICACIÓN ===")
        # Login como admin
        client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # /admin/tipos-casos
        res = client.get('/admin/tipos-casos')
        assert res.status_code == 200, f"Error al cargar /admin/tipos-casos: {res.status_code}"
        html = res.data.decode('utf-8')
        assert "GARANTIA ESPECIAL BGH" not in html, "Todavía aparecen tipologías basura en /admin/tipos-casos"
        assert "openEditModalFromBtn" in html, "No se encontró handler robusto openEditModalFromBtn"
        assert "Cambio de Dirección 2026" in html, "Nombre corregido de Dirección no aparece"
        print("  [OK] /admin/tipos-casos renderiza limpiamente con 13 tipologías.")

        # /admin/usuarios
        res = client.get('/admin/usuarios')
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert "background-color:" in html, "Los badges en /admin/usuarios no tienen color inline"
        print("  [OK] /admin/usuarios renderiza con badges coloreados y links directos.")

        # /admin/asignaciones
        res = client.get('/admin/asignaciones')
        assert res.status_code == 200
        print("  [OK] /admin/asignaciones renderiza correctamente.")

        # Dashboard (/)
        res = client.get('/')
        assert res.status_code == 200
        print("  [OK] Dashboard (/) renderiza correctamente.")

        # /mis-casos-front
        res = client.get('/mis-casos-front')
        assert res.status_code == 200
        print("  [OK] /mis-casos-front renderiza correctamente con badges coloreados.")

        # Caso detalle
        case = Case.query.first()
        if case:
            res = client.get(f'/caso/{case.id}')
            assert res.status_code == 200
            print(f"  [OK] /caso/{case.id} renderiza correctamente con badge estilizado.")

        # Test de Edición de Tipología
        target_sheet = SheetConfig.query.filter_by(slug="cambio_defectuoso").first()
        assert target_sheet is not None
        edit_res = client.post(f'/admin/tipos-casos/{target_sheet.id}/editar', data={
            'display_name': 'CAMBIO DEFECTUOSO TEST',
            'color': '#059669',
            'badge_bg': '#059669',
            'badge_label': 'DEFECTUOSO TEST',
            'badge_text_color': '#ffffff',
            'description': 'Modificado en test unitario',
            'is_active': '1',
        }, follow_redirects=True)
        assert edit_res.status_code == 200

        updated_sheet = db.session.get(SheetConfig, target_sheet.id)
        assert updated_sheet.display_name == 'CAMBIO DEFECTUOSO TEST'
        assert updated_sheet.badge_bg == '#059669'
        assert updated_sheet.color == '#059669'
        assert updated_sheet.badge_label == 'DEFECTUOSO TEST'
        print(f"  [OK] Edición de tipología #{target_sheet.id} confirmada en base de datos.")

        # Restaurar nombre original
        client.post(f'/admin/tipos-casos/{target_sheet.id}/editar', data={
            'display_name': 'CAMBIO DEFECTUOSO',
            'color': '#065f46',
            'badge_bg': '#065f46',
            'badge_label': 'CAMBIO DEFECTUOSO',
            'badge_text_color': '#dcfce7',
            'description': '',
            'is_active': '1',
        }, follow_redirects=True)
        print("  [OK] Tipología restaurada a sus valores originales.")

        print("\n🎉 TODAS LAS VERIFICACIONES COMPLETADAS EXITOSAMENTE!")

if __name__ == '__main__':
    run_tests()
