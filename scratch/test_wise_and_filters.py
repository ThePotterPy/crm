import json
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app
from models import db, User, SheetConfig, Case, CaseEvent

app = create_app()

with app.app_context():
    client = app.test_client()

    print("=== TEST 1: Login y Verificación de Links en Admin Usuarios y Asignaciones ===")
    res_login = client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
    assert res_login.status_code == 200, "Error en login admin"

    user_back = User.query.filter_by(role="agente_back").first()
    assert user_back is not None, "Debe existir al menos un agente_back"

    # Verificar usuarios.html contiene link a perfil_asesor
    res_users = client.get("/admin/usuarios")
    assert res_users.status_code == 200
    expected_link = f"/admin/asesores/{user_back.id}"
    assert expected_link.encode('utf-8') in res_users.data, f"Link {expected_link} no encontrado en /admin/usuarios"
    assert "👁️ Bandeja".encode('utf-8') in res_users.data, "Botón '👁️ Bandeja' no encontrado en /admin/usuarios"
    print("✅ /admin/usuarios contiene links y botón '👁️ Bandeja' al perfil Wise CX.")

    # Verificar asignaciones.html contiene link a perfil_asesor
    res_asig = client.get("/admin/asignaciones")
    assert res_asig.status_code == 200
    assert expected_link.encode('utf-8') in res_asig.data, f"Link {expected_link} no encontrado en /admin/asignaciones"
    assert "👁️ Ver Bandeja".encode('utf-8') in res_asig.data, "Botón '👁️ Ver Bandeja' no encontrado en /admin/asignaciones"
    print("✅ /admin/asignaciones contiene link y botón '👁️ Ver Bandeja'.")

    print("\n=== TEST 2: Creación de Caso con Asignación Automática al Encargado Back Office ===")
    sheet = SheetConfig.query.first()
    assert sheet is not None, "No hay tipos de caso"

    # Aseguramos que user_back tiene esta tipología asignada
    if sheet not in user_back.assigned_sheets.all():
        user_back.assigned_sheets.append(sheet)
        db.session.commit()

    # Logout y login como agente front
    client.get("/logout", follow_redirects=True)
    client.post("/login", data={"username": "front", "password": "front123"}, follow_redirects=True)

    test_pedido_id = "ROUTING-TEST-001"
    post_data = {
        "sheet_id": sheet.id,
        "input_id_pedido": test_pedido_id,
        "input_fecha": "2026-09-18",
        "input_tienda": "Tienda Oficial BGH",
        "input_solicitud": "Consulta de Entrega",
        "input_motivos": "Demora",
        "input_observacion_detalle": "Prueba de enrutamiento automático sin checkbox autoasignar.",
    }
    res_create = client.post("/nuevo-caso", data=post_data, follow_redirects=True)
    assert res_create.status_code == 200

    created = Case.query.filter_by(pedido_id=test_pedido_id).first()
    assert created is not None, "El caso de prueba no fue creado"
    assert created.assigned_to is not None, "El caso debe estar asignado automáticamente al encargado"
    assigned_user = db.session.get(User, created.assigned_to)
    assert assigned_user.role == "agente_back", f"El caso debió asignarse a un agente_back, fue asignado a {assigned_user.username} ({assigned_user.role})"
    print(f"✅ Caso #{created.id} asignado automáticamente y correctamente a {assigned_user.display_name} (@{assigned_user.username}) según balanceo de carga.")

    print("\n=== TEST 3: Multi-Filtros en Dashboard (/ y /casos) ===")
    client.get("/logout", follow_redirects=True)
    client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)

    # Filtrar por agente
    res_filter_agent = client.get(f"/casos?agente={assigned_user.id}")
    assert res_filter_agent.status_code == 200
    assert "Quién gestiona".encode('utf-8') in res_filter_agent.data
    assert test_pedido_id.encode('utf-8') in res_filter_agent.data, "El caso creado debe aparecer al filtrar por su agente asignado"

    # Filtrar por combinación: tipología + estado + agente
    res_multi = client.get(f"/?sheet={sheet.id}&status=nuevo&agente={assigned_user.id}")
    assert res_multi.status_code == 200
    assert test_pedido_id.encode('utf-8') in res_multi.data, "El caso creado debe aparecer con los filtros combinados"

    # Filtrar por 'unassigned'
    res_unassigned = client.get("/?agente=unassigned")
    assert res_unassigned.status_code == 200
    print("✅ Multi-filtros (tipología, estado, quién gestiona) funcionando correctamente en / y /casos.")

    print("\n=== TEST 4: Vista de Consola Asesor Wise CX (/admin/asesores/<id>) ===")
    res_profile = client.get(f"/admin/asesores/{assigned_user.id}")
    assert res_profile.status_code == 200, f"Error al cargar perfil de asesor: {res_profile.status_code}"
    assert assigned_user.display_name.encode('utf-8') in res_profile.data
    assert b"Bandeja de Entrada" in res_profile.data or b"Bandeja" in res_profile.data
    assert b"Carga Activa" in res_profile.data or b"Carga" in res_profile.data
    assert test_pedido_id.encode('utf-8') in res_profile.data, "El caso del asesor debe estar visible en su bandeja"
    print(f"✅ Consola Wise CX de {assigned_user.display_name} renderiza KPIs, estado de carga y bandeja en vivo.")

    print("\n=== TEST 5: Reasignación Rápida desde la Consola Wise CX ===")
    another_back = User.query.filter(User.role == "agente_back", User.id != assigned_user.id).first()
    if not another_back:
        # Si sólo hay un agente_back, creamos uno de test
        another_back = User(username="back_test2", display_name="Back Office Segundo", role="agente_back")
        another_back.set_password("back123")
        db.session.add(another_back)
        db.session.commit()

    reassign_url = f"/admin/asesores/{assigned_user.id}/reasignar-caso/{created.id}"
    res_reassign = client.post(reassign_url, data={"target_agent_id": another_back.id}, follow_redirects=True)
    assert res_reassign.status_code == 200

    # Verificar que el caso cambió de dueño
    db.session.refresh(created)
    assert created.assigned_to == another_back.id, f"El caso debió transferirse a {another_back.id}, pero está en {created.assigned_to}"

    # Verificar evento de timeline
    last_event = CaseEvent.query.filter_by(case_id=created.id).order_by(CaseEvent.id.desc()).first()
    assert last_event is not None
    print(f"✅ Caso #{created.id} reasignado exitosamente a {another_back.display_name} con evento de timeline registrado.")

    print("\n=== LIMPIEZA DE CASOS Y USUARIOS DE PRUEBA ===")
    CaseEvent.query.filter_by(case_id=created.id).delete()
    db.session.delete(created)
    if another_back.username == "back_test2":
        db.session.delete(another_back)
    db.session.commit()
    print("✅ Registros de prueba eliminados limpiamente.")

    print("\n🎉 TODOS LOS TESTS DE WISE CX Y MULTI-FILTROS PASARON EXITOSAMENTE.")
