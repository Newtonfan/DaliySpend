"""Flask extension singletons, bound to the app inside :func:`create_app`."""

from __future__ import annotations

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

__all__ = ["db", "migrate", "login_manager", "csrf"]
