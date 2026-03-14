#!/usr/bin/env bash
# Claude Usage Monitor for Linux — installer
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/claude-usage-monitor.desktop"

echo "=== Claude Usage Monitor for Linux — installer ==="

# ----- Python dependency check -----
echo ""
echo "Checking Python dependencies..."

missing=0

python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" 2>/dev/null \
    || { echo "  [!] PyGObject (GTK3) not found."; missing=1; }

python3 -c "
try:
    import gi; gi.require_version('AppIndicator3','0.1'); from gi.repository import AppIndicator3
except:
    import gi; gi.require_version('AyatanaAppIndicator3','0.1'); from gi.repository import AyatanaAppIndicator3
" 2>/dev/null \
    || { echo "  [!] AppIndicator3 not found."; missing=1; }

python3 -c "import requests" 2>/dev/null \
    || { echo "  [!] requests not found."; missing=1; }

python3 -c "import cairo" 2>/dev/null \
    || { echo "  [!] pycairo not found."; missing=1; }

if [ "$missing" -eq 1 ]; then
    echo ""
    echo "  Installing missing dependencies..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
            gir1.2-ayatanaappindicator3-0.1 python3-requests python3-cairo 2>/dev/null || true
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-gobject python3-cairo python3-requests \
            libayatana-appindicator-gtk3 2>/dev/null || true
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm python-gobject python-cairo python-requests \
            libayatana-appindicator 2>/dev/null || true
    else
        echo "  [!] Unknown package manager. Install manually:"
        echo "      PyGObject, pycairo, requests, ayatana-appindicator3"
        exit 1
    fi
fi

echo "  [OK] Dependencies satisfied"

# ----- Verify Claude CLI credentials -----
echo ""
if [ -f "$HOME/.claude/.credentials.json" ]; then
    echo "  [OK] Claude CLI credentials found"
else
    echo "  [!] No ~/.claude/.credentials.json found."
    echo "      Install Claude Code CLI first: https://docs.anthropic.com/en/docs/claude-code"
    echo "      Then run 'claude' once to authenticate."
fi

# ----- Make scripts executable -----
chmod +x "$SCRIPT_DIR/main.py"

# ----- Autostart entry -----
echo ""
read -rp "Enable autostart on login? [Y/n] " answer
answer="${answer:-Y}"
if [[ "$answer" =~ ^[Yy]$ ]]; then
    mkdir -p "$AUTOSTART_DIR"
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Usage Monitor for Linux
Comment=System tray monitor for Claude API rate limits
Exec=python3 $SCRIPT_DIR/main.py
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Icon=claude-usage-monitor
EOF
    echo "  [OK] Autostart entry created: $DESKTOP_FILE"
else
    echo "  [-] Skipping autostart"
fi

# ----- Launch -----
echo ""
read -rp "Launch now? [Y/n] " launch
launch="${launch:-Y}"
if [[ "$launch" =~ ^[Yy]$ ]]; then
    python3 "$SCRIPT_DIR/main.py" &
    echo "  [OK] Launched (PID $!)"
fi

echo ""
echo "Done! Manual start:  python3 $SCRIPT_DIR/main.py"
echo "Stop:                Click tray icon > Quit"
