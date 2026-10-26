"""Health endpoint and app factory smoke tests."""

from __future__ import annotations


def test_health_reports_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["database"] is True


def test_unknown_api_route_returns_json_404(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_unknown_method_returns_json_405(client):
    response = client.patch("/api/health")
    assert response.status_code == 405
    assert "error" in response.get_json()
