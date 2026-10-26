"""Default data created for every new account.

Registered users start with a usable set of categories and payment accounts so
the first screen is a working expense form instead of an empty shell.
"""

from __future__ import annotations

from ..extensions import db
from ..models import Account, Category, User

DEFAULT_EXPENSE_CATEGORIES = [
    ("餐饮", "🍜", "#f97316"),
    ("交通", "🚌", "#0ea5e9"),
    ("购物", "🛍️", "#ec4899"),
    ("居住", "🏠", "#8b5cf6"),
    ("娱乐", "🎬", "#22c55e"),
    ("医疗", "💊", "#ef4444"),
    ("学习", "📚", "#14b8a6"),
    ("通讯", "📱", "#6366f1"),
    ("人情", "🎁", "#f43f5e"),
    ("其他", "📦", "#94a3b8"),
]

DEFAULT_INCOME_CATEGORIES = [
    ("工资", "💰", "#16a34a"),
    ("奖金", "🏆", "#eab308"),
    ("理财", "📈", "#0d9488"),
    ("其他收入", "🧾", "#64748b"),
]

DEFAULT_ACCOUNTS = [
    ("现金", "cash"),
    ("支付宝", "alipay"),
    ("微信", "wechat"),
    ("银行卡", "bank"),
]


def bootstrap_new_user(user: User) -> None:
    """Create the starter categories and accounts for ``user``."""
    for index, (name, icon, color) in enumerate(DEFAULT_EXPENSE_CATEGORIES):
        db.session.add(
            Category(
                user_id=user.id,
                name=name,
                kind="expense",
                icon=icon,
                color=color,
                sort_order=index,
            )
        )
    for index, (name, icon, color) in enumerate(DEFAULT_INCOME_CATEGORIES):
        db.session.add(
            Category(
                user_id=user.id,
                name=name,
                kind="income",
                icon=icon,
                color=color,
                sort_order=index,
            )
        )
    for index, (name, account_type) in enumerate(DEFAULT_ACCOUNTS):
        db.session.add(
            Account(user_id=user.id, name=name, type=account_type, sort_order=index)
        )
    db.session.commit()
