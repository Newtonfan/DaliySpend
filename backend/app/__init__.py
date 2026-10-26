"""Application factory."""

from __future__ import annotations

from datetime import timedelta

from flask import Flask

from . import db as _db_module  # noqa: F401  (registers the SQLite pragma listener)
from .config import INSTANCE_DIR, get_settings
from .errors import json_error, register_error_handlers
from .extensions import csrf, db, login_manager, migrate


def create_app(test_config: dict | None = None) -> Flask:
    settings = get_settings()
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.secret_key,
        SQLALCHEMY_DATABASE_URI=settings.resolve_database_url(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.session_cookie_secure,
        PERMANENT_SESSION_LIFETIME=timedelta(days=settings.session_lifetime_days),
        WTF_CSRF_TIME_LIMIT=None,
        WTF_CSRF_HEADERS=["X-CSRFToken", "X-CSRF-Token"],
        APP_SETTINGS=settings,
    )
    if test_config:
        app.config.update(test_config)

    app.json.sort_keys = False

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.session_protection = "strong"

    @login_manager.unauthorized_handler
    def _unauthorized():
        return json_error("unauthorized", "请先登录", 401)

    @login_manager.user_loader
    def _load_user(user_id: str):
        from .models import User

        if not str(user_id).isdigit():
            return None
        return db.session.get(User, int(user_id))

    from .api import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    register_error_handlers(app)

    from .cli import register_cli

    register_cli(app)

    return app
