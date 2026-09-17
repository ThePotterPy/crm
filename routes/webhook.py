import json
import hmac
import hashlib
from flask import Blueprint, request, jsonify, current_app
from models import db, Case, SheetConfig, User, user_sheet_assignments

webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.route("/nuevo-caso", methods=["POST"])
def nuevo_caso():
    """Recibe un nuevo caso desde Google Apps Script."""
    # Validar token secreto
    token = request.headers.get("X-Webhook-Secret", "")
    expected = current_app.config.get("WEBHOOK_SECRET", "")
    if token != expected:
        return jsonify({"error": "Token inválido"}), 403

    data = request.json
    if not data:
        return jsonify({"error": "No se recibieron datos"}), 400

    sheet_name = data.get("sheet_name", "")
    row_number = data.get("row_number", None)
    row_data = data.get("row_data", {})

    # Buscar la configuración de la hoja
    sheet_config = SheetConfig.query.filter_by(sheet_name=sheet_name, is_active=True).first()
    if not sheet_config:
        return jsonify({"error": f"Hoja '{sheet_name}' no configurada"}), 404

    # Extraer campos comunes para búsqueda
    input_cols = json.loads(sheet_config.input_columns) if sheet_config.input_columns else []

    pedido_id = ""
    fecha = ""
    solicitud = ""
    tienda = ""
    agente_front = ""

    for col in input_cols:
        key = col.get("key", "")
        val = row_data.get(key, "")
        name_lower = col.get("name", "").lower()
        if "pedido" in name_lower or "numero" in name_lower:
            pedido_id = str(val)
        elif "fecha" in name_lower and not fecha:
            fecha = str(val)
        elif "solicitud" in name_lower and not solicitud:
            solicitud = str(val)
        elif "tienda" in name_lower and not tienda:
            tienda = str(val)
        elif "agente" in name_lower and "back" not in name_lower and not agente_front:
            agente_front = str(val)

    # Buscar a quién asignar (primer usuario asignado a esa hoja)
    assigned_user = None
    assigned_users = sheet_config.assigned_users.all()
    if assigned_users:
        # Asignar round-robin simple: al que menos casos abiertos tenga
        min_cases = float("inf")
        for u in assigned_users:
            open_cases = Case.query.filter(
                Case.assigned_to == u.id,
                Case.status.in_(["nuevo", "en_proceso"])
            ).count()
            if open_cases < min_cases:
                min_cases = open_cases
                assigned_user = u

    # Crear el caso
    case = Case(
        sheet_config_id=sheet_config.id,
        row_number=row_number,
        raw_data=json.dumps(row_data, ensure_ascii=False, default=str),
        pedido_id=pedido_id,
        fecha=fecha,
        solicitud=solicitud,
        tienda=tienda,
        agente_front=agente_front,
        status="nuevo",
        assigned_to=assigned_user.id if assigned_user else None,
    )
    db.session.add(case)
    db.session.commit()

    return jsonify({
        "status": "ok",
        "case_id": case.id,
        "assigned_to": assigned_user.display_name if assigned_user else "Sin asignar",
    }), 201


@webhook_bp.route("/sync-sheet", methods=["POST"])
def sync_from_sheet():
    """Sincronización masiva: recibe múltiples filas de una hoja."""
    token = request.headers.get("X-Webhook-Secret", "")
    expected = current_app.config.get("WEBHOOK_SECRET", "")
    if token != expected:
        return jsonify({"error": "Token inválido"}), 403

    data = request.json
    sheet_name = data.get("sheet_name", "")
    rows = data.get("rows", [])

    sheet_config = SheetConfig.query.filter_by(sheet_name=sheet_name, is_active=True).first()
    if not sheet_config:
        return jsonify({"error": f"Hoja '{sheet_name}' no configurada"}), 404

    created = 0
    for row in rows:
        row_number = row.get("row_number")
        row_data = row.get("row_data", {})

        # Evitar duplicados por fila
        existing = Case.query.filter_by(
            sheet_config_id=sheet_config.id, row_number=row_number
        ).first()
        if existing:
            continue

        input_cols = json.loads(sheet_config.input_columns) if sheet_config.input_columns else []
        pedido_id = ""
        for col in input_cols:
            name_lower = col.get("name", "").lower()
            if "pedido" in name_lower or "numero" in name_lower:
                pedido_id = str(row_data.get(col.get("key", ""), ""))
                break

        case = Case(
            sheet_config_id=sheet_config.id,
            row_number=row_number,
            raw_data=json.dumps(row_data, ensure_ascii=False, default=str),
            pedido_id=pedido_id,
            status="nuevo",
        )
        db.session.add(case)
        created += 1

    db.session.commit()

    return jsonify({"status": "ok", "created": created}), 201
