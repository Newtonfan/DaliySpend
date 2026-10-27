"""Transaction (expense / income) CRUD with filtering and pagination."""

from __future__ import annotations

from datetime import datetime
from math import ceil

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import Transaction
from ..money import to_cents
from ..schemas import TransactionCreate, TransactionQuery, TransactionUpdate, parse_payload, parse_query
from ..utils.time import now_local, today_local
from .helpers import (
    blank_to_none,
    commit,
    current_user_id,
    get_account,
    get_category,
    get_transaction,
    json_body,
)

bp = Blueprint("transactions", __name__, url_prefix="/transactions")

ORDERINGS = {
    "date_desc": (Transaction.biz_date.desc(), Transaction.id.desc()),
    "date_asc": (Transaction.biz_date.asc(), Transaction.id.asc()),
    "amount_desc": (Transaction.amount_cents.desc(), Transaction.id.desc()),
    "amount_asc": (Transaction.amount_cents.asc(), Transaction.id.asc()),
}


def _conditions(query: TransactionQuery) -> list:
    conditions = [
        Transaction.user_id == current_user_id(),
        Transaction.deleted_at.is_(None),
    ]
    if query.date_from:
        conditions.append(Transaction.biz_date >= query.date_from)
    if query.date_to:
        conditions.append(Transaction.biz_date <= query.date_to)
    if query.category_id:
        conditions.append(Transaction.category_id == query.category_id)
    if query.account_id:
        conditions.append(Transaction.account_id == query.account_id)
    if query.direction:
        conditions.append(Transaction.direction == query.direction)
    if query.source:
        conditions.append(Transaction.source == query.source)
    if query.q:
        needle = f"%{query.q}%"
        conditions.append(or_(Transaction.payee.ilike(needle), Transaction.note.ilike(needle)))
    return conditions


@bp.get("")
@login_required
def list_transactions():
    query = parse_query(TransactionQuery, request.args)
    conditions = _conditions(query)

    total = db.session.scalar(
        select(func.count(Transaction.id)).where(*conditions)
    ) or 0

    rows = db.session.scalars(
        select(Transaction)
        .where(*conditions)
        .order_by(*ORDERINGS[query.sort])
        .limit(query.page_size)
        .offset((query.page - 1) * query.page_size)
    ).unique().all()

    return jsonify(
        {
            "items": [transaction.to_dict() for transaction in rows],
            "page": query.page,
            "page_size": query.page_size,
            "total": total,
            "total_pages": ceil(total / query.page_size) if total else 0,
        }
    )


@bp.get("/<int:transaction_id>")
@login_required
def get_one(transaction_id: int):
    return jsonify({"transaction": get_transaction(transaction_id).to_dict()})


@bp.post("")
@login_required
def create_transaction():
    payload = parse_payload(TransactionCreate, json_body())
    category = get_category(payload.category_id)
    account = get_account(payload.account_id)

    biz_date = payload.biz_date
    if biz_date is None and payload.occurred_at is not None:
        biz_date = payload.occurred_at.date()
    if biz_date is None:
        biz_date = today_local()

    occurred_at = payload.occurred_at
    if occurred_at is None:
        occurred_at = datetime.combine(biz_date, now_local().time().replace(microsecond=0))

    transaction = Transaction(
        user_id=current_user_id(),
        biz_date=biz_date,
        occurred_at=occurred_at,
        amount_cents=to_cents(payload.amount),
        direction="in" if category.kind == "income" else "out",
        category_id=category.id,
        account_id=account.id if account else None,
        payee=blank_to_none(payload.payee),
        note=blank_to_none(payload.note),
    )
    db.session.add(transaction)
    commit("流水保存失败")
    return jsonify({"transaction": transaction.to_dict()}), 201


@bp.put("/<int:transaction_id>")
@login_required
def update_transaction(transaction_id: int):
    transaction = get_transaction(transaction_id)
    payload = parse_payload(TransactionUpdate, json_body())
    data = payload.model_dump(exclude_unset=True)

    if "category_id" in data and data["category_id"] is not None:
        category = get_category(data.pop("category_id"))
        transaction.category_id = category.id
        transaction.direction = "in" if category.kind == "income" else "out"
    else:
        data.pop("category_id", None)

    if "account_id" in data:
        account = get_account(data.pop("account_id"))
        transaction.account_id = account.id if account else None

    if "amount" in data and data["amount"] is not None:
        transaction.amount_cents = to_cents(data.pop("amount"))
    else:
        data.pop("amount", None)

    if data.get("biz_date") is not None:
        transaction.biz_date = data.pop("biz_date")
        if "occurred_at" not in data:
            transaction.occurred_at = datetime.combine(
                transaction.biz_date, transaction.occurred_at.time().replace(microsecond=0)
            )
    else:
        data.pop("biz_date", None)

    if data.get("occurred_at") is not None:
        transaction.occurred_at = data.pop("occurred_at")
        if "biz_date" not in payload.model_fields_set:
            transaction.biz_date = transaction.occurred_at.date()
    else:
        data.pop("occurred_at", None)

    if "payee" in data:
        transaction.payee = blank_to_none(data.pop("payee"))
    if "note" in data:
        transaction.note = blank_to_none(data.pop("note"))

    commit("流水保存失败")
    return jsonify({"transaction": transaction.to_dict()})


@bp.delete("/<int:transaction_id>")
@login_required
def delete_transaction(transaction_id: int):
    transaction = get_transaction(transaction_id)
    transaction.deleted_at = now_local()
    db.session.commit()
    return "", 204

