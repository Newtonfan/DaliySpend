"""Uniform JSON error handling for the API."""

from __future__ import annotations

from flask import Flask, Response, jsonify, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from .errors_types import ApiError


def error_payload(code: str, message: str, details=None) -> dict:
    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def json_error(code: str, message: str, status: int, details=None):
    response = jsonify(error_payload(code, message, details))
    response.status_code = status
    return response


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError) -> Response:
        return json_error(exc.code, exc.message, exc.status, exc.details)

    @app.errorhandler(CSRFError)
    def _handle_csrf_error(exc: CSRFError) -> Response:
        return json_error("csrf_failed", exc.description or "CSRF 校验失败", 400)

    @app.errorhandler(HTTPException)
    def _handle_http_exception(exc: HTTPException) -> Response:
        if request.path.startswith("/api/"):
            slug = (exc.name or "error").lower().replace(" ", "_")
            return json_error(slug, exc.description or exc.name, exc.code or 500)
        return exc  # type: ignore[return-value]

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception) -> Response:
        app.logger.exception("Unhandled error on %s %s", request.method, request.path)
        if app.config.get("TESTING"):
            raise exc
        return json_error("internal_error", "服务器内部错误", 500)
