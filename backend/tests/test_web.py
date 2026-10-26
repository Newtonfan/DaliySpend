"""Tests for serving the built single-page app."""

from __future__ import annotations

from flask import Flask

from app import create_app
from app.extensions import db
from app.web import register_frontend


def _build_fake_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=app></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    return dist


def test_spa_is_served_with_history_fallback(app, tmp_path):
    dist = _build_fake_dist(tmp_path)
    register_frontend(app, dist)

    index = app.test_client().get("/")
    assert index.status_code == 200
    assert b"id=app" in index.data

    deep_link = app.test_client().get("/transactions")
    assert deep_link.status_code == 200
    assert b"id=app" in deep_link.data

    asset = app.test_client().get("/assets/app.js")
    assert asset.status_code == 200
    assert b"console.log" in asset.data


def test_api_paths_are_not_swallowed_by_the_spa(app, tmp_path):
    dist = _build_fake_dist(tmp_path)
    register_frontend(app, dist)

    response = app.test_client().get("/api/nope")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_missing_build_keeps_api_only_mode(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'api-only.sqlite3').as_posix()}",
            "WTF_CSRF_ENABLED": False,
            "SERVE_FRONTEND": False,
        }
    )
    assert isinstance(app, Flask)
    # No build mounted, and mounting a non-existent directory is a no-op.
    assert register_frontend(app, tmp_path / "does-not-exist") is False

    with app.app_context():
        db.create_all()
        client = app.test_client()
        response = client.get("/")
        assert response.status_code == 404
        assert client.get("/api/health").status_code == 200
