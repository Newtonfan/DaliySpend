"""Category CRUD."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy import func, select

from ..errors_types import Conflict
from ..extensions import db
from ..models import Category, Transaction
from ..schemas import CategoryCreate, CategoryUpdate, parse_payload
from .helpers import commit, current_user_id, get_category, json_body

bp = Blueprint("categories", __name__, url_prefix="/categories")


@bp.get("")
@login_required
def list_categories():
    kind = request.args.get("kind")
    include_inactive = request.args.get("include_inactive") == "true"

    conditions = [Category.user_id == current_user_id()]
    if kind in ("expense", "income"):
        conditions.append(Category.kind == kind)
    if not include_inactive:
        conditions.append(Category.is_active.is_(True))

    rows = db.session.scalars(
        select(Category)
        .where(*conditions)
        .order_by(Category.kind, Category.sort_order, Category.id)
    ).all()
    return jsonify({"items": [category.to_dict() for category in rows]})


@bp.post("")
@login_required
def create_category():
    payload = parse_payload(CategoryCreate, json_body())
    category = Category(
        user_id=current_user_id(),
        name=payload.name,
        kind=payload.kind,
        icon=payload.icon,
        color=payload.color,
        sort_order=payload.sort_order,
    )
    db.session.add(category)
    commit("同类型下已存在同名分类")
    return jsonify({"category": category.to_dict()}), 201


@bp.put("/<int:category_id>")
@login_required
def update_category(category_id: int):
    category = get_category(category_id)
    payload = parse_payload(CategoryUpdate, json_body())
    data = payload.model_dump(exclude_unset=True)

    for field, value in data.items():
        setattr(category, field, value)
    commit("同类型下已存在同名分类")
    return jsonify({"category": category.to_dict()})


@bp.delete("/<int:category_id>")
@login_required
def delete_category(category_id: int):
    category = get_category(category_id)
    used = db.session.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.category_id == category.id,
            Transaction.deleted_at.is_(None),
        )
    )
    if used:
        raise Conflict(f"该分类下还有 {used} 条流水，删除前请先转移它们")

    db.session.delete(category)
    db.session.commit()
    return "", 204
