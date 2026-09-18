import json
from flask import Blueprint, request, jsonify, current_app
from models import db, Case, SheetConfig, User, log_case_event

webhook_bp = Blueprint("webhook", __name__)


def _extract_case_fields(input_cols, row_data, default_sheet_name=""):
    """Extrae campos del caso usando maps_to, nombres de columna y campos directos en row_data."""
    fields = {
        "pedido_id": "",
        "fecha": "",
        "solicitud": "",
        "tienda": "",
        "agente_front": "",
        "dni_cuit": "",
        "tracking": "",
        "codigo_sap": "",
        "nombre_cliente": "",
        "email_cliente": "",
        "caso_salesforce": "",
    }

    # 1. Chequeo directo por nombre de atributo de Case o alias común en row_data
    direct_aliases = {
        "pedido_id": ["pedido_id", "id_pedido", "nro_pedido", "numero_pedido"],
        "fecha": ["fecha"],
        "solicitud": ["solicitud"],
        "tienda": ["tienda"],
        "agente_front": ["agente_front", "agente_carga", "agente"],
        "dni_cuit": ["dni_cuit", "dni", "cuit"],
        "tracking": ["tracking", "nro_tracking", "numero_tracking", "guia"],
        "codigo_sap": ["codigo_sap", "sap", "zre", "zre2"],
        "nombre_cliente": ["nombre_cliente", "cliente", "nombre"],
        "email_cliente": ["email_cliente", "email", "correo", "mail"],
        "caso_salesforce": ["caso_salesforce", "salesforce", "caso_id_wise"],
    }
    for field_name, aliases in direct_aliases.items():
        for alias in aliases:
            if alias in row_data and row_data[alias]:
                fields[field_name] = str(row_data[alias]).strip()
                break

    # 2. Extracción a través de la configuración de columnas (maps_to y heurística)
    for col in input_cols:
        key = col.get("key", col.get("name", ""))
        val = str(row_data.get(key, "")).strip()
        if not val:
            continue

        maps_to = col.get("maps_to")
        if maps_to in fields and not fields[maps_to]:
            fields[maps_to] = val
        elif not maps_to:
            name_lower = col.get("name", "").lower()
            key_lower = key.lower()
            combined = f"{name_lower} {key_lower}"

            if any(x in combined for x in ("pedido", "numero", "nro_pedido", "id_pedido")) and not fields["pedido_id"]:
                fields["pedido_id"] = val
            elif "fecha" in combined and not fields["fecha"]:
                fields["fecha"] = val
            elif "solicitud" in combined and not fields["solicitud"]:
                fields["solicitud"] = val
            elif "tienda" in combined and not fields["tienda"]:
                fields["tienda"] = val
            elif any(x in combined for x in ("agente", "carga")) and "back" not in combined and not fields["agente_front"]:
                fields["agente_front"] = val
            elif any(x in combined for x in ("dni", "cuit")) and not fields["dni_cuit"]:
                fields["dni_cuit"] = val
            elif "tracking" in combined and not fields["tracking"]:
                fields["tracking"] = val
            elif any(x in combined for x in ("nombre", "cliente")) and not fields["nombre_cliente"]:
                fields["nombre_cliente"] = val
            elif any(x in combined for x in ("mail", "correo")) and not fields["email_cliente"]:
                fields["email_cliente"] = val
            elif "sap" in combined and not fields["codigo_sap"]:
                fields["codigo_sap"] = val
            elif "salesforce" in combined and not fields["caso_salesforce"]:
                fields["caso_salesforce"] = val

    if not fields["solicitud"]:
        fields["solicitud"] = default_sheet_name

    return fields


@webhook_bp.route("/nuevo-caso", methods=["POST"])
def nuevo_caso():
    """Recibe un nuevo caso desde Google Apps Script con extracción maps_to y timeline."""
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

    input_cols = json.loads(sheet_config.input_columns) if sheet_config.input_columns else []
    extracted = _extract_case_fields(input_cols, row_data, default_sheet_name=sheet_config.display_name)

    # Buscar a quién asignar (balanceo round-robin en agentes de back office activos)
    assigned_user = None
    assigned_agents = sheet_config.assigned_users.filter(User.role == "agente_back", User.is_active_user == True).all()
    if not assigned_agents:
        assigned_agents = sheet_config.assigned_users.filter_by(is_active_user=True).all()

    if assigned_agents:
        min_cases = float("inf")
        for u in assigned_agents:
            open_cases = Case.query.filter(
                Case.sheet_config_id == sheet_config.id,
                Case.assigned_to == u.id,
                Case.status.in_(["nuevo", "en_proceso", "reverificar", "reenviado"])
            ).count()
            if open_cases < min_cases:
                min_cases = open_cases
                assigned_user = u

    # Crear el caso
    case = Case(
        sheet_config_id=sheet_config.id,
        row_number=row_number,
        raw_data=json.dumps(row_data, ensure_ascii=False, default=str),
        pedido_id=extracted["pedido_id"] or "S/N",
        fecha=extracted["fecha"],
        solicitud=extracted["solicitud"],
        tienda=extracted["tienda"],
        agente_front=extracted["agente_front"],
        dni_cuit=extracted["dni_cuit"],
        tracking=extracted["tracking"],
        codigo_sap=extracted["codigo_sap"],
        nombre_cliente=extracted["nombre_cliente"],
        email_cliente=extracted["email_cliente"],
        caso_salesforce=extracted["caso_salesforce"],
        status="nuevo",
        assigned_to=assigned_user.id if assigned_user else None,
    )
    db.session.add(case)
    db.session.flush()

    # Registrar evento de creación en la línea de tiempo
    log_case_event(
        case_id=case.id,
        event_type="creacion",
        title="Caso Registrado via Webhook",
        description=f"Recibido automáticamente desde Google Sheets ('{sheet_config.display_name}').",
        new_val="nuevo",
    )

    if assigned_user:
        log_case_event(
            case_id=case.id,
            event_type="asignacion",
            title=f"Asignado a {assigned_user.display_name}",
            description="Enrutado automáticamente por balanceo de carga.",
            new_val=assigned_user.display_name,
        )

    db.session.commit()

    return jsonify({
        "status": "ok",
        "case_id": case.id,
        "assigned_to": assigned_user.display_name if assigned_user else "Sin asignar",
    }), 201


@webhook_bp.route("/sync-sheet", methods=["POST"])
def sync_from_sheet():
    """Sincronización masiva: recibe múltiples filas de una hoja con extracción completa."""
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

    input_cols = json.loads(sheet_config.input_columns) if sheet_config.input_columns else []
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

        extracted = _extract_case_fields(input_cols, row_data, default_sheet_name=sheet_config.display_name)

        case = Case(
            sheet_config_id=sheet_config.id,
            row_number=row_number,
            raw_data=json.dumps(row_data, ensure_ascii=False, default=str),
            pedido_id=extracted["pedido_id"] or "S/N",
            fecha=extracted["fecha"],
            solicitud=extracted["solicitud"],
            tienda=extracted["tienda"],
            agente_front=extracted["agente_front"],
            dni_cuit=extracted["dni_cuit"],
            tracking=extracted["tracking"],
            codigo_sap=extracted["codigo_sap"],
            nombre_cliente=extracted["nombre_cliente"],
            email_cliente=extracted["email_cliente"],
            caso_salesforce=extracted["caso_salesforce"],
            status="nuevo",
        )
        db.session.add(case)
        db.session.flush()

        log_case_event(
            case_id=case.id,
            event_type="creacion",
            title="Caso Sincronizado",
            description=f"Importado en sync masivo desde '{sheet_config.display_name}'.",
            new_val="nuevo",
        )
        created += 1

    db.session.commit()

    return jsonify({"status": "ok", "created": created}), 201
