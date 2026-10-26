"""Typed application errors that are rendered as JSON by :mod:`app.errors`."""

from __future__ import annotations


class ApiError(Exception):
    """An error whose payload is sent to the client verbatim."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "bad_request",
        status: int = 400,
        details=None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.details = details


class ValidationFailed(ApiError):
    def __init__(self, details) -> None:
        super().__init__("请求数据校验失败", code="validation_error", status=422, details=details)


class NotFound(ApiError):
    def __init__(self, message: str = "记录不存在") -> None:
        super().__init__(message, code="not_found", status=404)


class Unauthorized(ApiError):
    def __init__(self, message: str = "请先登录") -> None:
        super().__init__(message, code="unauthorized", status=401)


class Forbidden(ApiError):
    def __init__(self, message: str = "没有权限") -> None:
        super().__init__(message, code="forbidden", status=403)


class Conflict(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="conflict", status=409)
