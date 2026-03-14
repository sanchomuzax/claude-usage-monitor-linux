"""Settings and credentials management for Claude Usage Monitor."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
SETTINGS_DIR = Path.home() / ".config" / "claude-usage-monitor"
SETTINGS_PATH = SETTINGS_DIR / "settings.json"

DEFAULTS: dict = {
    "poll_interval_minutes": 15,
    "x": 100,
    "y": 100,
    "theme": "auto",
}


@dataclass
class Settings:
    poll_interval_minutes: int = 15
    x: int = 100
    y: int = 100
    theme: str = "auto"


def load_settings() -> Settings:
    """Load settings from disk, falling back to defaults."""
    if not SETTINGS_PATH.exists():
        return Settings(**DEFAULTS)
    try:
        with SETTINGS_PATH.open() as f:
            data = json.load(f)
        merged = {**DEFAULTS, **data}
        return Settings(
            poll_interval_minutes=int(merged["poll_interval_minutes"]),
            x=int(merged["x"]),
            y=int(merged["y"]),
            theme=str(merged["theme"]),
        )
    except Exception:
        return Settings(**DEFAULTS)


def save_settings(settings: Settings) -> None:
    """Persist settings to disk."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "poll_interval_minutes": settings.poll_interval_minutes,
        "x": settings.x,
        "y": settings.y,
        "theme": settings.theme,
    }
    with SETTINGS_PATH.open("w") as f:
        json.dump(data, f, indent=2)


def load_oauth_token() -> Optional[str]:
    """Read the OAuth access token from the Claude CLI credentials file."""
    if not CREDENTIALS_PATH.exists():
        return None
    try:
        with CREDENTIALS_PATH.open() as f:
            data = json.load(f)
        oauth = data.get("claudeAiOauth")
        if not oauth:
            return None
        # claudeAiOauth may be a dict with an accessToken, or a bare string
        if isinstance(oauth, dict):
            return oauth.get("accessToken")
        return str(oauth)
    except Exception:
        return None
