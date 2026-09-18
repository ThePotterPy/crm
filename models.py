import json
import re
from datetime import datetime, timezone, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def slugify(text):
    """Genera un slug simple a partir de texto."""
    text = text.lower().strip()
    text = re.sub(r'[áàäâ]', 'a', text)
    text = re.sub(r'[éèëê]', 'e', text)
    text = re.sub(r'[íìïî]', 'i', text)
    text = re.sub(r'[óòöô]', 'o', text)
    text = re.sub(r'[úùüû]', 'u', text)
    text = re.sub(r'[ñ]', 'n', text)
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = text.strip('_')
    return text


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
    role = db.Column(db.String(30), nullable=False, default="agente_back", index=True)
    is_active_user = db.Column(db.Boolean, default=True, index=True)
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
        return self.role in ("agente_back", "admin", "supervisor")

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
        return perm.can_resolve_cases if perm else (self.role == "agente_back")

    @property
    def can_reject_cases(self):
        if self.is_admin or self.is_supervisor:
            return True
        perm = self.permissions
        return perm.can_reject_cases if perm else (self.role == "agente_back")

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
        return perm.can_view_all_cases if perm else (self.role == "tyq")

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
        return perm.can_export_reports if perm else (self.role in ("tyq", "agente_back"))

    @property
    def can_manage_users(self):
        if self.is_admin or self.is_supervisor:
            return True
        perm = self.permissions
        return perm.can_manage_users if perm else False

    @property
    def can_manage_case_types(self):
        if self.is_admin or self.is_supervisor:
            return True
        perm = self.permissions
        return perm.can_manage_case_types if perm else False

    @property
    def role_label(self):
        labels = {
            "admin": "Administrador",
            "supervisor": "Supervisor",
            "agente_back": "Agente Back Office",
            "agente_front": "Agente Front",
            "tyq": "Calidad (TYQ)",
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
                db.session.flush()  # flush en vez de commit para no commitear cambios ajenos
            except Exception:
                db.session.rollback()
        return perm


class SheetConfig(db.Model):
    """Configuración de cada hoja del spreadsheet (Tipo de Caso)."""
    __tablename__ = "sheet_configs"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=True, index=True)  # Identificador inmutable
    sheet_name = db.Column(db.String(200), unique=True, nullable=False)
    display_name = db.Column(db.String(200), nullable=False)
    header_row = db.Column(db.Integer, default=1)  # En qué fila están los headers
    input_columns = db.Column(db.Text, nullable=False, default="")  # JSON: columnas de entrada
    output_columns = db.Column(db.Text, nullable=False, default="")  # JSON: columnas de gestión CRM
    color = db.Column(db.String(7), default="#6366f1")  # Color legacy
    is_active = db.Column(db.Boolean, default=True, index=True)
    description = db.Column(db.Text, default="")

    # Badge configurado (no hardcodeado)
    badge_label = db.Column(db.String(100), nullable=True)   # Texto del badge
    badge_bg = db.Column(db.String(9), nullable=True)         # Color de fondo hex
    badge_text_color = db.Column(db.String(9), nullable=True)  # Color de texto hex
    badge_css_class = db.Column(db.String(80), nullable=True)  # Clase CSS opcional

    # SLA y Prioridad (Estándar Wise CX / Salesforce)
    sla_hours = db.Column(db.Integer, default=48)             # Horas de resolución objetivo
    default_priority = db.Column(db.String(20), default="media")  # urgente, alta, media, baja

    cases = db.relationship("Case", backref="sheet_config", lazy="dynamic")

    @property
    def badge_style(self):
        """Retorna el dict de badge usando los campos configurados, con fallback robusto al color."""
        label = self.badge_label or self.display_name or "Tipología"
        bg = self.badge_bg or self.color or "#6366f1"
        if not isinstance(bg, str) or not bg.startswith("#") or len(bg) < 7:
            bg = "#6366f1"
        color = self.badge_text_color
        if not isinstance(color, str) or not color.startswith("#") or len(color) < 7:
            color = "#0f172a" if is_light_color(bg) else "#ffffff"
        css_class = self.badge_css_class or "badge-sheet-custom"
        return {"label": label, "bg": bg, "color": color, "css_class": css_class}

    @property
    def parsed_input_columns(self):
        try:
            return json.loads(self.input_columns or "[]")
        except Exception:
            return []

    @property
    def parsed_output_columns(self):
        try:
            return json.loads(self.output_columns or "[]")
        except Exception:
            return []


class Case(db.Model):
    """Un caso/ticket del CRM operativo."""
    __tablename__ = "cases"
    __table_args__ = (
        db.Index("idx_cases_assigned_status", "assigned_to", "status"),
        db.Index("idx_cases_created_status", "created_by", "status"),
        db.Index("idx_cases_sheet_status", "sheet_config_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sheet_config_id = db.Column(db.Integer, db.ForeignKey("sheet_configs.id"), nullable=False, index=True)
    row_number = db.Column(db.Integer, nullable=True)  # Fila en el sheet

    # ── Datos de entrada (vienen del webhook o cargados por Front) ──
    raw_data = db.Column(db.Text, nullable=False, default="{}")  # JSON con todos los campos de entrada

    # Campos clave extraídos e indexados para búsqueda global instantánea
    pedido_id = db.Column(db.String(100), nullable=True, index=True)
    caso_wise = db.Column(db.String(100), nullable=True, index=True)  # ID del caso en la plataforma Wise CX
    prioridad = db.Column(db.String(20), nullable=False, default="media", index=True)  # urgente | alta | media | baja
    sla_deadline = db.Column(db.DateTime, nullable=True, index=True)  # Fecha/hora límite de resolución SLA
    resolved_at = db.Column(db.DateTime, nullable=True, index=True)   # Fecha/hora en que fue resuelto/cerrado

    fecha = db.Column(db.String(50), nullable=True)
    solicitud = db.Column(db.String(300), nullable=True)
    tienda = db.Column(db.String(100), nullable=True)
    agente_front = db.Column(db.String(120), nullable=True)
    dni_cuit = db.Column(db.String(50), nullable=True, index=True)
    tracking = db.Column(db.String(100), nullable=True, index=True)
    nombre_cliente = db.Column(db.String(150), nullable=True)
    email_cliente = db.Column(db.String(150), nullable=True)
    codigo_sap = db.Column(db.String(100), nullable=True, index=True)
    caso_salesforce = db.Column(db.String(100), nullable=True, index=True)  # Alias legacy

    # ── Datos de gestión (columnas Back Office) ──
    output_data = db.Column(db.Text, nullable=False, default="{}")  # JSON con campos de salida

    # ── Estado del caso en el CRM ──
    # nuevo | en_proceso | reverificar | reenviado | resuelto | rechazado | cerrado
    status = db.Column(db.String(30), nullable=False, default="nuevo", index=True)

    # ── Circuito Front ⇄ Back Office ──
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    creator = db.relationship("User", foreign_keys=[created_by], backref="created_cases")

    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    assigned_user = db.relationship("User", foreign_keys=[assigned_to], backref="assigned_cases")

    # Motivos y comunicación
    motivo_rechazo = db.Column(db.Text, nullable=True)          # Indicado por Back Office al rechazar
    motivo_reverificacion = db.Column(db.Text, nullable=True)   # Nota de Back pidiendo a Front que chequee
    respuesta_front = db.Column(db.Text, nullable=True)         # Respuesta del Front al re-enviar el caso

    # ── Módulo TYQ (Training & Quality / Calidad) ──
    quality_score = db.Column(db.Integer, nullable=True, index=True)        # 0 a 100
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
                           onupdate=lambda: datetime.now(timezone.utc), index=True)

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
    @property
    def wise_ticket_id(self):
        """Retorna el ID de caso en Wise CX (o fallback a caso_salesforce si venía del modelo previo)."""
        return self.caso_wise or self.caso_salesforce or ""

    @property
    def priority_badge(self):
        """Badge de prioridad para visualización en tablas y cabeceras."""
        p = (self.prioridad or "media").lower()
        badges = {
            "urgente": {"label": "Urgente", "icon": "🔴", "color": "#ef4444", "bg": "rgba(239, 68, 68, 0.15)", "border": "rgba(239, 68, 68, 0.35)"},
            "alta": {"label": "Alta", "icon": "🟠", "color": "#f97316", "bg": "rgba(249, 115, 22, 0.15)", "border": "rgba(249, 115, 22, 0.35)"},
            "media": {"label": "Media", "icon": "🔵", "color": "#3b82f6", "bg": "rgba(59, 130, 246, 0.15)", "border": "rgba(59, 130, 246, 0.35)"},
            "baja": {"label": "Baja", "icon": "⚪", "color": "#94a3b8", "bg": "rgba(148, 163, 184, 0.12)", "border": "rgba(148, 163, 184, 0.25)"},
        }
        return badges.get(p, badges["media"])

    @property
    def sla_info(self):
        """Calcula el estado del SLA y tiempo restante o de atraso para Back Office."""
        if self.status in ("resuelto", "cerrado"):
            if self.sla_deadline and self.resolved_at:
                res_at = self.resolved_at if self.resolved_at.tzinfo else self.resolved_at.replace(tzinfo=timezone.utc)
                deadl = self.sla_deadline if self.sla_deadline.tzinfo else self.sla_deadline.replace(tzinfo=timezone.utc)
                if res_at <= deadl:
                    return {"status": "cumplido", "label": "A Tiempo", "color": "#10b981", "bg": "rgba(16, 185, 129, 0.15)", "icon": "✓", "text": "Resuelto a tiempo", "is_breached": False}
                else:
                    return {"status": "incumplido", "label": "Fuera de SLA", "color": "#ef4444", "bg": "rgba(239, 68, 68, 0.15)", "icon": "⚠️", "text": "Resuelto fuera de término", "is_breached": True}
            return {"status": "cumplido", "label": "Cerrado", "color": "#10b981", "bg": "rgba(16, 185, 129, 0.15)", "icon": "✓", "text": "Gestionado", "is_breached": False}

        if not self.sla_deadline:
            sla_h = (self.sheet_config.sla_hours if self.sheet_config and self.sheet_config.sla_hours else 48)
            base_created = self.created_at or datetime.now(timezone.utc)
            deadline = base_created + timedelta(hours=sla_h)
        else:
            deadline = self.sla_deadline

        now = datetime.now(timezone.utc)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        diff = deadline - now
        total_seconds = int(diff.total_seconds())

        if total_seconds < 0:
            abs_seconds = abs(total_seconds)
            h = abs_seconds // 3600
            m = (abs_seconds % 3600) // 60
            delay_str = f"{h}h {m}m" if h > 0 else f"{m}m"
            return {
                "status": "vencido",
                "label": "Vencido",
                "color": "#ef4444",
                "bg": "rgba(239, 68, 68, 0.15)",
                "icon": "🔴",
                "text": f"Vencido hace {delay_str}",
                "is_breached": True,
            }
        elif total_seconds <= 4 * 3600:
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            rem_str = f"{h}h {m}m" if h > 0 else f"{m}m"
            return {
                "status": "por_vencer",
                "label": "Por Vencer",
                "color": "#f59e0b",
                "bg": "rgba(245, 158, 11, 0.15)",
                "icon": "🟡",
                "text": f"Quedan {rem_str}",
                "is_breached": False,
            }
        else:
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            rem_str = f"{h}h {m}m" if h > 0 else f"{m}m"
            return {
                "status": "en_tiempo",
                "label": "En Tiempo",
                "color": "#10b981",
                "bg": "rgba(16, 185, 129, 0.15)",
                "icon": "🟢",
                "text": f"Restan {rem_str}",
                "is_breached": False,
            }

    @property
    def typology_badge(self):
        """Devuelve dict con label, bg, color y css_class delegando al sheet_config."""
        if self.sheet_config:
            return self.sheet_config.badge_style
        return {"label": self.solicitud or "General", "bg": "#6366f1", "color": "#ffffff", "css_class": "badge-sheet-custom"}

    @property
    def is_seguimiento_retiros(self):
        """Indica si el caso pertenece a la cola de Seguimiento de Retiros."""
        if self.sheet_config and self.sheet_config.slug:
            return self.sheet_config.slug == "seguimiento_retiros"
        name = (self.sheet_config.display_name if self.sheet_config else "").lower()
        return "seguimiento" in name and "retiro" in name

    @property
    def parsed_raw_data(self):
        """Dict parseado de raw_data con memoización en memoria por instancia."""
        if not hasattr(self, "_parsed_raw_cache") or getattr(self, "_parsed_raw_source", None) != self.raw_data:
            self._parsed_raw_cache = json.loads(self.raw_data) if self.raw_data else {}
            self._parsed_raw_source = self.raw_data
        return self._parsed_raw_cache

    @property
    def parsed_output_data(self):
        """Dict parseado de output_data con memoización en memoria por instancia."""
        if not hasattr(self, "_parsed_output_cache") or getattr(self, "_parsed_output_source", None) != self.output_data:
            self._parsed_output_cache = json.loads(self.output_data) if self.output_data else {}
            self._parsed_output_source = self.output_data
        return self._parsed_output_cache

    @property
    def tracking_data(self):
        """Retorna un dict con los datos combinados de output_data y raw_data memoizado."""
        source_tuple = (self.raw_data, self.output_data)
        if not hasattr(self, "_parsed_tracking_cache") or getattr(self, "_parsed_tracking_source", None) != source_tuple:
            self._parsed_tracking_cache = {**self.parsed_raw_data, **self.parsed_output_data}
            self._parsed_tracking_source = source_tuple
        return self._parsed_tracking_cache

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

    case = db.relationship("Case", backref=db.backref("events", lazy="dynamic", order_by="CaseEvent.created_at.desc()", cascade="all, delete-orphan"))
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


def ensure_database_schema(db_instance):
    """Crea columnas faltantes, migra roles legacy y crea índices adicionales."""
    with db_instance.engine.connect() as conn:
        # 1. Columnas faltantes en sheet_configs
        try:
            cols_result = conn.execute(db_instance.text("PRAGMA table_info(sheet_configs)"))
            existing_cols = {row[1] for row in cols_result.fetchall()}
            
            new_columns = [
                ("slug", "VARCHAR(100)"),
                ("badge_label", "VARCHAR(100)"),
                ("badge_bg", "VARCHAR(9)"),
                ("badge_text_color", "VARCHAR(9)"),
                ("badge_css_class", "VARCHAR(80)"),
                ("sla_hours", "INTEGER DEFAULT 48"),
                ("default_priority", "VARCHAR(20) DEFAULT 'media'"),
            ]
            for col_name, col_type in new_columns:
                if col_name not in existing_cols:
                    conn.execute(db_instance.text(f"ALTER TABLE sheet_configs ADD COLUMN {col_name} {col_type}"))
        except Exception:
            pass

        # 2. Columnas faltantes en cases (Wise CX & SLA Engine)
        try:
            case_cols_res = conn.execute(db_instance.text("PRAGMA table_info(cases)"))
            existing_case_cols = {row[1] for row in case_cols_res.fetchall()}

            new_case_columns = [
                ("caso_wise", "VARCHAR(100)"),
                ("prioridad", "VARCHAR(20) DEFAULT 'media'"),
                ("sla_deadline", "DATETIME"),
                ("resolved_at", "DATETIME"),
            ]
            for col_name, col_type in new_case_columns:
                if col_name not in existing_case_cols:
                    conn.execute(db_instance.text(f"ALTER TABLE cases ADD COLUMN {col_name} {col_type}"))
        except Exception:
            pass

        # 3. Migrar usuarios con rol legacy 'agent' a 'agente_back'
        try:
            conn.execute(db_instance.text("UPDATE users SET role = 'agente_back' WHERE role = 'agent'"))
        except Exception:
            pass

        # 4. Asignar slug a sheet_configs que no tengan slug y normalizar badges y SLAs
        try:
            configs = conn.execute(db_instance.text("SELECT id, display_name FROM sheet_configs WHERE slug IS NULL OR slug = ''")).fetchall()
            for row in configs:
                cid, dname = row[0], row[1]
                base_slug = slugify(dname or f"tipo_{cid}")
                conn.execute(db_instance.text("UPDATE sheet_configs SET slug = :slug WHERE id = :id"), {"slug": f"{base_slug}_{cid}", "id": cid})
            
            # Asegurar badge_bg, badge_label, badge_text_color y sla_hours
            conn.execute(db_instance.text("""
                UPDATE sheet_configs 
                SET badge_bg = CASE WHEN badge_bg IS NULL OR badge_bg = '' THEN COALESCE(color, '#6366f1') ELSE badge_bg END,
                    badge_label = CASE WHEN badge_label IS NULL OR badge_label = '' THEN display_name ELSE badge_label END,
                    color = CASE WHEN color IS NULL OR color = '' THEN '#6366f1' ELSE color END,
                    sla_hours = CASE WHEN sla_hours IS NULL OR sla_hours <= 0 THEN 48 ELSE sla_hours END,
                    default_priority = CASE WHEN default_priority IS NULL OR default_priority = '' THEN 'media' ELSE default_priority END
                WHERE badge_bg IS NULL OR badge_bg = '' OR badge_label IS NULL OR badge_label = '' OR color IS NULL OR color = '' OR sla_hours IS NULL OR default_priority IS NULL
            """))
            conn.execute(db_instance.text("""
                UPDATE sheet_configs 
                SET badge_text_color = '#ffffff'
                WHERE badge_text_color IS NULL OR badge_text_color = ''
            """))
        except Exception:
            pass

        # 5. Normalizar datos existentes en cases (caso_wise, prioridad, resolved_at, sla_deadline)
        try:
            conn.execute(db_instance.text("""
                UPDATE cases 
                SET caso_wise = caso_salesforce 
                WHERE (caso_wise IS NULL OR caso_wise = '') AND caso_salesforce IS NOT NULL AND caso_salesforce != ''
            """))
            conn.execute(db_instance.text("""
                UPDATE cases 
                SET prioridad = 'media' 
                WHERE prioridad IS NULL OR prioridad = ''
            """))
            conn.execute(db_instance.text("""
                UPDATE cases 
                SET resolved_at = updated_at 
                WHERE status IN ('resuelto', 'cerrado') AND resolved_at IS NULL
            """))
            conn.execute(db_instance.text("""
                UPDATE cases 
                SET sla_deadline = datetime(created_at, '+48 hours') 
                WHERE sla_deadline IS NULL AND created_at IS NOT NULL
            """))
        except Exception:
            pass

        # 6. Índices adicionales
        indexes = [
            ("idx_cases_updated_at", "cases", ["updated_at"]),
            ("idx_cases_pedido_id", "cases", ["pedido_id"]),
            ("idx_cases_caso_wise", "cases", ["caso_wise"]),
            ("idx_cases_prioridad", "cases", ["prioridad"]),
            ("idx_cases_sla_deadline", "cases", ["sla_deadline"]),
            ("idx_events_case_created", "case_events", ["case_id", "created_at"]),
            ("idx_sheet_configs_slug", "sheet_configs", ["slug"]),
        ]
        for idx_name, table_name, cols in indexes:
            cols_str = ", ".join(cols)
            sql = f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} ({cols_str})"
            try:
                conn.execute(db_instance.text(sql))
            except Exception:
                pass

        try:
            conn.commit()
        except Exception:
            pass


# Alias para retrocompatibilidad
ensure_database_indexes = ensure_database_schema

