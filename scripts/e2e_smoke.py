"""End-to-end smoke test: real HTTP + real browser against the built bundle.

What it does
------------
1. creates a throw-away SQLite database and seeds a user with demo transactions;
2. serves the real app (API + built SPA) on 127.0.0.1:5055 in a thread;
3. drives the HTTP API the way the browser does (CSRF token -> header), covering
   health, register/login, transaction CRUD, dashboard stats, CSV export and the
   SPA history fallback;
4. renders the login page and the signed-in dashboard with headless Edge and
   writes PNG screenshots, so a blank white page (bundle/runtime failure) is
   caught instead of silently shipped.

Run it with:  scripts\\dev.ps1 ..\\scripts\\e2e_smoke.py
It is developer tooling: nothing in here is imported by the application.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / ".tmp"
DB_PATH = TMP / "e2e.sqlite3"
SHOT_DIR = TMP / "screenshots"
PORT = 5055
BASE = f"http://127.0.0.1:{PORT}"
EMAIL = "e2e@example.com"
PASSWORD = "e2e-password-123"

EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
]

failures: list[str] = []
checks: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append(f"{'PASS' if ok else 'FAIL'} {name}{(' :: ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)


def build_app():
    from app import create_app
    from app.extensions import db
    from app.models import Category, Transaction, User
    from app.services.seed import bootstrap_new_user
    from app.money import to_cents
    from app.utils.time import add_months, month_start, now_local, today_local

    TMP.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    app = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{DB_PATH.as_posix()}",
            "SECRET_KEY": "e2e-secret",
            "SERVE_FRONTEND": True,
        }
    )

    with app.app_context():
        db.create_all()
        user = User(email=EMAIL, display_name="测试用户")
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        bootstrap_new_user(user)

        categories = (
            db.session.query(Category)
            .filter_by(user_id=user.id, kind="expense")
            .order_by(Category.sort_order)
            .all()
        )
        income = (
            db.session.query(Category)
            .filter_by(user_id=user.id, kind="income")
            .order_by(Category.sort_order)
            .first()
        )

        today = today_local()
        this_month = month_start(today)
        last_month = add_months(this_month, -1)
        samples = [
            (this_month, "32.50", "星巴克", "早餐"),
            (this_month + timedelta(days=2), "128.00", "盒马", "周末采购"),
            (this_month + timedelta(days=5), "12.00", "地铁", ""),
            (this_month + timedelta(days=7), "268.00", "优衣库", "换季"),
            (last_month, "88.00", "面馆", ""),
        ]
        for offset, (biz_day, amount, payee, note) in enumerate(samples):
            if biz_day > today:
                continue
            db.session.add(
                Transaction(
                    user_id=user.id,
                    biz_date=biz_day,
                    occurred_at=now_local(),
                    amount_cents=to_cents(amount),
                    direction="out",
                    category_id=categories[offset % len(categories)].id,
                    payee=payee,
                    note=note,
                )
            )
        db.session.add(
            Transaction(
                user_id=user.id,
                biz_date=this_month,
                occurred_at=now_local(),
                amount_cents=to_cents("12000"),
                direction="in",
                category_id=income.id,
                payee="月薪",
                note="",
            )
        )
        db.session.commit()

    # Convenience route used only by this script: signs the demo user in so the
    # headless browser can screenshot the authenticated dashboard.  It lives in
    # this file only; the application never registers such a route.
    from flask import redirect, request
    from flask_login import login_user
    from app.extensions import db as _db
    from app.models import User as _User

    @app.get("/__e2e/login")
    def _e2e_login():
        demo = _db.session.query(_User).filter_by(email=EMAIL).one()
        login_user(demo, remember=False)
        target = request.args.get("next", "/")
        if not target.startswith("/") or target.startswith("//"):
            target = "/"
        return redirect(target)

    return app


class Http:
    """Minimal browser-like client: cookie jar + CSRF header."""

    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar())
        )
        self.csrf: str | None = None

    def request(self, method: str, path: str, payload=None, *, raw: bool = False):
        url = path if path.startswith("http") else f"{BASE}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            if self.csrf is None:
                self.csrf = self.request("GET", "/api/auth/csrf").json()["csrf_token"]
            headers["X-CSRFToken"] = self.csrf
        request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        with self.opener.open(request, timeout=30) as response:
            body = response.read()
            status = response.status
            response_headers = response.headers
        # Login/logout rotate the session, which invalidates the CSRF token.
        if "/auth/login" in path or "/auth/register" in path or "/auth/logout" in path:
            self.csrf = None
        if raw:
            return status, body, response_headers
        return _JsonResponse(status, body, response_headers)

    def upload(self, path: str, file_path: Path, *, dry_run: bool) -> dict:
        """POST a multipart form with one CSV file, like the import page does."""
        if self.csrf is None:
            self.csrf = self.request("GET", "/api/auth/csrf").json()["csrf_token"]

        boundary = "----dailyspend-e2e-boundary"
        chunks: list[bytes] = [
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="dry_run"\r\n\r\n'
                f"{'true' if dry_run else 'false'}\r\n"
            ).encode(),
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
                "Content-Type: text/csv\r\n\r\n"
            ).encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        request = urllib.request.Request(
            f"{BASE}{path}",
            data=b"".join(chunks),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-CSRFToken": self.csrf,
            },
            method="POST",
        )
        with self.opener.open(request, timeout=60) as response:
            return json.loads(response.read().decode())


class _JsonResponse:
    def __init__(self, status: int, body: bytes, headers) -> None:
        self.status = status
        self.body = body
        self.headers = headers

    def json(self):
        return json.loads(self.body.decode())

    def text(self) -> str:
        return self.body.decode()


def find_browser() -> Path | None:
    for candidate in EDGE_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def screenshot(browser: Path, url: str, target: Path) -> bool:
    profile = TMP / f"browser-profile-{target.stem}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    command = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile}",
        "--window-size=1440,1000",
        "--virtual-time-budget=12000",
        f"--screenshot={target}",
        url,
    ]
    # No output capture: the sandbox blocks piped stdio for child processes.
    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=180,
        check=False,
    )
    return target.is_file() and target.stat().st_size > 5000, result.returncode


def main() -> int:
    app = build_app()

    import logging

    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", PORT, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(1.0)

    try:
        http = Http()

        health = http.request("GET", "/api/health")
        check("health", health.status == 200 and health.json()["database"] is True)

        login = http.request("POST", "/api/auth/login", {"email": EMAIL, "password": PASSWORD})
        check("login", login.status == 200 and login.json()["user"]["email"] == EMAIL)

        me = http.request("GET", "/api/auth/me")
        check("me", me.status == 200 and me.json()["user"]["display_name"] == "测试用户")

        categories = http.request("GET", "/api/categories").json()["items"]
        accounts = http.request("GET", "/api/accounts").json()["items"]
        check("categories seeded", len(categories) >= 10, f"{len(categories)} items")
        check("accounts seeded", len(accounts) >= 4, f"{len(accounts)} items")

        created = http.request(
            "POST",
            "/api/transactions",
            {
                "amount": "45.67",
                "category_id": categories[0]["id"],
                "account_id": accounts[0]["id"],
                "biz_date": date.today().isoformat(),
                "payee": "E2E 测试商户",
                "note": "由 e2e_smoke.py 创建",
            },
        )
        transaction_id = created.json()["transaction"]["id"] if created.status == 201 else None
        check("create transaction", created.status == 201, f"id={transaction_id}")

        listing = http.request("GET", "/api/transactions?page_size=50").json()
        check("list transactions", listing["total"] >= 5, f"total={listing['total']}")

        statement = ROOT / "backend" / "tests" / "fixtures" / "wechat_statement.csv"
        preview = http.upload("/api/imports/csv", statement, dry_run=True)
        check(
            "import preview",
            preview["source"] == "wechat" and preview["ready"] == 5 and preview["skipped"] == 2,
            f"ready={preview['ready']} skipped={preview['skipped']}",
        )
        first_import = http.upload("/api/imports/csv", statement, dry_run=False)
        check("import commit", first_import["imported"] == 5, f"imported={first_import['imported']}")
        second_import = http.upload("/api/imports/csv", statement, dry_run=False)
        check(
            "import is idempotent",
            second_import["imported"] == 0 and second_import["duplicates"] == 5,
            f"imported={second_import['imported']} duplicates={second_import['duplicates']}",
        )
        imported_rows = http.request("GET", "/api/transactions?source=wechat&page_size=50").json()
        check("imported rows are tagged", imported_rows["total"] == 5, f"total={imported_rows['total']}")

        dashboard = http.request("GET", "/api/stats/dashboard").json()
        check(
            "dashboard sections",
            set(dashboard) == {"summary", "daily", "by_category", "by_account", "monthly"},
        )
        check(
            "dashboard has expenses",
            float(dashboard["summary"]["expense"]["amount"]) > 0,
            dashboard["summary"]["expense"]["amount"],
        )
        check("daily trend filled", len(dashboard["daily"]) >= 1, f"{len(dashboard['daily'])} points")

        month = date.today().strftime("%Y-%m")
        budget = http.request(
            "PUT", "/api/budgets", {"month": month, "amount": "1000"}
        ).json()
        check(
            "set monthly budget",
            budget["status"]["total"]["amount"] == "1000.00",
            f"budget={budget['status']['total']['amount']}",
        )
        budget_status = http.request("GET", "/api/budgets").json()
        check(
            "budget tracks spending",
            budget_status["has_budget"] and float(budget_status["spent"]) > 0,
            f"spent={budget_status['spent']}",
        )

        csv_status, csv_body, csv_headers = http.request(
            "GET", "/api/exports/transactions.csv?date_from=1900-01-01", raw=True
        )
        text = csv_body.decode("utf-8-sig")
        check(
            "csv export",
            csv_status == 200
            and "日期,类型,分类,账户,金额(元),商户,备注" in text
            and "E2E 测试商户" in text,
        )

        if transaction_id:
            updated = http.request(
                "PUT", f"/api/transactions/{transaction_id}", {"note": "已更新"}
            )
            check("update transaction", updated.status == 200)
            deleted = http.request("DELETE", f"/api/transactions/{transaction_id}")
            check("delete transaction", deleted.status == 204)

            trash = http.request("GET", "/api/transactions/trash").json()
            check("trash lists the deleted row", trash["total"] >= 1, f"total={trash['total']}")
            restored = http.request("POST", f"/api/transactions/{transaction_id}/restore")
            check("restore from trash", restored.status == 200)
            trash_after = http.request("GET", "/api/transactions/trash").json()
            check(
                "restored row left the trash",
                trash_after["total"] == trash["total"] - 1,
                f"total={trash_after['total']}",
            )

        index = http.request("GET", "/", raw=True)
        html = index[1].decode()
        check("spa index served", index[0] == 200 and 'id="app"' in html)
        asset_match = re.search(r'src="(/assets/[^"]+\.js)"', html)
        if asset_match:
            asset = http.request("GET", asset_match.group(1), raw=True)
            check("spa main asset served", asset[0] == 200, f"{len(asset[1])} bytes")
        else:
            check("spa main asset served", False, "no script tag found")

        deep = http.request("GET", "/transactions", raw=True)
        check("spa history fallback", deep[0] == 200 and 'id="app"' in deep[1].decode())

        browser = find_browser()
        if browser:
            SHOT_DIR.mkdir(parents=True, exist_ok=True)
            pages = [
                ("login", f"{BASE}/login"),
                ("dashboard", f"{BASE}/__e2e/login"),
                ("transactions", f"{BASE}/__e2e/login?next=/transactions"),
                ("trash", f"{BASE}/__e2e/login?next=/trash"),
                ("budgets", f"{BASE}/__e2e/login?next=/budgets"),
                ("import", f"{BASE}/__e2e/login?next=/import"),
                ("settings", f"{BASE}/__e2e/login?next=/settings"),
            ]
            for name, url in pages:
                target = SHOT_DIR / f"{name}.png"
                ok, code = screenshot(browser, url, target)
                check(f"{name} page renders", ok, f"{target} (exit {code})")
        else:
            checks.append("SKIP browser screenshots (no Edge/Chrome found)")
    finally:
        server.shutdown()

    print("\n".join(checks))
    if failures:
        print(f"\n{len(failures)} check(s) failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"\nAll {len(checks)} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
