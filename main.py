#!/usr/bin/env python3
"""Claude Usage Monitor for Linux — system tray indicator for Claude API rate limits."""

import os
import signal
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure our directory is on the path regardless of how we're invoked
sys.path.insert(0, str(Path(__file__).parent))

# Ensure the Wayland display socket is set
if not os.environ.get("WAYLAND_DISPLAY"):
    os.environ["WAYLAND_DISPLAY"] = "wayland-0"

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from api import Poller, UsageData
from config import load_settings
from ui import UsageWidget

_DEMO = "--demo" in sys.argv


class App:
    def __init__(self) -> None:
        self._settings = load_settings()
        self._widget = UsageWidget(self._settings)
        self._countdown_source_id: int = 0

        if _DEMO:
            self._poller = None
        else:
            self._poller = Poller(
                interval_seconds=self._settings.poll_interval_minutes * 60,
                on_update=self._on_usage_update,
            )
        self._widget.set_refresh_callback(self._on_manual_refresh)
        self._widget.set_interval_change_callback(self._on_interval_change)

    def run(self) -> None:
        self._widget.show_all()

        if _DEMO:
            demo = UsageData(
                five_hour_pct=0.67,
                five_hour_reset=datetime.now(timezone.utc) + timedelta(hours=2, minutes=14),
                seven_day_pct=0.34,
                seven_day_reset=datetime.now(timezone.utc) + timedelta(days=5, hours=12),
            )
            self._widget.update_data(demo)
        else:
            self._poller.start()

        self._countdown_source_id = GLib.timeout_add_seconds(1, self._tick)

        GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, self._quit)
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, self._quit)

        Gtk.main()

    def _on_usage_update(self, data, error=None) -> None:
        GLib.idle_add(self._widget.update_data, data, error)

    def _tick(self) -> bool:
        GLib.idle_add(self._widget.queue_draw)
        return True

    def _on_manual_refresh(self) -> None:
        if self._poller:
            self._poller.poll_now()

    def _on_interval_change(self, minutes: int) -> None:
        if self._poller:
            self._poller.set_interval(minutes * 60)

    def _quit(self) -> bool:
        if self._poller:
            self._poller.stop()
        if self._countdown_source_id:
            GLib.source_remove(self._countdown_source_id)
        Gtk.main_quit()
        return False


def main() -> None:
    app = App()
    app.run()


if __name__ == "__main__":
    main()
