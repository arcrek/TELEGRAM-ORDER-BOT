"""Shared prorated-refund calculation.

Extracted from src/bot/handlers/refund.py so the bot and the dashboard share
one implementation of the formula and duration parsing. Keep the arithmetic
identical across both call sites.
"""

import re
from datetime import datetime, timezone

MONTH_DAYS = 30
YEAR_DAYS = 365

# Regex for duration argument: <n><unit?>  (e.g. "30", "4w", "2months")
_DURATION_RE = re.compile(r"^(\d+)\s*([a-z]*)$", re.IGNORECASE)

# Unit → multiplier (fixed approximations).
_UNIT_MAP: dict[str, int] = {
    "": 1,
    "d": 1,
    "day": 1,
    "days": 1,
    "w": 7,
    "wk": 7,
    "wks": 7,
    "week": 7,
    "weeks": 7,
    "m": MONTH_DAYS,
    "mo": MONTH_DAYS,
    "mon": MONTH_DAYS,
    "month": MONTH_DAYS,
    "months": MONTH_DAYS,
    "y": YEAR_DAYS,
    "yr": YEAR_DAYS,
    "yrs": YEAR_DAYS,
    "year": YEAR_DAYS,
    "years": YEAR_DAYS,
}


def parse_duration_to_days(text: str) -> int | None:
    """Parse a human duration string into a number of days.

    Returns None if the input is invalid or n <= 0.
    """
    m = _DURATION_RE.match(text.strip())
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    if n <= 0 or unit not in _UNIT_MAP:
        return None
    return n * _UNIT_MAP[unit]


def combine_duration(days: int, months: int, years: int) -> int:
    """Combine day/month/year inputs into total days (month=30, year=365)."""
    return days + months * MONTH_DAYS + years * YEAR_DAYS


def compute_refund(
    order_total: int,
    duration_days: int,
    created_at: datetime,
    now: datetime | None = None,
) -> tuple[int, int, int]:
    """Compute prorated refund.

    Returns (elapsed_days, remaining_days, refund_amount). A non-positive
    duration yields (0, 0, 0). The refund is capped at order_total to guard
    floating-point edge cases.
    """
    if duration_days <= 0:
        return 0, 0, 0
    # created_at (from the DB) is naive UTC by project convention — stay naive
    # here too so the subtraction below doesn't raise on aware-vs-naive.
    ref_now = now if now is not None else datetime.now(timezone.utc).replace(tzinfo=None)
    elapsed = max(0, (ref_now - created_at).days)
    remaining = max(0, duration_days - elapsed)
    refund = round(order_total / duration_days * remaining)
    refund = min(refund, order_total)
    return elapsed, remaining, refund
