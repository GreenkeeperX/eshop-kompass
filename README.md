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
  leicht und schwer erreichbaren Ländern), dem Abstand zum Maßstab des Urteils
  in Euro, deinem Zielpreis und einem Urteil. Maßstab ist der typische
  Angebotspreis (siehe unten), wo er fehlt der Bestpreis; beide stehen in der
  Zelle und im Tooltip.
  - kaufen: Zielpreis erreicht, Bestpreis erreicht (bis 2 % darüber, gilt
    immer) oder höchstens 0,50 € über dem Maßstab,
  - gutes Angebot: bis 15 % oder höchstens 2 € über dem Maßstab,
  - nur schwer: stark nur in einem Land der Stufe schwer,
  - warten: im Angebot, typischerweise aber günstiger.
  Ein leeres Zielfeld zeigt den Bestpreis grau, wenn er unter dem Preis jetzt
  liegt; "übernehmen" setzt ihn als Zielpreis.
  DE✓ am Preis heißt: deutsche Fassung bestätigt oder dasselbe Produkt wie im
  deutschen eShop; "andere Fassung" heißt: dort ohne Deutsch.
  Die beiden Euro-Grenzen sind unter Einstellungen änderbar.
- Kaufplan: ein Gesamtvorschlag, welche Titel du jetzt in welchem Land kaufst.
  Kandidaten sind die Titel mit dem Urteil "kaufen" oder "nur schwer",
  per Schalter auch "gutes Angebot". Jeder Titel geht ins Land, wo er am
  wenigsten kostet. Ein Land bleibt nur im Plan, wenn sein Paket die
  Mindestersparnis seiner Wechselstufe schafft; sonst wandern seine Titel ins
  nächstbeste Land. Ist ein Titel dort teurer als der Preis, der ihn zum
  Angebot machte, steht er unter "Lieber warten". Reihenfolge: zuerst das
  Land, in dem dein Konto steht, dann leicht, mittel, schwer, innerhalb einer
  Stufe nach Angebotsende. "Als Korb vergleichen" übernimmt die Titel in den
  gemeinsamen Korb.
  "gekauft" an einem Land vermerkt den Kauf im Kaufprotokoll
  (`data/purchases.json`): Dein Konto steht danach dort, ein Rest bleibt dort
  als Guthaben, Guthaben anderer Länder gilt als weg (Nintendo nimmt es beim
  Wechsel nicht mit). Gekaufte Titel verschwinden aus dem Plan, auch solange
  sie noch auf der Wishlist stehen. Unter dem Plan stehen die letzten Käufe
  mit der Ersparnis gegenüber Deutschland; "letzten zurücknehmen" stellt Land
  und Guthaben wieder her.
- Pakete, Angebote je Land: Länderkarten als dichtes Raster oder große Liste.
  Je Land die Wishlist-Angebote mit Kosten, Karten, Rest, Angebotsende und
  Vorschlägen zum Dazunehmen (+) oder Weglassen (−). Die Kopfzahl ist der
  Abstand zum Optimum: was die Titel hier zusammen über ihren Bestpreisen
  liegen (grün "Optimum", gold bis 2 € je Titel darüber). Die Ersparnis
  gegenüber Deutschland steht in der Zeile darunter und entscheidet weiter
  über die Wechselschwelle. Ein Rest ist kein Verlust: Ersparnis und
  Schwelle rechnen mit dem, was die Spiele selbst kosten ("Spiele X €"); ab
  5 € Rest warnt das Paket.
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

Bei Guthabenkarten ist der Europreis ein Anteil: Preis je Guthabeneinheit der
günstigsten Karte mal Shop-Preis. Kaufst du einen Titel allein, brauchst du
meist mehr Guthaben, als er kostet. Was das kostet, steht im Tooltip als
"allein gekauft" mit Karten und Rest.

Unter der Vergleichstabelle steht, was der Korb kostet, wenn jeder Titel im
günstigsten Land mit Kartenzahlung gekauft wird. Dort kostet der Wechsel
nichts und es bleibt kein Rest.

Marken an jedem Angebot: ★ Bestpreis über alle Länder, ☆ Bestpreis der leicht
erreichbaren Länder, grün Landestief, rot Angebot darüber. Der Bestpreis ist
der niedrigste Preis, den es je gab, zum heutigen Kurs.

Im Preisvergleich steht der Bestpreis je Titel in einer eigenen Spalte, das
Land, in dem es ihn gab, ist gold umrandet. Grün hinterlegt ist das günstigste
Angebot jetzt; ein günstiger Normalpreis ohne Angebot wird nicht hervorgehoben.

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
  Tag den Preis von der Shopseite (aus den Produktdaten der Seite; nennt sie
  mehrere Angebote, zählt das günstigste). Unter dem
  Eingabefeld steht, was es gelesen hat. Liefert die Seite keinen Preis oder
  ist der Wert älter als drei Tage, gilt dein eingetragener Preis.
  Auf gelesene Preise kommt die Servicegebühr des Shops (Einstellung,
  Vorgabe 0,40 € plus 7,75 %): Die Seite zeigt den Preis ohne sie, berechnet
  wird sie erst an der Kasse. Bei Eneba trafen diese Werte im Oktober 2026
  acht Käufe zwischen 5,57 und 93,03 € auf den Cent. Der feste Teil zählt je
  Karte; bei mehreren Karten in einer Bestellung fällt er nur einmal an. Von
  Hand eingetragene Preise bleiben, wie du sie einträgst.
- gg.deals: Für jedes aktive Land mit Guthabenkarten liest
  das Tool einmal am Tag die Kartengruppe bei gg.deals, eine Seite je Land.
  Sie nennt je Kartenwert den günstigsten Preis über alle Shops in Euro;
  gg.deals rechnet dort mit Gebühr und teils mit einem Rabattcode, den die
  Kartenseite nennt (der Tooltip verlinkt sie). Fehlende Kartenwerte kommen
  dazu, bei eingetragenen gilt der günstigere Preis, mit x markierte bleiben
  draußen. Werte älter als drei Tage zählen nicht. Abschaltbar unter
  Einstellungen. Stand Oktober 2026 verlangt gg.deals eine Cloudflare-Prüfung
  im Browser (HTTP 403). Das Tool umgeht sie nicht: Es meldet die Sperre,
  versucht es einmal am Tag wieder und rechnet mit den übrigen Preisen.
- Glaubhaft: Ein gelesener Kartenpreis (Shopseite oder gg.deals) zählt nur
  zwischen 70 und 160 % des Nennwerts zum Mittelkurs. Alles andere ist fast
  sicher ein Lesefehler, etwa ein Gebührenhinweis statt des Preises. Solche
  Werte stehen mit „unglaubhaft, ignoriert“ unter der Kartenliste und im
  Protokoll, es gilt dein Eintrag.
- Deutschland: Die Vergleichsbasis ist immer der Preis im deutschen eShop.
  Wer mit günstigen deutschen Guthabenkarten (etwa von Eneba) zahlt, schaltet
  "Deutschland mit Guthaben" (DG) ein: dasselbe Konto und dieselben Preise,
  gerechnet wie jedes Guthabenland. Ein Rest bleibt auf dem Konto und wird
  ab 5 € gewarnt (Nintendo nimmt Guthaben bei keinem Länderwechsel mit). Karten, die bis 0.9.2
  bei Deutschland standen, wandern beim Update dorthin.
- Datei einlesen: Unter `countries.<Land>.cards_add` ergänzt eine Datei
  Karten, ohne vorhandene zu ersetzen. Gibt es den Kartenwert schon, bekommt
  die Zeile nur den Link.
- Sprachen: Gibt es in Deutschland eine deutsche Fassung, fallen Regionen ohne
  sie weg. Europa gilt als dasselbe Produkt. Japan und Amerika prüft das Tool
  je Titel einmal bei Nintendo (store-jp.nintendo.com, nintendo.com über
  ec.nintendo.com) und danach nur, wo die Angabe fehlt. Was offen bleibt,
  steht unter Einstellungen, "Sprachen prüfen", mit Link in den Store:
  einmal "Deutsch ja" oder "nein" bestätigen, das gilt dauerhaft und geht der
  Angabe von Nintendo vor. Ist für eine Region unbekannt, ob es Deutsch gibt,
  bleibt das Angebot im Preisvergleich sichtbar („Sprache?“), zählt
  aber nicht für Bestpreis, Urteil und Kaufplan. Ist ein Titel nur dort
  kaufbar, sagt das Radar es als Grund. Mit „nur warnen“ zählen solche
  Angebote wie früher mit.
- Sicherung: Einstellungen, Karten, Zielpreise und Körbe als Datei.

Jede Spalte und jedes Feld erklärt sich im Tooltip. Das Protokoll unter
Einstellungen läuft während eines Abgleichs mit, nennt oben den Start des
Laufs und zeigt die Uhrzeit deines Browsers. "Verbindung testen" schreibt in
eine eigene Box darüber. Die Wechselkurse holt das Tool bei jedem Abgleich,
die Quelle erneuert sie einmal am Tag.

## Tiefstpreise und Verlauf

Nach dem Preisabruf lädt das Tool je Titel und Land den digitalen Tiefstpreis
von der DekuDeals-Artikelseite nach (ein Abruf alle 2,5 Sekunden, Angebote
zuerst) und führt ihn danach selbst fort, auch dort, wo DekuDeals keinen Wert
hat. Jeder Preiswechsel landet zusätzlich in `data/history.json`.

"Verlauf" neben jedem Titel (Radar, Preisvergleich) zeigt diese Aufzeichnung
als Kurve je Land und dazu: Preis jetzt, Normalpreis, tiefster
aufgezeichneter Preis mit Datum, Zahl der Angebote, typische Dauer, Anteil der
Zeit im Angebot und das letzte Angebot. Europreise rechnen mit dem heutigen
Kurs und Zahlweg, damit Länder und Zeitpunkte vergleichbar bleiben. Ein
Angebot ist jede Strecke unter dem heutigen Normalpreis. Die Aufzeichnung
kennt nur Zeiten, in denen das Tool lief; in den ersten Wochen sind die
Kurven entsprechend kurz.

### Typischer Angebotspreis

Die DekuDeals-Artikelseite enthält den Tagesverlauf des Preises seit etwa
Mitte 2024. Das Tool liest daraus die Angebotsphasen der letzten zwei Jahre
(Normalpreis ist der häufigste Preis, ein Angebot jede Strecke mindestens 3 %
darunter) und merkt sich je Phase den tiefsten Preis. Typischer
Angebotspreis ist der Median dieser Tiefstwerte, ab zwei Phasen. War das
letzte Angebot tiefer als der Median, gilt dieses: Nintendo senkt
Angebotspreise oft dauerhaft, und der Median würde dann noch den alten Preis
zeigen. Je Titel zählt das günstigste leicht erreichbare Land, in Euro zum
heutigen Kurs. Unter Einstellungen lässt sich das Urteil auf den
Allzeit-Bestpreis zurückstellen.

Den Verlauf lädt das Tool mit dem Tiefstpreis. Für Titel, deren Tiefstpreis
schon bekannt ist, holt es die Seite nur während eines Angebots nach,
höchstens 40 je Abgleich und danach einmal im Monat.

## Selbstprüfung

Nach jedem Abgleich prüft das Tool seine Ergebnisse: unglaubhafte
Kartenpreise, ein Preis je Währungseinheit, der sich seit dem letzten Lauf um
mehr als 15 % geändert hat, ein Land, in dem plötzlich weniger als die Hälfte
der Titel kaufbar ist, und Wechselkurse, die älter als drei Tage sind.
Auffälligkeiten stehen im Protokoll und als Hinweis über den Ansichten.

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
- Sprachen: search.nintendo-europe.com (Europa), store-jp.nintendo.com (Japan),
  nintendo.com-Produktseiten über ec.nintendo.com (Amerika), sonst deine Bestätigung
- Wechselkurse: open.er-api.com, ersatzweise frankfurter.dev (EZB)

## Tests

    python3 -m unittest tests.test_all
