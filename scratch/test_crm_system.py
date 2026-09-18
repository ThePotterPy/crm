import json
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app
from models import db, User, SheetConfig, Case, RolePermission, log_case_event, slugify

app = create_app()

with app.app_context():
    print("=== TEST 1: Modelos y Slugs ===")
    sheets = SheetConfig.query.all()
    assert len(sheets) > 0, "No hay tipos de caso en la base de datos"
    for s in sheets:
        assert s.slug is not None, f"Sheet {s.id} ({s.display_name}) tiene slug nulo"
        badge = s.badge_style
        assert "label" in badge and "bg" in badge and "color" in badge, f"Badge mal formado en sheet {s.id}"
    print(f"✅ {len(sheets)} tipos de caso con slugs y badges válidos.")

    print("\n=== TEST 2: Permisos Dinámicos ===")
    for role in ["admin", "supervisor", "agente_back", "agente_front", "tyq"]:
        perm = RolePermission.get_for_role(role)
        assert perm is not None, f"Permiso para rol {role} no encontrado"
    admin = User.query.filter_by(role="admin").first()
    assert admin.can_manage_users is True, "Admin debe poder gestionar usuarios"
    assert admin.can_manage_case_types is True, "Admin debe poder gestionar tipos de casos"
    print("✅ Matriz de permisos dinámica funcionando correctamente.")

    print("\n=== TEST 3: Creación de Caso via Test Client (Front Office) ===")
    client = app.test_client()

    # Login como front
    login_res = client.post("/login", data={"username": "front", "password": "front123"}, follow_redirects=True)
    assert login_res.status_code == 200, "Error de login como front"

    # Alta de caso con maps_to
    sheet_retiro = SheetConfig.query.filter_by(slug="retiro_arrepentimiento").first()
    assert sheet_retiro is not None, "No se encontró tipología retiro_arrepentimiento"

    post_data = {
        "sheet_id": sheet_retiro.id,
        "input_id_pedido": "TEST-PEDIDO-9999",
        "input_fecha": "2026-09-18",
        "input_agente_carga": "Agente Front Test",
        "input_tienda": "Tienda Online BGH",
        "input_solicitud": "Retiro arrepentimiento",
        "input_motivos": "Arrepentimiento de compra",
        "input_observacion_detalle": "El cliente desea cancelar el pedido antes de la entrega.",
    }
    create_res = client.post("/nuevo-caso", data=post_data, follow_redirects=True)
    assert create_res.status_code == 200

    created_case = Case.query.filter_by(pedido_id="TEST-PEDIDO-9999").first()
    assert created_case is not None, "No se encontró el caso creado"
    assert created_case.pedido_id == "TEST-PEDIDO-9999", "pedido_id no se mapeó correctamente"
    assert created_case.tienda == "Tienda Online BGH", "tienda no se mapeó correctamente"
    assert created_case.solicitud == "Retiro arrepentimiento", "solicitud no se mapeó correctamente"
    assert len(created_case.events.all()) >= 1, "No se registró evento en la línea de tiempo"
    print(f"✅ Caso #{created_case.id} creado con extracción maps_to y timeline exitosa.")

    print("\n=== TEST 4: Creación via Webhook con Extracción maps_to ===")
    webhook_secret = app.config.get("WEBHOOK_SECRET", "")
    webhook_payload = {
        "sheet_name": sheet_retiro.sheet_name,
        "row_number": 9999,
        "row_data": {
            "id_pedido": "WEBHOOK-PEDIDO-7777",
            "fecha": "2026-09-18",
            "tienda": "MercadoLibre BGH",
            "solicitud": "Retiro arrepentimiento",
            "dni_cuit": "20304050607",
            "tracking": "TRACK-AR-12345",
            "codigo_sap": "SAP-987654",
        }
    }
    wh_res = client.post(
        "/webhook/nuevo-caso",
        headers={"X-Webhook-Secret": webhook_secret},
        json=webhook_payload
    )
    assert wh_res.status_code == 201, f"Webhook falló: {wh_res.status_code} {wh_res.data}"
    wh_data = wh_res.get_json()
    wh_case = db.session.get(Case, wh_data["case_id"])
    assert wh_case.pedido_id == "WEBHOOK-PEDIDO-7777", "pedido_id no extraído en webhook"
    assert wh_case.dni_cuit == "20304050607", "dni_cuit no extraído en webhook"
    assert wh_case.tracking == "TRACK-AR-12345", "tracking no extraído en webhook"
    assert wh_case.codigo_sap == "SAP-987654", "codigo_sap no extraído en webhook"
    assert len(wh_case.events.all()) >= 1, "Webhook no creó timeline events"
    print(f"✅ Webhook caso #{wh_case.id} extrajo todos los campos y timeline.")

    print("\n=== TEST 5: Dashboard con Paginación y Tabs de Tipología ===")
    # Logout del usuario anterior y login como admin para ver todo
    client.get("/logout", follow_redirects=True)
    client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
    dash_res = client.get("/")
    assert dash_res.status_code == 200
    assert b"Bandejas por Tipo de Caso" in dash_res.data, "No se encontró la barra de tabs de tipología"
    print("✅ Dashboard con tabs de tipología y KPIs cargó correctamente.")

    print("\n=== TEST 6: Editor de Columnas CRUD ===")
    col_res = client.get(f"/admin/tipos-casos/{sheet_retiro.id}/columnas")
    assert col_res.status_code == 200
    col_data = col_res.get_json()
    assert "input_columns" in col_data and "output_columns" in col_data
    print(f"✅ Endpoint de columnas de tipología #{sheet_retiro.id} retornó {len(col_data['input_columns'])} inputs y {len(col_data['output_columns'])} outputs.")

    print("\n=== LIMPIEZA DE CASOS DE PRUEBA ===")
    db.session.delete(created_case)
    db.session.delete(wh_case)
    db.session.commit()
    print("✅ Casos de prueba eliminados limpiamente.")

print("\n🎉 ¡TODOS LOS TESTS PASARON EXITOSAMENTE (100%)!")
