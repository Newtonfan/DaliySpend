"""Liveness/readiness probe."""

from __future__ import annotations

import sqlalchemy
from flask import Blueprint, current_app, jsonify

from ..db import check_database_connection

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    database_ok = True
    error: str | None = None
    try:
        check_database_connection()
    except sqlalchemy.exc.SQLAlchemyError as exc:  # pragma: no cover - needs a broken DB
        database_ok = False
        error = str(exc.__class__.__name__)

    payload = {
        "status": "ok" if database_ok else "degraded",
        "database": database_ok,
        "app": current_app.config["APP_SETTINGS"].app_name,
    }
    if error:
        payload["error"] = error
    return jsonify(payload), (200 if database_ok else 503)
