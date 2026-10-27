"""Database engine tweaks shared by development (SQLite) and production (Oracle)."""

from __future__ import annotations

import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine

from .extensions import db


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite ignores foreign keys unless asked; do it on every connection."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def configure_driver_defaults() -> None:
    """Tune the Oracle driver so CLOB columns come back as plain ``str``.

    Without this, ``note`` (``Text`` -> ``CLOB``) is returned as a LOB handle and
    JSON serialisation fails.  The call is a no-op when ``oracledb`` is not
    installed, so SQLite-only setups never pay for it.
    """
    try:
        import oracledb
    except ImportError:  # pragma: no cover - only hit on pure-SQLite installs
        return

    oracledb.defaults.fetch_lobs = False


def engine_options(database_url: str) -> dict:
    """Per-dialect engine options.

    Oracle needs a shorter pool recycle (otherwise idle sessions hit
    ``ORA-02396``) and a bounded pool; SQLite rejects those arguments entirely,
    which is why the options are conditional.
    """
    options: dict = {"pool_pre_ping": True}
    if database_url.startswith("oracle"):
        options.update(
            {
                "pool_size": 5,
                "max_overflow": 5,
                "pool_recycle": 1800,
                "pool_timeout": 30,
            }
        )
    return options


def check_database_connection() -> bool:
    """Return ``True`` when a trivial query round-trips.

    ``select(1)`` is rendered as ``SELECT 1 FROM DUAL`` on Oracle, so the same
    probe keeps working after the switch.
    """
    from sqlalchemy import literal, select

    db.session.execute(select(literal(1))).scalar_one()
    return True
