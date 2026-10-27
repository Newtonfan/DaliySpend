"""Check a live Oracle database against the application schema.

Reads ``DS_DATABASE_URL`` (same variable the app uses) and reports:

* the Oracle version / current schema the app connects as;
* which expected tables exist and how many rows each holds;

It is read-only, so it is safe to run against a real database at any time.

Usage (PowerShell):

    $env:DS_DATABASE_URL = 'oracle+oracledb://dailyspend:pwd@localhost:1521/?service_name=FREEPDB1'
    scripts\\dev.ps1 ..\\scripts\\oracle_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

EXPECTED_TABLES = ["users", "categories", "accounts", "transactions", "alembic_version"]


def main() -> int:
    from sqlalchemy import inspect, text

    from app import create_app
    from app.config import get_settings
    from app.db import check_database_connection
    from app.extensions import db

    settings = get_settings()
    url = settings.resolve_database_url()

    if not url.startswith("oracle"):
        print(f"DS_DATABASE_URL is not an Oracle URL: {url}")
        print("Set DS_DATABASE_URL to an oracle+oracledb:// URL first.")
        return 2

    masked = url.split("@")[-1] if "@" in url else url
    print(f"target      : {masked}")
    print(f"timezone    : {settings.timezone}")

    app = create_app()
    with app.app_context():
        try:
            check_database_connection()
        except Exception as exc:  # noqa: BLE001 - report instead of a traceback
            print(f"connect FAILED: {type(exc).__name__}: {exc}")
            return 1

        version_text = None
        for query in (
            "select banner from v$version where rownum = 1",
            "select version from product_component_version where product like 'Oracle Database%'",
        ):
            try:
                row = db.session.execute(text(query)).first()
                if row:
                    version_text = str(row[0])
                    break
            except Exception:  # noqa: BLE001 - v$version needs extra grants
                db.session.rollback()
        if version_text is None:
            version_text = str(db.engine.dialect.server_version_info)
        print(f"version     : {version_text}")

        who = db.session.execute(
            text("select sys_context('userenv','current_user'), sys_context('userenv','db_name') from dual")
        ).one()
        print(f"schema/user : {who[0]}  (db={who[1]})")

        tables = sorted(inspect(db.engine).get_table_names())
        print(f"tables      : {len(tables)} -> {', '.join(tables) or '(none)'}")

        missing = [name for name in EXPECTED_TABLES if name not in tables]
        if missing:
            print(f"MISSING     : {', '.join(missing)}")
            print("Run: scripts\\dev.ps1 -m flask --app wsgi:app db upgrade")
            return 1

        for name in EXPECTED_TABLES:
            # SQLAlchemy created quoted lowercase identifiers, so raw SQL has to
            # quote them too.
            count = db.session.execute(text(f'select count(*) from "{name}"')).scalar_one()
            print(f"  {name:<18} {count} rows")

        version = db.session.execute(
            text('select version_num from "alembic_version"')
        ).scalar_one_or_none()
        print(f"migration   : {version}")

    print("\nOracle connection looks good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

