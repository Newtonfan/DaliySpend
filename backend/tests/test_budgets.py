"""Budget endpoints and progress calculations."""

from __future__ import annotations

from datetime import date

from app.extensions import db
from app.models import Budget, Category
from app.utils.time import month_start, today_local

MONTH = "2026-03"


def test_defaults_to_current_month(auth_client):
    payload = auth_client.get("/api/budgets").get_json()
    today = today_local()
    assert payload["month"] == f"{today.year:04d}-{today.month:02d}"
    assert payload["has_budget"] is False
    assert payload["total"] is None
    assert payload["categories"] == []


def test_set_total_budget_and_read_back(auth_client):
    response = auth_client.put("/api/budgets", json={"month": MONTH, "amount": "3000"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["budget"]["amount"] == "3000.00"
    assert body["status"]["month"] == MONTH
    assert body["status"]["has_budget"] is True

    status = auth_client.get(f"/api/budgets?month={MONTH}").get_json()
    assert status["total"]["amount"] == "3000.00"
    assert status["total"]["spent"] == "0.00"
    assert status["total"]["remaining"] == "3000.00"
    assert status["total"]["percent"] == 0.0
    assert status["total"]["over"] is False


def test_upsert_updates_instead_of_duplicating(auth_client):
    auth_client.put("/api/budgets", json={"month": MONTH, "amount": "3000"})
    auth_client.put("/api/budgets", json={"month": MONTH, "amount": "2000"})

    assert db.session.query(Budget).count() == 1
    status = auth_client.get(f"/api/budgets?month={MONTH}").get_json()
    assert status["total"]["amount"] == "2000.00"


def test_category_budget_progress_and_over_budget(
    auth_client, user, expense_category, make_transaction
):
    auth_client.put(
        "/api/budgets",
        json={"month": MONTH, "amount": "500", "category_id": expense_category.id},
    )
    make_transaction(
        user, category=expense_category, amount="120.00", biz_date=date(2026, 3, 5)
    )
    make_transaction(
        user, category=expense_category, amount="430.00", biz_date=date(2026, 3, 9)
    )

    status = auth_client.get(f"/api/budgets?month={MONTH}").get_json()
    assert status["over_budget"] is True

    item = status["categories"][0]
    assert item["category_id"] == expense_category.id
    assert item["spent"] == "550.00"
    assert item["remaining"] == "-50.00"
    assert item["percent"] == 110.0
    assert item["over"] is True


def test_only_current_month_expenses_count(
    auth_client, user, expense_category, make_transaction
):
    auth_client.put("/api/budgets", json={"month": MONTH, "amount": "1000"})
    make_transaction(user, category=expense_category, amount="100.00", biz_date=date(2026, 3, 1))
    make_transaction(user, category=expense_category, amount="999.00", biz_date=date(2026, 4, 1))
    make_transaction(user, category=expense_category, amount="888.00", biz_date=date(2026, 2, 28))

    status = auth_client.get(f"/api/budgets?month={MONTH}").get_json()
    assert status["spent"] == "100.00"
    assert status["total"]["remaining"] == "900.00"


def test_income_does_not_consume_budget(
    auth_client, user, expense_category, income_category, make_transaction
):
    auth_client.put("/api/budgets", json={"month": MONTH, "amount": "1000"})
    make_transaction(
        user, category=income_category, amount="5000.00", biz_date=date(2026, 3, 2), direction="in"
    )
    make_transaction(user, category=expense_category, amount="10.00", biz_date=date(2026, 3, 2))

    status = auth_client.get(f"/api/budgets?month={MONTH}").get_json()
    assert status["total"]["spent"] == "10.00"


def test_deleted_transactions_are_excluded(
    auth_client, user, expense_category, make_transaction
):
    auth_client.put("/api/budgets", json={"month": MONTH, "amount": "1000"})
    transaction = make_transaction(
        user, category=expense_category, amount="50.00", biz_date=date(2026, 3, 3)
    )
    transaction.deleted_at = transaction.created_at
    db.session.commit()

    status = auth_client.get(f"/api/budgets?month={MONTH}").get_json()
    assert status["total"]["spent"] == "0.00"


def test_month_can_be_given_as_a_full_date(auth_client):
    response = auth_client.put(
        "/api/budgets", json={"month": "2026-03-18", "amount": "100"}
    )
    assert response.status_code == 200
    assert response.get_json()["budget"]["month"] == MONTH


def test_delete_budget(auth_client):
    created = auth_client.put(
        "/api/budgets", json={"month": MONTH, "amount": "100"}
    ).get_json()["budget"]
    assert auth_client.delete(f"/api/budgets/{created['id']}").status_code == 204
    status = auth_client.get(f"/api/budgets?month={MONTH}").get_json()
    assert status["has_budget"] is False


def test_cannot_delete_someone_elses_budget(auth_client, other_user):
    foreign = Budget(
        user_id=other_user.id, month=month_start(date(2026, 3, 1)), amount_cents=10000
    )
    db.session.add(foreign)
    db.session.commit()

    assert auth_client.delete(f"/api/budgets/{foreign.id}").status_code == 404


def test_foreign_category_is_rejected(auth_client, other_user):
    foreign = Category(user_id=other_user.id, name="他的分类", kind="expense")
    db.session.add(foreign)
    db.session.commit()

    response = auth_client.put(
        "/api/budgets", json={"month": MONTH, "amount": "100", "category_id": foreign.id}
    )
    assert response.status_code == 404


def test_deleting_a_category_removes_its_budget(auth_client, expense_category):
    auth_client.put(
        "/api/budgets",
        json={"month": MONTH, "amount": "100", "category_id": expense_category.id},
    )
    assert db.session.query(Budget).count() == 1

    assert auth_client.delete(f"/api/categories/{expense_category.id}").status_code == 204
    assert db.session.query(Budget).count() == 0


def test_validation(auth_client):
    assert auth_client.put("/api/budgets", json={"month": "2026-3", "amount": "1"}).status_code == 422
    assert auth_client.put("/api/budgets", json={"month": MONTH, "amount": "0"}).status_code == 422
    assert auth_client.put("/api/budgets", json={"month": MONTH, "amount": "-5"}).status_code == 422
    assert auth_client.get("/api/budgets?month=bogus").status_code == 422


def test_requires_login(client):
    assert client.get("/api/budgets").status_code == 401
    assert client.put("/api/budgets", json={"month": MONTH, "amount": "1"}).status_code == 401
