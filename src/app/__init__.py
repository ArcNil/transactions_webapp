from flask import Flask, request as flask_request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, user_logged_in, user_logged_out
from flask_wtf.csrf import CSRFProtect
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.jinja_env.globals["web_app_title"] = os.environ.get("WEB_APP_TITLE", "WebApp Title")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "warning"

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.routes.auth import bp as auth_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.pos import bp as pos_bp
    from app.routes.products import bp as products_bp
    from app.routes.customers import bp as customers_bp
    from app.routes.transactions import bp as transactions_bp
    from app.routes.settings import bp as settings_bp
    from app.routes.monitoring import bp as monitoring_bp
    from app.routes.vendors import bp as vendors_bp
    from app.routes.restock import bp as restock_bp
    from app.routes.stock import bp as stock_bp
    from app.routes.finance import bp as finance_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(vendors_bp)
    app.register_blueprint(restock_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(finance_bp)

    # ── Monitoring hooks ──────────────────────────────────────────────────────
    from app.utils.monitor import record_request, session_opened, session_closed

    @app.after_request
    def _log_request(response):
        # Skip static assets and the SSE stream endpoint itself
        if not flask_request.path.startswith("/static") and flask_request.path != "/monitoring/stream":
            from flask_login import current_user
            uid = current_user.id if current_user.is_authenticated else None
            uname = current_user.username if current_user.is_authenticated else None
            record_request(
                ip=flask_request.remote_addr,
                method=flask_request.method,
                path=flask_request.path,
                user_id=uid,
                username=uname,
                status_code=response.status_code,
            )
        return response

    @user_logged_in.connect_via(app)
    def _on_login(sender, user, **extra):
        session_opened(user.id, user.username, flask_request.remote_addr)

    @user_logged_out.connect_via(app)
    def _on_logout(sender, user, **extra):
        session_closed(user.id)

    return app
