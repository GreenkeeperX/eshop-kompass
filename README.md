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
  leicht und schwer erreichbaren Ländern), dem Abstand zum Bestpreis in Euro
  (der Bestpreis selbst steht im Tooltip), deinem Zielpreis und einem Urteil:
  - kaufen: Zielpreis erreicht, Bestpreis (bis 2 % darüber) oder höchstens
    0,50 € über dem Bestpreis,
  - gutes Angebot: bis 15 % oder höchstens 2 € über dem Bestpreis,
  - nur schwer: stark nur in einem Land der Stufe schwer,
  - warten: im Angebot, war aber schon deutlich günstiger.
  Die beiden Euro-Grenzen sind unter Einstellungen änderbar.
- Pakete, Angebote je Land: Länderkarten als dichtes Raster oder große Liste.
  Je Land die Wishlist-Angebote mit Kosten, Karten, Rest, Angebotsende und
  Vorschlägen zum Dazunehmen (+) oder Weglassen (−).
- Pakete, gemeinsamer Korb: "Korb für alle" öffnet eine Vergleichstabelle,
  Titel als Zeilen, Länder als Spalten. Das günstigste Land ist hervorgehoben,
  aber nur unter Ländern, die den ganzen Korb anbieten.
- Preisvergleich: alle Titel mal alle Länder in Euro, mit Angebotsende.

Jeder Europreis enthält alles, was der Kauf dich kostet: Shop-Preis, Steuer,
Wechselkurs und den Weg zum Guthaben (Kartengebühr oder Preis der
Guthabenkarte). Der Tooltip am Preis zeigt die Rechnung samt Stand des
Wechselkurses. Ein ≈ vor dem Preis heißt geschätzt: Für das Land ist keine
Guthabenkarte mit bekanntem Preis eingetragen, gerechnet wird mit Kurs plus
pauschalem Aufschlag.
Auch Kartenzahlung ist eine Näherung (Mittelkurs plus Fremdwährungsgebühr),
die Bank rechnet mit ihrem eigenen Kurs.

Unter der Vergleichstabelle steht, was der Korb kostet, wenn jeder Titel im
günstigsten Land mit Kartenzahlung gekauft wird. Dort kostet der Wechsel
nichts und es bleibt kein Rest.

Marken an jedem Angebot: ★ Bestpreis über alle Länder, ☆ Bestpreis der leicht
erreichbaren Länder, grün Landestief, rot Angebot darüber. Der Bestpreis ist
der niedrigste Preis, den es je gab, zum heutigen Kurs.

Der Landespreis verlinkt den Verlauf bei DekuDeals, der Europreis die
eShop-Seite des Landes.

## Einrichten

Unter Einstellungen, jede Änderung wird sofort gespeichert:

- Länder: beliebig ein- und ausschalten. Die Spalte Preisniveau zeigt für
  jedes Land, wie es zu deiner Wishlist steht, auch wenn es abgeschaltet ist.
- Wechsel: leicht (Karte, kein Rest), mittel (Guthabenkarten, ein Rest
  verfällt beim Wechsel), schwer (Amerika: Guthaben muss vor dem Wechsel 0
  sein). Je Stufe gilt eine eigene Mindestersparnis.
- Fremdwährungsgebühr: 0 für Karten ohne Auslandseinsatzentgelt.
- Bezahlen: Karte, Guthabenkarte oder das Günstigere von beiden.
- Steuer: Aufschlag in Prozent, wo der Shop Preise ohne Steuer zeigt
  (USA, Kanada).
- Aufschlag: was Guthaben über dem Wechselkurs kostet, wenn bei einer Karte
  kein Preis steht. Je Land einstellbar, zum Beispiel 1,75 für Japan, wenn du
  das Guthaben dort per Kreditkarte zum Nennwert kaufst. Die Spalte "Dein Kurs"
  zeigt, was dabei herauskommt.
- Sammlung: Titel aus deiner DekuDeals-Sammlung werden als vorhanden markiert,
  bei DLC steht dabei, ob du das Hauptspiel hast.
- Guthabenkarten: eine Karte je Zeile, `Wert = Preis in Euro | Link`. Ein
  vorangestelltes `x` heißt nicht vorrätig. Kaufst du Guthaben zum Kurs (etwa
  bei Amazon Japan), genügen die Werte, zum Beispiel `500 1000 2000 3000 5000
  9000` mit Aufschlag 0: Dann folgen die Kosten jedem neuen Kurs und der Rest
  zählt mit.
  Hat eine Karte einen Link, liest das Tool beim Abgleich höchstens einmal am
  Tag den Preis von der Shopseite (aus den Produktdaten der Seite). Unter dem
  Eingabefeld steht, was es gelesen hat. Liefert die Seite keinen Preis oder
  ist der Wert älter als drei Tage, gilt dein eingetragener Preis.
- Deutschland: Karten unter Nennwert (etwa von Eneba) senken den
  Deutschland-Preis und damit die Vergleichsbasis. Ein Rest bleibt auf dem
  Konto und zählt nicht als Kosten. Karten zum Nennwert oder darüber zählen
  nicht.
- Datei einlesen: Unter `countries.<Land>.cards_add` ergänzt eine Datei
  Karten, ohne vorhandene zu ersetzen. Gibt es den Kartenwert schon, bekommt
  die Zeile nur den Link.
- Sprachen: Gibt es in Deutschland eine deutsche Fassung, fallen Regionen ohne
  sie weg. Europa gilt als dasselbe Produkt, Japan wird bei Nintendo geprüft.
- Sicherung: Einstellungen, Karten, Zielpreise und Körbe als Datei.

Jede Spalte und jedes Feld erklärt sich im Tooltip. Das Protokoll unter
Einstellungen läuft während eines Abgleichs mit und bleibt am Ende stehen.

## Tiefstpreise und Verlauf

Nach dem Preisabruf lädt das Tool je Titel und Land den digitalen Tiefstpreis
von der DekuDeals-Artikelseite nach (ein Abruf alle 2,5 Sekunden, Angebote
zuerst) und führt ihn danach selbst fort, auch dort, wo DekuDeals keinen Wert
hat. Jeder Preiswechsel landet zusätzlich in `data/history.json`.

## Abrufen

Das Tool fragt immer mit seiner eigenen Kennung an (`eshop-kompass/<Version>`),
macht Pausen zwischen den Abrufen und hört bei einer Sperre (HTTP 403 oder 429)
oder einer Prüfseite auf, statt sich als Browser auszugeben. Der Rest folgt
beim nächsten Abgleich. "Verbindung testen" zeigt je Quelle, was zurückkommt,
auch für die erste Guthabenkarte mit Link (liest die Seite einen Preis?).

Die Oberfläche nimmt Änderungen nur als JSON an. Eine fremde Webseite kann so
keine Einstellungen überschreiben. Eine Anmeldung gibt es nicht, nach außen
freigeben solltest du das Tool deshalb nicht.

## Datenquellen

- Wishlist, Sammlung und Titel-IDs: dekudeals.com (öffentliche Wishlist, IDs werden dauerhaft gespeichert)
- Preise und Verfügbarkeit: api.ec.nintendo.com/v1/price (inoffiziell)
- Sprachen: search.nintendo-europe.com (Europa), store-jp.nintendo.com (Japan)
- Wechselkurse: open.er-api.com, ersatzweise frankfurter.dev (EZB)

## Tests

    python3 -m unittest tests.test_all
