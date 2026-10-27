"""WeChat / Alipay statement import endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from ..errors_types import ApiError
from ..services import imports as import_service
from .helpers import current_user_id, get_account, get_category

bp = Blueprint("imports", __name__, url_prefix="/imports")

TRUE_VALUES = {"1", "true", "yes", "on"}


def _int_field(name: str) -> int | None:
    raw = request.form.get(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ApiError(
            f"字段 {name} 必须是整数",
            code="validation_error",
            status=422,
            details=[{"loc": [name], "msg": "必须是整数", "type": "value_error"}],
        ) from exc


def _read_upload() -> bytes:
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        raise ApiError("请选择要导入的 CSV 文件", code="missing_file", status=400)
    raw = upload.read()
    if not raw:
        raise ApiError("上传的文件是空的", code="empty_file", status=400)
    if len(raw) > import_service.MAX_BYTES:
        raise ApiError("文件超过 10MB，请拆分后再导入", code="file_too_large", status=413)
    return raw


@bp.post("/csv")
@login_required
def import_csv():
    """Parse a statement; ``dry_run`` (default) previews instead of writing.

    The same endpoint handles both steps so the client uploads the file twice
    instead of the server having to cache it between requests.
    """
    raw = _read_upload()
    dry_run = (request.form.get("dry_run", "true") or "").strip().lower() in TRUE_VALUES
    category_id = _int_field("default_category_id")
    account_id = _int_field("default_account_id")

    # Ownership checks raise 404 for somebody else's ids.
    if category_id is not None:
        get_category(category_id)
    if account_id is not None:
        get_account(account_id)

    user_id = current_user_id()
    if dry_run:
        return jsonify(import_service.preview(user_id, raw))

    result = import_service.commit(
        user_id,
        raw,
        default_category_id=category_id,
        default_account_id=account_id,
    )
    return jsonify(result)
