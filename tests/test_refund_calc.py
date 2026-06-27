"""Tests for the shared prorated-refund calculation util."""
from datetime import datetime

from src.utils.refund_calc import (
    MONTH_DAYS,
    YEAR_DAYS,
    combine_duration,
    compute_refund,
    parse_duration_to_days,
)


def test_combine_duration_uses_fixed_multipliers():
    assert combine_duration(5, 0, 0) == 5
    assert combine_duration(0, 1, 0) == MONTH_DAYS
    assert combine_duration(0, 0, 1) == YEAR_DAYS
    assert combine_duration(3, 2, 1) == 3 + 2 * MONTH_DAYS + 1 * YEAR_DAYS


def test_parse_duration_units():
    assert parse_duration_to_days("30") == 30
    assert parse_duration_to_days("4w") == 28
    assert parse_duration_to_days("1m") == 30
    assert parse_duration_to_days("2months") == 60
    assert parse_duration_to_days("1y") == 365


def test_parse_duration_invalid():
    assert parse_duration_to_days("0") is None
    assert parse_duration_to_days("abc") is None
    assert parse_duration_to_days("-5") is None
    assert parse_duration_to_days("10x") is None


def test_compute_refund_half_elapsed():
    created = datetime(2026, 1, 1)
    now = datetime(2026, 1, 16)  # 15 days elapsed
    elapsed, remaining, refund = compute_refund(300000, 30, created, now=now)
    assert elapsed == 15
    assert remaining == 15
    assert refund == 150000


def test_compute_refund_expired_returns_zero():
    created = datetime(2026, 1, 1)
    now = datetime(2026, 3, 1)  # well past 30 days
    elapsed, remaining, refund = compute_refund(300000, 30, created, now=now)
    assert remaining == 0
    assert refund == 0


def test_compute_refund_caps_at_total():
    created = datetime(2026, 1, 10)
    now = datetime(2026, 1, 1)  # future created → elapsed clamps to 0
    _, _, refund = compute_refund(100000, 30, created, now=now)
    assert refund == 100000


def test_compute_refund_zero_duration_is_safe():
    created = datetime(2026, 1, 1)
    now = datetime(2026, 1, 5)
    assert compute_refund(100000, 0, created, now=now) == (0, 0, 0)
