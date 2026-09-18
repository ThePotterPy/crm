"""Test integral del paradigma Centrado en Pedidos y Casos Wise CX.

Verifica:
1. Creación de casos con N° Pedido, ID Caso Wise, Prioridad y Deadline SLA automático.
2. Trazabilidad Order 360° (múltiples casos para un mismo N° Pedido).
3. Registro de notas internas operativas de trabajo en la línea de tiempo.
4. Modificación dinámica de prioridad del caso.
5. Cálculo dinámico de SLA en tiempo real (en tiempo, vencido, resuelto a tiempo).
6. Funcionamiento de las Vistas de Lista de Salesforce / Wise Queues (?view=todos, ?view=mis_casos, ?view=vencidos, ?view=sin_asignar, ?view=reverificar).
7. Creación y edición de tipologías con sla_hours y default_priority.
"""

import os
import sys
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import db, User, Case, SheetConfig, CaseEvent

app = create_app()

def run_tests():
    with app.app_context():
        print("==================================================")
        print("INICIANDO TEST: WISE CX & ORDER-CENTRIC PARADIGM")
        print("==================================================")

        client = app.test_client()

        # 1. Obtener usuarios de prueba
        admin_user = User.query.filter_by(role="admin").first()
        back_user = User.query.filter_by(role="agente_back").first()
        front_user = User.query.filter_by(role="agente_front").first()

        assert admin_user, "Debe existir un usuario admin"
        assert back_user, "Debe existir un agente back office"
        assert front_user, "Debe existir un agente front office"

        # 2. Obtener una tipología activa de prueba
        sheet = SheetConfig.query.filter_by(is_active=True).first()
        assert sheet, "Debe existir al menos una tipología activa"
        sheet.sla_hours = 24
        sheet.default_priority = "alta"
        if sheet not in back_user.assigned_sheets.all():
            back_user.assigned_sheets.append(sheet)
        db.session.commit()

        # 3. Test: Creación de Caso Front con N° Pedido y Caso Wise
        test_order_id = f"PED-WISE-{int(datetime.now(timezone.utc).timestamp())}"
        test_wise_id = f"WISE-{int(datetime.now(timezone.utc).timestamp())}"

        # Login como agente front
        res_login = client.post("/login", data={"username": "front", "password": "front123"}, follow_redirects=True)
        assert res_login.status_code == 200

        post_data = {
            "sheet_id": str(sheet.id),
            "caso_wise": test_wise_id,
            "prioridad": "alta",
            "pedido_id": test_order_id,
        }
        for col in sheet.parsed_input_columns:
            k = col.get("key", col.get("name", ""))
            k_lower = k.lower()
            if any(x in k_lower for x in ("pedido", "id_pedido")):
                post_data[f"input_{k}"] = test_order_id
            elif "fecha" in k_lower:
                post_data[f"input_{k}"] = datetime.now().strftime("%Y-%m-%d")
            elif "tienda" in k_lower:
                post_data[f"input_{k}"] = "Tienda Online BGH"
            elif "solicitud" in k_lower:
                post_data[f"input_{k}"] = "Cambio por falla"
            else:
                post_data[f"input_{k}"] = "Test data"

        resp_create = client.post("/nuevo-caso", data=post_data, follow_redirects=True)
        assert resp_create.status_code == 200, f"Error en /nuevo-caso: {resp_create.status_code}"

        # Verificar caso en DB
        case1 = Case.query.filter_by(pedido_id=test_order_id).first()
        assert case1 is not None, "El caso 1 debe haberse creado"
        assert case1.caso_wise == test_wise_id, f"caso_wise debe ser {test_wise_id}, obtuvo {case1.caso_wise}"
        assert case1.wise_ticket_id == test_wise_id
        assert case1.prioridad == "alta"
        assert case1.sla_deadline is not None, "Debe calcularse automáticamente sla_deadline"
        print(f"✓ Caso 1 creado exitosamente: ID #{case1.id}, Pedido: {case1.pedido_id}, Wise: {case1.wise_ticket_id}, SLA: {case1.sla_info['text']}")

        # 4. Test: Order 360° Traceability (Crear caso 2 con el mismo N° Pedido)
        test_wise_id_2 = f"WISE-2-{int(datetime.now(timezone.utc).timestamp())}"
        case2 = Case(
            sheet_config_id=sheet.id,
            pedido_id=test_order_id,
            caso_wise=test_wise_id_2,
            prioridad="urgente",
            status="en_proceso",
            created_by=front_user.id,
            assigned_to=back_user.id,
            tienda="Tienda Online BGH",
            solicitud="Reclamo logístico demorado",
            sla_deadline=datetime.now(timezone.utc) - timedelta(hours=2),  # Vencido a propósito para test
        )
        db.session.add(case2)
        db.session.commit()
        print(f"✓ Caso 2 para el mismo pedido creado: ID #{case2.id}, Wise: {case2.wise_ticket_id}")

        # Comprobar que en case_detail del Caso 1, se visualice el Caso 2 como caso relacionado
        client.get("/logout", follow_redirects=True)
        client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)

        resp_detail = client.get(f"/caso/{case1.id}")
        assert resp_detail.status_code == 200
        html = resp_detail.get_data(as_text=True)
        assert test_order_id in html
        assert test_wise_id in html
        assert f"#{case2.id}" in html, "El detalle del caso 1 debe mostrar el caso 2 en Historial del Pedido (Order 360°)"
        print("✓ Order 360° comprobado: el detalle lista casos hermanos por N° de Pedido")

        # 5. Test: Publicación de Nota Interna de Trabajo (Chatter / Wise Notes)
        resp_note = client.post(
            f"/caso/{case1.id}/nota-interna",
            data={"nota": "Se contactó al centro de distribución para validar despacho del pedido."},
            follow_redirects=True,
        )
        assert resp_note.status_code == 200

        note_event = CaseEvent.query.filter_by(case_id=case1.id, event_type="nota_interna").first()
        assert note_event is not None, "Debe haberse registrado el evento de nota_interna"
        assert "centro de distribución" in note_event.description
        print(f"✓ Nota interna registrada en auditoría del caso: '{note_event.description[:40]}...'")

        # 6. Test: Cambio dinámico de Prioridad
        resp_prio = client.post(
            f"/caso/{case1.id}/prioridad",
            data={"prioridad": "urgente"},
            follow_redirects=True,
        )
        assert resp_prio.status_code == 200
        db.session.refresh(case1)
        assert case1.prioridad == "urgente"
        assert case1.priority_badge["label"] == "Urgente"
        print(f"✓ Cambio dinámico de prioridad exitoso: {case1.priority_badge['label']}")

        # 7. Test: Comportamiento del SLA Engine
        # Caso 2 tiene deadline en el pasado (-2 horas)
        sla_info_2 = case2.sla_info
        assert sla_info_2["status"] == "vencido"
        assert sla_info_2["is_breached"] is True
        assert "Vencido hace" in sla_info_2["text"]
        print(f"✓ SLA Vencido detectado correctamente: {sla_info_2['text']}")

        # Caso 1 tiene deadline a 24 horas en el futuro
        sla_info_1 = case1.sla_info
        assert sla_info_1["status"] in ("en_tiempo", "por_vencer")
        assert sla_info_1["is_breached"] is False
        print(f"✓ SLA En Tiempo detectado correctamente: {sla_info_1['text']}")

        # Caso resuelto a tiempo
        case1.status = "resuelto"
        case1.resolved_at = datetime.now(timezone.utc)
        db.session.commit()
        sla_resolved = case1.sla_info
        assert sla_resolved["status"] == "cumplido"
        print(f"✓ SLA Cumplido al resolver caso: {sla_resolved['text']}")

        # 8. Test: Salesforce List Views & Wise Queues
        # ?view=todos (como admin)
        client.get("/logout", follow_redirects=True)
        client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
        r_todos = client.get("/?view=todos")
        assert r_todos.status_code == 200, f"?view=todos status: {r_todos.status_code}"

        # ?view=mis_casos (como Jorge - Back Office)
        client.get("/logout", follow_redirects=True)
        client.post("/login", data={"username": "jorge", "password": "jorge123"}, follow_redirects=True)
        r_mis_casos = client.get("/?view=mis_casos")
        assert r_mis_casos.status_code == 200, f"?view=mis_casos status: {r_mis_casos.status_code}"
        html_mis_casos = r_mis_casos.get_data(as_text=True)
        assert f"#{case2.id}" in html_mis_casos, "Caso 2 asignado a Jorge (Back Office) debe figurar en mis_casos"

        # ?view=vencidos (como admin)
        client.get("/logout", follow_redirects=True)
        client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
        r_vencidos = client.get("/?view=vencidos")
        assert r_vencidos.status_code == 200, f"?view=vencidos status: {r_vencidos.status_code}"
        html_vencidos = r_vencidos.get_data(as_text=True)
        assert f"#{case2.id}" in html_vencidos, "Caso 2 debe figurar en la vista de vencidos"

        # ?view=sin_asignar
        r_sin_asignar = client.get("/?view=sin_asignar")
        assert r_sin_asignar.status_code == 200, f"?view=sin_asignar status: {r_sin_asignar.status_code}"

        # ?view=reverificar
        r_reverificar = client.get("/?view=reverificar")
        assert r_reverificar.status_code == 200, f"?view=reverificar status: {r_reverificar.status_code}"
        print("✓ Todas las vistas de lista de Salesforce / Wise Queues probadas y respondiendo con éxito (200 OK)")

        # 9. Test: Typology Manager con sla_hours y default_priority
        typology_name = f"TEST TYPO {int(datetime.now(timezone.utc).timestamp())}"
        r_create_typo = client.post(
            "/admin/tipos-casos/crear",
            data={
                "display_name": typology_name,
                "color": "#10b981",
                "badge_label": "TEST TYPO",
                "sla_hours": "72",
                "default_priority": "urgente",
                "description": "Tipología de prueba automatizada",
            },
            follow_redirects=True,
        )
        assert r_create_typo.status_code == 200

        new_typo = SheetConfig.query.filter_by(display_name=typology_name).first()
        assert new_typo is not None, "La tipología debe haberse creado"
        assert new_typo.sla_hours == 72
        assert new_typo.default_priority == "urgente"
        print(f"✓ Creación de tipología con SLA (72h) y prioridad (urgente) confirmada")

        # Modificación de la tipología
        r_edit_typo = client.post(
            f"/admin/tipos-casos/{new_typo.id}/editar",
            data={
                "display_name": typology_name + " MOD",
                "color": "#6366f1",
                "badge_label": "TEST MOD",
                "sla_hours": "36",
                "default_priority": "media",
                "is_active": "1",
            },
            follow_redirects=True,
        )
        assert r_edit_typo.status_code == 200
        db.session.refresh(new_typo)
        assert new_typo.sla_hours == 36
        assert new_typo.default_priority == "media"
        print(f"✓ Edición de tipología con SLA (36h) y prioridad (media) confirmada")

        # Limpieza de datos de prueba
        db.session.delete(case1)
        db.session.delete(case2)
        db.session.delete(new_typo)
        db.session.commit()
        print("✓ Limpieza de datos de prueba completada")

        print("==================================================")
        print("TODOS LOS TESTS COMPLETADOS SATISFACTORIAMENTE! 🎉")
        print("==================================================")

if __name__ == "__main__":
    run_tests()
