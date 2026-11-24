# Roadmap

Woran am eShop-Kompass als Nächstes gearbeitet wird. Jeder Schritt wird eine kleine
Version mit Tests, Prüfung der Oberfläche, Versionsnummer, README und Commit. Erledigtes
fällt hier heraus (Entscheidung 13.10.2026); was das Tool kann, steht in der
[README](README.md), wann es dazukam, in der Git-Geschichte (ab 0.36).

Diese Datei liegt in einem öffentlichen Repository. Sie enthält deshalb keine Namen,
Wishlist-Links oder -Kennungen, Hostnamen, Adressen und keine Angaben aus dem eigenen
Konto (siehe [CLAUDE.md](CLAUDE.md)).

## Vision

**Ein ruhiges Werkzeug, dem man trauen kann.** Einmal am Tag draufschauen, auch auf dem Handy, in
fünf Sekunden wissen, was heute zu tun ist, und kaufen, ohne nachzurechnen. Vertrauen schlägt
Umfang: Jede Zahl lässt sich nachvollziehen, jede Abweichung wird gemeldet statt still geschluckt,
und das Werkzeug arbeitet weiter, wenn eine Quelle ausfällt.

Leitsätze für jede Entscheidung (Entscheidung 14.10.2026):

1. **Richtig vor neu.** Eine neue Funktion kommt erst, wenn die alten Regeln mit ihr getestet sind.
2. **Lieber melden als raten.** Fehlt etwas oder passt etwas nicht, sagt es das Tool, statt still
   Daten zu löschen oder zu schätzen.
3. **Nutzen belegen.** Jede größere Erweiterung nennt vorher, wie viel Geld oder Zeit sie im Jahr
   spart.

## Horizont 2: Überall nutzbar und wartbar

**Stabilisierung nach dem Review vom 13.11.2026** (Entscheidung 24.11.2026). Neue Funktionen erst
danach; jeder Abschnitt wird erst nach Freigabe übernommen.

- **E-1 Sofortmaßnahmen (1.7.32):** Tests und Repository-Prüfung für Pull Requests (`tests.yml`),
  `/healthz` mit `HEALTHCHECK` im Image, NaN und unendlich in Einstellungen, Oberflächendaten,
  Dateien und Antworten abgewiesen, `/api/status` ohne `data.json` zu lesen, Prüfung gegen
  Arbeitsdateien und unbekannte Dateien im Wurzelverzeichnis (`tools/repo_check.py`).
- **E-2 Ruhezeiten und Netzabruf**, erst nach einem Praxistest der jetzigen Regeln. Die
  Ruhezeiten bleiben verschieden (Kartenshops 6 Stunden, andere Quellen 24 Stunden nach 403
  oder 429), zentral einstellbar und über Neustarts gespeichert. Dazu Gesamtfristen beim Lesen,
  Pausen je Server, Erkennen von Prüfseiten, Verbindungstest im Hintergrund unter denselben
  Ruhezeiten, keine Umgehung einer Sperre über eine zweite Quelle auf demselben Server.
- **E-3 Datenintegrität:** gemeinsames Schloss für `history.json`, Konflikt statt stillem
  Überschreiben bei veralteten Formularen, `_eshop_matches` mit Index, `MutationObserver` nur wo
  nötig, Sicherung vor jeder Migration.
- **E-4 Darstellung und Betrieb:** „Was ist neu“, Zwischenspeichern von Skripten und Stil mit
  Versionsstempel und ETag, einklappbare Statuskarte in den Einstellungen (keine eigene Seite) mit
  monatlicher Prüfung der Sicherung und einem Leistungstest nur auf Klick, README auf Zweck,
  Installation, Bedienung und Betrieb kürzen, Rechenregeln nach `docs/`.

Danach, in dieser Reihenfolge: Erscheinungstermine mit Vorbestellpreis je Land, Paket gegen
Einzelteile (auch über Länder), Preis je Spielstunde. Nachrangig: Speicherbedarf in den
Spieldetails (nur aus titledb), Hinweis auf aus dem eShop verschwundene Titel nur dort, wo er für
einen Eintrag zählt, eine dezente Länderbewertung über die ganze Wishlist ohne Guthaben auf Vorrat.

## Von den Geschwistern

Pokédex und VR-Navigator teilen Standards, aber keinen Code. Was dort gut gelöst ist, wird hier
geprüft und nur übernommen, wenn es hier nützt.

- Kompakte Ansicht „Was ist neu“ wie im Pokédex (E-4).
- Grundflächen und Hintergründe schrittweise an Pokédex und VR-Navigator angleichen, die
  gemeinsame Hervorhebungsfarbe bleibt; eine sichtbare Schnellsuche mit Strg+K und `/`.

Umgekehrt nützlich für die Geschwister: `tools/repo_check.py` (Liste erlaubter Dateien statt
pauschalem Ausschluss), `/healthz` mit `HEALTHCHECK`, Abweisen von NaN beim Speichern.

## Horizont 3: Klüger, nur mit belegtem Nutzen

Derzeit nichts offen.

## Risiken

- **DekuDeals** liefert Wishlist, Sammlung, IDs, Tiefstpreise, DLC und Pakete. Ändert es seine
  Seiten oder sperrt es, rechnet das Tool mit den zuletzt gelesenen Listen weiter und zeigt
  „Notbetrieb“; neue Wishlist-Titel kommen dann nicht hinzu.
- **Nintendos Preisschnittstelle** ist nicht offiziell.
- **Shopseiten mit Prüfseiten** (Amazon) können jederzeit unlesbar werden; dann gilt der
  eingetragene Preis.
- **Wartung:** Der Abgleich hat rund 2300 Zeilen in einer Datei; die Oberfläche prüfen nur
  Vertrags- und Breitentests, keine Abläufe.

## Ohne Arbeit für uns

- **Sprache in Japan:** Titel, die titledb nicht kennt, liest der Browser-Helfer
  „JP-Sprachen lesen“. Ob der Bot-Schutz seine Abrufe dauerhaft durchlässt, zeigt erst der
  Gebrauch.
- **Südafrika:** Ob Kartenzahlung dort geht, ist ungetestet. Bis dahin gilt „leicht, Karte“.
- **Kaufverlauf:** Nintendo zeigt nur die letzten zwei Jahre.

## Zurückgestellt und gestrichen

- **Zurückgestellt: Füllartikel Stufe 3** (gute Spiele abseits der Wishlist). Es fehlt eine
  Quelle für „gut“, und ein Vorschlag für ein Spiel, das niemand wollte, hilft wenig.
- **Gestrichen:**
  - Benachrichtigung,
  - Wishlist aufräumen (geschieht in DekuDeals),
  - Budget,
  - Vorhersage des nächsten Angebots (nicht verlässlich),
  - ein Feld für den tatsächlich bezahlten Betrag,
  - gg.deals (Cloudflare sperrt jeden Abruf).
- **Gestrichen (Entscheidung 24.11.2026):** Kalender-Endpunkt für Angebotsenden,
  Push-Benachrichtigungen und ntfy, Demo-Kennzeichnung, Preise physischer Spiele im Handel,
  Preisvorhersagen, eine eigene Gesundheitsseite (stattdessen die Statuskarte) und eine gemeinsame
  Codebibliothek der drei Projekte.
- **Gestrichen (Entscheidung 19.10.2026):** Kleinteile wie Kostüme zusammenfassen; die Einzelteile
  bleiben, wie sie sind. Ebenso die „Heute“-Zeile; „Zu erledigen“ deckt sie ab. Ebenso: das
  Ablaufdatum der Mitgliedschaft aus dem Kaufverlauf (dort steht keine Laufzeit, der Betrag passt
  wegen Punkten und Codes oft zu keiner Variante), ein Rückblick über die Ersparnis, weitere
  Bezugsquellen wie Händler-Codes und das Alter der Angaben direkt an der Rechnung (der Tooltip
  genügt). Ebenso Käufe mit anderer Programm-ID in Japan und Amerika; „zuweisen“ genügt.
- **Woanders (Entscheidung 26.10.2026):** die Retro-Sammlung älterer Spiele aller Systeme. Sie
  kommt in den [VR-Navigator](https://github.com/GreenkeeperX/vr-navigator), dessen Reiter
  „Entdecken“ schon die ganze Sammlung mit Genre, Spielerzahl und Filtern zeigt; mit Preisen und
  Ländern hat sie nichts zu tun.
- **Gestrichen (Entscheidung 13.10.2026):** Das Tool bleibt ein privates Werkzeug auf dem
  eigenen Server. Damit entfallen:
  - die Sprache der Oberfläche,
  - das Heimatland,
  - ein neuer Name,
  - ein öffentliches Angebot mit Werbung.

## Eingang

Neue Wünsche, noch nicht eingeordnet.

- **Sammlung mit Spielinfos:** eine zweite Ansicht der Sammlung neben den DLC, mit Genre,
  Spielerzahl, lokal oder online, Koop, GameShare und Ähnlichem, automatisch gelesen. Switch 2 als
  Filter und Marke am Titel, kein eigener Reiter: Es sind dieselben Spiele. titledb (schon
  wöchentlich gestreamt) führt je Titel Kategorien, Spielerzahl, Verlag und Erscheinungsdatum,
  ohne neuen Abruf. Welche Felder die Nintendo-Europa-Suche dazu liefert und was die Shopseiten zu
  Koop und GameShare sagen, zeigt seit 1.4.1 „Verbindung testen“ (Spielinfos), seit 1.4.2 auch
  DekuDeals, Nintendos GameShare-Liste, Wikidata und IGDB (mit eigenem Schlüssel). Wie bei den
  Sprachen: eine offene Quelle liefert, Nintendo bestätigt, nur eine Quelle heißt „≈“.
  Entschieden (26.10.2026): Umschalter „DLC | Spiele“ im Reiter Sammlung, alle Angaben erst einmal
  zeigen, Mischungen wie vorgeschlagen. Schritte: 1.6.0 Daten (DekuDeals beim DLC-Schritt, Nintendo
  bestätigt, erledigt), 1.6.1 Ansicht „Spiele“ mit Filtern, Sortierung, „≈“, Mischungen und
  „Überrasch mich“ (erledigt), 1.6.2 IGDB für Koop (lokal, online, Höchstzahl, Splitscreen) und
  GameShare. Danach prüfen, welche Angaben wie prominent stehen.
  Runde 2 entschieden (27.10.2026): Tabelle bleibt, einzeilig, sortierbare Köpfe, Spalten Spiel ·
  Spieler · Koop · Genre · Metacritic · Spielzeit · Jahr; Pakete als ihre Spiele mit „aus: …“; Genre
  von Nintendo; Metacritic, sonst OpenCritic grau-kursiv (1.7.0, erledigt); „Mein Stand“ (Backlog,
  angefangen, durchgespielt, Favorit) und Sprachen der Spiele (1.7.1, erledigt); GameShare, Koop
  über IGDB und die Liste „Widersprüche“ mit Klarstellungen im Repository (1.7.2, erledigt); alle
  Genres farbig, Wertung farbig vor dem Genre, Einzelheiten wieder untereinander (1.7.3, erledigt);
  Angaben der Switch-2-Edition bei vorhandenem Upgrade-Paket (1.7.4, erledigt). Mein Stand „ignorieren“ (nie wieder vorschlagen), Backlog pink, Stern fett, wie im VR-Navigator (1.7.24, erledigt); ○ ▷ ✓ ebenso kräftig (1.7.25, erledigt). Zeichen von Mein Stand als Grafik, Preisverlauf mit ✕, „überm Bestpreis“, gutem Preis unter „zuletzt“ und Links (1.7.26, erledigt). Tooltips mit Bestpreis und Land, Zeile unter der Maus, Mein Stand ohne Neuaufbau, „jetzt“ im Preisverlauf grün mit ★ (1.7.27, erledigt). Zeile bleibt beim Aufklappen stehen, Hover im Darkmode dunkler (1.7.28, erledigt). Sortierte Spalte mit Richtung in „Sortieren“ (1.7.29, erledigt). Offen: Was die
  Switch-2-Edition verbessert (Auflösung, Bildrate, Maus), sobald eine Quelle es lesbar nennt; der
  Verbindungstest zeigt seit 1.7.2, ob die Europa-Suche zu einem Switch-2-Spiel passende Felder kennt.
