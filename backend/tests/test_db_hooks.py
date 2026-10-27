"""Connection-time behaviour that depends on the database dialect.

The Oracle session hook can only be exercised without a live database by
feeding it a fake DBAPI connection, which is exactly what these tests do: they
prove the hook fires for oracledb connections, issues the NLS statements, and
leaves SQLite alone.
"""

from __future__ import annotations

import sqlite3

from app.db import ORACLE_SESSION_SETTINGS, _configure_oracle_session, engine_options


class _FakeCursor:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.closed = False

    def execute(self, statement: str) -> None:
        self.log.append(statement)

    def close(self) -> None:
        self.closed = True


class _FakeOracleConnection:
    """Pretends to be ``oracledb.Connection`` (same module root)."""

    def __init__(self) -> None:
        self.executed: list[str] = []
        self.cursors: list[_FakeCursor] = []

    def cursor(self) -> _FakeCursor:
        cursor = _FakeCursor(self.executed)
        self.cursors.append(cursor)
        return cursor


_FakeOracleConnection.__module__ = "oracledb.connection"


def test_oracle_session_settings_are_applied():
    connection = _FakeOracleConnection()
    _configure_oracle_session(connection, None)

    assert connection.executed == list(ORACLE_SESSION_SETTINGS)
    assert any("NLS_LENGTH_SEMANTICS" in statement for statement in connection.executed)
    assert all(cursor.closed for cursor in connection.cursors)


def test_sqlite_connection_is_left_alone(tmp_path):
    connection = sqlite3.connect(tmp_path / "noop.sqlite3")
    try:
        # Should return immediately without touching the connection.
        _configure_oracle_session(connection, None)
        assert connection.execute("select 1").fetchone() == (1,)
    finally:
        connection.close()


def test_engine_options_are_dialect_specific():
    oracle = engine_options("oracle+oracledb://user:pwd@localhost:1521/?service_name=FREEPDB1")
    assert oracle["pool_pre_ping"] is True
    assert oracle["pool_recycle"] == 1800
    assert oracle["pool_size"] == 5

    sqlite = engine_options("sqlite:///instance/dev.sqlite3")
    assert sqlite == {"pool_pre_ping": True}
