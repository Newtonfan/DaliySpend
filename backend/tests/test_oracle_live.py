"""Oracle integration tests (opt-in).

Everything here needs a real Oracle schema, so the whole module is skipped
unless ``DS_ORACLE_TEST_URL`` points at a **throw-away** schema: the fixtures
run ``DROP TABLE`` / ``CREATE TABLE`` on it.

    $env:DS_ORACLE_TEST_URL = 'oracle+oracledb://dailyspend_test:pwd@localhost:1521/?service_name=FREEPDB1'
    scripts\\dev.ps1 -m pytest tests\\test_oracle_live.py -v

What it proves on the real server:

* ``Identity()`` primary keys really generate values (no ORA-01400);
* Chinese text longer than the byte limit still fits (``VARCHAR2(n CHAR)``);
* ``note`` (``Text`` -> ``CLOB``) round-trips as ``str``, not a LOB handle;
* ``(user_id, external_id)`` uniqueness is enforced by the database;
* the aggregation helpers and CSV export produce the same numbers as SQLite;
* the HTTP API works end to end against Oracle.
"""

from __future__ import annotations

import os
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import Category, Transaction, User
from app.services import stats as stats_service
from app.services.seed import bootstrap_new_user
from app.utils.time import now_local

ORACLE_URL = os.environ.get("DS_ORACLE_TEST_URL")

pytestmark = pytest.mark.skipif(
    not ORACLE_URL,
    reason="set DS_ORACLE_TEST_URL to a throw-away Oracle schema to run these tests",
)

PASSWORD = "oracle-test-pass"


@pytest.fixture(scope="module")
def oracle_app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": ORACLE_URL,
            "WTF_CSRF_ENABLED": False,
            "SERVE_FRONTEND": False,
            "SECRET_KEY": "oracle-test",
        }
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def oracle_user(oracle_app):
    user = User(email=f"oracle-{os.urandom(4).hex()}@example.com", display_name="Oracle 用户")
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    bootstrap_new_user(user)
    return user


def _expense_category(user: User) -> Category:
    return (
        db.session.query(Category)
        .filter_by(user_id=user.id, kind="expense")
        .order_by(Category.sort_order)
        .first()
    )


def test_identity_primary_keys_generate_values(oracle_user):
    assert oracle_user.id is not None and oracle_user.id > 0

    second = User(email=f"oracle-{os.urandom(4).hex()}@example.com", display_name="第二个")
    second.set_password(PASSWORD)
    db.session.add(second)
    db.session.commit()

    assert second.id > oracle_user.id
    # Defaults from the seeded rows also received generated ids.
    assert db.session.query(Category).filter_by(user_id=oracle_user.id).count() > 0


def test_chinese_text_uses_char_semantics(oracle_user):
    # 40 characters == 120 bytes in UTF-8: only CHAR semantics accepts this.
    name = "账" * 40
    category = Category(user_id=oracle_user.id, name=name, kind="expense")
    db.session.add(category)
    db.session.commit()

    db.session.expire_all()
    stored = db.session.get(Category, category.id)
    assert stored is not None
    assert stored.name == name
    assert len(stored.name) == 40


def test_clob_roundtrip(oracle_user):
    category = _expense_category(oracle_user)
    note = "备注内容" * 500  # 2000 characters -> CLOB

    transaction = Transaction(
        user_id=oracle_user.id,
        biz_date=date(2026, 5, 1),
        occurred_at=now_local(),
        amount_cents=1234,
        direction="out",
        category_id=category.id,
        note=note,
    )
    db.session.add(transaction)
    db.session.commit()

    db.session.expire_all()
    stored = db.session.get(Transaction, transaction.id)
    assert isinstance(stored.note, str)
    assert stored.note == note


def test_external_id_is_unique_per_user(oracle_user):
    category = _expense_category(oracle_user)
    common = dict(
        user_id=oracle_user.id,
        biz_date=date(2026, 5, 2),
        occurred_at=now_local(),
        amount_cents=100,
        direction="out",
        category_id=category.id,
        external_id="wx-duplicate-1",
    )
    db.session.add(Transaction(**common))
    db.session.commit()

    db.session.add(Transaction(**common))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_stats_and_export_match_expected_numbers(oracle_user):
    category = _expense_category(oracle_user)
    income = (
        db.session.query(Category)
        .filter_by(user_id=oracle_user.id, kind="income")
        .order_by(Category.sort_order)
        .first()
    )
    for amount, direction, day, target in (
        ("100.00", "out", date(2026, 6, 1), category),
        ("50.50", "out", date(2026, 6, 2), category),
        ("2000.00", "in", date(2026, 6, 3), income),
    ):
        db.session.add(
            Transaction(
                user_id=oracle_user.id,
                biz_date=day,
                occurred_at=now_local(),
                amount_cents=int(round(float(amount) * 100)),
                direction=direction,
                category_id=target.id,
            )
        )
    db.session.commit()

    summary = stats_service.summary(oracle_user.id, date(2026, 6, 1), date(2026, 6, 30))
    assert summary["expense"] == {"amount": "150.50", "count": 2}
    assert summary["income"] == {"amount": "2000.00", "count": 1}
    assert summary["net"] == "1849.50"

    daily = stats_service.daily(oracle_user.id, date(2026, 6, 1), date(2026, 6, 3))
    assert [point["expense"] for point in daily] == ["100.00", "50.50", "0.00"]

    by_category = stats_service.by_category(
        oracle_user.id, date(2026, 6, 1), date(2026, 6, 30), "out"
    )
    assert by_category[0]["amount"] == "150.50"

    rows = list(
        stats_service.iter_export_rows(oracle_user.id, date(2026, 6, 1), date(2026, 6, 30))
    )
    assert len(rows) == 3
    assert rows[0][4] == "100.00"


def test_http_api_round_trip(oracle_app):
    client = oracle_app.test_client()
    email = f"oracle-http-{os.urandom(4).hex()}@example.com"

    registered = client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD, "display_name": "HTTP"}
    )
    assert registered.status_code == 201, registered.get_json()

    categories = client.get("/api/categories").get_json()["items"]
    created = client.post(
        "/api/transactions",
        json={
            "amount": "66.60",
            "category_id": categories[0]["id"],
            "biz_date": "2026-06-15",
            "payee": "Oracle 测试商户",
        },
    )
    assert created.status_code == 201, created.get_json()
    assert created.get_json()["transaction"]["amount"] == "66.60"

    listing = client.get("/api/transactions").get_json()
    assert listing["total"] == 1

    dashboard = client.get("/api/stats/dashboard?date_from=2026-06-01&date_to=2026-06-30").get_json()
    assert dashboard["summary"]["expense"]["amount"] == "66.60"

    csv_response = client.get(
        "/api/exports/transactions.csv?date_from=2026-06-01&date_to=2026-06-30"
    )
    assert csv_response.status_code == 200
    body = csv_response.get_data(as_text=True)
    assert "Oracle 测试商户" in body
