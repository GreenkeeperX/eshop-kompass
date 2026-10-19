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

Derzeit nichts offen.

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
- **Gestrichen (Entscheidung 19.10.2026):** Kleinteile wie Kostüme zusammenfassen; die Einzelteile
  bleiben, wie sie sind. Ebenso die „Heute“-Zeile; „Zu erledigen“ deckt sie ab. Ebenso: das
  Ablaufdatum der Mitgliedschaft aus dem Kaufverlauf (dort steht keine Laufzeit, der Betrag passt
  wegen Punkten und Codes oft zu keiner Variante), ein Rückblick über die Ersparnis, weitere
  Bezugsquellen wie Händler-Codes und das Alter der Angaben direkt an der Rechnung (der Tooltip
  genügt).
- **Gestrichen (Entscheidung 13.10.2026):** Das Tool bleibt ein privates Werkzeug auf dem
  eigenen Server. Damit entfallen:
  - die Sprache der Oberfläche,
  - das Heimatland,
  - ein neuer Name,
  - ein öffentliches Angebot mit Werbung.

## Eingang

Neue Wünsche, noch nicht eingeordnet.

- [ ] **Käufe mit anderer Programm-ID in Amerika:** Manche Spiele haben in Japan eine andere
  Programm-ID als in den USA (anderer Verlag), dann fehlt der englische Name; bisher „zuweisen“.
- [ ] **Tastatur und Bildschirmleser:** Symbolknöpfe (+, ✓, ×, ↺, ✎) mit zugänglichem Namen, Fokus im
  Verlaufsdialog.
