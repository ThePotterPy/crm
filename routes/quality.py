import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db, Case, SheetConfig, User, CaseEvent, log_case_event

quality_bp = Blueprint("quality", __name__)


@quality_bp.route("/calidad")
@login_required
def dashboard_calidad():
    """Panel general de Control de Calidad (TYQ)."""
    if not (current_user.is_quality or current_user.is_supervisor or current_user.is_admin):
        flash("No tenés permisos para acceder al módulo de Calidad TYQ.", "error")
        return redirect(url_for("dashboard.index"))

    # Casos auditados
    audited_cases = Case.query.filter(Case.quality_score.isnot(None)).order_by(Case.audited_at.desc()).all()
    total_audited = len(audited_cases)

    # Promedio global
    avg_score = round(sum(c.quality_score for c in audited_cases) / total_audited) if total_audited > 0 else 0

    # Casos resueltos pendientes de auditar
    pending_audit_count = Case.query.filter(
        Case.status.in_(["resuelto", "rechazado"]),
        Case.quality_score.is_(None)
    ).count()

    # Desglose por agente
    back_agents = User.query.filter(User.role.in_(["agente_back", "agent"])).all()
    agent_stats = []
    for agent in back_agents:
        agent_audits = [c for c in audited_cases if c.assigned_to == agent.id]
        count = len(agent_audits)
        avg = round(sum(c.quality_score for c in agent_audits) / count) if count > 0 else None
        agent_stats.append({
            "name": agent.display_name,
            "audits_count": count,
            "avg_score": avg,
        })

    # Casos resueltos recientes para auditar
    cases_to_audit = Case.query.filter(
        Case.status.in_(["resuelto", "rechazado"]),
        Case.quality_score.is_(None)
    ).order_by(Case.updated_at.desc()).limit(20).all()

    return render_template(
        "quality/dashboard.html",
        total_audited=total_audited,
        avg_score=avg_score,
        pending_audit_count=pending_audit_count,
        agent_stats=agent_stats,
        recent_audited=audited_cases[:15],
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
