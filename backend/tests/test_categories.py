"""Category endpoint tests."""

from __future__ import annotations

import pytest

from app.extensions import db
from app.models import Category


def test_defaults_are_seeded(auth_client):
    response = auth_client.get("/api/categories")
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert any(item["name"] == "餐饮" for item in items)
    assert {item["kind"] for item in items} == {"expense", "income"}


def test_list_can_filter_by_kind(auth_client):
    items = auth_client.get("/api/categories?kind=income").get_json()["items"]
    assert items
    assert all(item["kind"] == "income" for item in items)


def test_create_update_delete(auth_client):
    created = auth_client.post(
        "/api/categories",
        json={"name": "宠物", "kind": "expense", "icon": "🐱", "color": "#f59e0b"},
    )
    assert created.status_code == 201
    category_id = created.get_json()["category"]["id"]

    updated = auth_client.put(
        f"/api/categories/{category_id}", json={"name": "猫粮", "sort_order": 99}
    )
    assert updated.status_code == 200
    assert updated.get_json()["category"]["name"] == "猫粮"

    deleted = auth_client.delete(f"/api/categories/{category_id}")
    assert deleted.status_code == 204
    assert db.session.get(Category, category_id) is None


def test_duplicate_name_conflicts(auth_client):
    payload = {"name": "宠物", "kind": "expense"}
    assert auth_client.post("/api/categories", json=payload).status_code == 201
    duplicate = auth_client.post("/api/categories", json=payload)
    assert duplicate.status_code == 409


def test_same_name_allowed_in_other_kind(auth_client):
    payload = {"name": "其他", "kind": "income"}
    response = auth_client.post("/api/categories", json=payload)
    assert response.status_code == 201


def test_cannot_delete_category_in_use(auth_client, expense_category, user, make_transaction):
    make_transaction(user, category=expense_category)
    response = auth_client.delete(f"/api/categories/{expense_category.id}")
    assert response.status_code == 409
    assert "流水" in response.get_json()["error"]["message"]


def test_other_users_category_is_invisible(auth_client, other_user, app):
    foreign = Category(user_id=other_user.id, name="私房钱", kind="expense")
    db.session.add(foreign)
    db.session.commit()

    assert auth_client.put(f"/api/categories/{foreign.id}", json={"name": "x"}).status_code == 404
    assert auth_client.delete(f"/api/categories/{foreign.id}").status_code == 404


def test_requires_login(client):
    assert client.get("/api/categories").status_code == 401


@pytest.mark.parametrize("bad", [{"name": ""}, {"name": "x", "kind": "bogus"}])
def test_validation_errors(auth_client, bad):
    assert auth_client.post("/api/categories", json=bad).status_code == 422
