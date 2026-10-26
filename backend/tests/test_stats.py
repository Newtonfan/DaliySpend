"""Dashboard aggregation tests."""

from __future__ import annotations

from datetime import date, timedelta

from app.utils.time import add_months, month_start, today_local


def test_summary_totals(auth_client, user, expense_category, income_category, make_transaction):
    make_transaction(user, category=expense_category, amount="100.00", biz_date=date(2026, 1, 5))
    make_transaction(user, category=expense_category, amount="50.50", biz_date=date(2026, 1, 6))
    make_transaction(
        user, category=income_category, amount="1000.00", biz_date=date(2026, 1, 6), direction="in"
    )
    make_transaction(user, category=expense_category, amount="20.00", biz_date=date(2026, 2, 1))

    payload = auth_client.get(
        "/api/stats/summary?date_from=2026-01-01&date_to=2026-01-31"
    ).get_json()

    assert payload["expense"] == {"amount": "150.50", "count": 2}
    assert payload["income"] == {"amount": "1000.00", "count": 1}
    assert payload["net"] == "849.50"
    assert payload["count"] == 3
    assert payload["average_expense"] == "75.25"


def test_daily_fills_missing_days(auth_client, user, expense_category, make_transaction):
    make_transaction(user, category=expense_category, amount="30.00", biz_date=date(2026, 3, 2))

    items = auth_client.get(
        "/api/stats/daily?date_from=2026-03-01&date_to=2026-03-04"
    ).get_json()["items"]

    assert [item["date"] for item in items] == [
        "2026-03-01",
        "2026-03-02",
        "2026-03-03",
        "2026-03-04",
    ]
    assert [item["expense"] for item in items] == ["0.00", "30.00", "0.00", "0.00"]


def test_by_category_shares(auth_client, user, expense_category, make_transaction):
    make_transaction(user, category=expense_category, amount="75.00", biz_date=date(2026, 1, 2))
    make_transaction(user, category=expense_category, amount="25.00", biz_date=date(2026, 1, 3))

    items = auth_client.get(
        "/api/stats/by-category?date_from=2026-01-01&date_to=2026-01-31"
    ).get_json()["items"]

    assert len(items) == 1
    assert items[0]["amount"] == "100.00"
    assert items[0]["count"] == 2
    assert items[0]["share"] == 1.0


def test_by_account_groups_unspecified(auth_client, user, expense_category, make_transaction):
    make_transaction(user, category=expense_category, amount="10.00", biz_date=date(2026, 1, 2))

    items = auth_client.get(
        "/api/stats/by-account?date_from=2026-01-01&date_to=2026-01-31"
    ).get_json()["items"]

    assert len(items) == 1
    assert items[0]["name"] == "未指定账户"


def test_monthly_window_is_anchored_to_today(auth_client, user, expense_category, make_transaction):
    today = today_local()
    this_month = month_start(today)
    last_month = add_months(this_month, -1)

    make_transaction(user, category=expense_category, amount="11.00", biz_date=last_month)
    make_transaction(user, category=expense_category, amount="22.00", biz_date=this_month)

    items = auth_client.get("/api/stats/monthly?months=2").get_json()["items"]

    assert len(items) == 2
    assert items[0]["month"] == f"{last_month.year:04d}-{last_month.month:02d}"
    assert items[0]["expense"] == "11.00"
    assert items[1]["expense"] == "22.00"


def test_dashboard_returns_every_section(auth_client, user, expense_category, make_transaction):
    make_transaction(user, category=expense_category, amount="5.00")

    payload = auth_client.get("/api/stats/dashboard").get_json()
    assert set(payload) == {"summary", "daily", "by_category", "by_account", "monthly"}
    assert payload["summary"]["count"] == 1


def test_invalid_range_is_rejected(auth_client):
    response = auth_client.get("/api/stats/summary?date_from=2026-02-01&date_to=2026-01-01")
    assert response.status_code == 422


def test_too_long_daily_range_is_rejected(auth_client):
    today = today_local()
    old = today - timedelta(days=500)
    response = auth_client.get(
        f"/api/stats/daily?date_from={old.isoformat()}&date_to={today.isoformat()}"
    )
    assert response.status_code == 422


def test_requires_login(client):
    assert client.get("/api/stats/summary").status_code == 401
