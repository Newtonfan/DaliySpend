"""Database engine tweaks shared by development and tests."""

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


def check_database_connection() -> bool:
    """Return ``True`` when a trivial query round-trips.

    ``select(1)`` is rendered as ``SELECT 1 FROM DUAL`` on Oracle, so the same
    probe keeps working after the switch.
    """
    from sqlalchemy import literal, select

    db.session.execute(select(literal(1))).scalar_one()
    return True
