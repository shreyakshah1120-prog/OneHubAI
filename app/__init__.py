"""App factory + extension setup."""
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .extensions import db
from .models import User

load_dotenv()

login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["600 per hour"])


def create_app() -> Flask:
    base_dir = Path(__file__).resolve().parent
    instance_dir = base_dir.parent / "instance"
    instance_dir.mkdir(exist_ok=True)

    app = Flask(
        __name__,
        instance_path=str(instance_dir),
        static_folder="static",
        template_folder="templates",
    )

    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-change-me"),
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL", f"sqlite:///{instance_dir / 'onehubai.db'}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=64 * 1024 * 1024,  # 64MB upload cap
        UPLOAD_FOLDER=str(base_dir / "static" / "uploads"),
        GENERATED_FOLDER=str(base_dir / "static" / "generated"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["GENERATED_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from .routes.main import bp as main_bp
    from .routes.auth import bp as auth_bp
    from .routes.dashboard import bp as dashboard_bp
    from .routes.ai_studio import bp as ai_studio_bp
    from .routes.image import bp as image_bp
    from .routes.voice import bp as voice_bp
    from .routes.interview import bp as interview_bp
    from .routes.debate import bp as debate_bp
    from .routes.study import bp as study_bp
    from .routes.health import bp as health_bp
    from .routes.history import bp as history_bp
    from .routes.settings import bp as settings_bp
    from .routes.notifications import bp as notifications_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/app")
    app.register_blueprint(ai_studio_bp, url_prefix="/app/studio")
    app.register_blueprint(image_bp, url_prefix="/app/image")
    app.register_blueprint(voice_bp, url_prefix="/app/voice")
    app.register_blueprint(interview_bp, url_prefix="/app/interview")
    app.register_blueprint(debate_bp, url_prefix="/app/debate")
    app.register_blueprint(study_bp, url_prefix="/app/study")
    app.register_blueprint(health_bp, url_prefix="/app/health")
    app.register_blueprint(history_bp, url_prefix="/app/history")
    app.register_blueprint(settings_bp, url_prefix="/app/settings")
    app.register_blueprint(notifications_bp, url_prefix="/app/notifications")

    @app.context_processor
    def inject_globals():
        return {
            "current_year": datetime.utcnow().year,
            "brand_name": "OneHubAI",
        }

    with app.app_context():
        db.create_all()

    return app
