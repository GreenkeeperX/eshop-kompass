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

- [ ] **Schritte als Paket prüfen.** „Andere Länder“ zeigt manchmal ein günstigeres Land für alle
  Titel eines Schritts, weil der Plan jeden Titel einzeln verteilt und erst danach die Karten
  rechnet. Der Plan könnte jeden Schritt am Ende gegen die anderen Länder prüfen (Rechenregel,
  braucht eine Entscheidung).
- [ ] **Handy: Korb und Rechnung.** Korb mit Länder-Umschalter statt seitlichem Scrollen, Antippen
  eines Preises zeigt die Rechnung (statt Wissen nur im Tooltip; hilft auch bei Tastatur).
- [ ] **„Heute“-Zeile.** Oben höchstens drei Aufgaben als Knöpfe mit Frist.
- [ ] **Code aufteilen.** Die Oberfläche in mehrere Dateien ohne Build, der Planer in Bewertung,
  Karten und Plan.
- [ ] **Notbetrieb.** Festlegen und zeigen, was läuft, wenn DekuDeals sperrt oder seine Seiten
  ändert.

## Horizont 3: Klüger, nur mit belegtem Nutzen

- [ ] **Käufe:** Ablaufdatum der Online-Mitgliedschaft aus dem letzten Kauf vorschlagen (nie von selbst).
- [ ] **Kleinteile zusammenfassen** (Kostüme, Packs), nach Erfahrung mit den gruppierten Pässen.
- [ ] **Weitere Bezugsquellen** wie Händler-Codes, nur wenn sie regelmäßig günstiger sind.
- [ ] **Mitgliedschaft:** Tiefstpreise für 1 Monat und Erweiterungspaket Familie.
- [ ] **Rückblick:** Was hat der Kompass im Jahr gespart, welche Länder haben sich gelohnt?

## Risiken

- **DekuDeals** liefert Wishlist, Sammlung, IDs, Tiefstpreise, DLC und Pakete. Ändert es seine
  Seiten oder sperrt es, bleiben nur die Preise (siehe Notbetrieb).
- **Nintendos Preisschnittstelle** ist nicht offiziell.
- **Shopseiten mit Prüfseiten** (Amazon) können jederzeit unlesbar werden; dann gilt der
  eingetragene Preis.
- **Wartung:** Planer und Oberfläche haben je rund 2600 Zeilen; die Oberfläche prüfen nur
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
- **Gestrichen (Entscheidung 13.10.2026):** Das Tool bleibt ein privates Werkzeug auf dem
  eigenen Server. Damit entfallen:
  - die Sprache der Oberfläche,
  - das Heimatland,
  - ein neuer Name,
  - ein öffentliches Angebot mit Werbung.

## Eingang

Neue Wünsche, noch nicht eingeordnet.

- [ ] **„Passt dazu“ am Bestpreis ausrichten?** Bisher zählt nur, was ein Titel heute spart; der
  Abstand zum Bestpreis steht klein daneben. Offen, ob Vorschläge weit über dem Bestpreis wegfallen
  oder nach unten rutschen sollen.
- [ ] **Käufe ohne titledb-Namen:** Upgrade-Pässe für die Switch 2, Erweiterungspässe und Titel in
  chinesischer Schrift fehlen in den Listen; Ausweg bisher „zuweisen“ von Hand.
