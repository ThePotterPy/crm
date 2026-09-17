import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db, Case, SheetConfig, User, CaseEvent, log_case_event
from services.sheets_sync import sync_case_to_sheet

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    """Dashboard principal: soporte para vistas 'Todos los Casos' y 'Casos Asignados'."""
    view_filter = request.args.get("view", "todos").strip().lower()
    if view_filter not in ("todos", "asignados"):
        view_filter = "todos"
    status_filter = request.args.get("status", "").strip()
    sheet_filter = request.args.get("sheet", "").strip() or request.args.get("tipo", "").strip()
    search_query = request.args.get("q", "").strip()

    # Determinar tipologías visibles según permisos
    if current_user.is_admin or current_user.is_supervisor or current_user.is_quality or current_user.can_view_all_cases:
        assigned_sheet_ids = [s.id for s in SheetConfig.query.filter_by(is_active=True).all()]
    elif current_user.is_back_office:
        assigned_sheet_ids = [s.id for s in current_user.assigned_sheets.all()]
    else:
        assigned_sheet_ids = [s.id for s in SheetConfig.query.filter_by(is_active=True).all()]

    sheets = SheetConfig.query.filter(
        SheetConfig.id.in_(assigned_sheet_ids), SheetConfig.is_active == True
    ).order_by(SheetConfig.display_name).all() if assigned_sheet_ids else SheetConfig.query.filter_by(is_active=True).order_by(SheetConfig.display_name).all()

    # Query base según la vista activa
    if view_filter == "asignados":
        if current_user.is_front_office and not current_user.is_back_office:
            base_view_query = Case.query.filter(
                db.or_(Case.assigned_to == current_user.id, Case.created_by == current_user.id)
            )
        else:
            base_view_query = Case.query.filter(Case.assigned_to == current_user.id)
    else:
        # 'todos': Todos los casos
        if current_user.is_admin or current_user.is_supervisor or current_user.is_quality or current_user.can_view_all_cases:
            base_view_query = Case.query
        elif current_user.is_back_office:
            base_view_query = Case.query.filter(Case.sheet_config_id.in_(assigned_sheet_ids)) if assigned_sheet_ids else Case.query.filter(Case.id == -1)
        else:
            base_view_query = Case.query.filter(Case.created_by == current_user.id)

    # Aplicar filtros interactivos de búsqueda, tipología y estado
    query = base_view_query
    if status_filter:
        query = query.filter(Case.status == status_filter)
    if sheet_filter:
        try:
            query = query.filter(Case.sheet_config_id == int(sheet_filter))
        except ValueError:
            pass
    if search_query:
        query = query.filter(
            db.or_(
                Case.pedido_id.ilike(f"%{search_query}%"),
                Case.solicitud.ilike(f"%{search_query}%"),
                Case.agente_front.ilike(f"%{search_query}%"),
                Case.dni_cuit.ilike(f"%{search_query}%"),
                Case.tracking.ilike(f"%{search_query}%"),
                Case.codigo_sap.ilike(f"%{search_query}%"),
                Case.nombre_cliente.ilike(f"%{search_query}%"),
                Case.email_cliente.ilike(f"%{search_query}%"),
            )
        )

    cases = query.order_by(Case.created_at.desc()).limit(150).all()

    # Métricas KPIs calculadas sobre la vista actual
    total_cases = base_view_query.count()
    new_cases = base_view_query.filter(Case.status == "nuevo").count()
    in_process = base_view_query.filter(Case.status == "en_proceso").count()
    reverificar_count = base_view_query.filter(Case.status == "reverificar").count()
    reenviado_count = base_view_query.filter(Case.status == "reenviado").count()
    resolved_cases = base_view_query.filter(Case.status == "resuelto").count()
    rejected_cases = base_view_query.filter(Case.status == "rechazado").count()

    # Conteos para los botones segmentados de vistas
    if current_user.is_admin or current_user.is_supervisor or current_user.is_quality or current_user.can_view_all_cases:
        count_todos = Case.query.count()
    elif current_user.is_back_office:
        count_todos = Case.query.filter(Case.sheet_config_id.in_(assigned_sheet_ids)).count() if assigned_sheet_ids else 0
    else:
        count_todos = Case.query.filter(Case.created_by == current_user.id).count()

    if current_user.is_front_office and not current_user.is_back_office:
        count_asignados = Case.query.filter(
            db.or_(Case.assigned_to == current_user.id, Case.created_by == current_user.id)
        ).count()
    else:
        count_asignados = Case.query.filter(Case.assigned_to == current_user.id).count()

    return render_template(
        "dashboard.html",
        cases=cases,
        sheets=sheets,
        total_cases=total_cases,
        new_cases=new_cases,
        in_process=in_process,
        reverificar_count=reverificar_count,
        reenviado_count=reenviado_count,
        resolved_cases=resolved_cases,
        rejected_cases=rejected_cases,
        status_filter=status_filter,
        sheet_filter=sheet_filter,
        search_query=search_query,
        view_filter=view_filter,
        count_todos=count_todos,
        count_asignados=count_asignados,
    )


@dashboard_bp.route("/buscar")
@login_required
def buscar_global():
    """Barra de búsqueda global universal (estilo Salesforce)."""
    q = request.args.get("q", "").strip()
    if not q:
        return redirect(url_for("dashboard.index"))

    # Búsqueda exhaustiva en todos los campos e información JSON
    results = Case.query.filter(
        db.or_(
            Case.pedido_id.ilike(f"%{q}%"),
            Case.dni_cuit.ilike(f"%{q}%"),
            Case.tracking.ilike(f"%{q}%"),
            Case.nombre_cliente.ilike(f"%{q}%"),
            Case.email_cliente.ilike(f"%{q}%"),
            Case.codigo_sap.ilike(f"%{q}%"),
            Case.caso_salesforce.ilike(f"%{q}%"),
            Case.solicitud.ilike(f"%{q}%"),
            Case.tienda.ilike(f"%{q}%"),
            Case.agente_front.ilike(f"%{q}%"),
            Case.motivo_rechazo.ilike(f"%{q}%"),
            Case.motivo_reverificacion.ilike(f"%{q}%"),
            Case.respuesta_front.ilike(f"%{q}%"),
            Case.raw_data.ilike(f"%{q}%"),
            Case.output_data.ilike(f"%{q}%"),
        )
    ).order_by(Case.created_at.desc()).limit(80).all()

    return render_template("search_results.html", query=q, cases=results)


@dashboard_bp.route("/caso/<int:case_id>")
@login_required
def case_detail(case_id):
    """Vista de detalle 360° del caso (Salesforce Record Page)."""
    case = Case.query.get_or_404(case_id)

    # Verificar acceso al caso
    can_access = (
        current_user.is_admin
        or current_user.is_supervisor
        or current_user.is_quality
        or current_user.can_view_all_cases
        or (case.created_by == current_user.id)
        or (case.assigned_to == current_user.id)
        or (case.sheet_config_id in [s.id for s in current_user.assigned_sheets.all()])
    )
    if not can_access:
        flash("No tenés acceso a este caso.", "error")
        return redirect(url_for("dashboard.index"))

    raw_data = json.loads(case.raw_data) if case.raw_data else {}
    output_data = json.loads(case.output_data) if case.output_data else {}
    input_columns = json.loads(case.sheet_config.input_columns) if case.sheet_config.input_columns else []
    output_columns = json.loads(case.sheet_config.output_columns) if case.sheet_config.output_columns else []
    events = case.events.all()

    # Checklist de calidad previo si existe
    quality_chk = json.loads(case.quality_checklist) if case.quality_checklist else {}

    # Lista de agentes para reasignación (Supervisores / Admins)
    back_agents = []
    if current_user.is_admin or current_user.is_supervisor:
        back_agents = User.query.filter(User.role.in_(["agente_back", "supervisor", "admin"]), User.is_active_user == True).order_by(User.display_name).all()

    return render_template(
        "caso_detalle.html",
        case=case,
        raw_data=raw_data,
        output_data=output_data,
        input_columns=input_columns,
        output_columns=output_columns,
        events=events,
        quality_chk=quality_chk,
        back_agents=back_agents,
    )


@dashboard_bp.route("/caso/<int:case_id>/gestionar", methods=["POST"])
@login_required
def manage_case(case_id):
    """Actualizar campos de Back Office, resolver, rechazar o pedir re-verificación."""
    case = Case.query.get_or_404(case_id)

    # Verificar acceso de edición (Back Office, Supervisor, Admin)
    can_manage = (
        current_user.is_admin
        or current_user.is_supervisor
        or (case.sheet_config_id in [s.id for s in current_user.assigned_sheets.all()])
    )
    if not can_manage:
        flash("No tenés permiso para editar la gestión de este caso.", "error")
        return redirect(url_for("dashboard.case_detail", case_id=case.id))

    old_status = case.status
    action = request.form.get("action", "guardar")

    # Recoger campos de salida de Back Office
    output_columns = json.loads(case.sheet_config.output_columns) if case.sheet_config.output_columns else []
    output_data = {}
    sap_code_found = ""
    salesforce_case_found = ""

    for col in output_columns:
        col_key = col.get("key", col.get("name", ""))
        col_name = col.get("name", "")
        val = request.form.get(f"output_{col_key}", request.form.get(f"output_{col_name}", ""))

        # Auto-completar agente back
        if col_key in ("agente_back", "agente_bo", "agente") and not val:
            val = current_user.display_name

        output_data[col_key] = val

        # Detectar código SAP y Salesforce para indexación
        k_lower = col_key.lower()
        if any(x in k_lower for x in ("sap", "codigo_sap", "zre", "zech")):
            if val and not sap_code_found:
                sap_code_found = val
        if any(x in k_lower for x in ("salesforce", "saleforce")) and val:
            salesforce_case_found = val

    if not salesforce_case_found:
        salesforce_case_found = request.form.get("caso_salesforce", "").strip()
    if not sap_code_found:
        sap_code_found = request.form.get("codigo_sap", "").strip()

    if sap_code_found:
        case.codigo_sap = sap_code_found
    if salesforce_case_found:
        case.caso_salesforce = salesforce_case_found

    # Asignar al usuario actual si no tenía asignado
    if not case.assigned_to:
        case.assigned_to = current_user.id

    # ── ACCIÓN: SOLICITAR RE-VERIFICACIÓN A FRONT ──
    if action == "solicitar_reverificacion":
        motivo_reverificar = (request.form.get("motivo_reverificar_texto") or request.form.get("motivo_reverificacion") or "").strip()
        if not motivo_reverificar:
            flash("Debés especificar qué dato necesita que el Agente Front re-verifique.", "error")
            return redirect(url_for("dashboard.case_detail", case_id=case.id))

        case.status = "reverificar"
        case.motivo_reverificacion = motivo_reverificar
        case.output_data = json.dumps(output_data, ensure_ascii=False)
        case.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_case_event(
            case_id=case.id,
            event_type="reverificar",
            title="Solicitud de Re-verificación enviada a Front",
            description=f"Back Office solicita corregir: '{motivo_reverificar}'",
            user_id=current_user.id,
            old_val=old_status,
            new_val="reverificar",
        )
        db.session.commit()

        flash(f"Caso #{case.id} derivado a la bandeja de Front Office para re-verificación.", "warning")
        return redirect(url_for("dashboard.case_detail", case_id=case.id))

    # ── ACCIÓN: RECHAZAR CASO ──
    elif action == "rechazar":
        if not current_user.can_reject_cases:
            flash("Tu rol no tiene permisos para rechazar casos.", "error")
            return redirect(url_for("dashboard.case_detail", case_id=case.id))

        motivo_categoria = request.form.get("motivo_categoria", "").strip()
        motivo_detalle = request.form.get("motivo_detalle", "").strip()

        full_motivo = ""
        if motivo_categoria and motivo_detalle:
            full_motivo = f"{motivo_categoria}: {motivo_detalle}"
        elif motivo_categoria:
            full_motivo = motivo_categoria
        elif motivo_detalle:
            full_motivo = motivo_detalle
        else:
            full_motivo = "Rechazado por Back Office sin motivo especificado"

        case.status = "rechazado"
        case.motivo_rechazo = full_motivo

        # Reflejar en desplegables de Back Office
        for col in output_columns:
            ckey = col.get("key", "")
            if ckey in ("resuelto", "estado_resuelto", "estado", "estado_caso", "estado_final"):
                if "Rechazado" in col.get("options", []):
                    output_data[ckey] = "Rechazado"

        # Incluir en observaciones
        obs_keys = ["observaciones", "observaciones_bo", "gestion_back", "obs", "resolucion_final"]
        for ok in obs_keys:
            if ok in output_data:
                tag = f"[RECHAZADO: {full_motivo}]"
                if tag not in output_data[ok]:
                    output_data[ok] = f"{tag} {output_data[ok]}".strip()
                break

        case.output_data = json.dumps(output_data, ensure_ascii=False)
        case.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_case_event(
            case_id=case.id,
            event_type="rechazo",
            title="Caso Rechazado",
            description=f"Motivo: {full_motivo}",
            user_id=current_user.id,
            old_val=old_status,
            new_val="rechazado",
        )
        db.session.commit()

        sync_case_to_sheet(case)
        flash(f"Caso #{case.id} marcado como RECHAZADO y notificado a Front.", "error")
        return redirect(url_for("dashboard.case_detail", case_id=case.id))

    # ── ACCIÓN: RESOLVER CASO ──
    elif action == "resolver":
        if not current_user.can_resolve_cases:
            flash("Tu rol no tiene permisos para resolver casos.", "error")
            return redirect(url_for("dashboard.case_detail", case_id=case.id))

        # Validación lógica de resolución segura: exige al menos un identificador o nota de gestión
        has_evidence = bool(
            case.caso_salesforce or
            case.codigo_sap or
            any(v.strip() for k, v in output_data.items() if k not in ("agente_back", "agente_bo", "agente"))
        )
        if not has_evidence:
            flash("Para marcar el caso como RESUELTO debés cargar el número de Caso SALESFORCE, Código SAP o completar los datos de gestión.", "warning")
            return redirect(url_for("dashboard.case_detail", case_id=case.id))

        case.status = "resuelto"
        for col in output_columns:
            ckey = col.get("key", "")
            if ckey in ("resuelto", "estado_resuelto"):
                if "Si" in col.get("options", []):
                    output_data[ckey] = "Si"

        case.output_data = json.dumps(output_data, ensure_ascii=False)
        case.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_case_event(
            case_id=case.id,
            event_type="resolucion",
            title="Caso Resuelto",
            description=f"Caso resuelto por {current_user.display_name}. SAP: {case.codigo_sap or '—'} | SF: {case.caso_salesforce or '—'}",
            user_id=current_user.id,
            old_val=old_status,
            new_val="resuelto",
        )
        db.session.commit()

        # Si el caso resuelto es una solicitud de Retiro por Arrepentimiento,
        # derivar automáticamente a la cola de 'Seguimiento de Retiros' para control logístico y reembolso
        tracking_sheet = SheetConfig.query.filter_by(id=8).first() or SheetConfig.query.filter(SheetConfig.display_name.ilike("%seguimiento%retiro%")).first()
        is_solicitud_retiro = (case.sheet_config_id == 1 or ("retiro" in (case.sheet_config.display_name or "").lower() and "seguimiento" not in (case.sheet_config.display_name or "").lower()))

        new_tracking_case = None
        if is_solicitud_retiro and tracking_sheet:
            # Verificar si ya existe un seguimiento para este pedido
            existing_tracking = Case.query.filter_by(sheet_config_id=tracking_sheet.id, pedido_id=case.pedido_id).first()
            if not existing_tracking:
                tracking_raw = {
                    "numero_pedido": case.pedido_id,
                    "fecha": datetime.now().strftime("%Y-%m-%d"),
                    "agente": current_user.display_name,
                    "caso": case.caso_salesforce or "",
                    "tienda": case.tienda or "",
                    "tipo": "Retiro arrepentimiento",
                    "estado_retiro": "Pendiente de retiro",
                    "reembolso": "Reembolso no solicitado",
                    "zre2": case.codigo_sap or "",
                    "ultimo_estado": "Retiro generado por Back Office",
                }
                tracking_out = {
                    "estado_retiro": "Pendiente de retiro",
                    "reembolso": "Reembolso no solicitado",
                    "zre2": case.codigo_sap or "",
                    "ultimo_estado": "Retiro generado por Back Office",
                    "obs": f"Generado automáticamente tras resolución de solicitud inicial #{case.id}.",
                }
                new_tracking_case = Case(
                    sheet_config_id=tracking_sheet.id,
                    raw_data=json.dumps(tracking_raw, ensure_ascii=False),
                    output_data=json.dumps(tracking_out, ensure_ascii=False),
                    pedido_id=case.pedido_id,
                    fecha=datetime.now().strftime("%Y-%m-%d"),
                    solicitud="Seguimiento de Retiros (Arrepentimiento)",
                    tienda=case.tienda,
                    agente_front=case.agente_front,
                    dni_cuit=case.dni_cuit,
                    tracking=case.tracking,
                    nombre_cliente=case.nombre_cliente,
                    email_cliente=case.email_cliente,
                    codigo_sap=case.codigo_sap,
                    caso_salesforce=case.caso_salesforce,
                    created_by=current_user.id,
                    assigned_to=current_user.id,
                    status="en_proceso",
                )
                db.session.add(new_tracking_case)
                db.session.commit()

                log_case_event(
                    case_id=new_tracking_case.id,
                    event_type="creacion",
                    title="Seguimiento de Retiro Iniciado",
                    description=f"Iniciado automáticamente a partir de la resolución del caso #{case.id}. Estado: Pendiente de retiro / Reembolso no solicitado.",
                    user_id=current_user.id,
                    new_val="en_proceso",
                )
                log_case_event(
                    case_id=case.id,
                    event_type="cambio_estado",
                    title="Derivado a Seguimiento de Retiros",
                    description=f"Se inició el seguimiento logístico en el Caso #{new_tracking_case.id}.",
                    user_id=current_user.id,
                    new_val=f"Seguimiento #{new_tracking_case.id}",
                )
                db.session.commit()

        sync_case_to_sheet(case)
        if new_tracking_case:
            flash(f"Caso #{case.id} RESUELTO. Se generó el Caso #{new_tracking_case.id} en 'Seguimiento de Retiros' para control de retiro y reembolso.", "success")
        else:
            flash(f"Caso #{case.id} marcado como RESUELTO exitosamente.", "success")
        return redirect(url_for("dashboard.case_detail", case_id=case.id))

    # ── ACCIÓN GENERAL: GUARDAR ──
    else:
        new_status = request.form.get("status", case.status)
        if new_status in ("nuevo", "en_proceso", "resuelto", "rechazado", "reverificar", "reenviado", "cerrado"):
            case.status = new_status

        case.output_data = json.dumps(output_data, ensure_ascii=False)
        case.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        if old_status != case.status:
            log_case_event(
                case_id=case.id,
                event_type="cambio_estado",
                title=f"Estado cambiado a {case.status_label}",
                description=f"Modificado por {current_user.display_name}",
                user_id=current_user.id,
                old_val=old_status,
                new_val=case.status,
            )
            db.session.commit()

        sync_case_to_sheet(case)
        flash(f"Caso #{case.id} actualizado con éxito.", "success")
        return redirect(url_for("dashboard.case_detail", case_id=case.id))


@dashboard_bp.route("/caso/<int:case_id>/tomar", methods=["POST"])
@login_required
def tomar_caso(case_id):
    """Permite a un agente de Back Office auto-asignarse un caso de su sub-rol."""
    case = Case.query.get_or_404(case_id)
    if not (current_user.is_back_office or current_user.is_admin or current_user.is_supervisor):
        flash("No tenés permisos de Back Office para tomar este caso.", "error")
        return redirect(url_for("dashboard.case_detail", case_id=case.id))

    old_name = case.assigned_user.display_name if case.assigned_user else "Sin asignar"
    case.assigned_to = current_user.id
    if case.status == "nuevo":
        case.status = "en_proceso"
    case.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_case_event(
        case_id=case.id,
        event_type="asignacion",
        title="Caso Tomado por Agente",
        description=f"Auto-asignado por {current_user.display_name} (antes: {old_name}).",
        user_id=current_user.id,
        new_val=current_user.display_name,
    )
    db.session.commit()
    flash(f"Te has auto-asignado el Caso #{case.id}.", "success")
    return redirect(url_for("dashboard.case_detail", case_id=case.id))


@dashboard_bp.route("/caso/<int:case_id>/reasignar", methods=["POST"])
@login_required
def reasignar_caso(case_id):
    """Permite a Administradores y Supervisores reasignar el caso a otro agente."""
    if not (current_user.is_admin or current_user.is_supervisor):
        flash("Solo administradores y supervisores pueden reasignar casos.", "error")
        return redirect(url_for("dashboard.case_detail", case_id=case_id))

    case = Case.query.get_or_404(case_id)
    new_user_id = request.form.get("nuevo_agente_id", type=int)
    if not new_user_id:
        flash("Debés seleccionar un agente para reasignar.", "error")
        return redirect(url_for("dashboard.case_detail", case_id=case.id))

    new_user = User.query.get_or_404(new_user_id)
    old_name = case.assigned_user.display_name if case.assigned_user else "Sin asignar"
    case.assigned_to = new_user.id
    case.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_case_event(
        case_id=case.id,
        event_type="asignacion",
        title=f"Caso Reasignado a {new_user.display_name}",
        description=f"Reasignado por {current_user.display_name} (antes: {old_name}).",
        user_id=current_user.id,
        new_val=new_user.display_name,
    )
    db.session.commit()
    flash(f"Caso #{case.id} reasignado exitosamente a {new_user.display_name}.", "success")
    return redirect(url_for("dashboard.case_detail", case_id=case.id))


@dashboard_bp.route("/caso/<int:case_id>/actualizar-seguimiento", methods=["POST"])
@login_required
def actualizar_seguimiento_retiro(case_id):
    """Permite al agente Back Office actualizar el estado del retiro y el estado del reembolso."""
    case = Case.query.get_or_404(case_id)

    can_manage = (
        current_user.is_admin
        or current_user.is_supervisor
        or (case.assigned_to == current_user.id)
        or (case.sheet_config_id in [s.id for s in current_user.assigned_sheets.all()])
        or current_user.is_back_office
    )
    if not can_manage:
        flash("No tenés permiso para actualizar el seguimiento de este caso.", "error")
        return redirect(url_for("dashboard.case_detail", case_id=case.id))

    estado_retiro = request.form.get("estado_retiro", "").strip()
    reembolso = request.form.get("reembolso", "").strip()
    zre2 = request.form.get("zre2", "").strip()
    ultimo_estado = request.form.get("ultimo_estado", "").strip()
    observaciones = request.form.get("observaciones_seguimiento", "").strip()

    out_data = json.loads(case.output_data) if case.output_data else {}
    raw_data = json.loads(case.raw_data) if case.raw_data else {}

    old_estado_retiro = out_data.get("estado_retiro") or raw_data.get("estado_retiro") or "Pendiente de retiro"
    old_reembolso = out_data.get("reembolso") or raw_data.get("reembolso") or "Reembolso no solicitado"

    if estado_retiro:
        out_data["estado_retiro"] = estado_retiro
        raw_data["estado_retiro"] = estado_retiro
    if reembolso:
        out_data["reembolso"] = reembolso
        raw_data["reembolso"] = reembolso
    if zre2:
        out_data["zre2"] = zre2
        raw_data["zre2"] = zre2
        case.codigo_sap = zre2
    if ultimo_estado:
        out_data["ultimo_estado"] = ultimo_estado
        raw_data["ultimo_estado"] = ultimo_estado
    if observaciones:
        out_data["obs"] = observaciones
        out_data["observaciones"] = observaciones

    # Si fue reembolsado y retirado/ingresado, opcionalmente puede marcarse como resuelto/cerrado
    if reembolso.lower() == "reembolsado":
        case.status = "resuelto"

    case.output_data = json.dumps(out_data, ensure_ascii=False)
    case.raw_data = json.dumps(raw_data, ensure_ascii=False)
    case.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    changes = []
    if estado_retiro and estado_retiro != old_estado_retiro:
        changes.append(f"Retiro: {old_estado_retiro} ➔ {estado_retiro}")
    if reembolso and reembolso != old_reembolso:
        changes.append(f"Reembolso: {old_reembolso} ➔ {reembolso}")
    if ultimo_estado:
        changes.append(f"Último estado: {ultimo_estado}")

    desc = " | ".join(changes) if changes else "Datos de seguimiento logístico actualizados."
    if observaciones:
        desc += f" (Nota: {observaciones})"

    log_case_event(
        case_id=case.id,
        event_type="cambio_estado",
        title="Actualización de Seguimiento de Retiro & Reembolso",
        description=desc,
        user_id=current_user.id,
        old_val=f"{old_estado_retiro} / {old_reembolso}",
        new_val=f"{estado_retiro} / {reembolso}",
    )
    db.session.commit()

    flash("Seguimiento de retiro y estado de reembolso actualizados correctamente.", "success")
    return redirect(url_for("dashboard.case_detail", case_id=case.id))

