"""Migrations must reproduce the models exactly.

These run on SQLite (no Oracle needed) but they guard the thing that would
otherwise only surface during the Oracle switch-over: a model change that never
made it into a migration.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db

BACKEND = Path(__file__).resolve().parents[1]
MIGRATIONS = BACKEND / "migrations"

EXPECTED_TABLES = {"users", "categories", "accounts", "transactions", "budgets"}


def _fresh_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'migrated.sqlite3').as_posix()}",
            "WTF_CSRF_ENABLED": False,
            "SERVE_FRONTEND": False,
        }
    )


def _head_revision() -> str:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    return ScriptDirectory.from_config(config).get_current_head()


def test_migrations_create_every_table_from_scratch(tmp_path):
    from flask_migrate import upgrade

    app = _fresh_app(tmp_path)
    with app.app_context():
        upgrade(directory=str(MIGRATIONS))

        tables = set(inspect(db.engine).get_table_names())
        assert EXPECTED_TABLES <= tables
        assert "alembic_version" in tables

        revision = db.session.execute(text("select version_num from alembic_version")).scalar_one()
        assert revision == _head_revision()


def test_no_pending_migration_diff(tmp_path):
    """`flask db check` equivalent: metadata and schema must agree."""
    from flask_migrate import check, upgrade

    app = _fresh_app(tmp_path)
    with app.app_context():
        upgrade(directory=str(MIGRATIONS))
        try:
            check(directory=str(MIGRATIONS))
        except Exception as exc:  # noqa: BLE001 - any diff is a failure
            pytest.fail(
                "models and migrations diverged; run "
                f"'flask db migrate -m ...' and re-render the Oracle DDL: {exc}"
            )


def test_every_model_table_is_migrated(tmp_path):
    from flask_migrate import upgrade

    app = _fresh_app(tmp_path)
    with app.app_context():
        upgrade(directory=str(MIGRATIONS))
        tables = set(inspect(db.engine).get_table_names())
        missing = set(db.metadata.tables) - tables
        assert not missing, f"tables in models but not in migrations: {sorted(missing)}"
