import json
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ── Tabla intermedia: qué hojas ve cada usuario ──
user_sheet_assignments = db.Table(
    "user_sheet_assignments",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("sheet_config_id", db.Integer, db.ForeignKey("sheet_configs.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    # Roles: admin | supervisor | agente_back | agente_front | tyq (calidad)
    role = db.Column(db.String(30), nullable=False, default="agente_back")
    is_active_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relación N:M con hojas (Sub-roles para agentes de Back Office)
    assigned_sheets = db.relationship(
        "SheetConfig",
        secondary=user_sheet_assignments,
        backref=db.backref("assigned_users", lazy="dynamic"),
        lazy="dynamic",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_supervisor(self):
        return self.role in ("admin", "supervisor")

    @property
    def is_back_office(self):
        return self.role in ("agente_back", "agent", "admin", "supervisor")

    @property
    def is_front_office(self):
        return self.role in ("agente_front", "admin", "supervisor")

    @property
    def is_quality(self):
        return self.role in ("tyq", "admin", "supervisor")

    @property
    def permissions(self):
        return RolePermission.get_for_role(self.role)

    @property
    def can_create_cases(self):
        if self.is_admin or self.is_supervisor:
            return True
        perm = self.permissions
        return perm.can_create_cases if perm else True

    @property
    def can_resolve_cases(self):
        if self.is_admin or self.is_supervisor:
            return True
        perm = self.permissions
        return perm.can_resolve_cases if perm else (self.role in ("agente_back", "agent"))

    @property
    def can_reject_cases(self):
        if self.is_admin or self.is_supervisor:
            return True
        perm = self.permissions
        return perm.can_reject_cases if perm else (self.role in ("agente_back", "agent"))

    @property
    def can_reopen_cases(self):
        if self.is_admin or self.is_supervisor:
            return True
        perm = self.permissions
        return perm.can_reopen_cases if perm else True

    @property
    def can_view_all_cases(self):
        if self.is_admin or self.is_supervisor:
            return True
        perm = self.permissions
        return perm.can_view_all_cases if perm else (self.role in ("tyq", "admin", "supervisor"))

    @property
    def can_audit_quality(self):
        if self.is_admin or self.is_supervisor:
            return True
        perm = self.permissions
        return perm.can_audit_quality if perm else (self.role == "tyq")

    @property
    def can_export_reports(self):
        if self.is_admin or self.is_supervisor:
            return True
        perm = self.permissions
        return perm.can_export_reports if perm else (self.role in ("admin", "supervisor", "tyq", "agente_back", "agent"))

    @property
    def can_manage_users(self):
        return self.role in ("admin", "supervisor")

    @property
    def can_manage_case_types(self):
        return self.role in ("admin", "supervisor")

    @property
    def role_label(self):
        labels = {
            "admin": "Administrador",
            "supervisor": "Supervisor",
            "agente_back": "Agente Back Office",
            "agente_front": "Agente Front",
            "tyq": "Calidad (TYQ)",
            "agent": "Agente Back Office",
        }
        return labels.get(self.role, self.role.capitalize())

    @property
    def role_badge_color(self):
        colors = {
            "admin": "#ef4444",
            "supervisor": "#8b5cf6",
            "agente_back": "#6366f1",
            "agente_front": "#3b82f6",
            "tyq": "#10b981",
            "agent": "#6366f1",
        }
        return colors.get(self.role, "#64748b")


def is_light_color(hex_str):
    """Calcula luminancia para seleccionar texto oscuro o blanco."""
    if not hex_str or not hex_str.startswith("#") or len(hex_str) < 7:
        return False
    try:
        r = int(hex_str[1:3], 16)
        g = int(hex_str[3:5], 16)
        b = int(hex_str[5:7], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return luminance > 0.6
    except Exception:
        return False


class RolePermission(db.Model):
    """Matriz dinámica de capacidades y permisos por rol del CRM."""
    __tablename__ = "role_permissions"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(30), unique=True, nullable=False)
    can_create_cases = db.Column(db.Boolean, default=True)
    can_resolve_cases = db.Column(db.Boolean, default=True)
    can_reject_cases = db.Column(db.Boolean, default=True)
    can_reopen_cases = db.Column(db.Boolean, default=True)
    can_view_all_cases = db.Column(db.Boolean, default=False)
    can_audit_quality = db.Column(db.Boolean, default=False)
    can_export_reports = db.Column(db.Boolean, default=True)
    can_manage_users = db.Column(db.Boolean, default=False)
    can_manage_case_types = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    @staticmethod
    def get_defaults():
        return {
            "admin": {
                "can_create_cases": True,
                "can_resolve_cases": True,
                "can_reject_cases": True,
                "can_reopen_cases": True,
                "can_view_all_cases": True,
                "can_audit_quality": True,
                "can_export_reports": True,
                "can_manage_users": True,
                "can_manage_case_types": True,
            },
            "supervisor": {
                "can_create_cases": True,
                "can_resolve_cases": True,
                "can_reject_cases": True,
                "can_reopen_cases": True,
                "can_view_all_cases": True,
                "can_audit_quality": True,
                "can_export_reports": True,
                "can_manage_users": True,
                "can_manage_case_types": True,
            },
            "agente_back": {
                "can_create_cases": True,  # Back office puede crear casos
                "can_resolve_cases": True,
                "can_reject_cases": True,
                "can_reopen_cases": True,
                "can_view_all_cases": False,
                "can_audit_quality": False,
                "can_export_reports": True,
                "can_manage_users": False,
                "can_manage_case_types": False,
            },
            "agente_front": {
                "can_create_cases": True,
                "can_resolve_cases": False,
                "can_reject_cases": False,
                "can_reopen_cases": True,
                "can_view_all_cases": False,
                "can_audit_quality": False,
                "can_export_reports": False,
                "can_manage_users": False,
                "can_manage_case_types": False,
            },
            "tyq": {
                "can_create_cases": False,
                "can_resolve_cases": False,
                "can_reject_cases": False,
                "can_reopen_cases": False,
                "can_view_all_cases": True,
                "can_audit_quality": True,
                "can_export_reports": True,
                "can_manage_users": False,
                "can_manage_case_types": False,
            },
        }

    @classmethod
    def get_for_role(cls, role_name):
        perm = cls.query.filter_by(role=role_name).first()
        if not perm:
            defaults = cls.get_defaults().get(role_name, cls.get_defaults().get("agente_back"))
            perm = cls(role=role_name, **defaults)
            try:
                db.session.add(perm)
                db.session.commit()
            except Exception:
                db.session.rollback()
        return perm


class SheetConfig(db.Model):
    """Configuración de cada hoja del spreadsheet (Tipo de Caso)."""
    __tablename__ = "sheet_configs"

    id = db.Column(db.Integer, primary_key=True)
    sheet_name = db.Column(db.String(200), unique=True, nullable=False)
    display_name = db.Column(db.String(200), nullable=False)
    header_row = db.Column(db.Integer, default=1)  # En qué fila están los headers
    input_columns = db.Column(db.Text, nullable=False, default="")  # JSON: columnas de entrada
    output_columns = db.Column(db.Text, nullable=False, default="")  # JSON: columnas de gestión CRM
    color = db.Column(db.String(7), default="#6366f1")  # Color para badges
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, default="")

    cases = db.relationship("Case", backref="sheet_config", lazy="dynamic")

    @property
    def badge_style(self):
        norm = self.display_name.upper().replace(" ", "").replace("_", "")
        if "RETIRO" in norm or "ARREPENTIMIENTO" in norm:
            return {"label": "Retiro arrepentimiento", "bg": "#0052cc", "color": "#ffffff", "css_class": "badge-retiro-arrepentimiento"}
        elif "DEFECTUOSO" in norm:
            return {"label": "CAMBIO DEFECTUOSO", "bg": "#065f46", "color": "#dcfce7", "css_class": "badge-cambio-defectuoso"}
        elif "INCORRECTO" in norm:
            return {"label": "CAMBIO INCORRECTO", "bg": "#fecdd3", "color": "#991b1b", "css_class": "badge-cambio-incorrecto"}
        elif "SEGUIMIENTO" in norm and "ENTREGA" not in norm:
            return {"label": "SEGUIMIENTO", "bg": "#fef08a", "color": "#713f12", "css_class": "badge-seguimiento"}
        elif "FACTURA" in norm or "NCPOR" in norm or norm.startswith("NC") or "NOTACREDITO" in norm:
            return {"label": "NC POR FACTURA B", "bg": "#991b1b", "color": "#ffffff", "css_class": "badge-nc-factura-b"}
        elif "OTROS" in norm or "OTRO" in norm:
            return {"label": "Otros", "bg": "#581c87", "color": "#ffffff", "css_class": "badge-otros"}
        else:
            txt_color = "#0f172a" if is_light_color(self.color) else "#ffffff"
            return {"label": self.display_name, "bg": self.color or "#6366f1", "color": txt_color, "css_class": "badge-sheet-custom"}


class Case(db.Model):
    """Un caso/ticket del CRM operativo."""
    __tablename__ = "cases"

    id = db.Column(db.Integer, primary_key=True)
    sheet_config_id = db.Column(db.Integer, db.ForeignKey("sheet_configs.id"), nullable=False)
    row_number = db.Column(db.Integer, nullable=True)  # Fila en el sheet

    # ── Datos de entrada (vienen del webhook o cargados por Front) ──
    raw_data = db.Column(db.Text, nullable=False, default="{}")  # JSON con todos los campos de entrada

    # Campos clave extraídos e indexados para búsqueda global instantánea
    pedido_id = db.Column(db.String(100), nullable=True, index=True)
    fecha = db.Column(db.String(50), nullable=True)
    solicitud = db.Column(db.String(300), nullable=True)
    tienda = db.Column(db.String(100), nullable=True)
    agente_front = db.Column(db.String(120), nullable=True)
    dni_cuit = db.Column(db.String(50), nullable=True, index=True)
    tracking = db.Column(db.String(100), nullable=True, index=True)
    nombre_cliente = db.Column(db.String(150), nullable=True)
    email_cliente = db.Column(db.String(150), nullable=True)
    codigo_sap = db.Column(db.String(100), nullable=True, index=True)
    caso_salesforce = db.Column(db.String(100), nullable=True, index=True)

    # ── Datos de gestión (columnas Back Office) ──
    output_data = db.Column(db.Text, nullable=False, default="{}")  # JSON con campos de salida

    # ── Estado del caso en el CRM ──
    # nuevo | en_proceso | reverificar | reenviado | resuelto | rechazado | cerrado
    status = db.Column(db.String(30), nullable=False, default="nuevo", index=True)

    # ── Circuito Front ⇄ Back Office ──
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    creator = db.relationship("User", foreign_keys=[created_by], backref="created_cases")

    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_user = db.relationship("User", foreign_keys=[assigned_to], backref="assigned_cases")

    # Motivos y comunicación
    motivo_rechazo = db.Column(db.Text, nullable=True)          # Indicado por Back Office al rechazar
    motivo_reverificacion = db.Column(db.Text, nullable=True)   # Nota de Back pidiendo a Front que chequee
    respuesta_front = db.Column(db.Text, nullable=True)         # Respuesta del Front al re-enviar el caso

    # ── Módulo TYQ (Training & Quality / Calidad) ──
    quality_score = db.Column(db.Integer, nullable=True)        # 0 a 100
    quality_checklist = db.Column(db.Text, nullable=True)       # JSON con respuestas del checklist
    quality_feedback = db.Column(db.Text, nullable=True)        # Devolución / Coaching
    audited_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    auditor = db.relationship("User", foreign_keys=[audited_by])
    audited_at = db.Column(db.DateTime, nullable=True)

    # ── Sincronización con Sheets (opcional / histórico) ──
    synced_to_sheet = db.Column(db.Boolean, default=False)
    synced_at = db.Column(db.DateTime, nullable=True)

    # ── Timestamps ──
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    @property
    def status_label(self):
        labels = {
            "nuevo": "Nuevo",
            "en_proceso": "En Proceso",
            "reverificar": "Re-verificar",
            "reenviado": "Re-enviado",
            "resuelto": "Resuelto",
            "rechazado": "Rechazado",
            "cerrado": "Cerrado",
        }
        return labels.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {
            "nuevo": "#3b82f6",
            "en_proceso": "#f59e0b",
            "reverificar": "#f97316",
            "reenviado": "#06b6d4",
            "resuelto": "#10b981",
            "rechazado": "#ef4444",
            "cerrado": "#6b7280",
        }
        return colors.get(self.status, "#6b7280")

    @property
    def typology_badge(self):
        """Devuelve dict con label, bg, color y clase css para renderizar la etiqueta exacta."""
        raw_text = (self.solicitud or (self.sheet_config.display_name if self.sheet_config else "")).strip()
        norm = raw_text.upper().replace(" ", "").replace("_", "")

        if self.sheet_config_id == 8 or ("SEGUIMIENTO" in norm and ("RETIRO" in norm or "ARREPENTIMIENTO" in norm)):
            return {
                "label": "Seguimiento de Retiros",
                "bg": "#0891b2",
                "color": "#ffffff",
                "css_class": "badge-seguimiento-retiros"
            }
        elif self.sheet_config_id == 1 or ("RETIRO" in norm or "ARREPENTIMIENTO" in norm):
            return {
                "label": "Retiro arrepentimiento",
                "bg": "#0052cc",
                "color": "#ffffff",
                "css_class": "badge-retiro-arrepentimiento"
            }
        elif "DEFECTUOSO" in norm:
            return {
                "label": "CAMBIO DEFECTUOSO",
                "bg": "#065f46",
                "color": "#dcfce7",
                "css_class": "badge-cambio-defectuoso"
            }
        elif "INCORRECTO" in norm:
            return {
                "label": "CAMBIO INCORRECTO",
                "bg": "#fecdd3",
                "color": "#991b1b",
                "css_class": "badge-cambio-incorrecto"
            }
        elif "SEGUIMIENTO" in norm and "ENTREGA" not in norm:
            return {
                "label": "SEGUIMIENTO",
                "bg": "#fef08a",
                "color": "#713f12",
                "css_class": "badge-seguimiento"
            }
        elif "FACTURA" in norm or "NCPOR" in norm or norm.startswith("NC") or "NOTACREDITO" in norm:
            return {
                "label": "NC POR FACTURA B",
                "bg": "#991b1b",
                "color": "#ffffff",
                "css_class": "badge-nc-factura-b"
            }
        elif "OTROS" in norm or "OTRO" in norm:
            return {
                "label": "Otros",
                "bg": "#581c87",
                "color": "#ffffff",
                "css_class": "badge-otros"
            }
        else:
            bg_color = self.sheet_config.color if self.sheet_config else "#6366f1"
            txt_color = "#0f172a" if is_light_color(bg_color) else "#ffffff"
            return {
                "label": self.sheet_config.display_name if self.sheet_config else (self.solicitud or "General"),
                "bg": bg_color,
                "color": txt_color,
                "css_class": "badge-sheet-custom"
            }

    @property
    def is_seguimiento_retiros(self):
        """Indica si el caso pertenece a la cola de Seguimiento de Retiros."""
        if self.sheet_config_id == 8:
            return True
        name = (self.sheet_config.display_name if self.sheet_config else (self.solicitud or "")).lower()
        return "seguimiento" in name and "retiro" in name

    @property
    def tracking_data(self):
        """Retorna un dict con los datos combinados de output_data y raw_data."""
        out = json.loads(self.output_data) if self.output_data else {}
        raw = json.loads(self.raw_data) if self.raw_data else {}
        return {**raw, **out}

    @property
    def estado_retiro(self):
        """Estado logístico del retiro: Pendiente de retiro | Retirado / En tránsito | Ingresado a depósito | No retirado / Fallido | Cancelado."""
        data = self.tracking_data
        val = data.get("estado_retiro") or data.get("estado") or ""
        if not val and self.is_seguimiento_retiros:
            return "Pendiente de retiro"
        return val

    @property
    def estado_retiro_badge(self):
        val = self.estado_retiro
        val_lower = val.lower() if val else ""
        if "ingresado" in val_lower or "deposito" in val_lower or "depósito" in val_lower:
            return {"label": val or "Ingresado a depósito", "bg": "#059669", "color": "#ffffff"}
        elif "retirado" in val_lower or "transito" in val_lower or "tránsito" in val_lower:
            return {"label": val or "Retirado / En tránsito", "bg": "#0284c7", "color": "#ffffff"}
        elif "no retirado" in val_lower or "fallido" in val_lower:
            return {"label": val or "No retirado / Fallido", "bg": "#dc2626", "color": "#ffffff"}
        elif "cancelado" in val_lower:
            return {"label": val or "Cancelado", "bg": "#64748b", "color": "#ffffff"}
        elif val:
            return {"label": val, "bg": "#d97706", "color": "#ffffff"}
        return {"label": "Pendiente de retiro", "bg": "#d97706", "color": "#ffffff"}

    @property
    def estado_reembolso(self):
        """Estado del reembolso: Reembolso no solicitado | Solicitado | Reembolsado."""
        data = self.tracking_data
        val = data.get("reembolso") or data.get("estado_reembolso") or ""
        if not val and self.is_seguimiento_retiros:
            return "Reembolso no solicitado"
        return val

    @property
    def estado_reembolso_badge(self):
        val = self.estado_reembolso
        val_lower = val.lower() if val else ""
        if "reembolsado" in val_lower:
            return {"label": "Reembolsado", "bg": "#10b981", "color": "#ffffff"}
        elif "solicitado" in val_lower and "no" not in val_lower:
            return {"label": "Solicitado", "bg": "#f97316", "color": "#ffffff"}
        elif "no" in val_lower or "pendiente" in val_lower:
            return {"label": "Reembolso no solicitado", "bg": "#475569", "color": "#cbd5e1"}
        elif val:
            return {"label": val, "bg": "#64748b", "color": "#ffffff"}
        return {"label": "Reembolso no solicitado", "bg": "#475569", "color": "#cbd5e1"}

    @property
    def zre2(self):
        data = self.tracking_data
        return data.get("zre2") or self.codigo_sap or ""

    @property
    def ultimo_estado_logistico(self):
        data = self.tracking_data
        return data.get("ultimo_estado") or ""


class CaseEvent(db.Model):
    """Línea de tiempo / Historial de auditoría para cada caso (Salesforce Timeline)."""
    __tablename__ = "case_events"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)
    # creacion | asignacion | cambio_estado | reverificar | reenvio | resolucion | rechazo | calidad | comentario
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    old_value = db.Column(db.String(100), nullable=True)
    new_value = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    case = db.relationship("Case", backref=db.backref("events", lazy="dynamic", order_by="CaseEvent.created_at.desc()"))
    user = db.relationship("User")


def log_case_event(case_id, event_type, title, description=None, user_id=None, old_val=None, new_val=None):
    """Helper para registrar eventos en la línea de tiempo del caso."""
    event = CaseEvent(
        case_id=case_id,
        user_id=user_id,
        event_type=event_type,
        title=title,
        description=description,
        old_value=str(old_val) if old_val is not None else None,
        new_value=str(new_val) if new_val is not None else None,
    )
    db.session.add(event)
    return event
