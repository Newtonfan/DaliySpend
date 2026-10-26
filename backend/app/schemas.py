"""Pydantic schemas for request payloads and query strings.

Validation failures are converted into :class:`ValidationFailed` so the API
always answers with the same JSON error envelope.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Mapping

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from .errors_types import ValidationFailed

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

Direction = Literal["out", "in"]
CategoryKind = Literal["expense", "income"]
AccountType = Literal["cash", "alipay", "wechat", "bank", "credit", "other"]


def _format_errors(exc: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "loc": [str(part) for part in error["loc"]],
            "msg": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors(include_url=False)
    ]


def parse_payload(model_type: type[BaseModel], payload: Any) -> Any:
    try:
        return model_type.model_validate(payload or {})
    except ValidationError as exc:
        raise ValidationFailed(_format_errors(exc)) from exc


def parse_query(model_type: type[BaseModel], args: Mapping[str, str]) -> Any:
    cleaned = {key: value for key, value in args.items() if value not in ("", None)}
    try:
        return model_type.model_validate(cleaned)
    except ValidationError as exc:
        raise ValidationFailed(_format_errors(exc)) from exc


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------- auth


class RegisterPayload(Payload):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError("邮箱格式不正确")
        return value

    @field_validator("display_name")
    @classmethod
    def _blank_name_to_none(cls, value: str | None) -> str | None:
        return value or None


class LoginPayload(Payload):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)
    remember: bool = False

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


# ----------------------------------------------------------------------- category


class CategoryCreate(Payload):
    name: str = Field(min_length=1, max_length=40)
    kind: CategoryKind = "expense"
    icon: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, max_length=16)
    sort_order: int = 0


class CategoryUpdate(Payload):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    icon: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, max_length=16)
    sort_order: int | None = None
    is_active: bool | None = None


# ------------------------------------------------------------------------ account


class AccountCreate(Payload):
    name: str = Field(min_length=1, max_length=40)
    type: AccountType = "other"
    initial_balance: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    sort_order: int = 0


class AccountUpdate(Payload):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    type: AccountType | None = None
    initial_balance: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    sort_order: int | None = None
    is_active: bool | None = None


# -------------------------------------------------------------------- transaction

MAX_AMOUNT = Decimal("99999999.99")


def _validate_amount(value: Decimal) -> Decimal:
    amount = Decimal(value)
    if amount <= 0:
        raise ValueError("金额必须大于 0")
    if amount > MAX_AMOUNT:
        raise ValueError("金额超出允许范围")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("金额最多两位小数")
    return amount


#: A positive money value with at most two decimal places, expressed in yuan.
AmountIn = Annotated[Decimal, AfterValidator(_validate_amount)]


class TransactionCreate(Payload):
    amount: AmountIn
    category_id: int
    account_id: int | None = None
    biz_date: date | None = None
    occurred_at: datetime | None = None
    payee: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)


class TransactionUpdate(Payload):
    amount: AmountIn | None = None
    category_id: int | None = None
    account_id: int | None = None
    biz_date: date | None = None
    occurred_at: datetime | None = None
    payee: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)


class TransactionQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date_from: date | None = None
    date_to: date | None = None
    category_id: int | None = None
    account_id: int | None = None
    direction: Direction | None = None
    q: str | None = Field(default=None, max_length=100)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    sort: Literal["date_desc", "date_asc", "amount_desc", "amount_asc"] = "date_desc"


class StatsQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date_from: date | None = None
    date_to: date | None = None
    direction: Direction | None = "out"
    months: int = Field(default=6, ge=1, le=36)
