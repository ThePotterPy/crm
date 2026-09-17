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
        print("=== INICIANDO PRUEBAS DE ASIGNACION DE TIPOLOGIAS AL CREAR Y EDITAR USUARIO ===")

        # Verificar hojas
        sheets = SheetConfig.query.filter_by(is_active=True).all()
        assert len(sheets) >= 2, "Debe haber al menos 2 tipologias activas"
        s1 = sheets[0]
        s2 = sheets[1]
        s3 = sheets[2] if len(sheets) > 2 else None

        print(f"Tipologia 1: {s1.display_name} (ID: {s1.id})")
        print(f"Tipologia 2: {s2.display_name} (ID: {s2.id})")
        if s3:
            print(f"Tipologia 3: {s3.display_name} (ID: {s3.id})")

        # 1. Admin se loguea y crea usuario con solo s1 y s2 asignadas
        login(client, "admin", "admin123")

        # Limpiar usuario de prueba si existia
        existing = User.query.filter_by(username="test_agente_nuevo").first()
        if existing:
            db.session.delete(existing)
            db.session.commit()

        res = client.post("/admin/usuarios/crear", data={
            "username": "test_agente_nuevo",
            "display_name": "Agente Asignado Test",
            "password": "pass12345",
            "role": "agente_back",
            "sheet_ids": [str(s1.id), str(s2.id)]
        }, follow_redirects=True)

        assert res.status_code == 200

        user = User.query.filter_by(username="test_agente_nuevo").first()
        assert user is not None, "El usuario debe existir"
        assigned_ids = [s.id for s in user.assigned_sheets.all()]
        print(f"Usuario creado con tipologias asignadas: {assigned_ids}")
        assert s1.id in assigned_ids, "s1 debe estar asignada"
        assert s2.id in assigned_ids, "s2 debe estar asignada"
        if s3:
            assert s3.id not in assigned_ids, "s3 NO debe estar asignada"
        print("[OK] Creacion de usuario con tipologias especificas asignadas exitosa!")

        # 2. Supervisor edita el usuario para cambiarle las tipologias asignadas (ej. quitar s1 y agregar s3)
        login(client, "supervisor", "super123")

        new_sheets = [s2.id]
        if s3:
            new_sheets.append(s3.id)

        res = client.post(f"/admin/usuarios/{user.id}/editar", data={
            "display_name": "Agente Asignado Modificado",
            "role": "agente_back",
            "is_active": "1",
            "sheet_ids": [str(sid) for sid in new_sheets]
        }, follow_redirects=True)

        assert res.status_code == 200
        db.session.refresh(user)
        assert user.display_name == "Agente Asignado Modificado"
        updated_assigned_ids = [s.id for s in user.assigned_sheets.all()]
        print(f"Usuario actualizado con tipologias: {updated_assigned_ids}")

        assert s1.id not in updated_assigned_ids, "s1 debio ser desasignada"
        assert s2.id in updated_assigned_ids, "s2 debe seguir asignada"
        if s3:
            assert s3.id in updated_assigned_ids, "s3 debio ser asignada"
        print("[OK] Edicion posterior de usuario y modificacion de tipologias asignadas exitosa!")

        # 3. Verificar que la vista /admin/usuarios renderiza correctamente los modales y badges
        res = client.get("/admin/usuarios")
        assert res.status_code == 200
        html = res.data.decode("utf-8")
        assert "openEditUserModal" in html
        assert "create-sheets-container" in html
        assert "edit-sheets-container" in html
        assert "modal-editar" in html
        assert "Agente Asignado Modificado" in html
        print("[OK] Renderizado de vista /admin/usuarios verificado correctamente en HTML DOM!")

        # Limpiar
        db.session.delete(user)
        db.session.commit()
        print("[OK] Limpieza de datos de prueba finalizada.")

        print("\n=== TODAS LAS PRUEBAS DE ASIGNACION DE TIPOLOGIAS AL CREAR Y EDITAR USUARIO PASARON EXITOSAMENTE! ===")

if __name__ == "__main__":
    run_tests()
