"""API blueprint aggregation."""

from __future__ import annotations

from flask import Blueprint

from .accounts import bp as accounts_bp
from .auth import bp as auth_bp
from .budgets import bp as budgets_bp
from .categories import bp as categories_bp
from .exports import bp as exports_bp
from .health import bp as health_bp
from .imports import bp as imports_bp
from .stats import bp as stats_bp
from .transactions import bp as transactions_bp

api_bp = Blueprint("api", __name__)
api_bp.register_blueprint(health_bp)
api_bp.register_blueprint(auth_bp)
api_bp.register_blueprint(categories_bp)
api_bp.register_blueprint(accounts_bp)
api_bp.register_blueprint(transactions_bp)
api_bp.register_blueprint(stats_bp)
api_bp.register_blueprint(exports_bp)
api_bp.register_blueprint(imports_bp)
api_bp.register_blueprint(budgets_bp)

__all__ = ["api_bp"]
