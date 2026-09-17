import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db, Case, SheetConfig, User, CaseEvent, log_case_event

front_bp = Blueprint("front", __name__)


@front_bp.route("/nuevo-caso", methods=["GET", "POST"])
@login_required
def nuevo_caso():
    """Formulario interactivo para cargar un nuevo caso (Front y Back Office)."""
    if not current_user.can_create_cases:
        flash("Tu rol no tiene permisos para dar de alta casos en el CRM.", "error")
        return redirect(url_for("dashboard.index"))

    sheets = SheetConfig.query.filter_by(is_active=True).order_by(SheetConfig.display_name).all()

    if request.method == "POST":
        sheet_id = request.form.get("sheet_id", type=int) or request.form.get("sheet_config_id", type=int)
        if not sheet_id:
            flash("Debés seleccionar el tipo de caso.", "error")
            return redirect(url_for("front.nuevo_caso"))

        sheet = SheetConfig.query.get_or_404(sheet_id)
        input_columns = json.loads(sheet.input_columns) if sheet.input_columns else []

        # Recoger datos del formulario
        raw_data = {}
        pedido_id = request.form.get("pedido_id", "").strip()
        fecha = request.form.get("fecha", "").strip() or datetime.now().strftime("%Y-%m-%d")
        solicitud = request.form.get("solicitud", "").strip()
        tienda = request.form.get("tienda", "").strip()
        dni_cuit = request.form.get("dni_cuit", "").strip()
        tracking = request.form.get("tracking", "").strip()
        codigo_sap = request.form.get("codigo_sap", "").strip()
        nombre_cliente = request.form.get("nombre_cliente", "").strip()
        email_cliente = request.form.get("email_cliente", "").strip()

        for col in input_columns:
            key = col.get("key", col.get("name", ""))
            val = request.form.get(f"input_{key}", request.form.get(f"field_{key}", request.form.get(key, ""))).strip()
            raw_data[key] = val

            # Extraer campos clave para búsquedas directas
            k_lower = key.lower()
            if any(x in k_lower for x in ("pedido", "nro_pedido", "numero_pedido", "id_pedido")):
                if not pedido_id:
                    pedido_id = val
            elif "fecha" in k_lower and not fecha:
                fecha = val
            elif "solicitud" in k_lower and not solicitud:
                solicitud = val
            elif "tienda" in k_lower and not tienda:
                tienda = val
            elif any(x in k_lower for x in ("dni", "cuit")) and not dni_cuit:
                dni_cuit = val
            elif "tracking" in k_lower and not tracking:
                tracking = val
            elif any(x in k_lower for x in ("nombre", "cliente")) and not nombre_cliente:
                nombre_cliente = val
            elif any(x in k_lower for x in ("mail", "correo")) and not email_cliente:
                email_cliente = val
            elif "sap" in k_lower and not codigo_sap:
                codigo_sap = val

        if not solicitud:
            solicitud = sheet.display_name

        # Fallback si pedido_id sigue vacío
        if not pedido_id:
            for val in raw_data.values():
                if val:
                    pedido_id = val
                    break

        agente_carga_name = current_user.display_name

        # ── Enrutamiento Inteligente / Auto-asignación ──
        autoasignar = (request.form.get("autoasignar") == "1")
        selected_back_agent = None

        if autoasignar and (current_user.is_back_office or current_user.is_admin or current_user.is_supervisor):
            selected_back_agent = current_user
        else:
            # Buscar qué agentes de Back Office tienen asignada esta hoja (sub-rol)
            assigned_agents = sheet.assigned_users.filter(User.role == "agente_back", User.is_active_user == True).all()
            if not assigned_agents:
                assigned_agents = sheet.assigned_users.filter_by(is_active_user=True).all()

            if assigned_agents:
                # Asignar al agente con menor carga de casos activos en este sub-rol
                best_agent = None
                min_active = 999999
                for agent in assigned_agents:
                    active_count = Case.query.filter(
                        Case.sheet_config_id == sheet.id,
                        Case.assigned_to == agent.id,
                        Case.status.in_(["nuevo", "en_proceso", "reverificar", "reenviado"]),
                    ).count()
                    if active_count < min_active:
                        min_active = active_count
                        best_agent = agent
                selected_back_agent = best_agent or assigned_agents[0]

        # Crear el caso
        case = Case(
            sheet_config_id=sheet.id,
            raw_data=json.dumps(raw_data, ensure_ascii=False),
            output_data="{}",
            pedido_id=pedido_id or "S/N",
            fecha=fecha,
            solicitud=solicitud,
            tienda=tienda,
            agente_front=agente_carga_name,
            dni_cuit=dni_cuit,
            tracking=tracking,
            nombre_cliente=nombre_cliente,
            email_cliente=email_cliente,
            created_by=current_user.id,
            assigned_to=selected_back_agent.id if selected_back_agent else None,
            status="nuevo",
        )
        db.session.add(case)
        db.session.commit()

        # Registrar evento de creación en la línea de tiempo
        log_case_event(
            case_id=case.id,
            event_type="creacion",
            title="Caso Registrado",
            description=f"Tipo '{sheet.display_name}' registrado por {current_user.display_name} ({current_user.role_label}).",
            user_id=current_user.id,
            new_val="nuevo",
        )

        if selected_back_agent:
            desc_asig = f"Auto-asignado a {selected_back_agent.display_name}." if selected_back_agent.id == current_user.id else f"Enrutado automáticamente por sub-rol a {selected_back_agent.display_name}."
            log_case_event(
                case_id=case.id,
                event_type="asignacion",
                title=f"Asignado a {selected_back_agent.display_name}",
                description=desc_asig,
                user_id=current_user.id if selected_back_agent.id == current_user.id else None,
                new_val=selected_back_agent.display_name,
            )
            flash(f"Caso #{case.id} creado con éxito y asignado a {selected_back_agent.display_name}.", "success")
        else:
            flash(f"Caso #{case.id} creado con éxito. Pendiente de asignación en la cola de Back Office.", "warning")

        db.session.commit()

        # Redirección inteligente: si lo cargó Back Office o Admin, abrir el caso directamente
        if current_user.is_back_office or current_user.is_admin or current_user.is_supervisor:
            return redirect(url_for("dashboard.case_detail", case_id=case.id))
        else:
            return redirect(url_for("front.bandeja_front"))

    # GET request: si viene ?sheet_id pre-seleccionado
    selected_sheet_id = request.args.get("sheet_id", type=int)
    selected_sheet = None
    if selected_sheet_id:
        selected_sheet = SheetConfig.query.get(selected_sheet_id)

    return render_template(
        "front/nuevo_caso.html",
        sheets=sheets,
        selected_sheet=selected_sheet,
    )


@front_bp.route("/mis-casos-front")
@login_required
def bandeja_front():
    """Bandeja de entrada del Agente Front: prioriza casos devueltos (re-verificar / rechazados)."""
    tab = request.args.get("tab", "devueltos")

    # Si es admin o supervisor puede ver todo o filtrar
    if current_user.is_admin or current_user.is_supervisor:
        query = Case.query
    else:
        query = Case.query.filter_by(created_by=current_user.id)

    # Conteos para badges
    if current_user.is_admin or current_user.is_supervisor:
        count_devueltos = Case.query.filter(Case.status.in_(["reverificar", "rechazado"])).count()
        count_activos = Case.query.filter(Case.status.in_(["nuevo", "en_proceso", "reenviado"])).count()
        count_resueltos = Case.query.filter(Case.status.in_(["resuelto", "cerrado"])).count()
    else:
        count_devueltos = Case.query.filter(
            Case.created_by == current_user.id,
            Case.status.in_(["reverificar", "rechazado"])
        ).count()
        count_activos = Case.query.filter(
            Case.created_by == current_user.id,
            Case.status.in_(["nuevo", "en_proceso", "reenviado"])
        ).count()
        count_resueltos = Case.query.filter(
            Case.created_by == current_user.id,
            Case.status.in_(["resuelto", "cerrado"])
        ).count()

    if tab == "devueltos":
        cases = query.filter(Case.status.in_(["reverificar", "rechazado"])).order_by(Case.updated_at.desc()).all()
    elif tab == "activos":
        cases = query.filter(Case.status.in_(["nuevo", "en_proceso", "reenviado"])).order_by(Case.updated_at.desc()).all()
    elif tab == "resueltos":
        cases = query.filter(Case.status.in_(["resuelto", "cerrado"])).order_by(Case.updated_at.desc()).all()
    else:
        cases = query.order_by(Case.created_at.desc()).all()

    return render_template(
        "front/bandeja.html",
        cases=cases,
        active_tab=tab,
        count_devueltos=count_devueltos,
        count_activos=count_activos,
        count_resueltos=count_resueltos,
    )


@front_bp.route("/caso/<int:case_id>/reenviar", methods=["POST"])
@login_required
def reenviar_caso(case_id):
    """Front corrige datos del caso y lo re-envía a Back Office con una respuesta."""
    case = Case.query.get_or_404(case_id)

    if not (current_user.is_admin or current_user.is_supervisor or case.created_by == current_user.id):
        flash("No tenés permiso para re-enviar este caso.", "error")
        return redirect(url_for("front.bandeja_front"))

    # Actualizar datos de Front si se editaron
    input_columns = json.loads(case.sheet_config.input_columns) if case.sheet_config.input_columns else []
    raw_data = json.loads(case.raw_data) if case.raw_data else {}

    for col in input_columns:
        key = col.get("key", col.get("name", ""))
        val = request.form.get(f"input_{key}")
        if val is not None:
            raw_data[key] = val.strip()

    case.raw_data = json.dumps(raw_data, ensure_ascii=False)

    # Respuesta de Front
    respuesta_front = request.form.get("respuesta_front", "").strip()
    case.respuesta_front = respuesta_front

    old_status = case.status
    case.status = "reenviado"
    case.updated_at = datetime.now(timezone.utc)

    db.session.commit()

    log_case_event(
        case_id=case.id,
        event_type="reenvio",
        title="Caso Re-enviado por Front",
        description=f"Front respondió a la solicitud: '{respuesta_front or 'Datos corregidos sin comentario adicional'}'",
        user_id=current_user.id,
        old_val=old_status,
        new_val="reenviado",
    )
    db.session.commit()

    flash(f"Caso #{case.id} corregido y re-enviado con éxito a Back Office.", "success")
    return redirect(url_for("dashboard.case_detail", case_id=case.id))
