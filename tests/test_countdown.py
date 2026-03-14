"""Focused tests for format_countdown edge cases (fixed reference time)."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import format_countdown

# Fixed "now" so tests are deterministic
BASE = datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc)


def _f(**kwargs) -> datetime:
    return BASE + timedelta(**kwargs)


def _p(**kwargs) -> datetime:
    return BASE - timedelta(**kwargs)


class TestFormatCountdownEdgeCases:
    def test_exactly_now(self):
        assert format_countdown(BASE, now=BASE) == "now"

    def test_one_second_future(self):
        assert format_countdown(_f(seconds=1), now=BASE) == "< 1m"

    def test_59_seconds(self):
        assert format_countdown(_f(seconds=59), now=BASE) == "< 1m"

    def test_exactly_one_minute(self):
        assert format_countdown(_f(minutes=1), now=BASE) == "1m"

    def test_exactly_one_hour(self):
        assert format_countdown(_f(hours=1), now=BASE) == "1h"

    def test_one_hour_one_minute(self):
        assert format_countdown(_f(hours=1, minutes=1), now=BASE) == "1h 1m"

    def test_large_minutes(self):
        assert format_countdown(_f(minutes=59), now=BASE) == "59m"

    def test_exactly_one_day(self):
        assert format_countdown(_f(days=1), now=BASE) == "1d"

    def test_max_plausible_seven_days(self):
        assert format_countdown(_f(days=7), now=BASE) == "7d"

    def test_past_datetime(self):
        assert format_countdown(_p(hours=1), now=BASE) == "now"

    def test_none(self):
        assert format_countdown(None, now=BASE) == "—"

    @pytest.mark.parametrize("hours,expected", [
        (2,  "2h"),
        (23, "23h"),
    ])
    def test_whole_hours(self, hours, expected):
        assert format_countdown(_f(hours=hours), now=BASE) == expected

    @pytest.mark.parametrize("days,hours,expected", [
        (1, 0,  "1d"),
        (1, 6,  "1d 6h"),
        (3, 12, "3d 12h"),
        (6, 23, "6d 23h"),
    ])
    def test_days_and_hours(self, days, hours, expected):
        assert format_countdown(_f(days=days, hours=hours), now=BASE) == expected

    @pytest.mark.parametrize("hours,minutes,expected", [
        (1, 30, "1h 30m"),
        (2, 14, "2h 14m"),
        (0, 45, "45m"),
    ])
    def test_hours_and_minutes(self, hours, minutes, expected):
        assert format_countdown(_f(hours=hours, minutes=minutes), now=BASE) == expected
