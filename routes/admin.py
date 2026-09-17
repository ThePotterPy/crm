import json
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db, User, SheetConfig, user_sheet_assignments, Case, RolePermission
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
    users = User.query.filter_by(is_active_user=True).order_by(User.display_name).all()
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
    users = User.query.filter_by(is_active_user=True).all()

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

    # Casos por hoja
    cases_by_sheet = []
    for sheet in sheets:
        total = Case.query.filter_by(sheet_config_id=sheet.id).count()
        nuevos = Case.query.filter_by(sheet_config_id=sheet.id, status="nuevo").count()
        en_proceso = Case.query.filter_by(sheet_config_id=sheet.id, status="en_proceso").count()
        resueltos = Case.query.filter_by(sheet_config_id=sheet.id, status="resuelto").count()
        rechazados = Case.query.filter_by(sheet_config_id=sheet.id, status="rechazado").count()
        cases_by_sheet.append({
            "name": sheet.display_name,
            "color": sheet.color,
            "total": total,
            "nuevos": nuevos,
            "en_proceso": en_proceso,
            "resueltos": resueltos,
            "rechazados": rechazados,
        })

    # Casos por agente
    cases_by_agent = []
    for user in users:
        total = Case.query.filter_by(assigned_to=user.id).count()
        resueltos = Case.query.filter_by(assigned_to=user.id, status="resuelto").count()
        rechazados = Case.query.filter_by(assigned_to=user.id, status="rechazado").count()
        cases_by_agent.append({
            "name": user.display_name,
            "total": total,
            "resueltos": resueltos,
            "rechazados": rechazados,
        })

    total_global = Case.query.count()
    sin_asignar = Case.query.filter_by(assigned_to=None).count()

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
    sheets = SheetConfig.query.order_by(SheetConfig.display_name).all()
    sheets_info = []
    for s in sheets:
        total = Case.query.filter_by(sheet_config_id=s.id).count()
        activos = Case.query.filter(
            Case.sheet_config_id == s.id,
            Case.status.in_(["nuevo", "en_proceso", "reverificar", "reenviado"])
        ).count()
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

    if not display_name:
        flash("El nombre del tipo de caso es obligatorio.", "error")
        return redirect(url_for("admin.tipos_casos"))

    # Validar unicidad de sheet_name
    base_sheet_name = f"SOLICITUDES BGH 2026 - {display_name}"
    sheet_name = base_sheet_name
    counter = 1
    while SheetConfig.query.filter_by(sheet_name=sheet_name).first() is not None:
        counter += 1
        sheet_name = f"{base_sheet_name} ({counter})"

    # Obtener esquema de columnas base de una hoja existente
    base_sheet = SheetConfig.query.first()
    in_cols = base_sheet.input_columns if base_sheet and base_sheet.input_columns else "[]"
    out_cols = base_sheet.output_columns if base_sheet and base_sheet.output_columns else "[]"

    sc = SheetConfig(
        sheet_name=sheet_name,
        display_name=display_name,
        color=color or "#6366f1",
        description=description,
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

    if display_name:
        sheet.display_name = display_name
    if color:
        sheet.color = color
    sheet.description = description
    sheet.is_active = is_active

    db.session.commit()
    flash(f"Tipo de caso '{sheet.display_name}' modificado correctamente.", "success")
    return redirect(url_for("admin.tipos_casos"))


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

    cases_count = Case.query.filter_by(sheet_config_id=sheet.id).count()
    if cases_count > 0:
        if not reassign_to:
            # Buscar tipología de respaldo (ej. 'Otros' o la primera activa disponible)
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
        Case.query.filter_by(sheet_config_id=sheet.id).update({"sheet_config_id": target_sheet.id})
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
