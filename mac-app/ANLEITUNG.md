# U-Bahn Anzeige als Mac-App

1. **Python 3 installieren** (einmalig): https://www.python.org/downloads/ → „Download Python“ → `.pkg` öffnen und installieren.
2. **`U-Bahn Anzeige.zip` öffnen** (Doppelklick) und **„U-Bahn Anzeige“ in den Ordner „Programme“ ziehen**.
3. **Erster Start:** Rechtsklick auf die App → **Öffnen** → **Öffnen**.
   Falls macOS trotzdem blockiert: **Systemeinstellungen → Datenschutz & Sicherheit** → ganz unten **„Dennoch öffnen“**.
4. Ab dann ganz normal per Launchpad, Spotlight (Cmd+Leertaste → „U-Bahn“) oder Dock starten.

Die App öffnet die Tafel (mit Google Chrome als eigenes Fenster ohne Leisten, sonst im Standardbrowser).
Vollbild: Doppelklick auf die Tafel oder Taste F. Wenn du das Fenster schließt, beendet sich alles
nach ca. 2 Minuten von selbst. Die App sucht sich selbst einen freien Port (ab 8765).

Automatisch beim Einschalten starten: **Systemeinstellungen → Allgemein → Anmeldeobjekte → „+“ → U-Bahn Anzeige**.

Bei Problemen: Protokoll unter `~/Library/Logs/U-Bahn-Anzeige.log`.

Neu bauen nach Änderungen an `ubahn-anzeige/`: `mac-app/build.sh`
