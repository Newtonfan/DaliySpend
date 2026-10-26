"""Dashboard aggregation endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from ..schemas import StatsQuery, parse_query
from ..services import stats as stats_service
from .helpers import current_user_id

bp = Blueprint("stats", __name__, url_prefix="/stats")


def _query() -> StatsQuery:
    return parse_query(StatsQuery, request.args)


@bp.get("/summary")
@login_required
def summary():
    query = _query()
    date_from, date_to = stats_service.resolve_range(query.date_from, query.date_to)
    return jsonify(stats_service.summary(current_user_id(), date_from, date_to))


@bp.get("/daily")
@login_required
def daily():
    query = _query()
    date_from, date_to = stats_service.resolve_range(query.date_from, query.date_to)
    return jsonify({"items": stats_service.daily(current_user_id(), date_from, date_to)})


@bp.get("/by-category")
@login_required
def by_category():
    query = _query()
    date_from, date_to = stats_service.resolve_range(query.date_from, query.date_to)
    return jsonify(
        {
            "items": stats_service.by_category(
                current_user_id(), date_from, date_to, query.direction or "out"
            )
        }
    )


@bp.get("/by-account")
@login_required
def by_account():
    query = _query()
    date_from, date_to = stats_service.resolve_range(query.date_from, query.date_to)
    return jsonify(
        {
            "items": stats_service.by_account(
                current_user_id(), date_from, date_to, query.direction or "out"
            )
        }
    )


@bp.get("/monthly")
@login_required
def monthly():
    query = _query()
    return jsonify({"items": stats_service.monthly(current_user_id(), query.months)})


@bp.get("/dashboard")
@login_required
def dashboard():
    """Everything the first screen needs, in a single round trip."""
    query = _query()
    user_id = current_user_id()
    date_from, date_to = stats_service.resolve_range(query.date_from, query.date_to)
    direction = query.direction or "out"

    return jsonify(
        {
            "summary": stats_service.summary(user_id, date_from, date_to),
            "daily": stats_service.daily(user_id, date_from, date_to),
            "by_category": stats_service.by_category(user_id, date_from, date_to, direction),
            "by_account": stats_service.by_account(user_id, date_from, date_to, direction),
            "monthly": stats_service.monthly(user_id, query.months),
        }
    )
