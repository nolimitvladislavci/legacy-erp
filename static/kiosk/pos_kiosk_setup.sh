#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  LIMIT Connect POS — Kiosk Setup (Linux / Raspberry Pi)
# ═══════════════════════════════════════════════════════════

POS_URL="https://limit-connect.com/hr/pos/quick/1/"
DESKTOP_FILE="$HOME/Desktop/pos-blagajna.desktop"

echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║   LIMIT Connect POS — Kiosk Installer     ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# Detect Chrome/Chromium
CHROME=$(which google-chrome-stable 2>/dev/null || which chromium-browser 2>/dev/null || which chromium 2>/dev/null)
if [ -z "$CHROME" ]; then
    echo "[!] Chrome/Chromium nije pronadjen. Instalirajte:"
    echo "    sudo apt install chromium-browser"
    exit 1
fi
echo "[1] Browser: $CHROME"

# Create .desktop file
cat > "$DESKTOP_FILE" << DESK
[Desktop Entry]
Name=POS Blagajna
Comment=LIMIT Connect POS Terminal
Exec=$CHROME --kiosk --kiosk-printing --disable-translate --noerrdialogs --disable-infobars --disable-session-crashed-bubble "$POS_URL"
Icon=chromium-browser
Terminal=false
Type=Application
Categories=Office;
DESK
chmod +x "$DESKTOP_FILE"

echo "[2] Desktop shortcut: $DESKTOP_FILE"

# Optional: autostart on boot (for dedicated POS terminals)
read -p "[?] Zelite li auto-pokretanje na boot? (y/N): " autostart
if [ "$autostart" = "y" ] || [ "$autostart" = "Y" ]; then
    mkdir -p "$HOME/.config/autostart"
    cp "$DESKTOP_FILE" "$HOME/.config/autostart/"
    echo "[3] Autostart konfiguriran!"
fi

echo ""
echo "┌─────────────────────────────────────────┐"
echo "│ Za izlaz iz kiosk moda: Alt+F4          │"
echo "│ Auto print: bez dijaloga                │"
echo "│ Fullscreen: bez URL trake               │"
echo "└─────────────────────────────────────────┘"
echo ""
echo "[OK] Dvaput kliknite 'POS Blagajna' za pokretanje."
