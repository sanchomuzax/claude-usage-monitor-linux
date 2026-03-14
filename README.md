# Claude Usage Monitor for Linux

A lightweight system tray indicator that displays your Claude API rate-limit usage in real time — directly in your Linux taskbar.

![Screenshot](panel-screenshot.png)

Inspired by [Claude-Code-Usage-Monitor](https://github.com/CodeZeno/Claude-Code-Usage-Monitor) for Windows by [@CodeZeno](https://github.com/CodeZeno). Huge respect for the original idea — this project brings the same concept to Linux.

## Features

- **System tray icon** with real-time 5-hour and 7-day usage percentages
- **Segmented progress bars** using Anthropic brand colors (#D97757)
- **Click menu** with detailed stats, countdown timers, and controls
- **Automatic polling** at configurable intervals (5/15/30/60 min)
- **Autostart on login** support
- **Single instance** lock (won't launch duplicates)
- **Cross-distro** — works on any Linux with GTK3 and a system tray

## How It Works

The monitor reads your Claude CLI OAuth credentials from `~/.claude/.credentials.json` and makes a minimal API call to `/v1/messages` with the `anthropic-beta: oauth-2025-04-20` header. The response headers contain rate-limit utilization data:

- `anthropic-ratelimit-unified-5h-utilization` — 5-hour rolling window
- `anthropic-ratelimit-unified-7d-utilization` — 7-day rolling window

This is the same mechanism the Claude CLI itself uses internally.

## Requirements

- **Python 3.10+**
- **Claude Code CLI** installed and authenticated (`~/.claude/.credentials.json` must exist)
- **GTK3** with PyGObject bindings
- **AppIndicator3** (Ayatana) for system tray support
- **pycairo** for icon rendering
- **requests** for HTTP calls

### Desktop Environment Compatibility

| Desktop | Tray Support | Notes |
|---------|-------------|-------|
| GNOME | Via extension | Needs [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/) |
| KDE Plasma | Native | Works out of the box |
| XFCE | Native | Works out of the box |
| LXQt | Native | Works out of the box |
| labwc + wf-panel-pi | Native | Raspberry Pi OS default — tested and working |
| Sway + waybar | Via tray module | Enable `tray` in waybar config |

## Installation

### Quick Install

```bash
git clone https://github.com/sanchomuzax/claude-usage-monitor-linux.git
cd claude-usage-monitor-linux
bash install.sh
```

The installer will:
1. Check and install missing dependencies (apt/dnf/pacman)
2. Verify Claude CLI credentials exist
3. Optionally enable autostart on login
4. Optionally launch the monitor immediately

### Manual Install

**Debian/Ubuntu/Raspberry Pi OS:**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
    gir1.2-ayatanaappindicator3-0.1 python3-requests python3-cairo
```

**Fedora:**
```bash
sudo dnf install python3-gobject python3-cairo python3-requests \
    libayatana-appindicator-gtk3
```

**Arch Linux:**
```bash
sudo pacman -S python-gobject python-cairo python-requests \
    libayatana-appindicator
```

Then run:
```bash
python3 main.py
```

## Usage

```bash
# Normal mode — polls the API every 15 minutes
python3 main.py

# Demo mode — shows fake data for testing the UI
python3 main.py --demo
```

### Tray Icon

The 32x32 tray icon shows:
- **Top row:** 5-hour usage percentage + mini segmented bar
- **Bottom row:** 7-day usage percentage + mini segmented bar

Bars use Anthropic's brand coral-orange (#D97757). Above 90% they turn red.

### Click Menu

Click the tray icon to see:
- **5h / 7d** — exact percentage and countdown to reset
- **Refresh Now** — trigger an immediate API poll
- **Update Interval** — change polling frequency
- **Start on Login** — toggle autostart
- **Quit** — exit the monitor

## Configuration

Settings are stored in `~/.config/claude-usage-monitor/settings.json`:

```json
{
  "poll_interval_minutes": 15,
  "x": 100,
  "y": 100,
  "theme": "auto"
}
```

## Troubleshooting

### Icon doesn't appear in the tray

1. **Check your desktop has a system tray.** GNOME needs the [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/).
2. **On labwc/wf-panel-pi (Raspberry Pi OS):** Icons must be in the GTK icon theme. The monitor handles this automatically via `~/.local/share/icons/hicolor/`.
3. **Try restarting the panel** after first launch — some panels need a refresh to detect new tray items.

### "token_expired" error

The Claude CLI OAuth token has a limited lifetime. Run any `claude` command to refresh it, then restart the monitor.

### "No credentials found"

Install and authenticate the Claude Code CLI first:
```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Authenticate (opens browser)
claude
```

### "Rate limited" error

The monitor makes one minimal API call per poll interval. If you see rate limiting, increase the poll interval via the tray menu, or wait for the rate limit to expire.

### Icon shows "?"

The API call failed. Check the click menu for the specific error message.

## Development

```bash
# Run tests
python3 -m pytest tests/ -v

# Run with demo data
python3 main.py --demo
```

### Project Structure

```
claude-usage-monitor-linux/
├── main.py         # Entry point, GTK main loop, polling orchestration
├── api.py          # Anthropic API calls, rate-limit header parsing
├── config.py       # Settings and credential management
├── ui.py           # System tray indicator, icon rendering
├── version.py      # Version info
├── install.sh      # Cross-distro installer
└── tests/          # Unit tests (51 tests)
    ├── test_api.py
    ├── test_config.py
    └── test_countdown.py
```

## Credits

- **Original concept:** [Claude-Code-Usage-Monitor](https://github.com/CodeZeno/Claude-Code-Usage-Monitor) for Windows by [@CodeZeno](https://github.com/CodeZeno) — thank you for the inspiration!
- **Anthropic brand colors:** #D97757 coral-orange from the [Anthropic brand guidelines](https://www.anthropic.com/brand)

## License

[MIT](LICENSE)
