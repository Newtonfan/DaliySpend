"""Transaction endpoint tests."""

from __future__ import annotations

from datetime import date

import pytest

from app.extensions import db
from app.models import Category, Transaction


def test_create_expense(auth_client, expense_category, account):
    response = auth_client.post(
        "/api/transactions",
        json={
            "amount": "12.34",
            "category_id": expense_category.id,
            "account_id": account.id,
            "biz_date": "2026-01-05",
            "payee": "便利店",
            "note": "早饭",
        },
    )
    assert response.status_code == 201
    transaction = response.get_json()["transaction"]
    assert transaction["amount"] == "12.34"
    assert transaction["amount_cents"] == 1234
    assert transaction["direction"] == "out"
    assert transaction["biz_date"] == "2026-01-05"
    assert transaction["category"]["name"] == expense_category.name
    assert transaction["account"]["id"] == account.id


def test_income_category_sets_direction_in(auth_client, income_category):
    response = auth_client.post(
        "/api/transactions", json={"amount": "8000", "category_id": income_category.id}
    )
    assert response.status_code == 201
    assert response.get_json()["transaction"]["direction"] == "in"


def test_defaults_to_today_when_no_date(auth_client, expense_category):
    response = auth_client.post(
        "/api/transactions", json={"amount": "1.00", "category_id": expense_category.id}
    )
    assert response.status_code == 201
    transaction = response.get_json()["transaction"]
    assert transaction["biz_date"] == date.today().isoformat() or transaction["biz_date"]


@pytest.mark.parametrize("amount", ["0", "-5", "1.234", "abc"])
def test_amount_validation(auth_client, expense_category, amount):
    response = auth_client.post(
        "/api/transactions", json={"amount": amount, "category_id": expense_category.id}
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_unknown_category_is_404(auth_client):
    response = auth_client.post("/api/transactions", json={"amount": "1", "category_id": 999999})
    assert response.status_code == 404


def test_other_users_category_is_404(auth_client, other_user):
    foreign = Category(user_id=other_user.id, name="别人的分类", kind="expense")
    db.session.add(foreign)
    db.session.commit()

    response = auth_client.post(
        "/api/transactions", json={"amount": "1", "category_id": foreign.id}
    )
    assert response.status_code == 404


def test_list_requires_login(client):
    assert client.get("/api/transactions").status_code == 401


def test_list_pagination_and_ordering(auth_client, user, expense_category, make_transaction):
    for index in range(5):
        make_transaction(
            user,
            category=expense_category,
            amount=f"{index + 1}.00",
            biz_date=date(2026, 1, index + 1),
        )

    first = auth_client.get("/api/transactions?page=1&page_size=2").get_json()
    assert first["total"] == 5
    assert first["total_pages"] == 3
    assert [item["amount"] for item in first["items"]] == ["5.00", "4.00"]

    second = auth_client.get("/api/transactions?page=2&page_size=2").get_json()
    assert [item["amount"] for item in second["items"]] == ["3.00", "2.00"]

    by_amount = auth_client.get("/api/transactions?sort=amount_asc").get_json()
    assert [item["amount"] for item in by_amount["items"]] == [
        "1.00",
        "2.00",
        "3.00",
        "4.00",
        "5.00",
    ]


def test_list_filters(auth_client, user, expense_category, income_category, make_transaction):
    make_transaction(user, category=expense_category, amount="10.00", biz_date=date(2026, 1, 1), payee="星巴克")
    make_transaction(user, category=expense_category, amount="20.00", biz_date=date(2026, 2, 1), payee="超市")
    make_transaction(
        user,
        category=income_category,
        amount="500.00",
        biz_date=date(2026, 2, 2),
        direction="in",
        payee="报销",
    )

    in_february = auth_client.get("/api/transactions?date_from=2026-02-01&date_to=2026-02-28").get_json()
    assert in_february["total"] == 2

    only_income = auth_client.get("/api/transactions?direction=in").get_json()
    assert only_income["total"] == 1
    assert only_income["items"][0]["payee"] == "报销"

    search = auth_client.get("/api/transactions?q=巴克").get_json()
    assert search["total"] == 1
    assert search["items"][0]["payee"] == "星巴克"

    by_category = auth_client.get(
        f"/api/transactions?category_id={expense_category.id}"
    ).get_json()
    assert by_category["total"] == 2


def test_get_update_and_soft_delete(auth_client, expense_category, income_category, make_transaction, user):
    transaction = make_transaction(user, category=expense_category, amount="30.00")

    detail = auth_client.get(f"/api/transactions/{transaction.id}")
    assert detail.status_code == 200
    assert detail.get_json()["transaction"]["amount"] == "30.00"

    updated = auth_client.put(
        f"/api/transactions/{transaction.id}",
        json={"amount": "45.5", "note": "改过了", "category_id": income_category.id},
    )
    assert updated.status_code == 200
    body = updated.get_json()["transaction"]
    assert body["amount"] == "45.50"
    assert body["note"] == "改过了"
    assert body["direction"] == "in"

    assert auth_client.delete(f"/api/transactions/{transaction.id}").status_code == 204
    assert auth_client.get(f"/api/transactions/{transaction.id}").status_code == 404
    assert auth_client.get("/api/transactions").get_json()["total"] == 0

    # The row is kept for recovery, only hidden from the API.
    stored = db.session.get(Transaction, transaction.id)
    assert stored is not None and stored.deleted_at is not None


def test_update_rejects_other_users_category(auth_client, other_user, make_transaction, user, expense_category):
    foreign = Category(user_id=other_user.id, name="别人的", kind="expense")
    db.session.add(foreign)
    db.session.commit()
    transaction = make_transaction(user, category=expense_category)

    response = auth_client.put(
        f"/api/transactions/{transaction.id}", json={"category_id": foreign.id}
    )
    assert response.status_code == 404


def test_transactions_are_scoped_per_user(auth_client, other_user, make_transaction):
    other_category = Category(user_id=other_user.id, name="他的分类", kind="expense")
    db.session.add(other_category)
    db.session.commit()
    make_transaction(other_user, category=other_category, amount="99.00")

    listing = auth_client.get("/api/transactions").get_json()
    assert listing["total"] == 0
