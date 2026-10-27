"""Database engine tweaks shared by development (SQLite) and production (Oracle)."""

from __future__ import annotations

import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine

from .extensions import db

#: DBAPI module roots that mean "we are talking to Oracle".
ORACLE_DRIVERS = ("oracledb", "cx_Oracle")

#: Session settings applied to every Oracle connection.
ORACLE_SESSION_SETTINGS = (
    # VARCHAR2 lengths are then counted in characters, matching `VARCHAR2(n CHAR)`
    # in the generated DDL and any hand-written `ALTER TABLE`.
    "ALTER SESSION SET NLS_LENGTH_SEMANTICS = 'CHAR'",
    "ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS'",
    "ALTER SESSION SET NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS.FF'",
)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite ignores foreign keys unless asked; do it on every connection."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@event.listens_for(Engine, "connect")
def _configure_oracle_session(dbapi_connection, _connection_record) -> None:
    """Pin NLS settings so behaviour never depends on the server's defaults."""
    module_root = type(dbapi_connection).__module__.split(".")[0]
    if module_root not in ORACLE_DRIVERS:
        return
    cursor = dbapi_connection.cursor()
    try:
        for statement in ORACLE_SESSION_SETTINGS:
            cursor.execute(statement)
    finally:
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
