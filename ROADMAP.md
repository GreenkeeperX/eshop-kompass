# Roadmap

Woran am eShop-Kompass als Nächstes gearbeitet wird. Jeder Schritt wird eine kleine
Version mit Tests, Prüfung der Oberfläche, Versionsnummer, README und Commit. Erledigtes
fällt hier heraus (Entscheidung 13.10.2026); was das Tool kann, steht in der
[README](README.md), wann es dazukam, in der Git-Geschichte.

Diese Datei liegt in einem öffentlichen Repository. Sie enthält deshalb keine Namen,
Wishlist-Links oder -Kennungen, Hostnamen, Adressen und keine Angaben aus dem eigenen
Konto (siehe [CLAUDE.md](CLAUDE.md)).

## Offen

- [ ] **Online-Mitgliedschaft ausbauen.** Da ist bisher: sechs Varianten je aktivem Land mit
  Einkaufspreis, Bestpreis, Links, Erinnerung vor Ablauf und eigenen Angeboten (Amazon Japan liest
  der Abgleich vom Link). Fehlt noch:
  - Tiefstpreise für 1 Monat und Erweiterungspaket Familie (DekuDeals führt sie nicht),
  - weitere Bezugsquellen: Händler-Codes (Keyshops), Deals etwa von mydealz,
  - die Mitgliedschaft wählbar im Warenkorb (als Hinweis im Rest steht sie seit 0.57.1).
- [ ] **Kleinteile zusammenfassen.** Viele Kleinteile eines Spiels (etwa Kostüme) zusammenfassen,
  aber erst nach Erfahrung mit den gruppierten Pässen.
- [ ] **Kaufverlauf und Sammlung abgleichen.** Den Kaufverlauf mit der ganzen DekuDeals-Sammlung
  abgleichen:
  - Slug-Stufe,
  - „Bei DekuDeals nachtragen“,
  - eine Zeile in „Zu erledigen“, nur für neue Spiele.

## Ohne Arbeit für uns

- **Sprache in Japan:** Titel, die titledb nicht kennt, liest der Browser-Helfer
  „JP-Sprachen lesen“. Ob der Bot-Schutz seine Abrufe dauerhaft durchlässt, zeigt erst der
  Gebrauch.
- **Südafrika:** Ob Kartenzahlung dort geht, ist ungetestet. Bis dahin gilt „leicht, Karte“.
- **Kaufverlauf:** Nintendo zeigt nur die letzten zwei Jahre.
- **Tests der Oberfläche:** Es gibt keine automatischen Tests. Geprüft wird per Screenshots
  mit Testdaten, weil das Tool ohne Zusatzpakete auskommen soll.

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
