"""Budget endpoints."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from flask_login import login_required

from ..errors_types import NotFound, ValidationFailed
from ..extensions import db
from ..models import Budget
from ..money import to_cents
from ..schemas import BudgetUpsert, parse_payload
from ..services import budgets as budget_service
from ..utils.time import today_local
from .helpers import current_user_id, get_category, json_body

bp = Blueprint("budgets", __name__, url_prefix="/budgets")


def _month_arg() -> date:
    raw = request.args.get("month")
    if not raw:
        return today_local()
    try:
        if len(raw) == 7:
            return date.fromisoformat(f"{raw}-01")
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationFailed(
            [{"loc": ["month"], "msg": "月份格式应为 YYYY-MM", "type": "value_error"}]
        ) from exc


@bp.get("")
@login_required
def status():
    return jsonify(budget_service.status(current_user_id(), _month_arg()))


@bp.put("")
@login_required
def upsert_budget():
    payload = parse_payload(BudgetUpsert, json_body())
    if payload.category_id is not None:
        get_category(payload.category_id)  # ownership check -> 404 for strangers

    budget = budget_service.upsert(
        current_user_id(),
        payload.month,
        payload.category_id,
        to_cents(payload.amount),
    )
    return jsonify(
        {
            "budget": budget.to_dict(),
            "status": budget_service.status(current_user_id(), payload.month),
        }
    )


@bp.delete("/<int:budget_id>")
@login_required
def delete_budget(budget_id: int):
    budget = db.session.get(Budget, budget_id)
    if budget is None or budget.user_id != current_user_id():
        raise NotFound("预算不存在")
    db.session.delete(budget)
    db.session.commit()
    return "", 204
