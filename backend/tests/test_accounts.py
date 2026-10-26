"""Account endpoint tests."""

from __future__ import annotations

from app.extensions import db
from app.models import Account


def test_defaults_are_seeded(auth_client):
    items = auth_client.get("/api/accounts").get_json()["items"]
    names = {item["name"] for item in items}
    assert {"现金", "支付宝", "微信", "银行卡"} <= names


def test_create_with_initial_balance(auth_client):
    response = auth_client.post(
        "/api/accounts", json={"name": "招行信用卡", "type": "credit", "initial_balance": "1234.5"}
    )
    assert response.status_code == 201
    account = response.get_json()["account"]
    assert account["initial_balance"] == "1234.50"
    assert account["type"] == "credit"


def test_update_and_delete(auth_client):
    created = auth_client.post("/api/accounts", json={"name": "零钱通", "type": "other"})
    account_id = created.get_json()["account"]["id"]

    updated = auth_client.put(
        f"/api/accounts/{account_id}", json={"name": "零钱通2", "initial_balance": "10"}
    )
    assert updated.status_code == 200
    assert updated.get_json()["account"]["name"] == "零钱通2"
    assert updated.get_json()["account"]["initial_balance"] == "10.00"

    assert auth_client.delete(f"/api/accounts/{account_id}").status_code == 204
    assert db.session.get(Account, account_id) is None


def test_duplicate_name_conflicts(auth_client):
    assert auth_client.post("/api/accounts", json={"name": "现金"}).status_code == 409


def test_cannot_delete_account_in_use(
    auth_client, account, expense_category, user, make_transaction
):
    make_transaction(user, category=expense_category, account=account)
    response = auth_client.delete(f"/api/accounts/{account.id}")
    assert response.status_code == 409


def test_requires_login(client):
    assert client.get("/api/accounts").status_code == 401
