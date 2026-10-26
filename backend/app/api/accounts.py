"""Payment account CRUD."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy import func, select

from ..errors_types import Conflict
from ..extensions import db
from ..models import Account, Transaction
from ..money import to_cents
from ..schemas import AccountCreate, AccountUpdate, parse_payload
from .helpers import commit, current_user_id, get_account, json_body

bp = Blueprint("accounts", __name__, url_prefix="/accounts")


@bp.get("")
@login_required
def list_accounts():
    include_inactive = request.args.get("include_inactive") == "true"
    conditions = [Account.user_id == current_user_id()]
    if not include_inactive:
        conditions.append(Account.is_active.is_(True))

    rows = db.session.scalars(
        select(Account).where(*conditions).order_by(Account.sort_order, Account.id)
    ).all()
    return jsonify({"items": [account.to_dict() for account in rows]})


@bp.post("")
@login_required
def create_account():
    payload = parse_payload(AccountCreate, json_body())
    account = Account(
        user_id=current_user_id(),
        name=payload.name,
        type=payload.type,
        initial_balance_cents=(
            to_cents(payload.initial_balance) if payload.initial_balance is not None else 0
        ),
        sort_order=payload.sort_order,
    )
    db.session.add(account)
    commit("账户名称重复")
    return jsonify({"account": account.to_dict()}), 201


@bp.put("/<int:account_id>")
@login_required
def update_account(account_id: int):
    account = get_account(account_id)
    payload = parse_payload(AccountUpdate, json_body())
    data = payload.model_dump(exclude_unset=True)

    if "initial_balance" in data and data["initial_balance"] is not None:
        account.initial_balance_cents = to_cents(data.pop("initial_balance"))
    else:
        data.pop("initial_balance", None)

    for field, value in data.items():
        setattr(account, field, value)
    commit("账户名称重复")
    return jsonify({"account": account.to_dict()})


@bp.delete("/<int:account_id>")
@login_required
def delete_account(account_id: int):
    account = get_account(account_id)
    used = db.session.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.account_id == account.id,
            Transaction.deleted_at.is_(None),
        )
    )
    if used:
        raise Conflict(f"该账户下还有 {used} 条流水，删除前请先转移它们")

    db.session.delete(account)
    db.session.commit()
    return "", 204
