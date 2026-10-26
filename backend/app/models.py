"""SQLAlchemy models.

The schema deliberately sticks to portable SQLAlchemy constructs (integers,
dates, strings, explicit indexes) so the same models run on SQLite during
development and on Oracle afterwards:

* money is an integer number of cents (``amount_cents``);
* identifiers are plain integers, so Oracle can be given an IDENTITY column or a
  sequence later without touching the ORM models;
* all grouping is done on real date columns instead of dialect-specific
  functions such as ``strftime`` / ``to_char``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from flask_login import UserMixin
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .money import from_cents
from .utils.time import now_local

DIRECTIONS = ("out", "in")
CATEGORY_KINDS = ("expense", "income")
ACCOUNT_TYPES = ("cash", "alipay", "wechat", "bank", "credit", "other")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_local, onupdate=now_local, nullable=False
    )


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active_flag: Mapped[bool] = mapped_column(
        "is_active", Boolean, nullable=False, default=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    categories: Mapped[list["Category"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    accounts: Mapped[list["Account"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # -- password helpers -------------------------------------------------
    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    # -- flask-login interface -------------------------------------------
    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return bool(self.is_active_flag)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "name", name="uq_categories_user_kind_name"),
        CheckConstraint("kind IN ('expense', 'income')", name="ck_categories_kind"),
        Index("ix_categories_user_kind", "user_id", "kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="expense")
    icon: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped["User"] = relationship(back_populates="categories")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "icon": self.icon,
            "color": self.color,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
        }


class Account(TimestampMixin, db.Model):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_accounts_user_name"),
        Index("ix_accounts_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    initial_balance_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped["User"] = relationship(back_populates="accounts")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "initial_balance": from_cents(self.initial_balance_cents),
            "sort_order": self.sort_order,
            "is_active": self.is_active,
        }


class Transaction(TimestampMixin, db.Model):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_transactions_amount_positive"),
        CheckConstraint("direction IN ('out', 'in')", name="ck_transactions_direction"),
        UniqueConstraint("user_id", "external_id", name="uq_transactions_user_external"),
        Index("ix_transactions_user_date", "user_id", "biz_date"),
        Index("ix_transactions_user_category_date", "user_id", "category_id", "biz_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    biz_date: Mapped[date] = mapped_column(Date, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(3), nullable=False, default="out")
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    payee: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    #: Reserved for future statement imports: unique per user when present.
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    category: Mapped["Category"] = relationship(lazy="joined")
    account: Mapped[Optional["Account"]] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "biz_date": self.biz_date.isoformat(),
            "occurred_at": self.occurred_at.isoformat(timespec="seconds"),
            "amount": from_cents(self.amount_cents),
            "amount_cents": self.amount_cents,
            "direction": self.direction,
            "category_id": self.category_id,
            "category": (
                {
                    "id": self.category.id,
                    "name": self.category.name,
                    "kind": self.category.kind,
                    "icon": self.category.icon,
                    "color": self.category.color,
                }
                if self.category
                else None
            ),
            "account_id": self.account_id,
            "account": (
                {"id": self.account.id, "name": self.account.name, "type": self.account.type}
                if self.account
                else None
            ),
            "payee": self.payee,
            "note": self.note,
            "created_at": self.created_at.isoformat(timespec="seconds") if self.created_at else None,
            "updated_at": self.updated_at.isoformat(timespec="seconds") if self.updated_at else None,
        }
