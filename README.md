# eShop-Kompass

Vergleicht die Titel deiner DekuDeals-Wishlist über mehrere Nintendo-eShops,
rechnet in Euro um und schnürt je Land das günstigste Paket inklusive
Guthabenkarten, Rest und Füllartikeln.

## Start

Das Image wird bei jeder Änderung automatisch gebaut und liegt unter
`ghcr.io/OWNER/eshop-kompass:latest`. Die `docker-compose.yml` zeigt den
Betrieb als unprivilegierter Benutzer mit schreibgeschütztem Dateisystem.

    docker compose up -d

Danach http://<server>:8787 öffnen. Der erste Abgleich startet von selbst,
sucht pro Titel die Nintendo-IDs (ein Abruf pro Sekunde) und dauert bei
44 Titeln rund drei Minuten. Spätere Läufe brauchen Sekunden.

Ohne Docker: `python3 -m app.server` (Python 3.10+, keine Zusatzpakete).

## Ansichten

- Radar: eine Zeile je Wishlist-Titel mit dem besten Preis jetzt (getrennt nach
  leicht und schwer erreichbaren Ländern), dem Bestpreis, deinem Zielpreis und
  einem Urteil (kaufen, gutes Angebot, nur schwer, warten).
- Pakete, Angebote je Land: Länderkarten als dichtes Raster oder große Liste.
  Je Land die Wishlist-Angebote mit Kosten, Karten, Rest, Angebotsende und
  Vorschlägen zum Dazunehmen (+) oder Weglassen (−).
- Pakete, gemeinsamer Korb: "Korb für alle" öffnet eine Vergleichstabelle,
  Titel als Zeilen, Länder als Spalten. Das günstigste Land ist hervorgehoben,
  aber nur unter Ländern, die den ganzen Korb anbieten.
- Preisvergleich: alle Titel mal alle Länder in Euro.

Marken an jedem Angebot: ★ Bestpreis über alle Länder, ☆ Bestpreis der leicht
erreichbaren Länder, grün Landestief, rot Angebot darüber. Der Bestpreis ist
der niedrigste Preis, den es je gab, zum heutigen Kurs.

Der Landespreis verlinkt den Verlauf bei DekuDeals, der Europreis die
eShop-Seite des Landes.

## Einrichten

Unter Einstellungen, jede Änderung wird sofort gespeichert:

- Länder: beliebig ein- und ausschalten. Die Spalte Preisniveau zeigt für
  jedes Land, wie es zu deiner Wishlist steht, auch wenn es abgeschaltet ist.
- Wechsel: leicht (Karte, kein Rest), mittel (Guthabenkarten), schwer
  (Amerika: Guthaben muss vor dem Wechsel 0 sein). Je Stufe gilt eine eigene
  Mindestersparnis.
- Bezahlen: Karte, Guthabenkarte oder das Günstigere von beiden.
- Steuer: Aufschlag in Prozent, wo der Shop Preise ohne Steuer zeigt
  (USA, Kanada).
- Guthabenkarten: eine Karte je Zeile, `Wert = Preis in Euro | Link`. Ein
  vorangestelltes `x` heißt nicht vorrätig.
- Sprachen: Gibt es in Deutschland eine deutsche Fassung, fallen Regionen ohne
  sie weg. Europa gilt als dasselbe Produkt, Japan wird bei Nintendo geprüft.
- Sicherung: Einstellungen, Karten, Zielpreise und Körbe als Datei.

## Tiefstpreise und Verlauf

Nach dem Preisabruf lädt das Tool je Titel und Land den digitalen Tiefstpreis
von der DekuDeals-Artikelseite nach (ein Abruf alle 2,5 Sekunden, Angebote
zuerst) und führt ihn danach selbst fort. Jeder Preiswechsel landet zusätzlich
in `data/history.json`.

## Datenquellen

- Wishlist und Titel-IDs: dekudeals.com (öffentliche Wishlist, IDs werden dauerhaft gespeichert)
- Preise und Verfügbarkeit: api.ec.nintendo.com/v1/price (inoffiziell)
- Sprachen: search.nintendo-europe.com (Europa), store-jp.nintendo.com (Japan)
- Wechselkurse: open.er-api.com, ersatzweise frankfurter.dev (EZB)

## Tests

    python3 -m unittest tests.test_all
