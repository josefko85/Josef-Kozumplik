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
EMBEDDED_HTML = '<!doctype html>\n<html lang="de" translate="no">\n<head>\n<meta charset="utf-8">\n<meta name="google" content="notranslate">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>U-Bahn Abfahrten</title>\n<style>\n  :root {\n    --housing: #15171c;\n    --panel-top: #0b2f9a;\n    --panel-bot: #06207a;\n    --text: #ffffff;\n    --dim: #a9c0ff;\n    --accent: #ffd400;\n    --red: #e4002b;\n  }\n  * { box-sizing: border-box; margin: 0; padding: 0; }\n  html, body { height: 100%; background: #000; overflow: hidden; }\n  body {\n    font-family: "Helvetica Neue", Arial, "Liberation Sans", sans-serif;\n    color: var(--text);\n    display: flex; align-items: center; justify-content: center;\n    cursor: none;\n  }\n  body.cursor { cursor: default; }\n\n  .housing {\n    width: 100vw; height: 100vh;\n    background: var(--housing);\n    padding: 1.6vh 1.6vw;\n    display: grid;\n    grid-template-columns: 1fr 22vh;\n    gap: 1.6vw;\n  }\n\n  .panel {\n    background: linear-gradient(180deg, var(--panel-top), var(--panel-bot));\n    border-radius: 0.6vh;\n    box-shadow: inset 0 0 4vh rgba(0,0,0,.45);\n    display: flex; flex-direction: column;\n    overflow: hidden;\n    position: relative;\n  }\n  /* leichte LCD-Rasterung */\n  .panel::after {\n    content: ""; position: absolute; inset: 0; pointer-events: none;\n    background: repeating-linear-gradient(0deg, rgba(0,0,0,.10) 0 1px, transparent 1px 3px);\n  }\n\n  header {\n    display: flex; align-items: baseline; justify-content: space-between;\n    padding: 1.6vh 2.4vh 1.2vh;\n    border-bottom: 0.3vh solid rgba(255,255,255,.25);\n    gap: 2vh;\n  }\n  header .station { font-size: 4.2vh; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n  header .dir { font-size: 3vh; color: var(--dim); white-space: nowrap; }\n\n  .cols, .row {\n    display: grid;\n    grid-template-columns: 11vh 1fr 17vh;\n    align-items: center;\n    gap: 2.4vh;\n    padding: 0 2.4vh;\n  }\n  .cols { font-size: 2.2vh; color: var(--dim); padding-top: 1vh; padding-bottom: .6vh; text-transform: uppercase; letter-spacing: .1em; }\n  .cols span:last-child, .row .min { text-align: right; }\n\n  #rows { flex: 1; display: flex; flex-direction: column; }\n  .row {\n    flex: 1;\n    max-height: 13vh;\n    font-size: 6.4vh;\n    font-weight: 700;\n    border-bottom: 0.2vh solid rgba(255,255,255,.12);\n  }\n  .row:first-child { font-size: 7.4vh; }\n  .badge {\n    display: inline-flex; align-items: center; justify-content: center;\n    width: 10vh; height: 6.2vh;\n    font-size: 4.4vh; font-weight: 800;\n    color: #fff; border-radius: 0.6vh;\n    box-shadow: 0 0 0 0.25vh rgba(255,255,255,.85);\n  }\n  .dest { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n  .dest small { display: block; font-size: 2.4vh; font-weight: 400; color: var(--accent); margin-top: .3vh; }\n  .min { font-variant-numeric: tabular-nums; }\n  .min.late { color: var(--accent); }\n  .min.now { animation: blink 1s steps(2, start) infinite; font-size: .8em; }\n  .row.cancelled .dest, .row.cancelled .min { text-decoration: line-through; opacity: .6; }\n  @keyframes blink { to { visibility: hidden; } }\n\n  footer {\n    height: 6vh; display: flex; align-items: center;\n    background: rgba(0,0,0,.25);\n    font-size: 2.8vh; overflow: hidden; white-space: nowrap;\n    border-top: 0.3vh solid rgba(255,255,255,.25);\n  }\n  footer .tag { background: var(--accent); color: #000; font-weight: 700; padding: 0 1.4vh; height: 100%; display: flex; align-items: center; flex: none; }\n  footer .ticker { flex: 1; overflow: hidden; }\n  footer .ticker span { display: inline-block; padding-left: 100%; animation: scroll 22s linear infinite; }\n  @keyframes scroll { to { transform: translateX(-100%); } }\n\n  /* rechte Säule: Notruf + Uhr + Gleis, wie an der Original-Tafel */\n  .side { display: flex; flex-direction: column; gap: 1.6vh; align-items: center; }\n  .notruf { width: 100%; text-align: center; color: #ff8a3d; font-weight: 700; font-size: 2.4vh; line-height: 1.3; }\n  .sos { display: inline-block; background: #ff6a00; color: #fff; padding: .2vh 1vh; margin: .6vh 0; border-radius: .3vh; }\n  .clock { width: 20vh; height: 20vh; }\n  .digital { font-size: 3.6vh; font-weight: 700; font-variant-numeric: tabular-nums; }\n  .gleis { font-size: 3vh; font-weight: 700; color: #fff; text-align: center; }\n  .gleis b { display: block; font-size: 8vh; line-height: 1; }\n\n  .empty { flex: 1; display: flex; align-items: center; justify-content: center; font-size: 4vh; color: var(--dim); text-align: center; padding: 4vh; }\n\n  @media (max-aspect-ratio: 1/1) {\n    .housing { grid-template-columns: 1fr; grid-template-rows: 1fr auto; }\n    .side { flex-direction: row; justify-content: space-around; }\n    .clock { width: 14vh; height: 14vh; }\n  }\n</style>\n</head>\n<body>\n<div class="housing">\n  <section class="panel">\n    <header>\n      <div class="station" id="station">Schwanthalerhöhe</div>\n      <div class="dir" id="dir">Richtung Hauptbahnhof</div>\n    </header>\n    <div class="cols"><span>Linie</span><span>Ziel</span><span>Min</span></div>\n    <div id="rows"><div class="empty">Lade Abfahrten …</div></div>\n    <footer><div class="tag" id="tag">MVG</div><div class="ticker"><span id="ticker">Echtzeitdaten werden geladen …</span></div></footer>\n  </section>\n\n  <aside class="side">\n    <div class="notruf">Notruf<br><span class="sos">SOS</span><br>Nothalt</div>\n    <svg class="clock" viewBox="0 0 200 200" aria-label="Uhr">\n      <circle cx="100" cy="100" r="96" fill="#fff" stroke="#222" stroke-width="6"/>\n      <g id="ticks"></g>\n      <line id="hh" x1="100" y1="112" x2="100" y2="52" stroke="#000" stroke-width="10" stroke-linecap="butt"/>\n      <line id="mh" x1="100" y1="116" x2="100" y2="22" stroke="#000" stroke-width="7" stroke-linecap="butt"/>\n      <g id="sh"><line x1="100" y1="130" x2="100" y2="40" stroke="#c00" stroke-width="2.5"/><circle cx="100" cy="40" r="9" fill="#c00"/></g>\n      <circle cx="100" cy="100" r="3" fill="#c00"/>\n    </svg>\n    <div class="digital" id="digital">--:--:--</div>\n    <div class="gleis">Gleis<b id="gleis">1</b></div>\n  </aside>\n</div>\n\n<script>\n/* ---------- Einstellungen (auch per URL: ?station=...&richtung=alle&demo=1) ---------- */\nconst P = new URLSearchParams(location.search);\nconst CONFIG = {\n  station: P.get("station") || "Schwanthalerhöhe",\n  // "hbf" = nur Züge Richtung Hauptbahnhof (Ostrichtung), "alle" = beide Richtungen\n  richtung: (P.get("richtung") || "hbf").toLowerCase(),\n  // Endhaltestellen der Gegenrichtung (Westen) – diese werden bei "hbf" ausgeblendet\n  gegenrichtung: ["Westendstraße", "Laimer Platz", "Friedenheimer Straße", "Pasing", "Heimeranplatz"],\n  rows: parseInt(P.get("zeilen") || "6", 10),\n  refreshSec: 20,\n  demo: P.has("demo"),\n};\nconst LINE_COLORS = { U1:"#52822f", U2:"#c20831", U3:"#ec6726", U4:"#00a984", U5:"#bc7a00", U6:"#0065ae", U7:"#52822f", U8:"#c20831" };\n\n/* ---------- Bahnhofsuhr (mit "Sekundenstopp" wie bei echten Bahnhofsuhren) ---------- */\nconst ticks = document.getElementById("ticks");\nfor (let i = 0; i < 60; i++) {\n  const big = i % 5 === 0;\n  const l = document.createElementNS("http://www.w3.org/2000/svg", "line");\n  l.setAttribute("x1", 100); l.setAttribute("x2", 100);\n  l.setAttribute("y1", big ? 10 : 10); l.setAttribute("y2", big ? 34 : 18);\n  l.setAttribute("stroke", "#000"); l.setAttribute("stroke-width", big ? 7 : 2.5);\n  l.setAttribute("transform", `rotate(${i * 6} 100 100)`);\n  ticks.appendChild(l);\n}\nfunction drawClock() {\n  const d = new Date();\n  const s = Math.min(d.getSeconds() + d.getMilliseconds() / 1000, 59.999) * (60 / 58.5);\n  const sec = Math.min(s, 60);\n  const m = d.getMinutes(), h = d.getHours() % 12;\n  document.getElementById("sh").setAttribute("transform", `rotate(${sec * 6} 100 100)`);\n  document.getElementById("mh").setAttribute("transform", `rotate(${m * 6} 100 100)`);\n  document.getElementById("hh").setAttribute("transform", `rotate(${h * 30 + m * 0.5} 100 100)`);\n  document.getElementById("digital").textContent = d.toLocaleTimeString("de-DE");\n  requestAnimationFrame(drawClock);\n}\nrequestAnimationFrame(drawClock);\n\n/* ---------- Daten ---------- */\nlet departures = [];   // {line, dest, time(ms), delay, cancelled, platform}\nlet lastOk = 0;\n\nfunction demoData() {\n  // Simulierter Fahrplan: U4 & U5 abwechselnd ca. alle 5 Minuten\n  const now = Date.now(), out = [];\n  const base = Math.floor(now / 300000) * 300000;\n  for (let i = -1; i < 14; i++) {\n    const u4 = i % 2 === 0;\n    const t = base + i * 300000 + (u4 ? 60000 : 210000);\n    const delay = (i === 2) ? 2 : 0;\n    out.push({ line: u4 ? "U4" : "U5", dest: u4 ? "Arabellapark" : "Neuperlach Süd", time: t + delay * 60000, delay, cancelled: false, platform: "1" });\n    out.push({ line: u4 ? "U4" : "U5", dest: u4 ? "Westendstraße" : "Laimer Platz", time: t + 120000, delay: 0, cancelled: false, platform: "2" });\n  }\n  return out;\n}\n\nasync function load() {\n  if (CONFIG.demo) {\n    departures = demoData();\n    setTicker("DEMO", "Demo-Modus – simulierte Abfahrten. Für Echtzeitdaten ohne ?demo öffnen.");\n    render();\n    return;\n  }\n  try {\n    const r = await fetch(`/api/departures?station=${encodeURIComponent(CONFIG.station)}`, { cache: "no-store" });\n    const j = await r.json();\n    if (!r.ok) throw new Error(j.error || r.status);\n    document.getElementById("station").textContent = j.station;\n    departures = j.departures.map(d => ({\n      line: d.label,\n      dest: d.destination,\n      time: d.realtimeDepartureTime || d.plannedDepartureTime,\n      delay: d.delayInMinutes || 0,\n      cancelled: !!d.cancelled,\n      platform: d.platform != null ? String(d.platform) : "",\n      realtime: d.realtime,\n    }));\n    // Störungsmeldungen der MVG (falls vorhanden) ins Laufband\n    const notes = new Set();\n    j.departures.forEach(d => [...(d.messages || []), ...(d.infos || [])].forEach(m => {\n      const t = typeof m === "string" ? m : (m.message || m.text || m.title || "");\n      if (t) notes.add(t.replace(/<[^>]*>/g, "").trim());\n    }));\n    window.mvgNotes = [...notes];\n    lastOk = Date.now();\n    if (window.mvgNotes.length) setTicker("INFO", window.mvgNotes.join("  ·  "));\n    else setTicker("MVG", `Echtzeitdaten der MVG · zuletzt aktualisiert ${new Date().toLocaleTimeString("de-DE")} · Bitte zurückbleiben!`);\n  } catch (e) {\n    const stale = lastOk ? ` (Daten von ${new Date(lastOk).toLocaleTimeString("de-DE")})` : "";\n    setTicker("STÖRUNG", `Keine Verbindung zur MVG${stale}: ${e.message}. Läuft server.py? Tipp: ?demo=1 für Demo-Daten.`);\n  }\n  render();\n}\n\nfunction setTicker(tag, text) {\n  document.getElementById("tag").textContent = tag;\n  const t = document.getElementById("ticker");\n  if (t.textContent !== text) t.textContent = text;\n}\n\nfunction render() {\n  const now = Date.now();\n  let list = departures.filter(d => d.time - now > -30000);\n  if (CONFIG.richtung !== "alle") {\n    list = list.filter(d => !CONFIG.gegenrichtung.some(g => d.dest && d.dest.startsWith(g)));\n    document.getElementById("dir").textContent = "Richtung Hauptbahnhof";\n  } else {\n    document.getElementById("dir").textContent = "Alle Richtungen";\n  }\n  list.sort((a, b) => a.time - b.time);\n  list = list.slice(0, CONFIG.rows);\n\n  const plat = list.find(d => d.platform)?.platform;\n  if (plat) document.getElementById("gleis").textContent = plat;\n\n  const rows = document.getElementById("rows");\n  if (!list.length) {\n    rows.innerHTML = `<div class="empty">Zurzeit keine Abfahrten</div>`;\n    return;\n  }\n  rows.innerHTML = list.map(d => {\n    const mins = Math.max(0, Math.floor((d.time - now) / 60000));\n    const color = LINE_COLORS[d.line] || "#444";\n    const minTxt = d.cancelled ? "" : (mins === 0 ? "jetzt" : mins);\n    const note = d.cancelled ? "<small>Fahrt fällt aus</small>" : (d.delay > 0 ? `<small>+${d.delay} Min Verspätung</small>` : "");\n    return `<div class="row${d.cancelled ? " cancelled" : ""}">\n      <span class="badge" style="background:${color}">${esc(d.line)}</span>\n      <span class="dest">${esc(d.dest)}${note}</span>\n      <span class="min${mins === 0 ? " now" : ""}${d.delay > 0 ? " late" : ""}">${minTxt}</span>\n    </div>`;\n  }).join("");\n}\nfunction esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", \'"\':"&quot;" }[c])); }\n\nload();\nsetInterval(load, CONFIG.refreshSec * 1000);\nsetInterval(render, 5000);\n\n/* Vollbild per Doppelklick oder Taste F; Mauszeiger nur bei Bewegung */\ndocument.addEventListener("dblclick", () => document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());\ndocument.addEventListener("keydown", e => { if (e.key === "f" || e.key === "F") document.documentElement.requestFullscreen(); });\nlet mt; document.addEventListener("mousemove", () => { document.body.classList.add("cursor"); clearTimeout(mt); mt = setTimeout(() => document.body.classList.remove("cursor"), 2500); });\n</script>\n</body>\n</html>\n'  # wird beim Bau der Mac-App mit index.html befüllt


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
