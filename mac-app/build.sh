#!/bin/bash
# Baut "U-Bahn Anzeige.app": kopiert server.py mit eingebetteter index.html ins App-Bundle.
set -e
cd "$(dirname "$0")"
RES="U-Bahn Anzeige.app/Contents/Resources"
python3 - ../ubahn-anzeige/server.py ../ubahn-anzeige/index.html "$RES/server.py" <<'PY'
import sys
src, html, out = sys.argv[1:]
s = open(src, encoding="utf-8").read()
marker = "EMBEDDED_HTML = None"
assert s.count(marker) == 1
s = s.replace(marker, "EMBEDDED_HTML = " + repr(open(html, encoding="utf-8").read()), 1)
open(out, "w", encoding="utf-8").write(s)
PY
rm -f "$RES/index.html"
chmod +x "U-Bahn Anzeige.app/Contents/MacOS/ubahn-anzeige"
echo "gebaut: U-Bahn Anzeige.app"
