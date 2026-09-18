from flask import Flask, request
from flask_login import LoginManager
from config import Config
from models import db, User, ensure_database_indexes


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── Configuración de caché para assets estáticos (12 horas) ──
    app.config.setdefault("SEND_FILE_MAX_AGE_DEFAULT", 43200)

    # ── Inicializar extensiones ──
    db.init_app(app)
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Iniciá sesión para acceder al CRM."
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ── Registrar blueprints ──
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.admin import admin_bp
    from routes.webhook import webhook_bp
    from routes.front import front_bp
    from routes.quality import quality_bp
    from routes.reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(webhook_bp, url_prefix="/webhook")
    app.register_blueprint(front_bp)
    app.register_blueprint(quality_bp)
    app.register_blueprint(reports_bp)

    # ── Context Processor Global ──
    @app.context_processor
    def inject_global_stats():
        if request.endpoint == "static":
            return {"my_assigned_cases_count": 0}
        from flask_login import current_user
        from models import Case
        if current_user.is_authenticated:
            if current_user.is_front_office and not current_user.is_back_office:
                assigned_count = Case.query.filter(
                    db.or_(Case.assigned_to == current_user.id, Case.created_by == current_user.id),
                    Case.status.in_(["nuevo", "en_proceso", "reverificar", "reenviado"])
                ).count()
            else:
                assigned_count = Case.query.filter(
                    Case.assigned_to == current_user.id,
                    Case.status.in_(["nuevo", "en_proceso", "reverificar", "reenviado"])
                ).count()
            return {"my_assigned_cases_count": assigned_count}
        return {"my_assigned_cases_count": 0}

    # ── Crear tablas, índices y auto-inicializar usuarios base si la BD es nueva ──
    with app.app_context():
        db.create_all()
        ensure_database_indexes(db)
        # Solo ejecutar seed si la base de datos es nueva (no existe admin aún)
        if not User.query.filter_by(username="admin").first():
            try:
                from seed import run_seed
                run_seed()
            except Exception as e:
                app.logger.warning(f"Auto-seed warning: {e}")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
