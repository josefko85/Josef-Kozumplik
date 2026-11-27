#!/usr/bin/env python3
"""U-Bahn Abfahrtsanzeige – kleiner lokaler Server.

Liefert die Anzeige (index.html) aus und holt die Echtzeit-Abfahrten von der
MVG (der Browser darf die MVG-Schnittstelle wegen CORS nicht direkt abfragen).

Start:  python3 server.py            -> http://localhost:8080
        python3 server.py --port 9000
Nur Python 3 nötig, keine Zusatzpakete.
"""
import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

MVG = "https://www.mvg.de/api/bgw-pt/v3"
HEADERS = {"User-Agent": "Mozilla/5.0 (Abfahrtsanzeige)", "Accept": "application/json"}
_station_cache = {}


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
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


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=os.path.dirname(os.path.abspath(__file__)), **kw)

    def log_message(self, fmt, *args):
        pass  # ruhige Konsole

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path != "/api/departures":
            return super().do_GET()
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
            self._send(502, json.dumps({"error": str(e)}))

    def _send(self, code, body):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    print(f"Abfahrtsanzeige läuft: http://localhost:{a.port}   (Beenden mit Strg+C)")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
