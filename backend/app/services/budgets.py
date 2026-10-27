"""Monthly budgets: storage helpers plus the "how much is left" projection."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select

from ..extensions import db
from ..models import Budget, Transaction
from ..money import from_cents
from ..utils.time import month_start


def normalise_month(value: date) -> date:
    return month_start(value)


def month_range(month: date) -> tuple[date, date]:
    """First and last day of the month containing ``month``."""
    first = month_start(month)
    next_first = date(first.year + (first.month // 12), first.month % 12 + 1, 1)
    return first, next_first - timedelta(days=1)


def month_key(month: date) -> str:
    return f"{month.year:04d}-{month.month:02d}"


def _progress(budget: Budget, spent_cents: int) -> dict:
    amount = budget.amount_cents
    remaining = amount - spent_cents
    percent = round(spent_cents / amount * 100, 1) if amount else 0.0
    return {
        **budget.to_dict(),
        "spent": from_cents(spent_cents),
        "remaining": from_cents(remaining),
        "percent": percent,
        "over": remaining < 0,
    }


def spent_by_category(user_id: int, month: date) -> dict[int, int]:
    """Expense totals per category for the month, in cents."""
    start, end = month_range(month)
    rows = db.session.execute(
        select(
            Transaction.category_id,
            func.coalesce(func.sum(Transaction.amount_cents), 0),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            Transaction.direction == "out",
            Transaction.biz_date >= start,
            Transaction.biz_date <= end,
        )
        .group_by(Transaction.category_id)
    ).all()
    return {category_id: int(total) for category_id, total in rows}


def status(user_id: int, month: date) -> dict:
    """Budget progress for one month: the overall cap plus per-category caps."""
    month = normalise_month(month)
    budgets = db.session.scalars(
        select(Budget)
        .where(Budget.user_id == user_id, Budget.month == month)
        .order_by(Budget.id)
    ).all()

    spent_map = spent_by_category(user_id, month)
    total_spent = sum(spent_map.values())

    total = None
    categories: list[dict] = []
    for budget in budgets:
        if budget.category_id is None:
            total = _progress(budget, total_spent)
        else:
            categories.append(_progress(budget, spent_map.get(budget.category_id, 0)))

    categories.sort(key=lambda item: item["percent"], reverse=True)

    return {
        "month": month_key(month),
        "spent": from_cents(total_spent),
        "total": total,
        "categories": categories,
        "has_budget": bool(total or categories),
        "over_budget": bool(total and total["over"]) or any(item["over"] for item in categories),
    }


def upsert(user_id: int, month: date, category_id: int | None, amount_cents: int) -> Budget:
    """Create or update the budget for ``(month, category_id)``.

    ``category_id IS NULL`` means the overall monthly cap.  SQLite and Oracle
    both treat NULLs as distinct in a unique constraint, so the duplicate check
    is done here rather than relying on the index.
    """
    month = normalise_month(month)
    query = select(Budget).where(Budget.user_id == user_id, Budget.month == month)
    if category_id is None:
        query = query.where(Budget.category_id.is_(None))
    else:
        query = query.where(Budget.category_id == category_id)

    budget = db.session.scalars(query).first()
    if budget is None:
        budget = Budget(
            user_id=user_id,
            month=month,
            category_id=category_id,
            amount_cents=amount_cents,
        )
        db.session.add(budget)
    else:
        budget.amount_cents = amount_cents
    db.session.commit()
    return budget
