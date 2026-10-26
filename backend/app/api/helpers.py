"""Small helpers shared by the CRUD endpoints."""

from __future__ import annotations

from typing import Any

from flask import request
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from ..errors_types import ApiError, Conflict, NotFound
from ..extensions import db
from ..models import Account, Category, Transaction


def json_body() -> Any:
    payload = request.get_json(silent=True)
    if payload is None:
        raise ApiError("请求体必须是 JSON", code="invalid_body", status=400)
    return payload


def commit(message: str) -> None:
    """Commit, translating unique/foreign-key violations into HTTP 409."""
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise Conflict(message) from exc


def current_user_id() -> int:
    return int(current_user.id)  # type: ignore[arg-type]


def get_category(category_id: int) -> Category:
    category = db.session.get(Category, category_id)
    if category is None or category.user_id != current_user_id():
        raise NotFound("分类不存在")
    return category


def get_account(account_id: int | None) -> Account | None:
    if account_id is None:
        return None
    account = db.session.get(Account, account_id)
    if account is None or account.user_id != current_user_id():
        raise NotFound("账户不存在")
    return account


def get_transaction(transaction_id: int) -> Transaction:
    transaction = db.session.get(Transaction, transaction_id)
    if (
        transaction is None
        or transaction.user_id != current_user_id()
        or transaction.deleted_at is not None
    ):
        raise NotFound("流水不存在")
    return transaction
