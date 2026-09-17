import sys
import os
import json

sys.path.insert(0, os.path.abspath("."))

from app import create_app
from models import db, User, Case, SheetConfig, CaseEvent

def test_retiros_lifecycle():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    print("\n=== INICIANDO PRUEBAS DEL CIRCUITO DE RETIROS Y SEGUIMIENTO ===")

    with app.test_client() as client:
        # 1. Login como Front Office para crear la solicitud inicial
        client.post("/login", data={"username": "front", "password": "front123"}, follow_redirects=True)

        resp_create = client.post("/nuevo-caso", data={
            "sheet_id": 1,
            "pedido_id": "PED-RETIRO-9999",
            "tienda": "Tienda BGH Online",
            "dni_cuit": "20334455667",
            "tracking": "ANDR-987654",
            "nombre_cliente": "Lucía Gómez",
            "email_cliente": "lucia.gomez@gmail.com",
            "motivos": "Arrepentimiento de compra",
            "observacion_detalle": "Cliente solicita retiro del producto dentro de los 10 días de corrido.",
            "direccion_datos": "Av. Corrientes 1234, 4to B, CABA",
        }, follow_redirects=True)
        assert resp_create.status_code == 200

        with app.app_context():
            solicitud_case = Case.query.filter_by(pedido_id="PED-RETIRO-9999", sheet_config_id=1).first()
            assert solicitud_case is not None, "No se creó el caso inicial de retiro"
            solicitud_id = solicitud_case.id
            print(f"[OK] 1. Solicitud inicial #{solicitud_id} creada por Front Office.")

        # 2. Login como Back Office (Jorge)
        client.get("/logout", follow_redirects=True)
        client.post("/login", data={"username": "jorge", "password": "jorge123"}, follow_redirects=True)

        # 3. Back Office gestiona y resuelve la solicitud cargando el Caso Salesforce y SAP ZRE2
        resp_resolve = client.post(f"/caso/{solicitud_id}/gestionar", data={
            "action": "resolver",
            "caso_salesforce": "SF-CASE-883311",
            "codigo_sap": "ZRE2-554433",
            "output_referencia_bo": "Retiro generado en Andreani con remito R-77221",
            "output_caso_salesforce": "SF-CASE-883311",
            "output_agente_back": "Jorge Back Office",
            "output_resuelto": "Si",
            "output_observaciones": "Orden de retiro emitida con éxito.",
        }, follow_redirects=True)
        assert resp_resolve.status_code == 200

        # 4. Verificar resolución y auto-handoff a Seguimiento de Retiros (SheetConfig 8)
        with app.app_context():
            solicitud_case = db.session.get(Case, solicitud_id)
            assert solicitud_case.status == "resuelto", f"Estado esperado resuelto, obtenido: {solicitud_case.status}"

            # Verificar creación automática en Seguimiento de Retiros
            tracking_case = Case.query.filter_by(pedido_id="PED-RETIRO-9999", sheet_config_id=8).first()
            assert tracking_case is not None, "¡No se generó automáticamente el caso en Seguimiento de Retiros!"
            tracking_id = tracking_case.id

            print(f"[OK] 2. Solicitud #{solicitud_id} marcada como RESUELTA.")
            print(f"[OK] 3. Se generó automáticamente el caso #{tracking_id} en Seguimiento de Retiros.")

            # Validar estados iniciales de seguimiento
            assert tracking_case.estado_retiro == "Pendiente de retiro", f"Estado retiro erróneo: {tracking_case.estado_retiro}"
            assert tracking_case.estado_reembolso == "Reembolso no solicitado", f"Estado reembolso erróneo: {tracking_case.estado_reembolso}"
            assert tracking_case.zre2 == "ZRE2-554433", f"ZRE2 erróneo: {tracking_case.zre2}"
            print(f"[OK] 4. Estados iniciales verificados: Retiro='{tracking_case.estado_retiro}' | Reembolso='{tracking_case.estado_reembolso}' | ZRE2='{tracking_case.zre2}'.")

        # 5. Back Office actualiza el estado de retiro a "Retirado / En tránsito" y reembolso a "Solicitado"
        resp_update1 = client.post(f"/caso/{tracking_id}/actualizar-seguimiento", data={
            "estado_retiro": "Retirado / En tránsito",
            "reembolso": "Solicitado",
            "zre2": "ZRE2-554433",
            "ultimo_estado": "Transporte retiró el paquete en domicilio del cliente.",
            "observaciones_seguimiento": "Verificado en portal de Andreani. En viaje a depósito.",
        }, follow_redirects=True)
        assert resp_update1.status_code == 200

        with app.app_context():
            tracking_case = db.session.get(Case, tracking_id)
            assert tracking_case.estado_retiro == "Retirado / En tránsito"
            assert tracking_case.estado_reembolso == "Solicitado"
            badge_ret = tracking_case.estado_retiro_badge
            badge_reemb = tracking_case.estado_reembolso_badge
            assert "Retirado" in badge_ret["label"]
            assert "Solicitado" in badge_reemb["label"]
            print(f"[OK] 5. Primera verificación guardada: Retiro='{tracking_case.estado_retiro}' | Reembolso='{tracking_case.estado_reembolso}'.")

        # 6. Back Office actualiza a "Ingresado a depósito" y "Reembolsado"
        resp_update2 = client.post(f"/caso/{tracking_id}/actualizar-seguimiento", data={
            "estado_retiro": "Ingresado a depósito",
            "reembolso": "Reembolsado",
            "zre2": "ZRE2-554433",
            "ultimo_estado": "Mercadería recibida en depósito central y chequeada.",
            "observaciones_seguimiento": "Reembolso acreditado en cuenta de Mercado Pago del cliente.",
        }, follow_redirects=True)
        assert resp_update2.status_code == 200

        with app.app_context():
            tracking_case = db.session.get(Case, tracking_id)
            assert tracking_case.estado_retiro == "Ingresado a depósito"
            assert tracking_case.estado_reembolso == "Reembolsado"
            badge_ret = tracking_case.estado_retiro_badge
            badge_reemb = tracking_case.estado_reembolso_badge
            assert "Ingresado a depósito" in badge_ret["label"]
            assert "Reembolsado" in badge_reemb["label"]
            print(f"[OK] 6. Segunda verificación guardada: Retiro='{tracking_case.estado_retiro}' | Reembolso='{tracking_case.estado_reembolso}'.")

            # Verificar timeline
            events = CaseEvent.query.filter_by(case_id=tracking_id).all()
            assert len(events) >= 3, f"Se esperaban al menos 3 eventos en el timeline, hay {len(events)}"
            print(f"[OK] 7. Timeline verificado: {len(events)} eventos registrados.")

        # 7. Verificar Dashboard: Badges y nombres en desplegable
        resp_dash = client.get("/?view=todos")
        assert resp_dash.status_code == 200
        html_dash = resp_dash.data.decode("utf-8")
        assert "Retiro por Arrepentimiento (Solicitud)" in html_dash
        assert "Seguimiento de Retiros (Arrepentimiento)" in html_dash
        assert "Ingresado a depósito" in html_dash
        assert "Reembolsado" in html_dash
        print("[OK] 8. Dashboard renderiza ambos tipos diferenciados y los badges de Retiro / Reembolso.")

    print("\n>>> ¡TODAS LAS PRUEBAS DEL CIRCUITO DE RETIROS PASARON AL 100%! <<<\n")

if __name__ == "__main__":
    test_retiros_lifecycle()
