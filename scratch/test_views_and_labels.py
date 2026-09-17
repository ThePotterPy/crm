import sys
import os

# Asegurar path
sys.path.insert(0, os.path.abspath("."))

from app import create_app
from models import db, User, Case, SheetConfig

def run_tests():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as client:
        # 1. Test login as admin
        resp = client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
        assert resp.status_code == 200, f"Login falló: {resp.status_code}"
        html = resp.data.decode("utf-8")

        # 2. Verificar que el navbar superior contiene "Todos los Casos" y "Casos Asignados"
        assert "Todos los Casos" in html, "No se encontró 'Todos los Casos' en la barra de navegación superior"
        assert "Casos Asignados" in html, "No se encontró 'Casos Asignados' en la barra de navegación superior"
        print("[TEST 1 PASSED] Navbar superior contiene 'Todos los Casos' y 'Casos Asignados'.")

        # 3. Verificar que NO aparece "Todas las hojas" en el HTML
        assert "Todas las hojas" not in html, "Aparece 'Todas las hojas' en el HTML del dashboard"
        assert "Todos los tipos de caso" in html, "No se encontró 'Todos los tipos de caso' en el desplegable de filtro"
        print("[TEST 2 PASSED] Desplegable muestra 'Todos los tipos de caso' (eliminado 'Todas las hojas').")

        # 4. Verificar vista ?view=todos
        resp_todos = client.get("/?view=todos")
        assert resp_todos.status_code == 200
        html_todos = resp_todos.data.decode("utf-8")
        assert "Todos los Casos" in html_todos
        assert "Bandeja operativa global" in html_todos
        print("[TEST 3 PASSED] Vista ?view=todos carga correctamente.")

        # 5. Verificar vista ?view=asignados
        resp_asig = client.get("/?view=asignados")
        assert resp_asig.status_code == 200
        html_asig = resp_asig.data.decode("utf-8")
        assert "Mis Casos Asignados" in html_asig
        assert "Bandeja personal de gestión" in html_asig
        print("[TEST 4 PASSED] Vista ?view=asignados carga correctamente.")

        # 6. Test login as Jorge (Back Office)
        client.get("/logout", follow_redirects=True)
        resp_jorge = client.post("/login", data={"username": "jorge", "password": "jorge123"}, follow_redirects=True)
        assert resp_jorge.status_code == 200
        html_jorge = resp_jorge.data.decode("utf-8")

        # Jorge debe ver ambos apartados en la barra superior
        assert "Todos los Casos" in html_jorge, "Jorge no ve 'Todos los Casos'"
        assert "Casos Asignados" in html_jorge, "Jorge no ve 'Casos Asignados'"
        print("[TEST 5 PASSED] Agente Back Office (Jorge) ve ambos apartados en el navbar.")

        # 7. Test filtro por tipo de caso (sheet_id) manteniendo view=asignados
        with app.app_context():
            first_sheet = SheetConfig.query.filter_by(is_active=True).first()
            sheet_id = first_sheet.id if first_sheet else 1

        resp_filter = client.get(f"/?view=asignados&sheet={sheet_id}")
        assert resp_filter.status_code == 200
        html_filter = resp_filter.data.decode("utf-8")
        assert 'name="view" value="asignados"' in html_filter, "El form de filtros no preserva el parámetro view"
        print("[TEST 6 PASSED] Filtros preservan view='asignados'.")

        # 8. Test nuevo caso template - verificar que no dice 'hoja'
        resp_nuevo = client.get("/nuevo-caso")
        assert resp_nuevo.status_code == 200
        html_nuevo = resp_nuevo.data.decode("utf-8")
        assert "Seleccioná el Tipo de Caso *" in html_nuevo
        assert "Hoja BGH" not in html_nuevo
        print("[TEST 7 PASSED] /nuevo-caso no menciona 'Hoja BGH'.")

        # 9. Test reportes - verificar que no dice 'Tipo de Caso (Hoja)'
        resp_rep = client.get("/reportes")
        assert resp_rep.status_code == 200
        html_rep = resp_rep.data.decode("utf-8")
        assert "Tipo de Caso (Hoja)" not in html_rep
        print("[TEST 8 PASSED] /reportes no menciona 'Tipo de Caso (Hoja)'.")

    print("\n>>> ¡TODOS LOS 8 TESTS PASARON EXITOSAMENTE AL 100%! <<<")

if __name__ == "__main__":
    run_tests()
