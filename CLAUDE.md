# Hinweise für die Arbeit am Repository

**Dieses Repository ist öffentlich.** Vor jedem Commit und jedem Push prüfen, dass
nirgends private Angaben stehen: nicht im Code, in Kommentaren, Tests, Beispielen, in der
README, der ROADMAP.md oder in Commit-Texten.

Nicht hinein gehören:
- Namen von Personen, auch Vornamen und Benutzernamen, etwa in Begründungen wie
  „(Name, Datum)“. Stattdessen „(Entscheidung 12.10.2026)“ oder ohne Herkunft,
- Wishlist- und Sammlungs-Links oder -Kennungen,
- Hostnamen, interne Domains, IP-Adressen, Zugangsdaten,
- Angaben aus dem eigenen Konto: Guthaben, Käufe, eigene Karten, Einstellungsdateien.

Prüfung vor dem Push, zum Beispiel:

    git diff origin/main --stat
    git grep -n -i -E "wishlist/[A-Za-z0-9]{6,}|collection/[A-Za-z0-9]{6,}|192\.168\.|@[a-z0-9-]+\.(de|com)"

Ein Treffer bei Namen fällt mit grep nicht sicher auf. Deshalb den eigenen Diff vor dem
Push lesen.

Weitere feste Regeln:
- nur die Python-Standardbibliothek, keine neuen Abhängigkeiten,
- Quellen schonend abrufen: Pausen, Abbruch bei 403 und 429, ehrliche Kennung,
- die Härtung des Containers bleibt,
- geschätzte Werte sind in der Oberfläche gekennzeichnet,
- jede Version mit Tests (`python3 -m unittest tests.test_all`), neuer Nummer in
  `app/sources.py`, aktueller README und aktueller ROADMAP.md.

## Aufbau

Zweck, Bedienung und Rechenregeln stehen in `README.md`, Geplantes in `ROADMAP.md`.

- `app/countries.py`: Länder, Regionen, Wechselstufen
- `app/sources.py`: Abruf und Parser der Quellen, `VERSION`
- `app/store.py`: Einstellungen und JSON-Dateien im Datenordner
- `app/planner.py`: Angebote, Bewertung (`Context`), Körbe je Land, Bestpreise, Urteile, Sammlung,
  Sprachen; reicht die Namen der folgenden vier weiter, `planner.X` gilt überall
- `app/cards.py`: Guthabenkarten (Kartenkombination, Kartenliste, Faktor)
- `app/titles.py`: Namen vergleichen, eShop-Käufe zuordnen, Pakete und Besitz
- `app/kaufplan.py`: Kaufplan; `app/membership.py`: Online-Mitgliedschaft. Beide laden `planner`;
  wer in Tests eine Funktion für den Kaufplan ersetzt, ersetzt sie in `kaufplan`
- `app/sync.py`: Abgleich, Zeitplan, Verbindungstest
- `app/server.py`: Webserver und JSON-Schnittstelle
- `app/static/`: Oberfläche, reines JavaScript ohne Build: `index.html` (Gerüst und Ladereihenfolge),
  `style.css`, `js/*.js` (Teile nach Reitern, gemeinsame Namen; Code oben in einer Datei darf nur
  nutzen, was in derselben oder einer früher geladenen Datei steht). Der Server liefert nur
  `style.css` und `js/<name>.js`
- `docs/oberflaeche.md`: Farben, Marken und Wortwahl der Oberfläche; bei jeder Änderung daran
  im selben Commit mitpflegen. Vor einer Änderung an Darstellung oder Angaben dort die Liste
  „Eine Sache, mehrere Orte“ durchgehen und alle genannten Stellen prüfen
- `docs/abrufe.md`: was das Tool woher, wann und wie oft holt und wo es die Daten ablegt; bei
  jeder Änderung an Abrufen, Grenzen, Zeitplan oder Ablage im selben Commit mitpflegen
- `tests/test_all.py`: alle Tests, `.github/workflows/image.yml`: Tests und Image bei Push auf `main`

Lokal starten: `python3 -m app.server` (Port 8787, Daten in `./data/`, ignoriert).
Tests: `python3 -m unittest tests.test_all`. Ein Linter ist nicht eingerichtet.
Bei Änderungen an Rechenlogik oder Datenfluss zusätzlich die neueste Momentaufnahme mit
`python3 -m tools.replay ... --vergleich main` durchrechnen (siehe README, Prüfumgebung).
Momentaufnahmen nie ins Repository legen.
Alte Datendateien müssen nach einem Update weiter laden.

## Graphify (optional, nur lokal)

`graphify-out/` ist ein lokal erzeugter Code-Graph und nicht versioniert. Fehlt er,
etwa in Cloud-Sitzungen, normal mit Lesen und Suchen arbeiten.

- Zur Orientierung nutzen, wenn es hilft: `graphify query "<Frage>"`,
  `graphify explain "<Begriff>"`, `graphify path "<A>" "<B>"`. Für kleine,
  klar umrissene Änderungen ist keine Abfrage nötig.
- Der Graph ist unvollständig. Fehlende Knoten oder Kanten belegen nie, dass etwas
  nicht existiert oder nicht aufgerufen wird. Maßgeblich ist der Code.
- Nicht im Graphen: die Oberfläche `app/static/` und der Datenfluss über
  die JSON-Dateien (`sync.py` schreibt `data.json`, `server.py` liest sie). Beides
  bei Bedarf direkt im Code prüfen.
- Bei Änderungen an Rechenlogik, Datenfluss oder Darstellung die betroffenen Stellen
  immer im Quellcode lesen, nicht nur im Graphen.
- Nach Codeänderungen `graphify update .`, sofern Graphify installiert ist.
