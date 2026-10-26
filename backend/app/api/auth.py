"""Registration, login, logout and the current-session endpoint."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import generate_csrf
from werkzeug.security import generate_password_hash

from ..errors_types import (
    ApiError,
    Conflict,
    Forbidden,
    Unauthorized,
    ValidationFailed,
)
from ..extensions import db
from ..models import User
from ..schemas import LoginPayload, RegisterPayload, parse_payload
from ..services.seed import bootstrap_new_user
from ..services.throttle import login_limiter
from ..utils.time import now_local

bp = Blueprint("auth", __name__, url_prefix="/auth")

#: Compared against when the e-mail is unknown, so a missing account costs the
#: same wall-clock time as a wrong password.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def _start_session(user: User, remember: bool = False) -> None:
    # ``session.clear()`` drops any pre-login state, which also prevents session
    # fixation when the login form is submitted with an attacker-known cookie.
    session.clear()
    session.permanent = True
    login_user(user, remember=remember)


def _public_settings() -> dict:
    settings = current_app.config["APP_SETTINGS"]
    return {
        "registration_enabled": bool(settings.registration_enabled),
        "password_min_length": int(settings.password_min_length),
        "app_name": settings.app_name,
    }


@bp.get("/csrf")
def csrf_token():
    return jsonify({"csrf_token": generate_csrf()})


@bp.get("/me")
def me():
    if not current_user.is_authenticated:
        raise Unauthorized()
    return jsonify({"user": current_user.to_dict(), "settings": _public_settings()})


@bp.post("/register")
def register():
    settings = current_app.config["APP_SETTINGS"]
    if not settings.registration_enabled:
        raise Forbidden("注册已关闭，请联系管理员开通账号")

    payload = parse_payload(RegisterPayload, request.get_json(silent=True))
    if len(payload.password) < settings.password_min_length:
        raise ValidationFailed(
            [
                {
                    "loc": ["password"],
                    "msg": f"密码至少需要 {settings.password_min_length} 位",
                    "type": "value_error",
                }
            ]
        )

    exists = db.session.query(User.id).filter_by(email=payload.email).first()
    if exists:
        raise Conflict("该邮箱已注册")

    user = User(
        email=payload.email,
        display_name=payload.display_name or payload.email.split("@")[0],
    )
    user.set_password(payload.password)
    db.session.add(user)
    db.session.commit()

    bootstrap_new_user(user)
    _start_session(user)
    return jsonify({"user": user.to_dict(), "settings": _public_settings()}), 201


@bp.post("/login")
def login():
    payload = parse_payload(LoginPayload, request.get_json(silent=True))
    throttle_key = f"{request.remote_addr or '-'}|{payload.email}"

    wait_seconds = login_limiter.retry_after(throttle_key)
    if wait_seconds is not None:
        raise ApiError(
            f"登录尝试过于频繁，请在 {wait_seconds} 秒后重试",
            code="too_many_attempts",
            status=429,
        )

    user = db.session.query(User).filter_by(email=payload.email).one_or_none()
    if user is None:
        # Keep the timing similar to a real password check.
        User(password_hash=_DUMMY_HASH).check_password(payload.password)
        login_limiter.register_failure(throttle_key)
        raise Unauthorized("邮箱或密码不正确")

    if not user.check_password(payload.password):
        login_limiter.register_failure(throttle_key)
        raise Unauthorized("邮箱或密码不正确")

    if not user.is_active:
        raise Forbidden("账号已被停用")

    login_limiter.reset(throttle_key)
    user.last_login_at = now_local()
    db.session.commit()
    _start_session(user, remember=payload.remember)
    return jsonify({"user": user.to_dict(), "settings": _public_settings()})


@bp.post("/logout")
def logout():
    logout_user()
    session.clear()
    return "", 204


@bp.post("/password")
@login_required
def change_password():
    body = request.get_json(silent=True) or {}
    current_password = str(body.get("current_password") or "")
    new_password = str(body.get("new_password") or "")
    settings = current_app.config["APP_SETTINGS"]

    if not current_user.check_password(current_password):
        raise Unauthorized("当前密码不正确")
    if len(new_password) < settings.password_min_length:
        raise ValidationFailed(
            [
                {
                    "loc": ["new_password"],
                    "msg": f"密码至少需要 {settings.password_min_length} 位",
                    "type": "value_error",
                }
            ]
        )

    current_user.set_password(new_password)
    db.session.commit()
    return "", 204
