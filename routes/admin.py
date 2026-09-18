import json
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db, User, SheetConfig, user_sheet_assignments, Case, RolePermission, slugify, is_light_color, log_case_event
from functools import wraps


admin_bp = Blueprint("admin", __name__)


def supervisor_or_admin_required(f):
    """Decorador para rutas que pueden ver admins y supervisores."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not (current_user.is_admin or current_user.is_supervisor):
            flash("No tenés permisos de administración o supervisión.", "error")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated


# ── Usuarios ──

@admin_bp.route("/usuarios")
@login_required
@supervisor_or_admin_required
def usuarios():
    users = User.query.order_by(User.display_name).all()
    sheets = SheetConfig.query.filter_by(is_active=True).order_by(SheetConfig.display_name).all()
    return render_template("admin/usuarios.html", users=users, sheets=sheets)


@admin_bp.route("/usuarios/crear", methods=["POST"])
@login_required
@supervisor_or_admin_required
def crear_usuario():
    username = request.form.get("username", "").strip().lower()
    display_name = request.form.get("display_name", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "agente_back")
    sheet_ids = request.form.getlist("sheet_ids")

    if not username or not password or not display_name:
        flash("Todos los campos son obligatorios.", "error")
        return redirect(url_for("admin.usuarios"))

    if User.query.filter_by(username=username).first():
        flash(f"El usuario '{username}' ya existe.", "error")
        return redirect(url_for("admin.usuarios"))

    user = User(username=username, display_name=display_name, role=role, is_active_user=True)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    for sid in sheet_ids:
        try:
            sheet = SheetConfig.query.get(int(sid))
            if sheet:
                user.assigned_sheets.append(sheet)
        except Exception:
            pass

    db.session.commit()
    assigned_count = user.assigned_sheets.count()
    flash(f"Usuario '{display_name}' creado con {assigned_count} tipo(s) de caso asignado(s).", "success")
    return redirect(url_for("admin.usuarios"))


@admin_bp.route("/usuarios/<int:user_id>/editar", methods=["POST"])
@login_required
@supervisor_or_admin_required
def editar_usuario(user_id):
    user = User.query.get_or_404(user_id)
    display_name = request.form.get("display_name", "").strip()
    role = request.form.get("role", user.role)
    is_active = (request.form.get("is_active") == "1")
    sheet_ids = request.form.getlist("sheet_ids")

    if display_name:
        user.display_name = display_name
    if role:
        user.role = role

    # No permitir que el usuario actual se inactive a sí mismo
    if user.id != current_user.id:
        user.is_active_user = is_active

    # Actualizar tipologías asignadas
    db.session.execute(
        user_sheet_assignments.delete().where(user_sheet_assignments.c.user_id == user.id)
    )
    for sid in sheet_ids:
        try:
            sheet = SheetConfig.query.get(int(sid))
            if sheet:
                user.assigned_sheets.append(sheet)
        except Exception:
            pass

    db.session.commit()
    assigned_count = user.assigned_sheets.count()
    flash(f"Usuario '{user.display_name}' actualizado con {assigned_count} tipo(s) de caso asignado(s).", "success")
    return redirect(url_for("admin.usuarios"))



@admin_bp.route("/usuarios/<int:user_id>/toggle", methods=["POST"])
@login_required
@supervisor_or_admin_required
def toggle_usuario(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("No podés desactivarte a vos mismo.", "error")
        return redirect(url_for("admin.usuarios"))

    user.is_active_user = not user.is_active_user
    db.session.commit()
    state = "activado" if user.is_active_user else "desactivado"
    flash(f"Usuario '{user.display_name}' {state}.", "success")
    return redirect(url_for("admin.usuarios"))


@admin_bp.route("/usuarios/<int:user_id>/reset-password", methods=["POST"])
@login_required
@supervisor_or_admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get("new_password", "")
    if not new_password:
        flash("La contraseña no puede estar vacía.", "error")
        return redirect(url_for("admin.usuarios"))

    user.set_password(new_password)
    db.session.commit()
    flash(f"Contraseña de '{user.display_name}' actualizada.", "success")
    return redirect(url_for("admin.usuarios"))


# ── Asignaciones (estilo Discord) ──

@admin_bp.route("/asignaciones")
@login_required
@supervisor_or_admin_required
def asignaciones():
    # Solo mostrar usuarios que gestionan colas de Back Office (Back Office, Supervisores, Admin)
    users = User.query.filter(
        User.is_active_user == True,
        User.role.in_(["agente_back", "supervisor", "admin"])
    ).order_by(User.display_name).all()
    sheets = SheetConfig.query.filter_by(is_active=True).order_by(SheetConfig.display_name).all()

    # Construir matriz de asignaciones
    assignments = {}
    for user in users:
        assigned_ids = [s.id for s in user.assigned_sheets.all()]
        assignments[user.id] = assigned_ids

    return render_template(
        "admin/asignaciones.html",
        users=users,
        sheets=sheets,
        assignments=assignments,
    )


@admin_bp.route("/asignaciones/guardar", methods=["POST"])
@login_required
@supervisor_or_admin_required
def guardar_asignaciones():
    users = User.query.filter(
        User.is_active_user == True,
        User.role.in_(["agente_back", "supervisor", "admin"])
    ).all()

    for user in users:
        # Obtener los sheet IDs marcados para este usuario
        sheet_ids = request.form.getlist(f"user_{user.id}_sheets")
        sheet_ids = [int(sid) for sid in sheet_ids]

        # Limpiar asignaciones actuales
        db.session.execute(
            user_sheet_assignments.delete().where(
                user_sheet_assignments.c.user_id == user.id
            )
        )

        # Insertar nuevas asignaciones
        for sid in sheet_ids:
            db.session.execute(
                user_sheet_assignments.insert().values(user_id=user.id, sheet_config_id=sid)
            )

    db.session.commit()
    flash("Asignaciones actualizadas.", "success")
    return redirect(url_for("admin.asignaciones"))


# ── Estadísticas ──

@admin_bp.route("/estadisticas")
@login_required
@supervisor_or_admin_required
def estadisticas():
    sheets = SheetConfig.query.filter_by(is_active=True).all()
    users = User.query.filter_by(is_active_user=True).all()

    from sqlalchemy import func

    # 1. Casos agrupados por hoja y estado en 1 sola consulta SQL
    sheet_grouped = db.session.query(
        Case.sheet_config_id,
        Case.status,
        func.count(Case.id).label("count")
    ).group_by(Case.sheet_config_id, Case.status).all()

    sheet_counts_map = {}
    for sid, st, cnt in sheet_grouped:
        if sid not in sheet_counts_map:
            sheet_counts_map[sid] = {}
        sheet_counts_map[sid][st] = cnt

    cases_by_sheet = []
    for sheet in sheets:
        counts = sheet_counts_map.get(sheet.id, {})
        nuevos = counts.get("nuevo", 0)
        en_proceso = counts.get("en_proceso", 0)
        resueltos = counts.get("resuelto", 0)
        rechazados = counts.get("rechazado", 0)
        total = sum(counts.values())
        cases_by_sheet.append({
            "name": sheet.display_name,
            "color": sheet.color,
            "total": total,
            "nuevos": nuevos,
            "en_proceso": en_proceso,
            "resueltos": resueltos,
            "rechazados": rechazados,
        })

    # 2. Casos agrupados por agente y estado en 1 sola consulta SQL
    agent_grouped = db.session.query(
        Case.assigned_to,
        Case.status,
        func.count(Case.id).label("count")
    ).group_by(Case.assigned_to, Case.status).all()

    agent_counts_map = {}
    sin_asignar = 0
    total_assigned_global = 0
    for uid, st, cnt in agent_grouped:
        if uid is None:
            sin_asignar += cnt
            continue
        if uid not in agent_counts_map:
            agent_counts_map[uid] = {}
        agent_counts_map[uid][st] = cnt
        total_assigned_global += cnt

    cases_by_agent = []
    for user in users:
        counts = agent_counts_map.get(user.id, {})
        resueltos = counts.get("resuelto", 0)
        rechazados = counts.get("rechazado", 0)
        total = sum(counts.values())
        cases_by_agent.append({
            "name": user.display_name,
            "total": total,
            "resueltos": resueltos,
            "rechazados": rechazados,
        })

    total_global = total_assigned_global + sin_asignar

    return render_template(
        "admin/estadisticas.html",
        cases_by_sheet=cases_by_sheet,
        cases_by_agent=cases_by_agent,
        total_global=total_global,
        sin_asignar=sin_asignar,
    )


# ── Matriz Dinámica de Permisos por Rol ──

@admin_bp.route("/permisos")
@login_required
@supervisor_or_admin_required
def permisos():
    roles = ["admin", "supervisor", "agente_back", "agente_front", "tyq"]
    role_labels = {
        "admin": "Administrador",
        "supervisor": "Supervisor",
        "agente_back": "Agente Back Office",
        "agente_front": "Agente Front",
        "tyq": "Calidad (TYQ)",
    }
    permissions_data = []
    for r in roles:
        p = RolePermission.get_for_role(r)
        permissions_data.append({
            "role": r,
            "label": role_labels.get(r, r),
            "perm": p
        })
    return render_template("admin/permisos.html", permissions=permissions_data)


@admin_bp.route("/permisos/guardar", methods=["POST"])
@login_required
@supervisor_or_admin_required
def guardar_permisos():
    roles = ["admin", "supervisor", "agente_back", "agente_front", "tyq"]
    perm_fields = [
        "can_create_cases",
        "can_resolve_cases",
        "can_reject_cases",
        "can_reopen_cases",
        "can_view_all_cases",
        "can_audit_quality",
        "can_export_reports",
    ]
    for r in roles:
        p = RolePermission.get_for_role(r)
        if r in ("admin", "supervisor"):
            p.can_manage_users = True
            p.can_manage_case_types = True

        for f in perm_fields:
            # Checkbox sends "on" if checked, otherwise absent
            val = (request.form.get(f"{r}_{f}") == "on")
            setattr(p, f, val)

    db.session.commit()
    flash("Matriz de permisos por rol actualizada exitosamente.", "success")
    return redirect(url_for("admin.permisos"))


# ── Gestor Completo de Tipos de Casos (Tipologías / Hojas) ──

@admin_bp.route("/tipos-casos")
@login_required
@supervisor_or_admin_required
def tipos_casos():
    from sqlalchemy import func, case as sql_case
    sheets = SheetConfig.query.order_by(SheetConfig.display_name).all()

    # 1 sola consulta SQL optimizada con GROUP BY en vez de 2N queries individuales
    stats = db.session.query(
        Case.sheet_config_id,
        func.count(Case.id).label("total"),
        func.sum(
            sql_case(
                (Case.status.in_(["nuevo", "en_proceso", "reverificar", "reenviado"]), 1),
                else_=0
            )
        ).label("activos")
    ).group_by(Case.sheet_config_id).all()

    counts_map = {sid: (tot or 0, act or 0) for sid, tot, act in stats}

    sheets_info = []
    for s in sheets:
        total, activos = counts_map.get(s.id, (0, 0))
        sheets_info.append({
            "sheet": s,
            "total_cases": total,
            "active_cases": activos,
        })
    return render_template("admin/tipos_casos.html", sheets_info=sheets_info)


@admin_bp.route("/tipos-casos/crear", methods=["POST"])
@login_required
@supervisor_or_admin_required
def crear_tipo_caso():
    display_name = request.form.get("display_name", "").strip()
    color = request.form.get("color", "#6366f1").strip()
    description = request.form.get("description", "").strip()
    badge_label = request.form.get("badge_label", "").strip() or display_name
    badge_bg = request.form.get("badge_bg", "").strip() or color
    badge_text_color = request.form.get("badge_text_color", "").strip()

    if not display_name:
        flash("El nombre del tipo de caso es obligatorio.", "error")
        return redirect(url_for("admin.tipos_casos"))

    # Generar slug único automático
    base_slug = slugify(display_name)
    slug = base_slug
    counter = 1
    while SheetConfig.query.filter_by(slug=slug).first() is not None:
        counter += 1
        slug = f"{base_slug}_{counter}"

    # Nombre de hoja único
    sheet_name = display_name
    counter = 1
    while SheetConfig.query.filter_by(sheet_name=sheet_name).first() is not None:
        counter += 1
        sheet_name = f"{display_name} ({counter})"

    # Columnas base limpias y estandarizadas
    in_cols = json.dumps([
        {"key": "id_pedido", "name": "ID Pedido", "column": "A", "index": 0, "maps_to": "pedido_id", "required": True},
        {"key": "fecha", "name": "Fecha", "column": "B", "index": 1, "maps_to": "fecha"},
        {"key": "tienda", "name": "Tienda", "column": "C", "index": 2, "maps_to": "tienda"},
        {"key": "solicitud", "name": "Solicitud", "column": "D", "index": 3, "maps_to": "solicitud"},
        {"key": "observaciones", "name": "Observaciones", "column": "E", "index": 4, "type": "textarea"}
    ], ensure_ascii=False)

    out_cols = json.dumps([
        {"key": "referencia_bo", "name": "Referencia Back Office", "column": "F", "index": 5, "type": "text"},
        {"key": "resuelto", "name": "Resuelto", "column": "G", "index": 6, "type": "select", "options": ["", "Si", "No", "Rechazado"]},
        {"key": "observaciones_bo", "name": "Observaciones Back Office", "column": "H", "index": 7, "type": "textarea"}
    ], ensure_ascii=False)

    if not badge_text_color:
        badge_text_color = "#0f172a" if is_light_color(badge_bg) else "#ffffff"

    sla_hours_val = request.form.get("sla_hours", "48").strip()
    try:
        sla_hours = int(sla_hours_val)
        if sla_hours <= 0:
            sla_hours = 48
    except ValueError:
        sla_hours = 48

    default_priority = request.form.get("default_priority", "media").strip().lower()
    if default_priority not in ("urgente", "alta", "media", "baja"):
        default_priority = "media"

    sc = SheetConfig(
        slug=slug,
        sheet_name=sheet_name,
        display_name=display_name,
        color=color or "#6366f1",
        description=description,
        badge_label=badge_label,
        badge_bg=badge_bg,
        badge_text_color=badge_text_color,
        badge_css_class=f"badge-{slug}",
        sla_hours=sla_hours,
        default_priority=default_priority,
        input_columns=in_cols,
        output_columns=out_cols,
        is_active=True,
    )
    db.session.add(sc)
    db.session.flush()

    # Asignar automáticamente a admins y supervisores
    super_users = User.query.filter(User.role.in_(["admin", "supervisor"])).all()
    for u in super_users:
        if sc not in u.assigned_sheets.all():
            u.assigned_sheets.append(sc)

    db.session.commit()
    flash(f"Tipo de caso '{display_name}' creado con éxito.", "success")
    return redirect(url_for("admin.tipos_casos"))


@admin_bp.route("/tipos-casos/<int:sheet_id>/editar", methods=["POST"])
@login_required
@supervisor_or_admin_required
def editar_tipo_caso(sheet_id):
    sheet = SheetConfig.query.get_or_404(sheet_id)
    display_name = request.form.get("display_name", "").strip()
    color = request.form.get("color", "").strip()
    description = request.form.get("description", "").strip()
    is_active = request.form.get("is_active") == "1"

    badge_label = request.form.get("badge_label", "").strip()
    badge_bg = request.form.get("badge_bg", "").strip()
    badge_text_color = request.form.get("badge_text_color", "").strip()

    if display_name:
        sheet.display_name = display_name
    if color:
        sheet.color = color
    sheet.description = description
    sheet.is_active = is_active

    if badge_label:
        sheet.badge_label = badge_label
    elif not sheet.badge_label:
        sheet.badge_label = sheet.display_name

    if badge_bg:
        sheet.badge_bg = badge_bg
        sheet.color = badge_bg
    elif color:
        sheet.badge_bg = color
        sheet.color = color
    else:
        if not sheet.badge_bg:
            sheet.badge_bg = sheet.color or "#6366f1"
        if not sheet.color:
            sheet.color = sheet.badge_bg

    if badge_text_color:
        sheet.badge_text_color = badge_text_color
    else:
        sheet.badge_text_color = "#0f172a" if is_light_color(sheet.badge_bg or sheet.color) else "#ffffff"

    if not sheet.slug:
        sheet.slug = slugify(sheet.display_name)

    sla_hours_val = request.form.get("sla_hours", "").strip()
    if sla_hours_val:
        try:
            val = int(sla_hours_val)
            if val > 0:
                sheet.sla_hours = val
        except ValueError:
            pass

    default_priority = request.form.get("default_priority", "").strip().lower()
    if default_priority in ("urgente", "alta", "media", "baja"):
        sheet.default_priority = default_priority

    db.session.commit()
    flash(f"Tipo de caso '{sheet.display_name}' modificado correctamente.", "success")
    return redirect(url_for("admin.tipos_casos"))


@admin_bp.route("/tipos-casos/<int:sheet_id>/columnas", methods=["GET", "POST"])
@login_required
@supervisor_or_admin_required
def columnas_tipo_caso(sheet_id):
    sheet = SheetConfig.query.get_or_404(sheet_id)
    if request.method == "POST":
        if request.is_json:
            data = request.get_json()
            input_cols = data.get("input_columns", [])
            output_cols = data.get("output_columns", [])
            sheet.input_columns = json.dumps(input_cols, ensure_ascii=False)
            sheet.output_columns = json.dumps(output_cols, ensure_ascii=False)
            db.session.commit()
            return {"status": "ok", "message": "Columnas actualizadas correctamente"}
        else:
            in_cols_raw = request.form.get("input_columns", "")
            out_cols_raw = request.form.get("output_columns", "")
            try:
                if in_cols_raw:
                    json.loads(in_cols_raw)
                    sheet.input_columns = in_cols_raw
                if out_cols_raw:
                    json.loads(out_cols_raw)
                    sheet.output_columns = out_cols_raw
                db.session.commit()
                flash(f"Columnas de '{sheet.display_name}' actualizadas.", "success")
            except Exception as e:
                flash(f"Error en formato de columnas: {e}", "error")
            return redirect(url_for("admin.tipos_casos"))

    # GET
    return {
        "sheet_id": sheet.id,
        "display_name": sheet.display_name,
        "input_columns": json.loads(sheet.input_columns) if sheet.input_columns else [],
        "output_columns": json.loads(sheet.output_columns) if sheet.output_columns else []
    }


@admin_bp.route("/tipos-casos/<int:sheet_id>/toggle", methods=["POST"])
@login_required
@supervisor_or_admin_required
def toggle_tipo_caso(sheet_id):
    sheet = SheetConfig.query.get_or_404(sheet_id)
    sheet.is_active = not sheet.is_active
    db.session.commit()
    estado = "activado" if sheet.is_active else "desactivado/pausado"
    flash(f"Tipo de caso '{sheet.display_name}' {estado}.", "info")
    return redirect(url_for("admin.tipos_casos"))


@admin_bp.route("/tipos-casos/<int:sheet_id>/eliminar", methods=["POST"])
@login_required
@supervisor_or_admin_required
def eliminar_tipo_caso(sheet_id):
    sheet = SheetConfig.query.get_or_404(sheet_id)
    reassign_to = request.form.get("reassign_to", type=int)

    cases_to_reassign = Case.query.filter_by(sheet_config_id=sheet.id).all()
    cases_count = len(cases_to_reassign)
    if cases_count > 0:
        if not reassign_to:
            fallback = SheetConfig.query.filter(
                SheetConfig.id != sheet.id,
                SheetConfig.display_name.ilike("%otros%")
            ).first() or SheetConfig.query.filter(SheetConfig.id != sheet.id, SheetConfig.is_active == True).first()

            if fallback:
                reassign_to = fallback.id
            else:
                flash("No podés eliminar la única tipología existente.", "error")
                return redirect(url_for("admin.tipos_casos"))

        target_sheet = SheetConfig.query.get_or_404(reassign_to)
        for c in cases_to_reassign:
            c.sheet_config_id = target_sheet.id
            log_case_event(
                case_id=c.id,
                event_type="reasignacion",
                title="Tipología Reasignada",
                description=f"Caso transferido a '{target_sheet.display_name}' por eliminación de '{sheet.display_name}'.",
                user_id=current_user.id,
            )
        db.session.commit()
        flash(f"Se reasignaron automáticamente {cases_count} caso(s) a '{target_sheet.display_name}'.", "info")

    name = sheet.display_name
    # Limpiar asignaciones de usuarios antes de borrar la hoja
    db.session.execute(
        user_sheet_assignments.delete().where(user_sheet_assignments.c.sheet_config_id == sheet.id)
    )
    db.session.delete(sheet)
    db.session.commit()
    flash(f"Tipo de caso '{name}' eliminado exitosamente.", "success")
    return redirect(url_for("admin.tipos_casos"))


# ── Consola de Supervisión de Asesores (Estilo Wise CX) ──

@admin_bp.route("/asesores/<int:user_id>")
@login_required
@supervisor_or_admin_required
def perfil_asesor(user_id):
    """Ficha y consola de supervisión del asesor en vivo (estilo Wise CX / Salesforce)."""
    advisor = User.query.get_or_404(user_id)

    status_filter = request.args.get("status", "").strip()
    sheet_filter = request.args.get("sheet", "").strip()
    search_query = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 25

    # Métricas de rendimiento y carga del asesor
    total_assigned = Case.query.filter_by(assigned_to=advisor.id).count()
    active_cases = Case.query.filter(
        Case.assigned_to == advisor.id,
        Case.status.in_(["nuevo", "en_proceso", "reverificar", "reenviado"])
    ).count()
    resolved_cases = Case.query.filter(Case.assigned_to == advisor.id, Case.status == "resuelto").count()
    returned_cases = Case.query.filter(Case.assigned_to == advisor.id, Case.status == "reverificar").count()

    quality_avg_query = db.session.query(db.func.avg(Case.quality_score)).filter(
        Case.assigned_to == advisor.id,
        Case.quality_score.isnot(None)
    ).scalar()
    quality_avg = round(float(quality_avg_query), 1) if quality_avg_query is not None else None

    # Semáforo de carga activa estilo Wise
    if active_cases == 0:
        load_status = {"label": "Sin Carga Activa", "color": "#10b981", "bg": "rgba(16, 185, 129, 0.15)", "border": "rgba(16, 185, 129, 0.3)"}
    elif active_cases <= 5:
        load_status = {"label": "Carga Óptima", "color": "#38bdf8", "bg": "rgba(56, 189, 248, 0.15)", "border": "rgba(56, 189, 248, 0.3)"}
    elif active_cases <= 15:
        load_status = {"label": "Carga Normal", "color": "#f59e0b", "bg": "rgba(245, 158, 11, 0.15)", "border": "rgba(245, 158, 11, 0.3)"}
    else:
        load_status = {"label": "Carga Elevada", "color": "#ef4444", "bg": "rgba(239, 68, 68, 0.15)", "border": "rgba(239, 68, 68, 0.3)"}

    # Query de casos en la bandeja del asesor
    query = Case.query.filter_by(assigned_to=advisor.id)
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
                Case.dni_cuit.ilike(f"%{search_query}%"),
                Case.tracking.ilike(f"%{search_query}%"),
                Case.codigo_sap.ilike(f"%{search_query}%"),
                Case.nombre_cliente.ilike(f"%{search_query}%"),
            )
        )

    pagination = query.options(
        db.joinedload(Case.sheet_config)
    ).order_by(Case.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    cases = pagination.items

    # Otros asesores activos para reasignación rápida de casos
    other_agents = User.query.filter(
        User.id != advisor.id,
        User.is_active_user == True,
        User.role.in_(["agente_back", "supervisor", "admin"])
    ).order_by(User.display_name).all()

    sheets = SheetConfig.query.filter_by(is_active=True).order_by(SheetConfig.display_name).all()

    return render_template(
        "admin/perfil_asesor.html",
        advisor=advisor,
        cases=cases,
        pagination=pagination,
        sheets=sheets,
        other_agents=other_agents,
        total_assigned=total_assigned,
        active_cases=active_cases,
        resolved_cases=resolved_cases,
        returned_cases=returned_cases,
        quality_avg=quality_avg,
        load_status=load_status,
        status_filter=status_filter,
        sheet_filter=sheet_filter,
        search_query=search_query,
    )


@admin_bp.route("/asesores/<int:user_id>/reasignar-caso/<int:case_id>", methods=["POST"])
@login_required
@supervisor_or_admin_required
def reasignar_caso_asesor(user_id, case_id):
    """Reasigna un caso de este asesor a otro asesor desde la consola Wise."""
    advisor = User.query.get_or_404(user_id)
    case = Case.query.get_or_404(case_id)
    target_agent_id = request.form.get("target_agent_id", type=int)

    if not target_agent_id:
        flash("Debés seleccionar un asesor de destino.", "error")
        return redirect(url_for("admin.perfil_asesor", user_id=user_id))

    target_agent = User.query.get_or_404(target_agent_id)
    old_agent_name = advisor.display_name
    new_agent_name = target_agent.display_name

    case.assigned_to = target_agent.id
    log_case_event(
        case_id=case.id,
        event_type="reasignacion",
        title="Caso Reasignado por Supervisor",
        description=f"Transferido de {old_agent_name} a {new_agent_name} vía Consola de Supervisión Wise.",
        user_id=current_user.id,
        old_val=old_agent_name,
        new_val=new_agent_name,
    )
    db.session.commit()
    flash(f"Caso #{case.id} transferido exitosamente a {new_agent_name}.", "success")
    return redirect(url_for("admin.perfil_asesor", user_id=user_id))

