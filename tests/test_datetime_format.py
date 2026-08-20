"""
Unit tests for src/utils/datetime_format.py
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.utils.datetime_format import (
    format_local,
    now_local,
    resolve_tz,
    to_utc_iso,
    validate_timezone,
)

# ---------------------------------------------------------------------------
# to_utc_iso
# ---------------------------------------------------------------------------


class TestToUtcIso:
    def test_none_returns_none(self):
        assert to_utc_iso(None) is None

    def test_naive_datetime_becomes_utc(self):
        dt = datetime(2026, 6, 16, 10, 30, 0)  # naive
        result = to_utc_iso(dt)
        assert result == "2026-06-16T10:30:00+00:00"

    def test_utc_aware_is_unchanged(self):
        dt = datetime(2026, 6, 16, 10, 30, 0, tzinfo=timezone.utc)
        result = to_utc_iso(dt)
        assert result == "2026-06-16T10:30:00+00:00"

    def test_aware_non_utc_converted_to_utc(self):
        # UTC+7 → subtract 7 hours
        vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
        dt = datetime(2026, 6, 16, 17, 30, 0, tzinfo=vn_tz)  # 17:30 VN = 10:30 UTC
        result = to_utc_iso(dt)
        assert result is not None
        assert result.endswith("+00:00")
        # parse back and confirm UTC value
        from datetime import datetime as dt2

        parsed = dt2.fromisoformat(result)
        assert parsed.utctimetuple()[:6] == (2026, 6, 16, 10, 30, 0)

    def test_result_is_string(self):
        dt = datetime(2026, 1, 1)
        result = to_utc_iso(dt)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# resolve_tz
# ---------------------------------------------------------------------------


class TestResolveTz:
    def test_valid_tz_returns_zoneinfo(self):
        tz = resolve_tz("Asia/Ho_Chi_Minh")
        assert str(tz) == "Asia/Ho_Chi_Minh"

    def test_invalid_tz_falls_back(self):
        tz = resolve_tz("Not/A/Real/Timezone")
        assert str(tz) == "Asia/Ho_Chi_Minh"

    def test_utc_works(self):
        tz = resolve_tz("UTC")
        assert str(tz) == "UTC"


# ---------------------------------------------------------------------------
# now_local
# ---------------------------------------------------------------------------


class TestNowLocal:
    def test_now_local_returns_aware_datetime(self):
        tz = ZoneInfo("Asia/Ho_Chi_Minh")
        result = now_local(tz)
        assert result.tzinfo is not None

    def test_now_local_correct_tz(self):
        tz = ZoneInfo("Asia/Ho_Chi_Minh")
        result = now_local(tz)
        assert result.tzinfo == tz or str(result.tzinfo) == "Asia/Ho_Chi_Minh"

    def test_now_local_fixed_offset_zone(self):
        # UTC+0 should give same hour as UTC
        utc_tz = ZoneInfo("UTC")
        result = now_local(utc_tz)
        utc_now = datetime.now(tz=timezone.utc)
        # Within a few seconds
        assert abs((result - utc_now).total_seconds()) < 5


# ---------------------------------------------------------------------------
# format_local
# ---------------------------------------------------------------------------


class TestFormatLocal:
    def test_naive_datetime_treated_as_utc(self):
        # 2026-06-16 03:30:00 naive (UTC) → UTC+7 → 10:30
        vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
        naive_utc = datetime(2026, 6, 16, 3, 30, 0)
        result = format_local(naive_utc, vn_tz, fmt="%H:%M")
        assert result == "10:30"

    def test_aware_utc_converted(self):
        vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
        aware_utc = datetime(2026, 6, 16, 3, 30, 0, tzinfo=timezone.utc)
        result = format_local(aware_utc, vn_tz, fmt="%H:%M")
        assert result == "10:30"

    def test_default_format_includes_zone(self):
        vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
        dt = datetime(2026, 6, 16, 0, 0, 0, tzinfo=timezone.utc)
        result = format_local(dt, vn_tz)
        # Default format is "%Y-%m-%d %H:%M %Z" — should include zone abbreviation
        assert "2026" in result
        assert "07:00" in result  # UTC+7

    def test_fixed_offset_zone(self):
        # Test with a fixed UTC+5:30 (Asia/Kolkata) to cover non-integer offset
        kolkata = ZoneInfo("Asia/Kolkata")
        naive_utc = datetime(2026, 6, 16, 0, 0, 0)
        result = format_local(naive_utc, kolkata, fmt="%H:%M")
        assert result == "05:30"

    def test_dst_zone(self):
        # America/New_York in summer (EDT = UTC-4)
        ny_tz = ZoneInfo("America/New_York")
        # June 16, 2026 12:00 UTC → 08:00 EDT
        dt = datetime(2026, 6, 16, 12, 0, 0, tzinfo=timezone.utc)
        result = format_local(dt, ny_tz, fmt="%H:%M")
        assert result == "08:00"

    def test_dst_zone_winter(self):
        # America/New_York in winter (EST = UTC-5)
        ny_tz = ZoneInfo("America/New_York")
        # Jan 16, 2026 12:00 UTC → 07:00 EST
        dt = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        result = format_local(dt, ny_tz, fmt="%H:%M")
        assert result == "07:00"


# ---------------------------------------------------------------------------
# validate_timezone
# ---------------------------------------------------------------------------


class TestValidateTimezone:
    def test_valid_returns_true(self):
        assert validate_timezone("Asia/Ho_Chi_Minh") is True
        assert validate_timezone("UTC") is True
        assert validate_timezone("America/New_York") is True

    def test_invalid_returns_false(self):
        assert validate_timezone("Not/A/Timezone") is False
        assert validate_timezone("") is False
        assert validate_timezone("Europe/FakeCity") is False

    def test_aliases_are_accepted(self):
        # Aliases are absent from available_timezones() but resolvable by
        # ZoneInfo; the browser may offer them (e.g. Intl.supportedValuesOf).
        assert validate_timezone("Asia/Saigon") is True
        assert validate_timezone("US/Pacific") is True
