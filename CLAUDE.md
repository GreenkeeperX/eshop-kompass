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
