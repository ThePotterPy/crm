import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, Case, SheetConfig, User, CaseEvent, log_case_event

quality_bp = Blueprint("quality", __name__)


@quality_bp.route("/calidad")
@login_required
def dashboard_calidad():
    """Panel general de Control de Calidad (TYQ)."""
    if not (current_user.is_quality or current_user.is_supervisor or current_user.is_admin):
        flash("No tenés permisos para acceder al módulo de Calidad TYQ.", "error")
        return redirect(url_for("dashboard.index"))

    # Métricas agregadas directamente en SQL
    audit_stats = db.session.query(
        func.count(Case.id).label("total"),
        func.avg(Case.quality_score).label("avg_score")
    ).filter(Case.quality_score.isnot(None)).first()

    total_audited = (audit_stats.total if audit_stats else 0) or 0
    avg_score = round(audit_stats.avg_score) if (audit_stats and audit_stats.avg_score is not None) else 0

    # Casos resueltos pendientes de auditar
    pending_audit_count = Case.query.filter(
        Case.status.in_(["resuelto", "rechazado"]),
        Case.quality_score.is_(None)
    ).count()

    # Desglose por agente con GROUP BY en SQL en una sola consulta
    back_agents = User.query.filter(User.role.in_(["agente_back", "agent"])).order_by(User.display_name).all()
    agent_grouped = db.session.query(
        Case.assigned_to,
        func.count(Case.id).label("count"),
        func.avg(Case.quality_score).label("avg")
    ).filter(Case.quality_score.isnot(None)).group_by(Case.assigned_to).all()

    agent_metrics = {row.assigned_to: (row.count, round(row.avg) if row.avg else None) for row in agent_grouped}

    agent_stats = []
    for agent in back_agents:
        count, avg = agent_metrics.get(agent.id, (0, None))
        agent_stats.append({
            "name": agent.display_name,
            "audits_count": count,
            "avg_score": avg,
        })

    # Cargar solo los 15 más recientes con relaciones precargadas
    recent_audited = Case.query.options(
        db.joinedload(Case.sheet_config),
        db.joinedload(Case.assigned_user),
    ).filter(Case.quality_score.isnot(None)).order_by(Case.audited_at.desc()).limit(15).all()

    # Casos resueltos recientes para auditar con relaciones precargadas
    cases_to_audit = Case.query.options(
        db.joinedload(Case.sheet_config),
        db.joinedload(Case.assigned_user),
    ).filter(
        Case.status.in_(["resuelto", "rechazado"]),
        Case.quality_score.is_(None)
    ).order_by(Case.updated_at.desc()).limit(20).all()

    return render_template(
        "quality/dashboard.html",
        total_audited=total_audited,
        avg_score=avg_score,
        pending_audit_count=pending_audit_count,
        agent_stats=agent_stats,
        recent_audited=recent_audited,
        cases_to_audit=cases_to_audit,
    )


@quality_bp.route("/caso/<int:case_id>/auditar", methods=["POST"])
@quality_bp.route("/calidad/caso/<int:case_id>/auditar", methods=["POST"])
@login_required
def auditar_caso(case_id):
    """Guardar o actualizar la auditoría de calidad de un caso."""
    if not (current_user.is_quality or current_user.is_supervisor or current_user.is_admin):
        flash("No tenés permisos para auditar casos.", "error")
        return redirect(url_for("dashboard.case_detail", case_id=case_id))

    case = Case.query.get_or_404(case_id)

    try:
        score = int(request.form.get("quality_score", 100))
        score = max(0, min(100, score))
    except (ValueError, TypeError):
        score = 100

    feedback = request.form.get("quality_feedback", "").strip()

    # Checklist
    checklist = {
        "datos_correctos": request.form.get("chk_datos") == "on",
        "procedimiento_cumplido": request.form.get("chk_procedimiento") == "on",
        "sap_cargado": request.form.get("chk_sap") == "on",
        "tiempos_sla": request.form.get("chk_tiempos") == "on",
    }

    case.quality_score = score
    case.quality_checklist = json.dumps(checklist)
    case.quality_feedback = feedback
    case.audited_by = current_user.id
    case.audited_at = datetime.now(timezone.utc)

    # Registrar evento en la línea de tiempo
    log_case_event(
        case_id=case.id,
        event_type="calidad",
        title=f"Auditoría TYQ: {score}%",
        description=f"Auditado por {current_user.display_name}. Devolución: {feedback or 'Sin observaciones adicionales.'}",
        user_id=current_user.id,
        new_val=f"{score}%",
    )
    db.session.commit()

    flash(f"Auditoría de Calidad guardada con éxito (Calificación: {score}%).", "success")
    return redirect(url_for("dashboard.case_detail", case_id=case.id))
