"""System tray indicator for Claude usage — renders into the wf-panel-pi tray.

Dynamically generates icons into ~/.local/share/icons/hicolor/ so the
panel's SNI tray can find them by theme name (the ONLY way wf-panel-pi
renders custom icons).
"""

import cairo
import fcntl
import math
import os
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "3.0")

try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3
except (ValueError, ImportError):
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3

from gi.repository import Gtk, GLib

from api import UsageData, format_countdown
from config import Settings, save_settings

from version import __app_id__ as APP_ID, __app_name__ as APP_NAME
_LOCK_FH = None

# Icon theme directory (user-local, no sudo needed)
_ICON_BASE = Path.home() / ".local" / "share" / "icons" / "hicolor"
_ICON_DIR = _ICON_BASE / "32x32" / "apps"
_ICON_PREFIX = "claude-usage-"
_ICON_COUNTER = 0

# Segment bar config
_NUM_SEGS = 10
_SEG_W = 5
_SEG_H = 5
_SEG_GAP = 1

# Anthropic brand palette — matches the Windows Claude Code Usage Monitor
_ACCENT = (0.851, 0.467, 0.341)   # #D97757 — Anthropic coral-orange
_WARN = (0.85, 0.2, 0.2)          # Red for >90% usage
_EMPTY = (0.267, 0.267, 0.267)    # #444444
_TEXT_W = (0.533, 0.533, 0.533)   # #888888
_DIM = (0.533, 0.533, 0.533)      # #888888
_BG = (0.11, 0.11, 0.11)          # #1C1C1C

_AUTOSTART_DIR = Path.home() / ".config" / "autostart"
_AUTOSTART_FILE = _AUTOSTART_DIR / "claude-usage-monitor.desktop"
_MONITOR_DIR = Path(__file__).parent.resolve()


def _acquire_single_instance_lock():
    global _LOCK_FH
    lock_path = f"/tmp/{APP_ID}.{os.getuid()}.lock"
    try:
        _LOCK_FH = open(lock_path, "w")
        fcntl.flock(_LOCK_FH.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _seg_color(pct):
    if pct > 0.9:
        return _WARN
    return _ACCENT


def _render_icon(data: Optional[UsageData], error: Optional[str] = None) -> str:
    """Render a 32x32 square icon into hicolor theme. Returns theme name."""
    global _ICON_COUNTER
    _ICON_COUNTER += 1

    _ICON_DIR.mkdir(parents=True, exist_ok=True)

    S = 32
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, S, S)
    cr = cairo.Context(surface)

    # Transparent background
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.set_source_rgba(0, 0, 0, 0)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)

    # Dark rounded background
    r = 4
    cr.new_path()
    cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
    cr.arc(S - r, r, r, 3 * math.pi / 2, 0)
    cr.arc(S - r, S - r, r, 0, math.pi / 2)
    cr.arc(r, S - r, r, math.pi / 2, math.pi)
    cr.close_path()
    cr.set_source_rgb(*_BG)
    cr.fill()

    if data is None:
        # Loading/error: "?" centered
        cr.set_source_rgb(*_DIM)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(20)
        ext = cr.text_extents("?")
        cr.move_to((S - ext.width) / 2 - ext.x_bearing, (S - ext.height) / 2 - ext.y_bearing)
        cr.show_text("?")
    else:
        # Two rows: percentage + mini bar
        _draw_icon_row(cr, y=2, pct=data.five_hour_pct, label="5h")
        _draw_icon_row(cr, y=17, pct=data.seven_day_pct, label="7d")

    icon_name = f"{_ICON_PREFIX}{_ICON_COUNTER}"
    icon_path = _ICON_DIR / f"{icon_name}.png"
    surface.write_to_png(str(icon_path))

    # Cleanup old
    for old in _ICON_DIR.glob(f"{_ICON_PREFIX}*.png"):
        if old.name != f"{icon_name}.png":
            try:
                old.unlink()
            except OSError:
                pass

    # Update GTK icon cache so the panel can find the new icon by name
    import subprocess
    subprocess.run(
        ["gtk-update-icon-cache", "-f", "-t", str(_ICON_BASE)],
        capture_output=True, timeout=5,
    )

    return icon_name


def _draw_icon_row(cr, y: int, pct: float, label: str) -> None:
    """Draw one row in the 32x32 icon: '5h 67%' + mini segmented bar."""
    fill_col = _seg_color(pct)

    # Label + percentage text
    pct_val = int(round(pct * 100))
    text = f"{pct_val}%"

    cr.set_source_rgb(*_TEXT_W)
    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(9)
    cr.move_to(2, y + 8)
    cr.show_text(text)

    # Mini segmented bar (5 segments, right-aligned)
    num = 5
    seg_w = 3
    seg_h = 3
    gap = 1
    total_w = num * (seg_w + gap) - gap
    bar_x = 32 - total_w - 2
    bar_y = y + 9
    filled = int(round(pct * num))

    for i in range(num):
        sx = bar_x + i * (seg_w + gap)
        cr.set_source_rgb(*(fill_col if i < filled else _EMPTY))
        cr.rectangle(sx, bar_y, seg_w, seg_h)
        cr.fill()


class UsageWidget:
    """System tray indicator — same AppIndicator3 pattern as grim-tray.py."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._data: Optional[UsageData] = None
        self._last_error: Optional[str] = None

        # Initial icon in hicolor theme
        icon_name = _render_icon(None)

        self._indicator = AppIndicator3.Indicator.new(
            APP_ID,
            icon_name,
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        # NO set_icon_theme_path — icons are in ~/.local/share/icons/hicolor/
        # which is already in the default GTK icon search path
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self._indicator.set_title(APP_NAME)
        self._indicator.set_menu(self._build_menu())

    def _build_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()

        self._item_5h = Gtk.MenuItem(label="5h: —")
        self._item_5h.set_sensitive(False)
        menu.append(self._item_5h)

        self._item_7d = Gtk.MenuItem(label="7d: —")
        self._item_7d.set_sensitive(False)
        menu.append(self._item_7d)

        menu.append(Gtk.SeparatorMenuItem())

        item_refresh = Gtk.MenuItem(label="Refresh Now")
        item_refresh.connect("activate", lambda _: self._trigger_refresh())
        menu.append(item_refresh)

        menu.append(Gtk.SeparatorMenuItem())

        item_interval = Gtk.MenuItem(label="Update Interval")
        sub = Gtk.Menu()
        group = []
        for minutes, lbl in [(5, "5 min"), (15, "15 min"),
                              (30, "30 min"), (60, "60 min")]:
            ri = Gtk.RadioMenuItem.new_with_label(group, lbl)
            group = ri.get_group()
            ri.set_active(minutes == self._settings.poll_interval_minutes)
            ri.connect("toggled", self._on_interval_toggled, minutes)
            sub.append(ri)
        item_interval.set_submenu(sub)
        menu.append(item_interval)

        menu.append(Gtk.SeparatorMenuItem())

        self._item_autostart = Gtk.CheckMenuItem(label="Start on Login")
        self._item_autostart.set_active(_AUTOSTART_FILE.exists())
        self._item_autostart.connect("toggled", self._on_autostart_toggled)
        menu.append(self._item_autostart)

        menu.append(Gtk.SeparatorMenuItem())

        item_quit = Gtk.MenuItem(label="Quit")
        item_quit.connect("activate", lambda _: Gtk.main_quit())
        menu.append(item_quit)

        menu.show_all()
        return menu

    # -- Public ---------------------------------------------------------

    def update_data(self, data: Optional[UsageData], error: Optional[str] = None) -> None:
        if data is not None:
            self._data = data
            self._last_error = None
        else:
            self._last_error = error or "API unavailable"
        self._refresh_display()

    def set_refresh_callback(self, cb) -> None:
        self._refresh_cb = cb

    def set_interval_change_callback(self, cb) -> None:
        self._interval_change_cb = cb

    def show_all(self) -> None:
        pass

    def queue_draw(self) -> None:
        self._refresh_display()

    # -- Internal -------------------------------------------------------

    def _refresh_display(self) -> None:
        icon_name = _render_icon(self._data, self._last_error)
        self._indicator.set_icon_full(icon_name, APP_NAME)
        self._update_menu_labels()

    def _update_menu_labels(self) -> None:
        if self._data:
            d = self._data
            fh = f"5h:  {int(round(d.five_hour_pct * 100))}%  \u00b7  resets {format_countdown(d.five_hour_reset)}"
            sd = f"7d:  {int(round(d.seven_day_pct * 100))}%  \u00b7  resets {format_countdown(d.seven_day_reset)}"
            self._item_5h.set_label(fh)
            self._item_7d.set_label(sd)
        elif self._last_error:
            self._item_5h.set_label(f"Error: {self._last_error}")
            self._item_7d.set_label("")

    def _trigger_refresh(self) -> None:
        if hasattr(self, "_refresh_cb") and self._refresh_cb:
            self._refresh_cb()

    def _on_interval_toggled(self, item, minutes) -> None:
        if not item.get_active():
            return
        self._settings = Settings(
            poll_interval_minutes=minutes,
            x=self._settings.x, y=self._settings.y,
            theme=self._settings.theme,
        )
        save_settings(self._settings)
        if hasattr(self, "_interval_change_cb") and self._interval_change_cb:
            self._interval_change_cb(minutes)

    def _on_autostart_toggled(self, item) -> None:
        if item.get_active():
            _enable_autostart()
        else:
            _disable_autostart()


def _enable_autostart() -> None:
    _AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    desktop = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Claude Usage Monitor\n"
        f"Exec=python3 {_MONITOR_DIR}/main.py\n"
        "Hidden=false\n"
        "NoDisplay=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    _AUTOSTART_FILE.write_text(desktop)


def _disable_autostart() -> None:
    if _AUTOSTART_FILE.exists():
        _AUTOSTART_FILE.unlink()
