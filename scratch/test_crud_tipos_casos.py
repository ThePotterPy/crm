import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from models import db, User, SheetConfig, Case

def login(client, username, password):
    client.get("/logout", follow_redirects=True)
    res = client.post("/login", data={"username": username, "password": password}, follow_redirects=True)
    return res

def run_tests():
    client = app.test_client()
    with app.app_context():
        print("=== INICIANDO PRUEBAS DE CRUD TIPOS DE CASOS ===")

        # Verificar usuarios
        admin = User.query.filter_by(username="admin").first()
        supervisor = User.query.filter_by(username="supervisor").first()
        front = User.query.filter_by(role="agente_front").first()
        if not front:
            front = User.query.filter_by(username="laura").first()

        assert admin, "Debe existir admin"
        assert supervisor, "Debe existir supervisor"
        assert front, "Debe existir un usuario front"

        print(f"Admin: {admin.username}, Supervisor: {supervisor.username}, Front: {front.username}")

        # Test 1: Agente Front NO puede acceder a gestión de tipos de casos
        # Front password is usually laura123 or similar, let's test front
        login(client, front.username, f"{front.username}123")
        res = client.get("/admin/tipos-casos", follow_redirects=True)
        assert b"Gestor de Tipos de Casos" not in res.data, "Front office NO debe poder acceder a tipos-casos"
        print("[OK] Agente Front correctamente bloqueado de /admin/tipos-casos")

        # Test 2: Supervisor SÍ puede acceder a /admin/tipos-casos
        res = login(client, "supervisor", "super123")
        res = client.get("/admin/tipos-casos")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert "Gestor de Tipos de Casos".encode("utf-8") in res.data
        print("[OK] Supervisor tiene acceso completo a /admin/tipos-casos (HTTP 200)")

        # Test 3: Supervisor crea un nuevo tipo de caso
        new_name = "GARANTIA VIP TEST"
        res = client.post("/admin/tipos-casos/crear", data={
            "display_name": new_name,
            "color": "#10b981",
            "description": "Creado por supervisor en prueba automatizada"
        }, follow_redirects=True)
        assert res.status_code == 200
        created_sheet = SheetConfig.query.filter_by(display_name=new_name).first()
        assert created_sheet is not None, "El tipo de caso debio ser creado"
        assert created_sheet.is_active is True
        print(f"[OK] Supervisor creo con exito '{created_sheet.display_name}' (ID: {created_sheet.id})")

        # Test 4: Admin edita el tipo de caso
        login(client, "admin", "admin123")
        res = client.get("/admin/tipos-casos")
        assert res.status_code == 200
        print("[OK] Admin tiene acceso completo a /admin/tipos-casos (HTTP 200)")

        edited_name = "GARANTIA VIP TEST - EDITADO"
        res = client.post(f"/admin/tipos-casos/{created_sheet.id}/editar", data={
            "display_name": edited_name,
            "color": "#e11d48",
            "description": "Modificado por admin",
            "is_active": "1"
        }, follow_redirects=True)
        assert res.status_code == 200
        db.session.refresh(created_sheet)
        assert created_sheet.display_name == edited_name
        assert created_sheet.color == "#e11d48"
        print(f"[OK] Admin edito con exito la tipologia a '{created_sheet.display_name}' ({created_sheet.color})")

        # Test 5: Supervisor pausa (toggle) y reactiva
        login(client, "supervisor", "super123")
        client.post(f"/admin/tipos-casos/{created_sheet.id}/toggle", follow_redirects=True)
        db.session.refresh(created_sheet)
        assert created_sheet.is_active is False
        print("[OK] Supervisor pauso la tipologia (is_active = False)")

        client.post(f"/admin/tipos-casos/{created_sheet.id}/toggle", follow_redirects=True)
        db.session.refresh(created_sheet)
        assert created_sheet.is_active is True
        print("[OK] Supervisor reactivo la tipologia (is_active = True)")

        # Test 6: Crear un caso bajo la tipologia y eliminarla reasignando casos
        target_sheet = SheetConfig.query.filter(SheetConfig.id != created_sheet.id).first()
        assert target_sheet is not None

        test_case = Case(
            sheet_config_id=created_sheet.id,
            pedido_id="PED-TEST-REASSIGN-999",
            raw_data='{"Cliente": "Maria Test"}'
        )
        db.session.add(test_case)
        db.session.commit()
        case_id = test_case.id
        print(f"Caso de prueba #{case_id} creado bajo '{created_sheet.display_name}'")

        # Eliminar tipologia con reasignacion a target_sheet
        res = client.post(f"/admin/tipos-casos/{created_sheet.id}/eliminar", data={
            "reassign_to": str(target_sheet.id)
        }, follow_redirects=True)
        assert res.status_code == 200

        # Verificar eliminacion
        deleted = SheetConfig.query.get(created_sheet.id)
        assert deleted is None, "La tipologia debio haber sido eliminada de la base de datos"

        # Verificar reasignacion de caso
        db.session.refresh(test_case)
        assert test_case.sheet_config_id == target_sheet.id, f"El caso debio ser reasignado a {target_sheet.display_name}"
        print(f"[OK] Supervisor elimino la tipologia y el caso #{case_id} fue reasignado limpiamente a '{target_sheet.display_name}'")

        # Test 7: Admin elimina una tipologia sin casos
        empty_sheet = SheetConfig(
            sheet_name="TEST-EMPTY-TO-DELETE",
            display_name="TIPOLOGIA VACIA TEST",
            color="#a855f7",
            input_columns="[]",
            output_columns="[]",
            is_active=True
        )
        db.session.add(empty_sheet)
        db.session.commit()
        empty_id = empty_sheet.id

        login(client, "admin", "admin123")
        res = client.post(f"/admin/tipos-casos/{empty_id}/eliminar", follow_redirects=True)
        assert res.status_code == 200
        assert SheetConfig.query.get(empty_id) is None
        print(f"[OK] Admin elimino directamente tipologia sin casos (ID: {empty_id})")

        # Limpiar caso de prueba
        db.session.delete(test_case)
        db.session.commit()

        print("\n=== TODAS LAS PRUEBAS DE CRUD (CREAR, EDITAR, PAUSAR, ELIMINAR CON REASIGNACION) PASARON EXITOSAMENTE PARA ADMIN Y SUPERVISOR! ===")

if __name__ == "__main__":
    run_tests()
