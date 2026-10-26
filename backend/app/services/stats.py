"""Aggregation queries behind the dashboard.

All grouping happens on plain date/integer columns so the same SQL runs on
SQLite today and on Oracle later (no ``strftime``/``to_char``).
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Sequence

from sqlalchemy import func, select

from ..errors_types import ValidationFailed
from ..extensions import db
from ..models import Account, Category, Transaction
from ..money import from_cents
from ..utils.time import add_months, month_start, today_local

MAX_DAILY_POINTS = 400
MAX_MONTHLY_POINTS = 36


def _conditions(user_id: int, date_from: date, date_to: date) -> list:
    return [
        Transaction.user_id == user_id,
        Transaction.deleted_at.is_(None),
        Transaction.biz_date >= date_from,
        Transaction.biz_date <= date_to,
    ]


def resolve_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = today_local()
    end = date_to or today
    start = date_from or month_start(end)
    if start > end:
        raise ValidationFailed(
            [{"loc": ["date_from"], "msg": "开始日期不能晚于结束日期", "type": "value_error"}]
        )
    return start, end


def summary(user_id: int, date_from: date, date_to: date) -> dict:
    rows = db.session.execute(
        select(
            Transaction.direction,
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount_cents), 0),
        )
        .where(*_conditions(user_id, date_from, date_to))
        .group_by(Transaction.direction)
    ).all()

    totals = {"out": (0, 0), "in": (0, 0)}
    for direction, count, amount in rows:
        totals[direction] = (int(count), int(amount))

    expense_count, expense_cents = totals["out"]
    income_count, income_cents = totals["in"]

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "expense": {"amount": from_cents(expense_cents), "count": expense_count},
        "income": {"amount": from_cents(income_cents), "count": income_count},
        "net": from_cents(income_cents - expense_cents),
        "count": expense_count + income_count,
        "average_expense": (
            from_cents(expense_cents // expense_count) if expense_count else "0.00"
        ),
    }


def _daily_rows(user_id: int, date_from: date, date_to: date) -> Sequence:
    return db.session.execute(
        select(
            Transaction.biz_date,
            Transaction.direction,
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount_cents), 0),
        )
        .where(*_conditions(user_id, date_from, date_to))
        .group_by(Transaction.biz_date, Transaction.direction)
        .order_by(Transaction.biz_date)
    ).all()


def daily(user_id: int, date_from: date, date_to: date) -> list[dict]:
    span = (date_to - date_from).days + 1
    if span > MAX_DAILY_POINTS:
        raise ValidationFailed(
            [
                {
                    "loc": ["date_to"],
                    "msg": f"日趋势最多查询 {MAX_DAILY_POINTS} 天，请缩小范围",
                    "type": "value_error",
                }
            ]
        )

    buckets: OrderedDict[date, dict[str, int]] = OrderedDict()
    cursor = date_from
    while cursor <= date_to:
        buckets[cursor] = {"out": 0, "in": 0}
        cursor += timedelta(days=1)

    for biz_date, direction, _count, amount in _daily_rows(user_id, date_from, date_to):
        buckets.setdefault(biz_date, {"out": 0, "in": 0})[direction] = int(amount)

    return [
        {
            "date": day.isoformat(),
            "expense": from_cents(values["out"]),
            "income": from_cents(values["in"]),
        }
        for day, values in buckets.items()
    ]


def by_category(user_id: int, date_from: date, date_to: date, direction: str) -> list[dict]:
    rows = db.session.execute(
        select(
            Category.id,
            Category.name,
            Category.icon,
            Category.color,
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount_cents), 0),
        )
        .select_from(Transaction)
        .join(Category, Transaction.category_id == Category.id)
        .where(*_conditions(user_id, date_from, date_to), Transaction.direction == direction)
        .group_by(Category.id, Category.name, Category.icon, Category.color)
        .order_by(func.sum(Transaction.amount_cents).desc())
    ).all()

    total = sum(int(row[5]) for row in rows)
    items = []
    for category_id, name, icon, color, count, amount_cents in rows:
        share = (Decimal(amount_cents) / Decimal(total)) if total else Decimal(0)
        items.append(
            {
                "category_id": category_id,
                "name": name,
                "icon": icon,
                "color": color,
                "amount": from_cents(int(amount_cents)),
                "count": int(count),
                "share": float(round(share, 4)),
            }
        )
    return items


def by_account(user_id: int, date_from: date, date_to: date, direction: str) -> list[dict]:
    rows = db.session.execute(
        select(
            Account.id,
            Account.name,
            Account.type,
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount_cents), 0),
        )
        .select_from(Transaction)
        .outerjoin(Account, Transaction.account_id == Account.id)
        .where(*_conditions(user_id, date_from, date_to), Transaction.direction == direction)
        .group_by(Account.id, Account.name, Account.type)
        .order_by(func.sum(Transaction.amount_cents).desc())
    ).all()

    total = sum(int(row[4]) for row in rows)
    items = []
    for account_id, name, account_type, count, amount_cents in rows:
        share = (Decimal(amount_cents) / Decimal(total)) if total else Decimal(0)
        items.append(
            {
                "account_id": account_id,
                "name": name or "未指定账户",
                "type": account_type,
                "amount": from_cents(int(amount_cents)),
                "count": int(count),
                "share": float(round(share, 4)),
            }
        )
    return items


def monthly(user_id: int, months: int) -> list[dict]:
    months = max(1, min(months, MAX_MONTHLY_POINTS))
    today = today_local()
    first_month = month_start(today)
    start = add_months(first_month, -(months - 1))
    end = today

    buckets: OrderedDict[str, dict[str, int]] = OrderedDict()
    cursor = start
    while cursor <= end:
        buckets[f"{cursor.year:04d}-{cursor.month:02d}"] = {"out": 0, "in": 0}
        cursor = add_months(month_start(cursor), 1)

    for biz_date, direction, _count, amount in _daily_rows(user_id, start, end):
        key = f"{biz_date.year:04d}-{biz_date.month:02d}"
        buckets.setdefault(key, {"out": 0, "in": 0})[direction] += int(amount)

    return [
        {
            "month": key,
            "expense": from_cents(values["out"]),
            "income": from_cents(values["in"]),
        }
        for key, values in buckets.items()
    ]


def iter_export_rows(user_id: int, date_from: date, date_to: date) -> Iterable[list[str]]:
    rows = db.session.scalars(
        select(Transaction)
        .where(*_conditions(user_id, date_from, date_to))
        .order_by(Transaction.biz_date, Transaction.id)
    ).unique().all()

    for transaction in rows:
        yield [
            transaction.biz_date.isoformat(),
            "支出" if transaction.direction == "out" else "收入",
            transaction.category.name if transaction.category else "",
            transaction.account.name if transaction.account else "",
            from_cents(transaction.amount_cents),
            transaction.payee or "",
            (transaction.note or "").replace("\n", " "),
        ]
