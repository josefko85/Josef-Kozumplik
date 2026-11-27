#!/bin/bash
# Richtet die U-Bahn-Anzeige auf einem Raspberry Pi (Raspberry Pi OS mit Desktop) ein:
#  - server.py startet automatisch beim Hochfahren (systemd-Dienst)
#  - Chromium öffnet die Anzeige automatisch im Vollbild (Kiosk-Modus)
#  - Bildschirmschoner/Abschalten des Monitors wird deaktiviert
# Aufruf im Ordner ubahn-anzeige:   bash raspberry-pi-einrichten.sh
# Optional andere Adresse:          bash raspberry-pi-einrichten.sh "?richtung=alle"
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(whoami)"
PARAMS="${1:-}"
URL="http://localhost:8080/${PARAMS}"

echo "1/3  Dienst für server.py einrichten …"
sudo tee /etc/systemd/system/ubahn-anzeige.service >/dev/null <<UNIT
[Unit]
Description=U-Bahn Abfahrtsanzeige
After=network-online.target
Wants=network-online.target

[Service]
User=${USER_NAME}
WorkingDirectory=${DIR}
ExecStart=/usr/bin/python3 ${DIR}/server.py --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now ubahn-anzeige.service

echo "2/3  Chromium-Kiosk beim Anmelden starten …"
BROWSER="$(command -v chromium-browser || command -v chromium || true)"
if [ -z "$BROWSER" ]; then
  sudo apt-get update && sudo apt-get install -y chromium-browser || sudo apt-get install -y chromium
  BROWSER="$(command -v chromium-browser || command -v chromium)"
fi
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/ubahn-anzeige.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=U-Bahn Anzeige
Exec=sh -c "sleep 8; ${BROWSER} --kiosk --noerrdialogs --disable-infobars --incognito --check-for-update-interval=31536000 '${URL}'"
X-GNOME-Autostart-enabled=true
DESK

echo "3/3  Bildschirm-Abschaltung deaktivieren …"
if command -v raspi-config >/dev/null; then sudo raspi-config nonint do_blanking 1 || true; fi

echo
echo "Fertig! Nach einem Neustart (sudo reboot) erscheint die Anzeige automatisch im Vollbild."
echo "Kiosk beenden: Alt+F4.   Server-Status: systemctl status ubahn-anzeige"
