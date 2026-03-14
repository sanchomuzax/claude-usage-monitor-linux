"""Anthropic API polling for rate-limit utilization data."""

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

from config import load_oauth_token

_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_ANTHROPIC_BETA = "oauth-2025-04-20"
_TIMEOUT = 15  # seconds


@dataclass
class UsageData:
    five_hour_pct: float        # 0.0 – 1.0
    five_hour_reset: Optional[datetime]
    seven_day_pct: float        # 0.0 – 1.0
    seven_day_reset: Optional[datetime]


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # Python 3.11+ handles Z; older needs explicit replacement
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _fetch_usage_from_headers(token: str) -> tuple:
    """Make a minimal messages call with OAuth beta header, parse rate-limit
    headers from the response. This is how the Claude CLI gets usage data.

    Returns (UsageData | None, error_string | None).
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-version": _ANTHROPIC_VERSION,
        "anthropic-beta": _ANTHROPIC_BETA,
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }
    try:
        resp = requests.post(
            _MESSAGES_URL, headers=headers, json=payload, timeout=_TIMEOUT
        )
        if resp.status_code == 401:
            return None, "token_expired"
        if resp.status_code == 429:
            retry = resp.headers.get("Retry-After", "?")
            try:
                mins = int(retry) // 60
                return None, f"Rate limited ({mins}m)"
            except ValueError:
                return None, "Rate limited"

        h = resp.headers
        fh_pct = h.get("anthropic-ratelimit-unified-5h-utilization")
        sd_pct = h.get("anthropic-ratelimit-unified-7d-utilization")
        fh_reset = h.get("anthropic-ratelimit-unified-5h-reset")
        sd_reset = h.get("anthropic-ratelimit-unified-7d-reset")

        if fh_pct is None and sd_pct is None:
            return None, "No rate-limit headers"

        # Reset values are unix timestamps (seconds), not ISO strings
        def _parse_ts(val):
            if not val:
                return None
            try:
                return datetime.fromtimestamp(int(val), tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                return _parse_iso(val)

        return UsageData(
            five_hour_pct=float(fh_pct) if fh_pct is not None else 0.0,
            five_hour_reset=_parse_ts(fh_reset),
            seven_day_pct=float(sd_pct) if sd_pct is not None else 0.0,
            seven_day_reset=_parse_ts(sd_reset),
        ), None
    except requests.RequestException as e:
        return None, str(e)[:80]


def fetch_usage_with_error() -> tuple:
    """Returns (UsageData | None, error_string | None)."""
    token = load_oauth_token()
    if not token:
        return None, "No credentials found"

    data, err = _fetch_usage_from_headers(token)
    if data is not None:
        return data, None

    # If token expired, re-read (Claude CLI may have refreshed it)
    if err == "token_expired":
        token = load_oauth_token()
        if not token:
            return None, "No credentials found"
        data, err = _fetch_usage_from_headers(token)
        if data is not None:
            return data, None

    return None, err or "API unavailable"


def fetch_usage() -> Optional[UsageData]:
    """Fetch usage data, trying primary endpoint then fallback."""
    data, _ = fetch_usage_with_error()
    return data


def format_countdown(
    reset: Optional[datetime],
    now: Optional[datetime] = None,
) -> str:
    """Return a human-readable countdown string to the given UTC datetime.

    The optional `now` parameter exists for testing; it defaults to the
    current UTC time when omitted.
    """
    if reset is None:
        return "—"
    if now is None:
        now = datetime.now(timezone.utc)
    delta = reset - now
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "now"
    if total_seconds < 60:
        return "< 1m"
    minutes = total_seconds // 60
    hours = minutes // 60
    days = hours // 24
    if days > 0:
        remaining_hours = hours % 24
        if remaining_hours:
            return f"{days}d {remaining_hours}h"
        return f"{days}d"
    if hours > 0:
        remaining_minutes = minutes % 60
        if remaining_minutes:
            return f"{hours}h {remaining_minutes}m"
        return f"{hours}h"
    return f"{minutes}m"


class Poller:
    """Background polling thread that calls `on_update` with fresh UsageData."""

    def __init__(
        self,
        interval_seconds: int,
        on_update: Callable[[Optional[UsageData], Optional[str]], None],
    ) -> None:
        self._interval = interval_seconds
        self._on_update = on_update
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def poll_now(self) -> None:
        """Trigger an immediate poll in a one-shot daemon thread."""
        threading.Thread(target=self._do_poll, daemon=True).start()

    def set_interval(self, interval_seconds: int) -> None:
        self._interval = interval_seconds

    def _run(self) -> None:
        # Poll immediately on start, then on each interval
        self._do_poll()
        while not self._stop_event.wait(self._interval):
            self._do_poll()

    def _do_poll(self) -> None:
        data, error = fetch_usage_with_error()
        self._on_update(data, error)
