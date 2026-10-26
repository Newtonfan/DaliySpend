"""Authentication flow tests."""

from __future__ import annotations

from app.extensions import db
from app.models import Category, User
from app.services.throttle import login_limiter

PASSWORD = "s3cret-pass"


def test_register_creates_user_with_defaults(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "New@Example.com", "password": PASSWORD, "display_name": "新用户"},
    )
    assert response.status_code == 201
    assert response.get_json()["user"]["email"] == "new@example.com"

    user = db.session.query(User).filter_by(email="new@example.com").one()
    assert user.display_name == "新用户"
    assert db.session.query(Category).filter_by(user_id=user.id).count() > 0

    # registration signs the user in
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"]["email"] == "new@example.com"


def test_register_rejects_duplicate_email(client, user):
    response = client.post(
        "/api/auth/register", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "conflict"


def test_register_rejects_bad_email_and_short_password(client):
    bad_email = client.post(
        "/api/auth/register", json={"email": "nope", "password": PASSWORD}
    )
    assert bad_email.status_code == 422
    assert bad_email.get_json()["error"]["code"] == "validation_error"

    short_password = client.post(
        "/api/auth/register", json={"email": "ok@example.com", "password": "123"}
    )
    assert short_password.status_code == 422
    assert short_password.get_json()["error"]["details"][0]["loc"] == ["password"]


def test_register_can_be_disabled(app, client):
    app.config["APP_SETTINGS"].registration_enabled = False
    try:
        response = client.post(
            "/api/auth/register", json={"email": "x@example.com", "password": PASSWORD}
        )
        assert response.status_code == 403
    finally:
        app.config["APP_SETTINGS"].registration_enabled = True


def test_login_and_me(client, user):
    response = client.post(
        "/api/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["user"]["id"] == user.id
    assert payload["settings"]["registration_enabled"] is True

    assert client.get("/api/auth/me").status_code == 200

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_login_rejects_wrong_password(client, user):
    response = client.post(
        "/api/auth/login", json={"email": user.email, "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthorized"


def test_login_unknown_email_returns_same_error(client, user):
    response = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["message"] == "邮箱或密码不正确"


def test_login_is_throttled_after_repeated_failures(client, user):
    login_limiter.reset(f"127.0.0.1|{user.email}")
    try:
        for _ in range(login_limiter.max_failures):
            client.post(
                "/api/auth/login", json={"email": user.email, "password": "bad-password"}
            )
        blocked = client.post(
            "/api/auth/login", json={"email": user.email, "password": PASSWORD}
        )
        assert blocked.status_code == 429
        assert blocked.get_json()["error"]["code"] == "too_many_attempts"
    finally:
        login_limiter.reset(f"127.0.0.1|{user.email}")


def test_me_requires_login(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_change_password(auth_client, user):
    response = auth_client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "brand-new-pass"},
    )
    assert response.status_code == 204

    auth_client.post("/api/auth/logout")
    assert (
        auth_client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "brand-new-pass"},
        ).status_code
        == 200
    )


def test_change_password_requires_current_password(auth_client):
    response = auth_client.post(
        "/api/auth/password",
        json={"current_password": "wrong", "new_password": "brand-new-pass"},
    )
    assert response.status_code == 401


def test_csrf_token_endpoint(client):
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    assert response.get_json()["csrf_token"]
