"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db
from app.models import Account, Category, Transaction, User
from app.money import to_cents
from app.services.seed import bootstrap_new_user
from app.utils.time import now_local

PASSWORD = "s3cret-pass"


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / "test.sqlite3"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret",
            "SERVER_NAME": None,
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def user(app):
    """A registered user with the default categories and accounts."""
    user = User(email="alice@example.com", display_name="Alice")
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    bootstrap_new_user(user)
    return user


@pytest.fixture()
def other_user(app):
    user = User(email="bob@example.com", display_name="Bob")
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    bootstrap_new_user(user)
    return user


@pytest.fixture()
def auth_client(client, user):
    """A test client already signed in as :func:`user`."""
    response = client.post(
        "/api/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.get_json()
    return client


@pytest.fixture()
def expense_category(user):
    return (
        db.session.query(Category)
        .filter_by(user_id=user.id, kind="expense")
        .order_by(Category.sort_order)
        .first()
    )


@pytest.fixture()
def income_category(user):
    return (
        db.session.query(Category)
        .filter_by(user_id=user.id, kind="income")
        .order_by(Category.sort_order)
        .first()
    )


@pytest.fixture()
def account(user):
    return db.session.query(Account).filter_by(user_id=user.id).first()


def _insert_transaction(
    user: User,
    *,
    category: Category,
    amount: str = "12.34",
    biz_date=None,
    direction: str = "out",
    account: Account | None = None,
    payee: str = "测试商户",
    note: str = "",
) -> Transaction:
    """Insert a transaction directly, bypassing the HTTP layer."""
    moment = biz_date or now_local().date()
    txn = Transaction(
        user_id=user.id,
        biz_date=moment,
        occurred_at=now_local(),
        amount_cents=to_cents(amount),
        direction=direction,
        category_id=category.id,
        account_id=account.id if account else None,
        payee=payee,
        note=note,
    )
    db.session.add(txn)
    db.session.commit()
    return txn


@pytest.fixture()
def make_transaction():
    """Factory fixture: insert a transaction directly, bypassing the HTTP layer."""
    return _insert_transaction
