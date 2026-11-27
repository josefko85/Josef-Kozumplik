#!/bin/sh
# Doppelklick im Finder startet die U-Bahn-Anzeige.
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 fehlt. Bitte von https://www.python.org/downloads/ installieren."
  read -r _; exit 1
fi
(sleep 1.5; open "http://localhost:8080") &
python3 server.py
