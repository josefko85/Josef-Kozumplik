#!/usr/bin/env python3
"""U-Bahn Abfahrtsanzeige – kleiner lokaler Server.

Liefert die Anzeige (index.html) aus und holt die Echtzeit-Abfahrten von der
MVG (der Browser darf die MVG-Schnittstelle wegen CORS nicht direkt abfragen).

Start:  python3 server.py            -> http://localhost:8080
        python3 server.py --port 9000
Nur Python 3 nötig, keine Zusatzpakete.
"""
import argparse
import threading
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "3"
MVG = "https://www.mvg.de/api/bgw-pt/v3"
HEADERS = {"User-Agent": "Mozilla/5.0 (Abfahrtsanzeige)", "Accept": "application/json"}
_station_cache = {}
HERE = os.path.dirname(os.path.abspath(__file__))
EMBEDDED_HTML = None  # wird beim Bau der Mac-App mit index.html befüllt


def load_page():
    if EMBEDDED_HTML:
        return EMBEDDED_HTML.encode("utf-8")
    with open(os.path.join(HERE, "index.html"), "rb") as f:
        return f.read()

_last_request = [time.time()]


def make_ssl_context():
    """Python von python.org auf dem Mac hat oft keine Stammzertifikate
    (CERTIFICATE_VERIFY_FAILED). Dann die Zertifikate von macOS verwenden."""
    try:
        import certifi  # falls installiert
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        pass
    ctx = ssl.create_default_context()
    if sys.platform == "darwin":
        try:
            pem = subprocess.run(
                ["/usr/bin/security", "find-certificate", "-a", "-p",
                 "/System/Library/Keychains/SystemRootCertificates.keychain",
                 "/Library/Keychains/System.keychain"],
                capture_output=True, timeout=20).stdout.decode("ascii", "ignore")
            if "BEGIN CERTIFICATE" in pem:
                ctx.load_verify_locations(cadata=pem)
        except Exception as e:  # noqa: BLE001
            print("Zertifikate von macOS nicht ladbar:", e, file=sys.stderr)
    return ctx


SSL_CTX = make_ssl_context()


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def resolve_station(name):
    """Haltestellenname -> MVG globalId (z.B. de:09162:...)."""
    if name.startswith("de:"):
        return name, name
    if name in _station_cache:
        return _station_cache[name]
    q = urllib.parse.urlencode({"query": name, "locationTypes": "STATION"})
    for loc in fetch_json(f"{MVG}/locations?{q}"):
        if loc.get("globalId"):
            _station_cache[name] = (loc["globalId"], loc.get("name", name))
            return _station_cache[name]
    raise LookupError(f"Haltestelle '{name}' nicht gefunden")


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # ruhige Konsole

    def do_GET(self):
        _last_request[0] = time.time()
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/index.html"):
            try:
                return self._send(200, load_page(), "text/html; charset=utf-8")
            except OSError as e:
                return self._send(500, f"index.html nicht lesbar: {e}".encode(), "text/plain; charset=utf-8")
        if u.path == "/api/ping":
            return self._send(200, json.dumps({"app": "ubahn-anzeige", "version": VERSION}))
        if u.path == "/api/quit":
            self._send(200, json.dumps({"ok": True}))
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if u.path != "/api/departures":
            return self._send(404, b"Nicht gefunden", "text/plain; charset=utf-8")
        p = urllib.parse.parse_qs(u.query)
        station = p.get("station", ["Schwanthalerhöhe"])[0]
        types = p.get("types", ["UBAHN"])[0]
        try:
            gid, sname = resolve_station(station)
            q = urllib.parse.urlencode({"globalId": gid, "limit": 40, "transportTypes": types})
            deps = fetch_json(f"{MVG}/departures?{q}")
            body = json.dumps({"station": sname, "globalId": gid,
                               "serverTime": int(time.time() * 1000), "departures": deps})
            self._send(200, body)
        except Exception as e:  # noqa: BLE001
            print("Fehler beim Abruf:", repr(e), file=sys.stderr)
            self._send(502, json.dumps({"error": str(e)}))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--idle-exit", type=int, default=0,
                    help="beendet sich nach N Sekunden ohne Anfragen (0 = nie)")
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    if a.idle_exit:
        def watchdog():
            while time.time() - _last_request[0] < a.idle_exit:
                time.sleep(5)
            srv.shutdown()
        threading.Thread(target=watchdog, daemon=True).start()
    print(f"Abfahrtsanzeige läuft: http://localhost:{a.port}   (Beenden mit Strg+C)")
    srv.serve_forever()
