"""Recycle bin for soft-deleted transactions."""

from __future__ import annotations

from datetime import date

from app.extensions import db
from app.models import Category, Transaction
from app.utils.time import now_local


def test_trash_lists_only_deleted_rows(auth_client, user, expense_category, make_transaction):
    kept = make_transaction(user, category=expense_category, amount="10.00", payee="保留")
    removed = make_transaction(user, category=expense_category, amount="20.00", payee="删掉")
    removed.deleted_at = removed.created_at
    db.session.commit()

    payload = auth_client.get("/api/transactions/trash").get_json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == removed.id
    assert payload["items"][0]["deleted_at"] is not None
    assert payload["items"][0]["payee"] == "删掉"

    active = auth_client.get("/api/transactions").get_json()
    assert active["total"] == 1
    assert active["items"][0]["id"] == kept.id


def test_restore_puts_the_row_back(auth_client, user, expense_category, make_transaction):
    transaction = make_transaction(user, category=expense_category, amount="30.00")
    assert auth_client.delete(f"/api/transactions/{transaction.id}").status_code == 204
    assert auth_client.get("/api/transactions").get_json()["total"] == 0

    restored = auth_client.post(f"/api/transactions/{transaction.id}/restore")
    assert restored.status_code == 200
    assert restored.get_json()["transaction"]["deleted_at"] is None

    assert auth_client.get("/api/transactions").get_json()["total"] == 1
    assert auth_client.get("/api/transactions/trash").get_json()["total"] == 0


def test_purge_removes_the_row_permanently(
    auth_client, user, expense_category, make_transaction
):
    transaction = make_transaction(user, category=expense_category)
    auth_client.delete(f"/api/transactions/{transaction.id}")

    assert auth_client.delete(f"/api/transactions/{transaction.id}/purge").status_code == 204
    assert db.session.get(Transaction, transaction.id) is None


def test_restore_requires_a_deleted_row(auth_client, user, expense_category, make_transaction):
    active = make_transaction(user, category=expense_category)
    response = auth_client.post(f"/api/transactions/{active.id}/restore")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_trash_is_per_user(auth_client, other_user):
    other_category = Category(user_id=other_user.id, name="他的分类", kind="expense")
    db.session.add(other_category)
    db.session.commit()

    moment = now_local()
    foreign = Transaction(
        user_id=other_user.id,
        biz_date=date(2026, 1, 1),
        occurred_at=moment,
        amount_cents=1000,
        direction="out",
        category_id=other_category.id,
        deleted_at=moment,
    )
    db.session.add(foreign)
    db.session.commit()

    assert auth_client.get("/api/transactions/trash").get_json()["total"] == 0
    assert auth_client.post(f"/api/transactions/{foreign.id}/restore").status_code == 404
    assert auth_client.delete(f"/api/transactions/{foreign.id}/purge").status_code == 404


def test_empty_trash(auth_client, user, expense_category, make_transaction):
    for index in range(3):
        transaction = make_transaction(
            user, category=expense_category, amount=f"{index + 1}.00"
        )
        auth_client.delete(f"/api/transactions/{transaction.id}")

    response = auth_client.post("/api/transactions/trash/empty")
    assert response.status_code == 200
    assert response.get_json()["removed"] == 3
    assert auth_client.get("/api/transactions/trash").get_json()["total"] == 0


def test_trash_requires_login(client):
    assert client.get("/api/transactions/trash").status_code == 401
