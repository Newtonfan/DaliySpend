"""In-memory login throttling.

Good enough for a single-process personal deployment and it keeps the login
endpoint from being brute-forced.  Swapping this for Redis (or Flask-Limiter)
is a local change once the site runs on more than one worker.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..utils.time import now_local


@dataclass
class _Bucket:
    failures: int = 0
    first_failure_at: datetime | None = None
    locked_until: datetime | None = None


@dataclass
class AttemptLimiter:
    max_failures: int = 5
    window: timedelta = timedelta(minutes=15)
    lockout: timedelta = timedelta(minutes=15)
    _buckets: dict[str, _Bucket] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _bucket(self, key: str) -> _Bucket:
        return self._buckets.setdefault(key, _Bucket())

    def retry_after(self, key: str) -> int | None:
        """Seconds until ``key`` may try again, or ``None`` when allowed."""
        with self._lock:
            bucket = self._bucket(key)
            now = now_local()
            if bucket.locked_until and bucket.locked_until > now:
                return int((bucket.locked_until - now).total_seconds()) + 1
            if bucket.locked_until and bucket.locked_until <= now:
                self._buckets.pop(key, None)
            return None

    def register_failure(self, key: str) -> None:
        with self._lock:
            bucket = self._bucket(key)
            now = now_local()
            if bucket.first_failure_at is None or now - bucket.first_failure_at > self.window:
                bucket.failures = 0
                bucket.first_failure_at = now
            bucket.failures += 1
            if bucket.failures >= self.max_failures:
                bucket.locked_until = now + self.lockout
                bucket.failures = 0
                bucket.first_failure_at = None

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)


login_limiter = AttemptLimiter()
