import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User, SheetConfig, Case, RolePermission

app = create_app()

def run_tests():
    with app.app_context():
        print("=== INICIANDO PRUEBAS DE PERMISOS Y TIPOS DE CASOS ===")
        client = app.test_client()

        import time
        run_id = str(int(time.time()))

        # 1. Login con Jorge (Back Office)
        res = client.post("/login", data={"username": "jorge", "password": "jorge123"}, follow_redirects=True)
        assert res.status_code == 200
        jorge = User.query.filter_by(username="jorge").first()
        assert jorge.can_create_cases == True, "Jorge debería poder crear casos"
        assert jorge.can_resolve_cases == True, "Jorge debería poder resolver casos"
        print("[OK] 1. Permisos de Jorge verificados: can_create_cases=True, can_resolve_cases=True")

        # 2. Jorge crea un nuevo caso desde /nuevo-caso
        sheet = SheetConfig.query.filter_by(is_active=True).first()
        if sheet not in jorge.assigned_sheets.all():
            jorge.assigned_sheets.append(sheet)
            db.session.commit()
        test_ped = f"PED-BACK-{run_id}"
        res = client.post("/nuevo-caso", data={
            "sheet_id": sheet.id,
            "pedido_id": test_ped,
            "input_id_pedido": test_ped,
            "fecha": "2026-09-17",
            "solicitud": sheet.display_name,
            "input_observacion_detalle": "Creado por Back Office directamente",
        }, follow_redirects=True)
        assert res.status_code == 200
        case = Case.query.filter_by(pedido_id=test_ped).first()
        assert case is not None, "El caso creado por Back Office no se encontró"
        assert case.assigned_to == jorge.id, f"El caso debería estar asignado a Jorge como encargado, está en {case.assigned_to}"
        assert case.created_by == jorge.id
        print(f"[OK] 2. Caso #{case.id} creado por Jorge y asignado al encargado correctamente")

        # 3. Intentar resolver sin evidencia (debe fallar la validación segura)
        res = client.post(f"/caso/{case.id}/gestionar", data={
            "action": "resolver",
            "caso_salesforce": "",
            "codigo_sap": "",
        }, follow_redirects=True)
        assert "Para marcar el caso como RESUELTO" in res.get_data(as_text=True)
        case = Case.query.get(case.id)
        assert case.status != "resuelto", "No debería resolverse sin datos"
        print("[OK] 3. Validación de Resolución Segura: rechaza resolución sin evidencia")

        # 4. Resolver con evidencia
        res = client.post(f"/caso/{case.id}/gestionar", data={
            "action": "resolver",
            "caso_salesforce": "SF-998877",
            "codigo_sap": "SAP-12345",
            "output_observaciones": "Resuelto con cambio autorizado",
        }, follow_redirects=True)
        assert res.status_code == 200
        case = Case.query.get(case.id)
        assert case.status == "resuelto"
        assert case.caso_salesforce == "SF-998877"
        print(f"[OK] 4. Caso #{case.id} resuelto exitosamente por Back Office con datos de gestión")

        # 5. Tomar caso (Claim)
        # Crear un caso sin asignar
        unassigned_case = Case(
            sheet_config_id=sheet.id,
            pedido_id="PED-UNASSIGNED-01",
            solicitud=sheet.display_name,
            created_by=jorge.id,
            assigned_to=None,
            status="nuevo",
        )
        db.session.add(unassigned_case)
        db.session.commit()
        assert unassigned_case.assigned_to is None

        res = client.post(f"/caso/{unassigned_case.id}/tomar", follow_redirects=True)
        assert res.status_code == 200
        unassigned_case = Case.query.get(unassigned_case.id)
        assert unassigned_case.assigned_to == jorge.id
        assert unassigned_case.status == "en_proceso"
        print(f"[OK] 5. Caso #{unassigned_case.id} tomado exitosamente por Jorge")

        # 6. Reasignación por Supervisor
        client.get("/logout", follow_redirects=True)
        client.post("/login", data={"username": "supervisor", "password": "super123"}, follow_redirects=True)
        super_user = User.query.filter_by(username="supervisor").first()
        admin_user = User.query.filter_by(username="admin").first()

        res = client.post(f"/caso/{unassigned_case.id}/reasignar", data={
            "nuevo_agente_id": admin_user.id
        }, follow_redirects=True)
        assert res.status_code == 200
        unassigned_case = Case.query.get(unassigned_case.id)
        assert unassigned_case.assigned_to == admin_user.id
        print(f"[OK] 6. Caso #{unassigned_case.id} reasignado exitosamente a Admin por el Supervisor")

        # 7. Crear nuevo Tipo de Caso
        res = client.post("/admin/tipos-casos/crear", data={
            "display_name": "GARANTIA ESPECIAL BGH",
            "color": "#7c3aed",
            "description": "Casos de garantía extendida",
        }, follow_redirects=True)
        assert res.status_code == 200
        new_type = SheetConfig.query.filter_by(display_name="GARANTIA ESPECIAL BGH").first()
        assert new_type is not None
        assert new_type.color == "#7c3aed"
        badge = new_type.badge_style
        assert badge["label"] == "GARANTIA ESPECIAL BGH"
        assert badge["bg"] == "#7c3aed"
        print(f"[OK] 7. Nuevo Tipo de Caso '{new_type.display_name}' creado con color {new_type.color}")

        # 8. Modificar Tipo de Caso
        res = client.post(f"/admin/tipos-casos/{new_type.id}/editar", data={
            "display_name": "GARANTIA PREMIUM BGH",
            "color": "#f59e0b",
            "description": "Actualizado a Premium",
        }, follow_redirects=True)
        assert res.status_code == 200
        new_type = SheetConfig.query.get(new_type.id)
        assert new_type.display_name == "GARANTIA PREMIUM BGH"
        assert new_type.color == "#f59e0b"
        print(f"[OK] 8. Tipo de Caso modificado a '{new_type.display_name}' con color {new_type.color}")

        # 9. Guardar Matriz de Permisos
        res = client.post("/admin/permisos/guardar", data={
            "admin_can_create_cases": "on",
            "admin_can_resolve_cases": "on",
            "supervisor_can_create_cases": "on",
            "supervisor_can_resolve_cases": "on",
            "agente_back_can_create_cases": "on",
            "agente_back_can_resolve_cases": "on",
            "agente_back_can_export_reports": "on",
            "agente_front_can_create_cases": "on",
            "tyq_can_audit_quality": "on",
            "tyq_can_export_reports": "on",
            "tyq_can_view_all_cases": "on",
        }, follow_redirects=True)
        assert res.status_code == 200
        perm_back = RolePermission.get_for_role("agente_back")
        assert perm_back.can_create_cases == True
        assert perm_back.can_resolve_cases == True
        print("[OK] 9. Matriz de permisos actualizada y persistida correctamente")

        print("\n[EXITO TOTAL] Todos los flujos y validaciones pasaron exitosamente.")

if __name__ == "__main__":
    run_tests()
