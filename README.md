# eShop-Kompass

Vergleicht die Titel deiner DekuDeals-Wishlist über mehrere Nintendo-eShops,
rechnet in Euro um und schnürt je Land das günstigste Paket inklusive
Guthabenkarten, Rest und Füllartikeln.

## Start

Jeder Push auf `main` lässt die Tests laufen und baut danach das Image. Es
liegt unter `ghcr.io/OWNER/eshop-kompass:latest`, zusätzlich mit der
Versionsnummer als Tag (etwa `:0.18`). Die `docker-compose.yml` zeigt den
Betrieb als unprivilegierter Benutzer mit schreibgeschütztem Dateisystem.

    docker compose up -d

Danach http://<server>:8787 öffnen. Der erste Abgleich startet von selbst,
sucht pro Titel die Nintendo-IDs (ein Abruf pro Sekunde) und dauert bei
44 Titeln rund drei Minuten. Spätere Läufe brauchen Sekunden.

Ohne Docker: `python3 -m app.server` (Python 3.10+, keine Zusatzpakete).

## Ansichten

Vier Reiter: Jetzt, Titel, Länder, Einstellungen. Das "?" oben rechts öffnet
die Legende mit allen Farben, Marken und Begriffen. Die Farben haben je eine
Bedeutung: Grün nur fürs Urteil, Gold (★, Umrandung) nur für den Bestpreis,
Bernstein heißt prüfen, Rot heißt nein (Wechsel lohnt nicht, Rest blockiert,
hier teurer als ohne den Wechsel). Rabatte stehen grau daneben.

Begriffe: Einkaufspreis ist, was du zahlst, mit Steuer, Kurs, Guthabenkarten
und Gebühr. Bestpreis ist der niedrigste Einkaufspreis der letzten 24 Monate in
einem zählenden Land, mit deinem heutigen Einkaufsweg gerechnet; Normalpreise
zählen mit. Das Urteil misst nur die Preisgüte des günstigsten zählenden
Preises jetzt, mit oder ohne Rabatt, mit denselben Grenzen für jedes Land:
- kaufen: Zielpreis erreicht, Bestpreis erreicht (bis 2 % darüber) oder
  höchstens 0,50 € darüber,
- gut: bis 15 % oder höchstens 2 € darüber,
- warten: weiter weg.
Ein dauerhaft günstiger Normalpreis am Bestpreis ist also "kaufen" wie ein
Angebot (der Grund nennt dann "Normalpreis"), und ein teureres Angebot in einem
anderen Land macht daraus kein "warten". Rabatt und Angebotsende stehen nur
daneben. "kein Urteil" heißt: nirgends kaufbar, wo es zählt, oder der
Bestpreis ist noch nicht bekannt. Der Grund sagt, was Nintendo meldet: "noch
nicht erschienen", "nicht mehr im Verkauf", "im eShop nicht einzeln kaufbar"
(etwa nur im Abo wie N64-Spiele oder nur in einem Paket), "nicht im eShop
gefunden" (keine Nintendo-Kennung) oder "kostenlos".
Eurobeträge tragen immer das €-Zeichen, Beträge in Landeswährung stehen ohne
Zeichen in Spalten mit der Währung im Kopf oder mit Kürzel daneben.
Die beiden Euro-Grenzen sind unter Einstellungen änderbar. Ob sich der Weg in
ein Land lohnt, sagt getrennt davon die Zeile "Wechsel".

- Jetzt (Startseite): oben, in welchem Land dein Konto steht und mit wie viel
  Guthaben, direkt änderbar. Darunter "Zu erledigen": ungeprüfte Sprachen, die
  etwas ändern würden, Länder ohne Guthabenkarte mit Preis und Kartenpreise,
  die älter als 30 Tage sind, jeweils mit Sprung an die richtige Stelle.
  Dann der Kaufplan: ein Gesamtvorschlag, welche Titel du jetzt in welchem
  Land kaufst. Kandidaten sind die Titel mit dem Urteil "kaufen", per Schalter
  auch "gut". Jeder Titel geht ins Land, wo er am wenigsten kostet. Ein Land
  bleibt nur im Plan, wenn sein Wechselgewinn die Mindestersparnis seiner
  Wechselstufe schafft. Wechselgewinn ist, was dieselben Titel ohne diesen
  Wechsel kosten ("sonst": günstigstes zählendes Land gleicher oder leichterer
  Stufe, oder das Land, in dem dein Konto steht), minus was sie hier kosten.
  Das gilt auch für den Weg zurück nach Deutschland, wenn dein Konto woanders
  steht. Ohne eingetragenes Kontoland gilt Deutschland als Konto.
  Schafft ein Land das nicht, wandern seine Titel ins nächstbeste Land; sind
  sie dort kein Kauf mehr, stehen sie unter "Nicht im Plan" (zugeklappt), mit
  Grund, jeder Titel nur einmal. Reihenfolge: zuerst das Land, in dem dein Konto steht, dann leicht,
  mittel, schwer, innerhalb einer Stufe nach Angebotsende. Ein Rest ist kein
  Verlust, solange du im Land bleibst; folgt im Plan noch ein Wechsel, verfällt
  er (Nintendo nimmt Guthaben nicht mit) und zählt dort als Kosten ("Rest
  verfällt"). Das gilt auch für Guthaben, das im Land deines Kontos liegt,
  wenn der Plan es verlässt. Wo ein Rest den Wechsel blockiert (Einstellung
  "Rest blockiert", ab Werk Amerika), plant der Plan keinen Wechsel danach:
  So ein Land kommt nur als letzter Schritt, höchstens eins je Plan; das
  schwächere fällt heraus ("nur ein Land mit blockierendem Rest je Plan").
  Steht dein Konto in so einem Land und liegt dort Guthaben, plant der Plan
  nur dort, nennt, was hineinpasst, und führt die übrigen Titel unter "Nicht
  im Plan" ("Wechsel blockiert"), bis das Guthaben aufgebraucht ist oder der
  Support es löst. Das gilt auch am Tag nach einem vermerkten Kauf. Ist heute
  nichts auf "kaufen", nennt die Seite die Angebote, die am nächsten am
  Bestpreis liegen.
  "gekauft" an einem Land vermerkt den Kauf im Kaufprotokoll
  (`data/purchases.json`): Dein Konto steht danach dort, ein Rest bleibt dort
  als Guthaben, Guthaben anderer Länder gilt als weg. Gekaufte Titel
  verschwinden aus dem Plan, auch solange sie noch auf der Wishlist stehen.
  Unter "Gekauft" stehen die letzten Käufe, die Ersparnis rechnet wie der Plan
  mit dem, was die Spiele kosten (ein Rest bleibt Guthaben). "letzten Kauf zurücknehmen" stellt
  Land und Guthaben wieder her. "als Korb vergleichen" übernimmt die Titel in
  den gemeinsamen Korb.
- Titel, Liste: eine Zeile je Wishlist-Titel mit Urteil, Einkaufspreis samt
  Land und Stufe, Abstand zum Bestpreis und, wenn das beste Angebot in einem
  schweren Land liegt, der Alternative in einem leichten oder mittleren Land.
  Unter dem Urteil steht, ob der Titel im Plan ist oder warum nicht. Filter
  nach Urteil und Suche oben. Ein Klick auf den Titel klappt die Einzelheiten
  auf: die Rechnung, alle Länder mit Preis, Stufe, Rabatt, Angebotsende und
  Landestief (ungeprüfte Sprache direkt bestätigen), Bestpreis, typischer
  Angebotspreis, Zielpreis (leer heißt: das Urteil misst am Bestpreis;
  "Bestpreis übernehmen" setzt ihn) und die Links zu DekuDeals, eShop-Prices
  und zum eigenen Verlauf.
- Titel, Sammlung: die Spiele deiner DekuDeals-Sammlung mit ihren
  Zusatzinhalten (Abschnitt "DLC" der DekuDeals-Artikelseite), je DLC "hast du"
  oder "fehlt". Ob du einen DLC hast, sagt deine Sammlung bei DekuDeals. Steht
  ein fehlender DLC auf deiner Wishlist, stehen Urteil, Einkaufspreis und Land
  dabei, sonst ein Link zu DekuDeals, um ihn auf die Wishlist zu setzen.
  Upgrade-Pakete für die Switch 2 sind markiert. Spiele mit fehlenden DLC
  stehen oben, "nur Spiele mit fehlenden" blendet die übrigen aus. Das Tool
  liest dafür die Artikelseiten von Sammlung und Wishlist, höchstens 40 je
  Abgleich und jede einmal im Monat; nach dem Update dauert es also einige
  Abgleiche, bis alle gelesen sind.
- Switch 2: Steht eine Nintendo Switch 2 Edition auf der Wishlist und die
  Switch-1-Fassung in deiner Sammlung, trägt der Titel die Marke "Upgrade
  genügt", und die Einzelheiten nennen den Preis des Upgrade-Pakets und die
  Ersparnis gegenüber der Edition (wenn das Paket auf der Wishlist steht). Ohne
  die Switch-1-Fassung vergleicht die Zeile "Spiel plus Paket" mit der Edition,
  sofern beides auf der Wishlist steht. Die Edition gehört zum Spiel, dessen
  Kürzel sie bei DekuDeals um "nintendo-switch-2-edition" verlängert; das
  Paket ist ein DLC dieses Spiels.
  Der Kaufplan kauft nur einen Weg zur Switch 2: Hast du das Spiel, lässt er
  die Edition weg und plant das Upgrade-Paket wie jeden Wishlist-Titel. Stehen
  Edition und Switch-1-Fassung beide zum Kauf an, bleibt der günstigere Weg
  (Spiel plus Paket gegen die Edition). Ist der Preis des Pakets unbekannt,
  bleibt die Edition. Was wegfällt, steht unter "Nicht im Plan".
- Pakete: Steht eine Komplett-Edition oder ein Paket auf der Wishlist, nennen
  die Einzelheiten die bekannten Teile und vergleichen den Paketpreis mit dem,
  was die fehlenden Teile einzeln jetzt kosten ("Paket spart" oder "einzeln
  günstiger"). Teile in deiner Sammlung zählen nicht ("hättest du doppelt").
  Die Teile kommen aus "Contains" der Paketseite und "Included In" der Seiten
  der Teile; DekuDeals nennt dort oft nur das Hauptspiel. Ist nur ein Teil
  bekannt oder fehlt einem Teil der Preis (nicht auf der Wishlist), gibt es
  keinen Vergleich. Bei einem Titel steht außerdem, in welchen Paketen er
  steckt.
- Titel, Tabelle: alle Titel mal alle Länder in Euro, Spalten nach Stufe
  gruppiert (Länder, in denen gerade nichts zählt, am Ende). Angebote mit dem
  Urteil "kaufen" sind dunkelgrün hinterlegt, "gut" hellgrün; gold umrandet ist
  das Land, in dem es den Bestpreis gab. "Details" zeigt in jeder Zelle
  Landestief, Angebotsende und Sprache. Die Tabelle scrollt in einem eigenen
  Fenster, Kopfzeile und Titelspalte bleiben stehen. "nur Angebote" blendet
  auch Länder ohne Angebot aus.
- Länder, je Land: Länderkarten als dichtes Raster oder große Liste. Jede
  Karte enthält die Angebote des Landes, die günstiger als in Deutschland
  sind, und dauerhaft günstige Normalpreise mit dem Urteil "kaufen", also
  dieselben Titel, mit denen auch der Kaufplan rechnet. Die
  Kopfzahl ist der Einkaufspreis des Pakets. Darunter drei Zeilen:
  "Preis" nennt den Abstand der Spiele zur Summe ihrer Bestpreise (grün, wenn
  jeder Titel "kaufen" ist) und zählt die Urteile; "Wechsel" sagt, ob sich der
  Weg hierher lohnt ("✓ lohnt" oder rot "lohnt nicht", mit Gewinn gegenüber
  "sonst" und der Schwelle der Stufe); "Rest" nennt, was als Guthaben bleibt
  und was hineinpasst. Hürden (Rest blockiert, Karten fehlen, DLC braucht eine
  andere Region) stehen darunter. Die Tabelle zeigt je Titel Einkaufspreis,
  Abstand zum Bestpreis und den Preis ohne diesen Wechsel ("sonst").
  Vorschläge zum Dazunehmen (+) oder Weglassen (−) stehen unter der Tabelle,
  die ganze Rechnung unter "Rechnung". Ein Rest ist kein Verlust: Gewinn und
  Schwelle rechnen mit dem, was die Spiele selbst kosten ("Spiele X €").
  Vorhandenes Guthaben ist schon bezahlt, zählt aber zum Kurs mit.
- Länder, Korb: ein gemeinsamer Korb, verglichen in allen Ländern, Titel als
  Zeilen, Länder als Spalten, darunter Einkaufspreis, Preis, Wechsel und Rest
  wie auf den Karten. Das günstigste Land ist hervorgehoben, aber nur unter
  Ländern, die den ganzen Korb anbieten. "+" in der Titelliste legt einen
  Titel in den Korb.

Die Ansicht (Reiter, Liste oder Tabelle, Filter, aufgeklappte Kästen) merkt
sich der Browser; Korb, Auswahl und Zielpreise speichert der Server.

Jeder Europreis enthält alles, was der Kauf dich kostet: Shop-Preis, Steuer,
Wechselkurs und den Weg zum Guthaben (Kartengebühr oder Preis der
Guthabenkarte). Der Tooltip am Preis zeigt die Rechnung samt Stand des
Wechselkurses. Ein ≈ vor dem Preis heißt geschätzt: Für das Land ist keine
Guthabenkarte mit bekanntem Preis eingetragen, gerechnet wird mit Kurs plus
pauschalem Aufschlag.
Auch Kartenzahlung ist eine Näherung (Mittelkurs plus Fremdwährungsgebühr),
die Bank rechnet mit ihrem eigenen Kurs.

Ein Guthabenland ohne Karte mit Preis (weder eingetragen noch gelesen) zählt
nicht für Bestpreis, Urteil und Kaufplan: Dort ist Guthaben nicht zu bekommen,
der Europreis wäre geraten. Die Angebote bleiben sichtbar ("ohne Karte").

Die Servicegebühr eines Kartenshops (Eneba: 0,40 € plus 7,75 % je Bestellung)
steckt in jeder gelesenen Karte; besteht ein Paket aus mehreren Karten, zählt
der feste Teil nur einmal. Cashback des Shops (Eneba gibt es manchmal) steht
nicht in den Preisen. Mit "Mögliches Cashback" unter Einstellungen markiert
die Titelliste mit ✱, wo es ein Angebot zum Bestpreis machen könnte.

Bei Guthabenkarten ist der Europreis ein Anteil: Preis je Guthabeneinheit der
günstigsten Karte mal Shop-Preis. Kaufst du einen Titel allein, brauchst du
meist mehr Guthaben, als er kostet. Was das kostet, steht im Tooltip als
"allein gekauft" mit Karten und Rest.

Unter dem Korb steht, was er kostet, wenn jeder Titel im günstigsten Land
mit Kartenzahlung gekauft wird, sofern das günstiger ist als alles in einem
Land. Dort kostet der Wechsel nichts und es bleibt kein Rest.

Marken an jedem Angebot: ★ Bestpreis über alle Länder, rot: hier teurer als
ohne den Wechsel, ? zählt nicht (Sprache ungeprüft oder ohne Guthabenkarte).
Bestpreis und Landestief sind die niedrigsten Preise der letzten 24 Monate,
zum heutigen Kurs und Einkaufsweg.

Guthaben passend zum Einkauf: Jeder Europreis eines Guthabenlandes rechnet
mit den Karten, die du für genau diesen Betrag kaufen würdest (die
günstigste Kombination, die ihn deckt), anteilig. Für ein Spiel zu 60 MXN
zählt also die 100er Karte, nicht der bessere Kurs einer 1000er. Im Paket
teilen sich die Titel die Karten. Der Tooltip nennt die Karten und den Rest.

Bestpreis und Landestief kommen aus dem digitalen Tagesverlauf der
DekuDeals-Artikelseite (das Tool speichert je Monat den tiefsten Preis) und
der eigenen Aufzeichnung, jeweils der letzten 24 Monate. Ältere Tiefstwerte
zum heutigen Kurs zeigten Preise, die es so nie gab. Nur wo der Verlauf fehlt
oder die Seite Tiefstpreise für Switch und Switch 2 nennt (dann ist offen, zu
welcher Fassung der Verlauf gehört), gilt der Allzeit-Tiefstpreis. Beim
ersten Abgleich nach dem Update von einer Version vor 0.16 liest das Tool
dafür jede Artikelseite einmal neu (etwa 15 bis 25 Minuten).

Fehlt auf der DekuDeals-Seite ein digitaler Tiefstpreis (manchmal steht
dort nur der eines Händlers), gilt der niedrigste Preis aus dem digitalen
Verlauf. Das Protokoll zählt Seiten, die gar keinen nennen. Spiele für
Switch und Switch 2 haben je Plattform einen Tiefstpreis; es gilt der
höchste, den der Preis jetzt nicht übersteigt, also der der eigenen Fassung.

Der Landespreis verlinkt den Verlauf bei DekuDeals, der Europreis die
eShop-Seite des Landes.

## Einrichten

Unter Einstellungen, jede Änderung wird sofort gespeichert. Eine Leiste oben
springt zu den Abschnitten Länder, Regeln, Gebühren, Sprachen, Quellen sowie
Sicherung und Protokoll.

- Länder: Die aktiven Länder stehen oben, ihre Guthabenkarten aufklappbar
  direkt unter dem Land. Die übrigen stehen eingeklappt unter "weitere
  Länder", mit Schalter. Die Spalte Preisniveau zeigt für jedes Land, wie es
  zu deiner Wishlist steht, auch wenn es abgeschaltet ist.
- Regeln: Urteilsgrenzen, Wechselschwellen je Stufe und die Sprachregel. Ein
  Satz darüber fasst die aktuellen Werte zusammen.
- Wechsel: leicht (Karte, kein Rest), mittel (Guthabenkarten, ein Rest
  verfällt beim Wechsel), schwer (Amerika: Guthaben muss vor dem Wechsel 0
  sein). Je Stufe gilt ein eigener Mindestgewinn gegenüber dem, was die Titel
  ohne diesen Wechsel kosten.
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
  acht Käufe zwischen 5,57 und 93,03 € auf den Cent. Bei mehreren Karten in
  einer Bestellung fällt der feste Teil nur einmal an. Von
  Hand eingetragene Preise bleiben, wie du sie einträgst. Sperrt der Shop nach
  einigen Abrufen (bei Eneba nach etwa elf), kommen zuerst die Karten der
  Länder dran, in denen der Kaufplan gerade kauft, danach die Links, die am
  längsten nicht gelesen wurden. So bleiben die Preise frisch, die gerade
  zählen, und kein Link bleibt dauerhaft liegen.
- Glaubhaft: Ein gelesener Kartenpreis zählt nur
  zwischen 70 und 160 % des Nennwerts zum Mittelkurs. Alles andere ist fast
  sicher ein Lesefehler, etwa ein Gebührenhinweis statt des Preises. Solche
  Werte stehen mit „unglaubhaft, ignoriert“ unter der Kartenliste und im
  Protokoll, es gilt dein Eintrag.
- Deutschland: Die Vergleichsbasis ist immer der Preis im deutschen eShop.
  Wer mit günstigen deutschen Guthabenkarten (etwa von Eneba) zahlt, schaltet
  "Deutschland (Guthaben)" (DG) ein: dasselbe Konto und dieselben Preise,
  gerechnet wie jedes Guthabenland. Ein Rest bleibt auf dem Konto und wird
  ab 5 € gewarnt (Nintendo nimmt Guthaben bei keinem Länderwechsel mit). Karten, die bis 0.9.2
  bei Deutschland standen, wandern beim Update dorthin.
- Datei einlesen: Unter `countries.<Land>.cards_add` ergänzt eine Datei
  Karten, ohne vorhandene zu ersetzen. Gibt es den Kartenwert schon, bekommt
  die Zeile nur den Link.
- Sprachen: Gibt es in Deutschland eine deutsche Fassung, fallen Regionen ohne
  sie weg. Europa gilt als dasselbe Produkt. Japan und Amerika prüft das Tool
  je Titel einmal bei Nintendo (store-jp.nintendo.com, nintendo.com über
  ec.nintendo.com) und danach nur, wo die Angabe fehlt; Amerika liefert
  Angaben, Japan nur eine JavaScript-Seite. Unter Einstellungen, "Sprachen
  prüfen", stehen alle Titel: oben die ungeprüften, bei denen die Prüfung
  etwas ändert (die Fassung wäre billiger als der Bestpreis der zählenden
  Länder), mit Link in den Store und "Deutsch ja"/"nein". Aufgeklappt
  folgen die von Nintendo geprüften ("stimmt nicht" überschreibt), die von
  Hand gesetzten ("zurücksetzen" stellt die Angabe von Nintendo wieder her)
  und die ungeprüften ohne Folgen. Von Hand gilt dauerhaft und geht der
  Angabe von Nintendo vor. Ist für eine Region unbekannt, ob es Deutsch gibt,
  bleibt das Angebot in der Titeltabelle sichtbar („Sprache?“), zählt
  aber nicht für Bestpreis, Urteil und Kaufplan. Ist ein Titel nur dort
  kaufbar, nennt die Titelliste es als Grund. Mit „nur warnen“ zählen solche
  Angebote wie früher mit.
- Sicherung: Einstellungen, Karten, Zielpreise, Körbe, Kaufprotokoll und die
  eigene Preisaufzeichnung als eine Datei. Beim Einlesen wird die Aufzeichnung
  ergänzt, nicht ersetzt; alles andere holt das Tool beim Abgleich neu.

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

"Fall exportieren" im Verlauf-Fenster lädt alle Daten dieses Titels als Datei
(Preise, Tiefstwerte, Verlauf, Karten, Kurse, Einstellungen ohne Wishlist- und
Sammlungslink). Damit lässt sich ein auffälliger Fall genau nachrechnen.

"Verlauf" in den Einzelheiten jedes Titels zeigt diese Aufzeichnung
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
zeigen. Je Titel zählt das günstigste Land, in Euro zum heutigen Kurs.
Er steht nur zur Information in den Einzelheiten und im Verlauf; das Urteil misst am Bestpreis.

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
