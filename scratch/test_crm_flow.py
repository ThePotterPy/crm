import os
import sys
from datetime import datetime, date

# Asegurar path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User, Case, SheetConfig, CaseEvent

app = create_app()

def test_full_lifecycle():
    with app.app_context():
        # Limpieza previa
        ids = [c.id for c in Case.query.filter_by(pedido_id="TEST-PEDIDO-9999").all()]
        if ids:
            CaseEvent.query.filter(CaseEvent.case_id.in_(ids)).delete()
            Case.query.filter(Case.id.in_(ids)).delete()
            db.session.commit()

        print("=== 1. Probando usuarios y roles ===")
        admin = User.query.filter_by(username="admin").first()
        supervisor = User.query.filter_by(username="supervisor").first()
        jorge = User.query.filter_by(username="jorge").first()
        front = User.query.filter_by(username="front").first()
        calidad = User.query.filter_by(username="calidad").first()

        assert admin.is_admin, "Admin role error"
        assert supervisor.is_supervisor, "Supervisor role error"
        assert jorge.is_back_office, "Back office role error"
        assert front.is_front_office, "Front office role error"
        assert calidad.is_quality, "Quality role error"
        print("[OK] Todos los roles configurados correctamente.")

        print("\n=== 2. Probando Creación de Caso por Front Office con Sub-rol Back Office ===")
        # Asignar a jorge la hoja 1 si no la tiene
        sheet1 = SheetConfig.query.first()
        if sheet1 not in jorge.assigned_sheets.all():
            jorge.assigned_sheets.append(sheet1)
            db.session.commit()

        client = app.test_client()

        # Login Front
        resp = client.post("/login", data={"username": "front", "password": "front123"}, follow_redirects=True)
        assert resp.status_code == 200

        # Crear nuevo caso
        form_payload = {
            "sheet_config_id": sheet1.id,
            "pedido_id": "TEST-PEDIDO-9999",
            "dni_cuit": "20334455667",
            "tracking": "TRACK-AR-12345",
            "codigo_sap": "SAP-009988",
            "solicitud": "Retiro por Arrepentimiento",
            "tienda": "Tienda BGH Oficial",
            "field_ID Pedido": "TEST-PEDIDO-9999",
            "field_Tienda": "Tienda BGH Oficial",
            "field_Solicitud": "Retiro por Arrepentimiento",
            "field_Observación - Detalle del inconveniente": "Cliente solicita retiro por disconformidad con el tamaño.",
            "field_Dirección/Teléfono/Datos (Gestión Front)": "Av. Corrientes 1234, CABA - Tel: 11-4433-2211",
        }
        create_resp = client.post("/nuevo-caso", data=form_payload, follow_redirects=True)
        assert create_resp.status_code == 200

        # Verificar caso creado en DB
        new_case = Case.query.filter_by(pedido_id="TEST-PEDIDO-9999").first()
        assert new_case is not None, "El caso no fue guardado en la base de datos"
        assert new_case.created_by == front.id
        assert new_case.status == "nuevo"
        assert new_case.assigned_to == jorge.id, f"Auto-asignación falló: asignado a {new_case.assigned_to}, esperado {jorge.id}"
        print(f"[OK] Caso #{new_case.id} creado y asignado a Jorge (Back Office) automáticamente.")

        # Verificar evento de creación
        events = CaseEvent.query.filter_by(case_id=new_case.id).all()
        assert len(events) >= 1
        print(f"[OK] Timeline: {len(events)} evento(s) registrado(s).")

        print("\n=== 3. Probando Solicitud de Re-verificación de Back Office a Front ===")
        # Login como Jorge (Back Office)
        client.get("/logout", follow_redirects=True)
        client.post("/login", data={"username": "jorge", "password": "jorge123"}, follow_redirects=True)

        reverify_resp = client.post(f"/caso/{new_case.id}/gestionar", data={
            "action": "solicitar_reverificacion",
            "motivo_reverificacion": "Falta el piso y departamento en la dirección de retiro."
        }, follow_redirects=True)
        assert reverify_resp.status_code == 200

        db.session.refresh(new_case)
        assert new_case.status == "reverificar"
        assert "piso y departamento" in new_case.motivo_reverificacion
        print("[OK] Caso cambiado a estado 'reverificar' con nota para Front.")

        print("\n=== 4. Probando Bandeja Front y Re-envío de Caso Corregido ===")
        # Login Front
        client.get("/logout", follow_redirects=True)
        client.post("/login", data={"username": "front", "password": "front123"}, follow_redirects=True)

        # Consultar bandeja front
        bandeja_resp = client.get("/mis-casos-front")
        assert bandeja_resp.status_code == 200
        assert b"TEST-PEDIDO-9999" in bandeja_resp.data
        print("[OK] Caso aparece en la bandeja de Front de devueltos.")

        # Re-enviar caso con corrección
        reenviar_resp = client.post(f"/caso/{new_case.id}/reenviar", data={
            "respuesta_front": "Corregido: Piso 4 Depto B. Cliente estará por la tarde."
        }, follow_redirects=True)
        assert reenviar_resp.status_code == 200

        db.session.refresh(new_case)
        assert new_case.status == "reenviado"
        assert "Piso 4 Depto B" in new_case.respuesta_front
        print("[OK] Caso re-enviado por Front. Estado: 'reenviado'.")

        print("\n=== 5. Probando Resolución por Back Office ===")
        client.get("/logout", follow_redirects=True)
        client.post("/login", data={"username": "jorge", "password": "jorge123"}, follow_redirects=True)

        resolve_resp = client.post(f"/caso/{new_case.id}/gestionar", data={
            "action": "resolver",
            "output_caso_salesforce": "SF-2026-8888",
            "output_referencia_bo": "REF-CORR-LOG",
            "output_resuelto": "Si",
            "output_observaciones": "Retiro coordinado con Andreani correctamente."
        }, follow_redirects=True)
        assert resolve_resp.status_code == 200

        db.session.refresh(new_case)
        assert new_case.status == "resuelto"
        assert new_case.caso_salesforce == "SF-2026-8888"
        print("[OK] Caso resuelto exitosamente por Back Office con Salesforce ID y datos de gestión.")

        print("\n=== 6. Probando Evaluación de Calidad TYQ ===")
        client.get("/logout", follow_redirects=True)
        client.post("/login", data={"username": "calidad", "password": "calidad123"}, follow_redirects=True)

        audit_resp = client.post(f"/calidad/caso/{new_case.id}/auditar", data={
            "quality_score": "95",
            "check_datos_completos": "y",
            "check_clasificacion": "y",
            "check_claridad": "y",
            "check_tiempos": "y",
            "quality_feedback": "Excelente coordinación tras la corrección de datos."
        }, follow_redirects=True)
        assert audit_resp.status_code == 200

        db.session.refresh(new_case)
        assert new_case.quality_score == 95.0
        assert new_case.audited_by == calidad.id
        print(f"[OK] Auditoría TYQ guardada. Score: {new_case.quality_score}%")

        print("\n=== 7. Probando Búsqueda Universal Global ===")
        # Búsqueda por N° Pedido
        search_resp1 = client.get("/buscar?q=9999")
        assert b"TEST-PEDIDO-9999" in search_resp1.data
        # Búsqueda por DNI
        search_resp2 = client.get("/buscar?q=20334455667")
        assert b"TEST-PEDIDO-9999" in search_resp2.data
        # Búsqueda por Salesforce ID
        search_resp3 = client.get("/buscar?q=SF-2026-8888")
        assert b"TEST-PEDIDO-9999" in search_resp3.data
        # Búsqueda por tracking
        search_resp4 = client.get("/buscar?q=TRACK-AR-12345")
        assert b"TEST-PEDIDO-9999" in search_resp4.data
        print("[OK] Búsqueda Universal encontró el caso por Pedido, DNI, Salesforce ID y Tracking.")

        print("\n=== 8. Probando Exportación de Informes y Reportes ===")
        csv_resp = client.get("/reportes/exportar/csv")
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.content_type
        assert b"TEST-PEDIDO-9999" in csv_resp.data

        excel_resp = client.get("/reportes/exportar/excel")
        assert excel_resp.status_code == 200
        assert "spreadsheetml" in excel_resp.content_type
        assert len(excel_resp.data) > 1000
        print("[OK] Exportación CSV y Excel (.xlsx) funcionando correctamente.")

        # Limpiar caso de prueba
        CaseEvent.query.filter_by(case_id=new_case.id).delete()
        db.session.delete(new_case)
        db.session.commit()
        print("\n[TODO OK] Todos los flujos y requerimientos pasaron al 100%.")

if __name__ == "__main__":
    test_full_lifecycle()
