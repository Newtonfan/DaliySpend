"""CSRF and session-security behaviour of the API."""

from __future__ import annotations

from app import create_app
from app.extensions import db


def test_csrf_is_enforced_when_enabled(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'csrf.sqlite3').as_posix()}",
            "WTF_CSRF_ENABLED": True,
            "SERVE_FRONTEND": False,
        }
    )
    with app.app_context():
        db.create_all()
        client = app.test_client()

        blocked = client.post(
            "/api/auth/register", json={"email": "csrf@example.com", "password": "password-123"}
        )
        assert blocked.status_code == 400
        assert blocked.get_json()["error"]["code"] == "csrf_failed"

        token = client.get("/api/auth/csrf").get_json()["csrf_token"]
        allowed = client.post(
            "/api/auth/register",
            json={"email": "csrf@example.com", "password": "password-123"},
            headers={"X-CSRFToken": token},
        )
        assert allowed.status_code == 201
        db.drop_all()


def test_safe_methods_need_no_token(client):
    assert client.get("/api/health").status_code == 200


def test_session_cookie_is_httponly(client, user):
    response = client.post("/api/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    assert response.status_code == 200
    cookie_header = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie_header
    assert "SameSite=Lax" in cookie_header
