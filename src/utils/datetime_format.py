"""
Datetime formatting utilities for timezone-aware display.

All datetime values stored in the DB are naive UTC.
- to_utc_iso: normalizes naive → UTC-aware and emits ISO 8601 with +00:00
- resolve_tz / now_local / format_local: bot-side helpers using stdlib zoneinfo
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

_DEFAULT_TZ_NAME = "Asia/Ho_Chi_Minh"


# ---------------------------------------------------------------------------
# API serialization helper
# ---------------------------------------------------------------------------


def to_utc_iso(dt: datetime | None) -> str | None:
    """Serialize a datetime to a UTC-aware ISO 8601 string (e.g. 2026-06-16T10:30:00+00:00).

    - None → None
    - naive datetime → assumed UTC, tzinfo attached, .isoformat() returned
    - aware datetime → converted to UTC, .isoformat() returned
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Bot timezone helpers
# ---------------------------------------------------------------------------


def resolve_tz(name: str) -> ZoneInfo:
    """Return a ZoneInfo for the given IANA name.

    Falls back to Asia/Ho_Chi_Minh on any error and logs a warning.
    """
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        logger.warning(
            "Unknown timezone %r — falling back to %s", name, _DEFAULT_TZ_NAME
        )
        return ZoneInfo(_DEFAULT_TZ_NAME)


def now_local(tz: ZoneInfo) -> datetime:
    """Return the current time as an aware datetime in the given timezone."""
    return datetime.now(tz=tz)


def format_local(dt: datetime, tz: ZoneInfo, fmt: str = "%Y-%m-%d %H:%M %Z") -> str:
    """Format a datetime in the given timezone.

    Treats naive datetimes as UTC before converting.
    The default format appends the abbreviated zone name so users see the zone.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(tz)
    return local_dt.strftime(fmt)


def validate_timezone(name: str) -> bool:
    """Return True if name is a valid IANA timezone, False otherwise.

    Validates by attempting to construct a ZoneInfo, which accepts timezone
    *aliases* (e.g. 'Asia/Saigon' → 'Asia/Ho_Chi_Minh') in addition to
    canonical names. A plain membership check against available_timezones()
    would reject valid aliases and is also sensitive to whether the host's
    tz database lists them. Requires the `tzdata` package for a complete,
    portable database (see requirements.txt).
    """
    if not name:
        return False
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return False
