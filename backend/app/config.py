"""Application configuration.

Values come from environment variables prefixed with ``DS_`` (optionally from a
``.env`` file at the repository root).  Keeping the settings in one place means
moving from SQLite to Oracle later is a one-line change of ``DS_DATABASE_URL``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
INSTANCE_DIR = REPO_ROOT / "instance"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DS_",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "DailySpend"
    debug: bool = False
    secret_key: str = "dev-secret-change-me"

    # ``sqlite:///instance/dailyspend.sqlite3`` today, later e.g.
    # ``oracle+oracledb://dailyspend:pwd@localhost:1521/?service_name=FREEPDB1``
    database_url: str = "sqlite:///instance/dailyspend.sqlite3"

    #: IANA timezone used to decide "today" and to stamp audit columns.
    timezone: str = "Asia/Shanghai"

    #: Sign-in/session hardening.  Turn ``session_cookie_secure`` on once the
    #: site is served over HTTPS in production.
    session_lifetime_days: int = 14
    session_cookie_secure: bool = False

    #: Open registration.  Disable it (``DS_REGISTRATION_ENABLED=false``) if the
    #: site is reachable from the internet and accounts must be created by hand.
    registration_enabled: bool = True

    #: Password policy.
    password_min_length: int = 8

    def resolve_database_url(self) -> str:
        """Return a database URL with a relative SQLite path anchored to the repo."""
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            raw = self.database_url[len(prefix) :]
            if raw and not Path(raw).is_absolute():
                return f"{prefix}{(REPO_ROOT / raw).as_posix()}"
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
