"""Money helpers.

Amounts are persisted as integer cents.  That keeps SQLite and Oracle byte-for-
byte compatible, avoids binary-float drift, and sidesteps the two databases'
different decimal round-tripping rules.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def to_cents(amount: Decimal | int | str) -> int:
    value = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_cents(cents: int) -> str:
    """Render cents as a fixed two-decimal amount string (``1234`` -> ``"12.34"``)."""
    return str((Decimal(cents) / 100).quantize(Decimal("0.01")))
