"""API blueprint aggregation."""

from __future__ import annotations

from flask import Blueprint

from .auth import bp as auth_bp
from .health import bp as health_bp

api_bp = Blueprint("api", __name__)
api_bp.register_blueprint(health_bp)
api_bp.register_blueprint(auth_bp)

__all__ = ["api_bp"]
