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

- Pakete, Angebote je Land: Länderkarten als dichtes Raster oder große Liste
  (Umschalter). Je Land die Wishlist-Angebote mit Kosten, Karten, Rest,
  Angebotsende und Vorschlägen zum Dazunehmen (+) oder Weglassen (−).
- Pakete, gemeinsamer Korb: "Korb für alle" öffnet eine Vergleichstabelle,
  Titel als Zeilen, Länder als Spalten. Das günstigste Land ist hervorgehoben,
  aber nur unter Ländern, die den ganzen Korb anbieten.
- Preisvergleich: alle Titel mal alle Länder in Euro. Der Stern legt einen
  Titel in den gemeinsamen Korb.

Grüne Rabatt-Marke = Tiefstpreis erreicht, rote = Angebot über Tiefstpreis.
Ein Klick auf einen Preis öffnet den Preisverlauf bei DekuDeals im passenden Land.

## Einrichten

Unter Einstellungen je Land:

- Bezahlen: Karte (exakter Betrag, Rest 0) oder Guthabenkarte.
- Guthabenkarten: Werte in Landeswährung, z. B. `1000 3000 5000=29,50`.
  Hinter `=` steht dein Kaufpreis in Euro. Ohne Preis gilt Kurs plus Aufschlag.
- Guthaben: was auf dem Konto in diesem Land noch liegt.
- Rest blockiert Wechsel: in Amerika muss das Guthaben vor dem Länderwechsel 0 sein.

"Konto steht aktuell in" markiert dein jetziges Land. Dort gilt keine
Wechsel-Schwelle.

## Tiefstpreise und Verlauf

Nach dem Preisabruf lädt das Tool je Titel und Land den Tiefstpreis von der
DekuDeals-Artikelseite nach (ein Abruf alle 2,5 Sekunden, Angebote zuerst, bei
44 Titeln und 11 Ländern einmalig rund 20 Minuten im Hintergrund). Danach
führt es den Tiefstpreis selbst fort. Jeder Preiswechsel landet zusätzlich in
`data/history.json`. In Ländern, in denen DekuDeals auch Händler führt, kann
der Tiefstpreis von einer Händler-Version stammen.

## Datenquellen

- Wishlist und Titel-IDs: dekudeals.com (öffentliche Wishlist, IDs werden dauerhaft gespeichert)
- Preise und Verfügbarkeit: api.ec.nintendo.com/v1/price (inoffiziell)
- Wechselkurse: open.er-api.com, ersatzweise frankfurter.dev (EZB)

## Tests

    python3 -m unittest tests.test_all
