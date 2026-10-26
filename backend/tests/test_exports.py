"""CSV export tests."""

from __future__ import annotations

from datetime import date

from app.models import Category


def test_export_contains_header_and_rows(auth_client, user, expense_category, make_transaction):
    make_transaction(
        user,
        category=expense_category,
        amount="18.80",
        biz_date=date(2026, 1, 8),
        payee="面馆",
        note="午饭",
    )

    response = auth_client.get(
        "/api/exports/transactions.csv?date_from=2026-01-01&date_to=2026-01-31"
    )
    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith("attachment;")
    assert "text/csv" in response.headers["Content-Type"]

    body = response.get_data(as_text=True)
    assert body.startswith("\ufeff")
    assert "日期,类型,分类,账户,金额(元),商户,备注" in body
    assert f"2026-01-08,支出,{expense_category.name}" in body
    assert "18.80" in body
    assert "面馆" in body


def test_export_respects_date_filter(auth_client, user, expense_category, make_transaction):
    make_transaction(user, category=expense_category, amount="1.00", biz_date=date(2026, 1, 1))
    make_transaction(user, category=expense_category, amount="2.00", biz_date=date(2026, 6, 1))

    body = auth_client.get(
        "/api/exports/transactions.csv?date_from=2026-06-01&date_to=2026-06-30"
    ).get_data(as_text=True)

    assert "2.00" in body
    assert "1.00" not in body


def test_export_is_scoped_per_user(auth_client, other_user, make_transaction):
    other_category = Category(user_id=other_user.id, name="他的分类", kind="expense")
    from app.extensions import db

    db.session.add(other_category)
    db.session.commit()
    make_transaction(other_user, category=other_category, amount="77.00", payee="别人的消费")

    body = auth_client.get(
        "/api/exports/transactions.csv?date_from=1900-01-01"
    ).get_data(as_text=True)

    assert "别人的消费" not in body


def test_export_requires_login(client):
    assert client.get("/api/exports/transactions.csv").status_code == 401
