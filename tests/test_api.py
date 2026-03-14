"""Unit tests for api.py — polling and data parsing."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import UsageData, _parse_iso, fetch_usage, format_countdown

BASE = datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc)


def _future(**kwargs):
    return BASE + timedelta(**kwargs)


def _past(**kwargs):
    return BASE - timedelta(**kwargs)


# ------------------------------------------------------------------ #
#  _parse_iso                                                           #
# ------------------------------------------------------------------ #

class TestParseIso:
    def test_valid_z_suffix(self):
        result = _parse_iso("2026-03-14T10:30:00Z")
        assert result is not None
        assert result.tzinfo is not None

    def test_valid_offset(self):
        assert _parse_iso("2026-03-14T10:30:00+00:00") is not None

    def test_none_input(self):
        assert _parse_iso(None) is None

    def test_empty_string(self):
        assert _parse_iso("") is None

    def test_invalid_string(self):
        assert _parse_iso("not-a-date") is None


# ------------------------------------------------------------------ #
#  format_countdown                                                     #
# ------------------------------------------------------------------ #

class TestFormatCountdown:
    def test_none_returns_dash(self):
        assert format_countdown(None, now=BASE) == "—"

    def test_past_returns_now(self):
        assert format_countdown(_past(seconds=10), now=BASE) == "now"

    def test_under_one_minute(self):
        assert format_countdown(_future(seconds=30), now=BASE) == "< 1m"

    def test_minutes_only(self):
        assert format_countdown(_future(minutes=45), now=BASE) == "45m"

    def test_hours_and_minutes(self):
        assert format_countdown(_future(hours=2, minutes=14), now=BASE) == "2h 14m"

    def test_exact_hours(self):
        assert format_countdown(_future(hours=3), now=BASE) == "3h"

    def test_days_and_hours(self):
        assert format_countdown(_future(days=5, hours=12), now=BASE) == "5d 12h"

    def test_exact_days(self):
        assert format_countdown(_future(days=7), now=BASE) == "7d"


# ------------------------------------------------------------------ #
#  fetch_usage — via messages API with rate-limit headers               #
# ------------------------------------------------------------------ #

class TestFetchUsage:
    @patch("api.load_oauth_token", return_value="test-token")
    @patch("api.requests.post")
    def test_success_with_headers(self, mock_post, _):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {
            "anthropic-ratelimit-unified-5h-utilization": "0.67",
            "anthropic-ratelimit-unified-7d-utilization": "0.34",
            "anthropic-ratelimit-unified-5h-reset": "1773540000",
            "anthropic-ratelimit-unified-7d-reset": "1773842400",
        }
        mock_post.return_value = mock_resp

        result = fetch_usage()
        assert result is not None
        assert abs(result.five_hour_pct - 0.67) < 0.001
        assert abs(result.seven_day_pct - 0.34) < 0.001
        assert result.five_hour_reset is not None
        assert result.seven_day_reset is not None

    @patch("api.load_oauth_token", return_value=None)
    def test_no_token_returns_none(self, _):
        assert fetch_usage() is None

    @patch("api.load_oauth_token", return_value="test-token")
    @patch("api.requests.post")
    def test_401_token_expired(self, mock_post, _):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.headers = {}
        mock_post.return_value = mock_resp

        result = fetch_usage()
        assert result is None

    @patch("api.load_oauth_token", return_value="test-token")
    @patch("api.requests.post")
    def test_429_rate_limited(self, mock_post, _):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "300"}
        mock_post.return_value = mock_resp

        result = fetch_usage()
        assert result is None

    @patch("api.load_oauth_token", return_value="test-token")
    @patch("api.requests.post")
    def test_no_headers_returns_none(self, mock_post, _):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_post.return_value = mock_resp

        result = fetch_usage()
        assert result is None

    @patch("api.load_oauth_token", return_value="test-token")
    @patch("api.requests.post")
    def test_network_error(self, mock_post, _):
        import requests as _req
        mock_post.side_effect = _req.RequestException("fail")

        result = fetch_usage()
        assert result is None

    @patch("api.load_oauth_token", return_value="test-token")
    @patch("api.requests.post")
    def test_unix_timestamp_reset_parsing(self, mock_post, _):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {
            "anthropic-ratelimit-unified-5h-utilization": "0.5",
            "anthropic-ratelimit-unified-7d-utilization": "0.1",
            "anthropic-ratelimit-unified-5h-reset": "1773540000",
            "anthropic-ratelimit-unified-7d-reset": "1773842400",
        }
        mock_post.return_value = mock_resp

        result = fetch_usage()
        assert result is not None
        # Unix timestamp 1773540000 -> valid datetime
        assert result.five_hour_reset.year == 2026
