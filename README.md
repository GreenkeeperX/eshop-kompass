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

Danach gleicht das Tool im eingestellten Abstand ab (Standard 6 Stunden) und
zusätzlich fünf Minuten nach jedem Start, etwa nach einem Update. Lief der
letzte Abgleich vor weniger als 30 Minuten, entfällt der beim Start.
Ein Klick auf den Namen oben links lädt die Startseite neu.

Ohne Docker: `python3 -m app.server` (Python 3.10+, keine Zusatzpakete).

## Ansichten

Fünf Reiter: Jetzt, Titel, Sammlung, Länder, Einstellungen. Das "?" oben rechts öffnet
die Legende mit allen Farben, Marken und Begriffen. Die Farben haben je eine
Bedeutung: Grün fürs Urteil und für Positives (Ersparnis, vollständig), Gold
(★, Umrandung) nur für den Bestpreis,
Bernstein heißt prüfen, Rot heißt nein oder teurer (Wechsel lohnt nicht, Rest
blockiert, hier teurer als ohne den Wechsel, Betrag über dem Bestpreis). Rabatte
stehen dezent blau daneben. Die verbindlichen Regeln stehen in
`docs/oberflaeche.md`.

Hell oder dunkel: Der runde Knopf rechts vom "?" zeigt die aktuelle Ansicht (System, Hell
oder Dunkel); ein Klick öffnet die Auswahl. Vorgabe ist System, also wie das Gerät. Die
Wahl merkt sich der Browser. Kopf und Reiter blenden sich beim Scrollen nach unten aus und
beim Hochscrollen wieder ein.

Lesezeichen (Käufe lesen, JP-Sprachen lesen): Webseiten dürfen selbst keine Lesezeichen
anlegen. Den gestrichelten Knopf zieht man deshalb in die Lesezeichenleiste; „Code kopieren“
ist der Weg ohne Ziehen, auch am Handy (Lesezeichen anlegen, Code als Adresse einfügen).
Beide Lesezeichen geben ihr Ergebnis mit „Im eShop-Kompass übernehmen“ direkt ans Tool;
die Textfelder zum Kopieren stehen eingeklappt unter „Geht das nicht?“. Ist ein angelegtes
Lesezeichen älter als nötig, meldet das Tool es beim Übernehmen und am Knopf.

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
  etwas ändern würden (die Fassung wäre günstiger; alle offenen stehen unter
  Einstellungen, "Sprachen prüfen"), Länder ohne Guthabenkarte mit Preis und Kartenpreise,
  die älter als 30 Tage sind, jeweils mit Sprung an die richtige Stelle. Dazu fehlende DLC
  deiner Spiele, die gerade kostenlos sind; ein Pass, der günstiger ist als seine fehlenden
  Teile, wenn Teile davon auf der Wishlist stehen, er selbst aber nicht (auf die Wishlist
  gesetzt, plant der Kaufplan ihn statt der Teile); und eine Erinnerung an „Käufe lesen“,
  wenn der letzte Lauf älter als 30 Tage ist und du seitdem gekauft hast (vermerkter Kauf
  oder größere DekuDeals-Sammlung).
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
  Grund, jeder Titel nur einmal. Reihenfolge: zuerst das Land, in dem dein Konto steht (ohne Angabe Deutschland), dann leicht,
  mittel, schwer, innerhalb einer Stufe nach Angebotsende. Ein Rest ist kein
  Verlust, solange du im Land bleibst; folgt im Plan noch ein Wechsel, verfällt
  er (Nintendo nimmt Guthaben nicht mit) und zählt dort als Kosten ("Rest
  verfällt"). Das gilt auch für Guthaben, das im Land deines Kontos liegt,
  wenn der Plan es verlässt. Ab Werk blockiert ein Rest nirgends den Wechsel:
  Er geht auch mit Guthaben, über den Support, und der Rest verfällt oder wartet
  auf den nächsten Wechsel dorthin. Wer es anders will, setzt in den
  Einstellungen je Land "Rest blockiert". Wo das gilt, plant der Plan keinen Wechsel danach:
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
  Dasselbe gilt für alles, was in deiner Sammlung bei DekuDeals steht: Es steht
  unter "Nicht im Plan" ("schon gekauft oder in deiner Sammlung").
  Unter "Gekauft" stehen die letzten Käufe, die Ersparnis rechnet wie der Plan
  mit dem, was die Spiele kosten (ein Rest bleibt Guthaben). "letzten Kauf zurücknehmen" stellt
  Land und Guthaben wieder her. "als Korb vergleichen" übernimmt die Titel in
  den gemeinsamen Korb.
- Füllartikel: Bleibt in einem Schritt des Kaufplans ein Rest, stehen darunter bis
  zu drei Wishlist-Titel, die hineinpassen, der kleinste verbleibende Rest zuerst.
  Das Urteil zählt dabei nicht, Titel aus der Sammlung, gekaufte und DLC ohne
  Hauptspiel fehlen. Ein Klick nimmt den Titel in den Schritt, "Füller ×" nimmt
  ihn wieder heraus. Nach "gekauft" sind die Füller dieses Landes vergessen.
  Auch fehlende DLC deiner Spiele erscheinen dort, als Link zu DekuDeals:
  Übernehmen lassen sie sich, sobald sie auf der Wishlist stehen. Ein DLC gilt
  nur in der Region, in der du das Hauptspiel hast.
- Titel, Liste: eine Zeile je Wishlist-Titel mit Urteil, Einkaufspreis samt
  Land und Stufe, Abstand zum Bestpreis und, wenn das beste Angebot in einem
  schweren Land liegt, der Alternative in einem leichten oder mittleren Land.
  Steht der Titel im Kaufplan, zeigt die Zeile den Preis im Land des Plans; ist
  er anderswo günstiger, steht dieses Land als Alternative daneben. Bis 2 % über
  dem Bestpreis heißt es "am Bestpreis", wie im Urteil.
  Unter dem Urteil steht, ob der Titel im Plan ist oder warum nicht. Filter
  nach Urteil und Suche oben. Ein Klick auf den Titel klappt die Einzelheiten
  auf: die Rechnung, alle Länder mit Preis, Stufe, Rabatt, Angebotsende und
  Abstand zum Bestpreis, Landestief als graue Auskunft (ungeprüfte Sprache direkt bestätigen), Bestpreis, typischer
  Angebotspreis, die Ersparnis gegenüber dem nächstbesten zählenden Land (Deutschland
  steht nur zur Information daneben), Zielpreis (leer heißt: das Urteil misst am Bestpreis;
  "Bestpreis übernehmen" setzt ihn) und die Links zu DekuDeals, eShop-Prices
  und zum eigenen Verlauf.
- Käufe aus dem eShop (oben im Reiter Sammlung): Das Lesezeichen „Käufe lesen“ liest in
  deinem Browser, angemeldet bei Nintendo, deinen Kaufverlauf (ec.nintendo.com/my/transactions,
  laut Nintendo zwei Jahre) auf dieselbe Weise wie die Seite selbst, mit kurzen Pausen.
  „Im eShop-Kompass übernehmen“ öffnet das Tool und gibt die Liste im Adressteil hinter #
  weiter (geht nicht übers Netz); ersatzweise Text kopieren und einfügen. Der Kaufverlauf
  nennt keine Nintendo-ID, nur Titel, Datum, Art und Betrag. Abgeglichen wird deshalb in
  Stufen: Passt der Titel genau auf einen Wishlist-Titel oder fehlenden DLC (bei DLC auch
  als „Spiel: DLC“), zählt er als Besitz und fällt aus dem Kaufplan, auch ohne Eintrag bei
  DekuDeals. Ist er nur ähnlich, schlägt das Tool bis zu drei Titel vor, die erst nach
  deiner Bestätigung zählen. Der Rest, meist längst Besessenes, steht eingeklappt darunter.
  Erstattete Käufe zählen nicht. Zuordnungen bleiben und stecken in der Sicherung. Der Link
  zur Kaufhistorie im Tool gibt den Stand des letzten lückenlosen Laufs mit, das Lesezeichen
  liest dann bis dorthin und zur Sicherheit eine ganze Seite bereits bekannter Käufe weiter. Bricht ein Lauf ab, übernimmt das Tool das Gelesene, behält aber
  den alten Stand, der nächste Lauf liest wieder ab dort.
- Pakete (Editionen, Season und Expansion Passes, DLC-Bundles): Wer ein Paket hat, hat seine
  Teile, auch über mehrere Stufen (Edition → Pass → DLC). Die Verbindungen kommen aus den
  Abschnitten „Contains“ (Paketseite) und „Included In“ (Seite eines Teils) bei DekuDeals und
  werden gespeichert; was du hast, rechnet das Tool jedes Mal neu aus Sammlung, Kaufverlauf
  und diesen Verbindungen, nur abwärts (ein Teil macht nie das Paket). Neue Verbindungen
  gelten sofort, eine Verbindung fällt erst weg, wenn sie zweimal hintereinander fehlt; fehlt
  ein Abschnitt ganz, ändert sich nichts. Änderungen nennt das Protokoll. Die Seiten fehlender
  DLC liest das Tool für die ID-Suche ohnehin und merkt sich ihre Pakete dabei, sonst
  vierteljährlich im Rahmen der 40 Seiten je Abgleich. Spiele, die du nur über eine Edition
  hast, stehen in der Sammlung mit „über …“, ihre neueren DLC als fehlend, enthaltene als
  „hast du, im Paket …“. Liegt DekuDeals bei einem Teil falsch, schaltet „stimmt nicht“ ihn
  wieder auf „fehlt“ (gilt auch für alles, was darin steckt). Ein fehlender Pass steht mit
  seinen Teilen eingerückt darunter („enthält 3 DLC, 1 schon da“) und vergleicht „einzeln …
  · als Pass …“ für die noch fehlenden Teile. „fehlen“ zählt Inhalte, nicht Kaufwege, der
  Pass zählt nicht zusätzlich; in die Summe geht der günstigere Weg. Stehen ein Pass und
  seine Teile zum Kauf an, kauft der Kaufplan den Pass, die Teile stehen unter „Nicht im
  Plan“ („steckt in …“).
- Nicht mehr erhältliche DLC: Findet die ID-Suche einen fehlenden DLC in keiner gesuchten
  Region, jeweils zweimal, gibt es ihn meist nur im Spiel oder nicht mehr im eShop. Er
  zählt nicht als fehlend und steht eingeklappt unter „nicht mehr erhältlich“.
- Sammlung (eigener Reiter): alle Spiele deiner DekuDeals-Sammlung mit ihren
  Zusatzinhalten (Abschnitt "DLC" der DekuDeals-Artikelseite), je DLC "hast du"
  oder "fehlt". Ob du einen DLC hast, sagt deine Sammlung bei DekuDeals; was sie
  nicht kennt, etwa einen DLC aus einem Paket, hakst du mit "habe ich" ab.
  "ignorieren" (je DLC) und "alle DLC ignorieren" (je Spiel) blenden Inhalte aus,
  die dich nicht interessieren: Sie zählen nicht als fehlend und stehen eingeklappt
  unter dem Spiel. Die DekuDeals-Sammlung geht vor, die Haken stecken in der
  Sicherung. Für fehlende DLC, die nicht auf der Wishlist stehen, sucht das Tool
  die Nintendo-IDs über die DekuDeals-Artikelseiten (höchstens 40 Seiten je
  Abgleich, Abbruch bei Sperren; gefundene IDs bleiben, ohne ID wieder nach 14 Tagen, nach zwei erfolglosen
  Suchen nur noch alle drei Monate (meist Inhalte, die es nur im Spiel gibt);
  den Stand je Region nennt das Protokoll). Die Japan- und Amerika-ID eines DLC holt es
  zuerst aus titledb: über die Programm-ID der Europa-ID, die in allen Regionen meist
  gleich ist (dafür einmal zusätzlich die US-Liste, rund 25 MB gepackt). Nur was titledb
  nicht kennt, sucht es danach bei DekuDeals. Findet keine der beiden Quellen eine ID,
  gibt es den DLC dort meist nicht: titledb sieht dann wöchentlich wieder nach,
  DekuDeals erst nach drei Monaten. Dann holt es die Preise mit der üblichen
  Preisabfrage. Dann steht der günstigste Preis dabei, je Spiel und insgesamt die
  Summe der fehlenden DLC. Urteil und Bestpreis gibt es nur für die Wishlist.
  Steht
  ein fehlender DLC auf deiner Wishlist, stehen Urteil, Einkaufspreis und Land
  dabei, sonst ein Link zu DekuDeals, um ihn auf die Wishlist zu setzen.
  Upgrade-Pakete für die Switch 2 sind markiert. Spiele mit fehlenden DLC
  stehen oben, je eines in einem Kasten. Darunter zugeklappt (0.53.1): "Ohne offene DLC",
  Spiele, bei denen alle DLC da, ignoriert oder nicht mehr erhältlich sind, je eine Zeile
  (alle da grün, die Zahl ignorierter rot),
  die seine DLC aufklappt; dann "Ohne Zusatzinhalte", A–Z spaltenweise. Die Suche klappt
  Abschnitte mit Treffern auf. Die noch nicht gelesenen Spiele stehen offen am Ende.
  Preise fehlender DLC zeigen seit 0.53.3 dieselben Zeichen wie die Titelliste: Stern am
  Bestpreis, grün bei der Güte „kaufen“ oder „gut“, Rabatt blau. Dafür liest der Abgleich
  auch für fehlende DLC im Angebot die Tiefstpreise bei DekuDeals, höchstens 30 Seiten je
  Abgleich. Ohne diese Daten steht der Preis ohne Zeichen. Das Tool
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
- Sortieren: Ein Klick auf einen Spaltenkopf sortiert aufsteigend, der zweite
  absteigend, der dritte stellt die gewohnte Reihenfolge wieder her; leere Werte
  stehen am Ende. Das geht in der Titel-Liste (dazu eine Auswahl, auch nach
  Angebotsende), in der Titel-Tabelle (auch nach dem Preis in einem Land), in
  den Warenkörben von Kaufplan und Ländern, im Verlauf, in der Länderliste der
  Einstellungen und in der Sprachliste. Die Sammlung hat eine Auswahl (Name,
  Zahl, Preis oder Angebote fehlender DLC). Die Wahl merkt sich der Browser.
- Titel, Tabelle: alle Titel mal alle Länder in Euro, Spalten nach Stufe
  gruppiert und darin nach der Zahl der Bestpreise (im Spaltenkopf mit ★),
  wahlweise nur nach Bestpreisen oder nur nach Stufe; Deutschland bleibt vorn,
  Länder, in denen gerade nichts zählt, am Ende. Angebote mit dem
  Urteil "kaufen" sind dunkelgrün hinterlegt, "gut" hellgrün; gold umrandet ist
  das Land, in dem es den Bestpreis gab. "Details" zeigt in jeder Zelle
  Landestief, Angebotsende und Sprache. Die Tabelle scrollt in einem eigenen
  Fenster, Kopfzeile und Titelspalte bleiben stehen. "nur Angebote" blendet
  auch Länder ohne Angebot aus.
- Länder, je Land: Länderkarten als dichtes Raster oder große Liste. Das Land,
  in dem dein Konto steht, kommt zuerst, dann die übrigen nach der gewählten
  Reihenfolge, Deutschland als Vergleich am Ende. Hast du Warenkörbe geändert,
  setzt "alle zurücksetzen" in der Leiste alle auf einmal zurück. Jede
  Karte enthält die Angebote des Landes, die günstiger als in Deutschland
  sind, und dauerhaft günstige Normalpreise mit dem Urteil "kaufen", also
  dieselben Titel, mit denen auch der Kaufplan rechnet. Steht das Land im
  Kaufplan, zeigt die Karte genau dessen Korb ("Korb: wie im Kaufplan"), denn der
  Einkaufspreis hängt an den Guthabenkarten für den ganzen Korb; so stimmen Karte
  und "Jetzt" überein. Änderst du die Karte, wird daraus ein eigener Korb. Die
  Kopfzahl ist der Einkaufspreis des Pakets. Darunter drei Zeilen:
  "Preis" nennt den Abstand der Spiele zur Summe ihrer Bestpreise (rot, grün nur
  "am Bestpreis") und zählt die Urteile; "Wechsel" sagt, ob sich der
  Weg hierher lohnt ("✓ lohnt" oder rot "lohnt nicht", mit Gewinn gegenüber
  "sonst" und der Schwelle der Stufe); "Rest" nennt, was als Guthaben bleibt
  und was hineinpasst. Bezahlst du ganz oder teils aus vorhandenem Guthaben,
  steht das unter der Kopfzahl. Hürden (Rest blockiert, Karten fehlen, DLC
  braucht eine andere Region als Europa) stehen darunter. Die betroffenen DLC sind in der
  Tabelle wie der Hinweis bernsteinfarben markiert. Die Tabelle zeigt je Titel Einkaufspreis,
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
Wechselkurses. Den Preis einer Guthabenkarte nimmt das Tool in dieser Reihenfolge: der
gelesene Preis vom Link (scheitert ein Abruf, gilt der zuletzt gelesene bis zu 14 Tage weiter,
mit Datum), dein eingetragener Preis, bei Werten ohne Link Guthaben zum Kurs. Gibt es nichts
davon, heißt ein ≈ vor dem Preis geschätzt (Kurs plus der Wert unter Gebühren, Erweitert):
Solche Preise entscheiden nichts, „das Günstigere“ nimmt dann die Kreditkarte, und „Zu
erledigen“ nennt das Land.
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
Verlauf. Das Protokoll zählt, wie viele Wishlist-Titel einen Tiefstpreis und einen
Angebotsverlauf haben (bis 0.53 die Summe aller je gelesenen Seiten). Spiele für
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
  Satz fasst die aktuellen Werte zusammen, die Felder stehen eingeklappt unter
  „Grenzen anpassen“.
- Wechsel: leicht (Karte, kein Rest), mittel (Guthabenkarten, ein Rest
  verfällt beim Wechsel), schwer (Amerika: Guthaben muss vor dem Wechsel 0
  sein). Je Stufe gilt ein eigener Mindestgewinn gegenüber dem, was die Titel
  ohne diesen Wechsel kosten.
- Fremdwährungsgebühr: 0 für Karten ohne Auslandseinsatzentgelt.
- Bezahlen: Karte, Guthabenkarte oder das Günstigere von beiden.
- Steuer: Aufschlag in Prozent, wo der Shop Preise ohne Steuer zeigt
  (USA, Kanada).
- "Das Günstigere" nimmt Guthabenkarten nur, wenn sie weniger kosten als die
  Kreditkarte. Die Spalte "Dein Faktor" zeigt, was dabei herauskommt. Einen Aufschlag
  je Land gibt es seit 0.52.1 nicht mehr (Entscheidung 13.10.2026).
- Faktor (0.53): Preis einer Guthabenkarte in Euro geteilt durch ihren Wert zum
  Mittelkurs. 1,00 heißt zum Kurs, 1,08 heißt 8 % teurer, 0,85 heißt: 100 € Guthaben
  kosten 85 €. Die Spalte "Dein Faktor" nennt ihn je Land mit Zahlweg ("1,00 Kreditkarte",
  "0,98 Guthaben"), aufgeklappt stehen unter dem Land alle Karten mit Wert, Preis, Faktor
  und Bewertung (der Faktor in der Farbe der Bewertung, ein gelesener Preis mit Servicegebühr),
  zugeklappt eine Zeile mit dem besten Faktor. Bewertet wird je nach Land
  (Entscheidung 13.10.2026):
  - Kreditkarte möglich ("das Günstigere", "Karte"): gegen den Faktor der Kreditkarte
    (1 plus Fremdwährungsgebühr): "günstiger als Kreditkarte" oder "teurer als
    Kreditkarte, nicht genutzt".
  - Nur Guthaben (Amerika, Australien): gegen den besten Faktor derselben Karte in den
    letzten 90 Tagen. Am Bestwert Top, bis 2 % darüber gut, bis 5 % okay, darüber teuer.
    Das Tool merkt sich dafür je Karten-Link einen Faktor am Tag (der niedrigste). Bis der
    Verlauf zwei Wochen umfasst, steht grau "Bewertung ab" mit dem Tag, ab dem verglichen wird.
  - Euro-Guthaben ("Deutschland (Guthaben)"): feste Stufen wie bei Kenixa, Top bis 0,81,
    gut bis 0,83, okay bis 0,86, darüber teuer; einstellbar unter Gebühren, Erweitert.
  Im Kaufplan steht der Faktor hinter den Karten in der Rechnung. Liegt Guthaben in einem
  reinen Guthabenland gerade über "okay", zeigt der Schritt "Guthaben teuer": Wenn die
  Titel nicht drängen, lohnt Warten eher wegen des Guthabens. Der Tooltip am Preis nennt
  Karte, Wert, Preis und Faktor. Eine eigene Zeile unter "Zu erledigen" gibt es dafür nicht.
- Sammlung: Titel aus deiner DekuDeals-Sammlung werden als vorhanden markiert,
  bei DLC steht dabei, ob du das Hauptspiel hast.
- Guthabenkarten: eine Karte je Zeile, `Wert = Preis in Euro | Link`. Ein
  vorangestelltes `x` heißt nicht vorrätig. Kaufst du Guthaben zum Kurs (etwa
  bei Amazon Japan), genügen die Werte ohne Link, zum Beispiel `500 1000 2000 3000 5000
  9000`: Dann rechnet das Tool zum Kurs, bezahlt mit deiner Karte (also plus deiner
  Fremdwährungsgebühr, bei einer Karte ohne Gebühr genau zum Kurs), und der Rest zählt mit.
  Hat eine Karte einen Link, liest das Tool beim Abgleich höchstens einmal am
  Tag den Preis von der Shopseite (aus den Produktdaten der Seite; nennt sie
  mehrere Angebote, zählt das günstigste). Über dem
  Eingabefeld steht, was es gelesen hat. Scheitert ein Abruf, gilt der zuletzt gelesene
  Preis mit seinem Datum weiter; erst wenn 14 Tage lang kein Abruf gelingt, gilt dein
  eingetragener Preis.
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
  sie weg. Europa gilt als dasselbe Produkt. Das Tool prüft jeden Titel einmal
  je Region und speichert das Ergebnis dauerhaft, unabhängig vom Preis:
  Wishlist-Titel und die fehlenden DLC deiner Spiele (Füllartikel). Europa in
  einem Abruf, Japan und Amerika je Titel bei Nintendo (store-jp.nintendo.com,
  nintendo.com über ec.nintendo.com, Pakete dort unter bundles), höchstens 40 Seiten je Region und
  Abgleich (beide Durchgänge eines Abgleichs zusammen), ungeprüfte zuerst. Sperren und Fehler zählen nicht als Versuch, der
  Titel kommt beim nächsten Abgleich wieder dran. Liefert eine gelesene Seite
  keine Sprachen, fragt es an den nächsten Tagen noch zweimal, danach monatlich; ebenso Europa, wenn
  die Antwort für einen Titel keine nennt (meist DLC, die die Sprache ihres Spiels übernehmen).
  Für fehlende DLC fragt Europa deshalb seit 0.53 auch das Spiel selbst (eine ID-Suche je Spiel,
  einmalig); kennt das Spiel die Sprache, braucht sein DLC keine eigene Angabe. Amerika liefert Angaben.
  Japan: store-jp steht hinter einem Warteraum (Queue-it) mit Bot-Schutz, durch kommt
  nur ein Browser mit JavaScript. Das Tool erkennt den Warteraum, fragt dann je
  Abgleich nur eine Seite und hört auf. Die Sprachen kommen stattdessen aus zwei Wegen:
  titledb, eine offene Titelliste auf GitHub (nicht von Nintendo, in der Oberfläche
  „laut titledb“), für Titel ohne Angabe höchstens wöchentlich geladen, für neu gefundene
  IDs gleich im nächsten Abgleich (rund 24 MB,
  Stück für Stück gelesen, nur die eigenen IDs behalten); und der Browser-Helfer unter
  „Sprachen prüfen“: ein Lesezeichen, das in deinem Browser die Shopseiten der
  offenen Titel liest (eine alle 2,5 Sekunden; die IDs bekommt es über den Link zu
  store-jp im Tool, der sie zugleich in die Zwischenablage legt; sonst fragt es danach) und das Ergebnis mit „Im eShop-Kompass
  übernehmen“ ans Tool gibt, ersatzweise als Text mit Kopieren-Knopf. Zeigt eine DLC-Seite keine Sprachen, liest es die Seite des
  Spiels, auf die sie verweist. Angaben von Nintendo (store-jp, Browser-Helfer) gehen titledb vor. DLC übernimmt
  die Sprache seines Spiels, für fehlende DLC reicht deshalb eine Seite je
  Spiel und Region: die Shopseite des Spiels selbst, dessen IDs das Tool dafür einmal
  bei DekuDeals sucht (DLC-Seiten nennen die Sprachen oft nicht, in Japan gibt es sie
  unter dieser Adresse gar nicht); bis die IDs da sind, die Seite des ersten DLC.
  Findet das Tool unter einer ID keine Seite (oder nach drei Versuchen keine Sprache),
  sucht der nächste Abgleich die ID bei DekuDeals einmal neu: Eine andere ID ersetzt die
  alte und die Sprache wird neu gefragt, dieselbe gilt danach als geprüft. Für Japan meldet
  das der Browser-Helfer („keine Seite“), weil das Tool selbst nur den Warteraum sieht. Dazu
  gleicht es jede Japan-ID einmal mit titledb ab: Die Programm-ID eines Spiels ist meist in
  allen Regionen gleich. Kennt titledb in Japan einen anderen Titel mit der Programm-ID aus
  Europa, sucht es die Japan-ID neu (dafür lädt es einmal zusätzlich die deutsche
  titledb-Liste, rund 28 MB); bleibt DekuDeals bei der alten ID, gilt die aus titledb. Ohne
  solchen Titel hat das Spiel in Japan eine eigene Programm-ID (etwa Hyrule Warriors), die
  ID bleibt. Unter Einstellungen, "Sprachen prüfen", stehen oben alle
  offenen Titel, einmal je Region (fehlende DLC als ein Eintrag je Spiel; der Preis nennt
  dann den günstigsten fehlenden DLC, „fehlende DLC dort ab“, denn das Spiel selbst ist schon
  gekauft), mit Link in den Store und "Deutsch ja"/"nein" (was dort gerade nicht kaufbar ist, steht unten);
  wo die Fassung gerade günstiger
  wäre, steht „günstiger“ und der Titel oben. Aufgeklappt folgen die geprüften:
  gruppiert nach Quelle (von Nintendo gelesen, laut titledb, von dir bestätigt). Die Spalte
  zeigt „✓ Deutsch“ oder „– ohne Deutsch“, der Tooltip nennt Quelle und gelesene Sprachen auf
  Deutsch, Angaben aus titledb sind gepunktet unterstrichen. ✎ überschreibt eine gelesene
  Angabe, ↺ stellt sie wieder her. Von Hand gilt
  dauerhaft und geht der Angabe von Nintendo vor. Steht ein Titel weder auf der
  Wishlist noch in der Sammlung, löscht der Abgleich seine Angaben wieder. Ist
  für eine Region unbekannt, ob es Deutsch gibt, bleibt das Angebot in der
  Titeltabelle sichtbar („Sprache?“), zählt aber nicht für Bestpreis, Urteil,
  Kaufplan und Füllartikel. Ist ein Titel nur dort kaufbar, nennt die
  Titelliste es als Grund. Mit „nur warnen“ zählen solche Angebote wie früher mit.
- Sicherung: Einstellungen, Karten, Zielpreise, Körbe, Kaufprotokoll und die
  eigene Preisaufzeichnung als eine Datei. Beim Einlesen wird die Aufzeichnung
  ergänzt, nicht ersetzt; alles andere holt das Tool beim Abgleich neu.

Jede Spalte und jedes Feld erklärt sich im Tooltip. Das Protokoll unter
Einstellungen läuft während eines Abgleichs mit, nennt oben Start und Version des
Laufs und zeigt die Uhrzeit deines Browsers. Seit 0.54 schreibt jeder Schritt eine Zeile,
auch wenn nichts fällig ist ("nichts fällig", "alle aktuell"), damit sich Abgleiche
vergleichen lassen. "Verbindung testen" schreibt in eine eigene Box darüber. Die
Wechselkurse erneuert die Quelle einmal am Tag; das Tool holt sie nur dann, wenn es
Neues gibt. Was das Tool woher, wann und wie oft holt und wo es die Daten ablegt, steht in
`docs/abrufe.md`. Seit 0.54.1 kommt jede DekuDeals-Seite je Abgleich höchstens einmal, und
Titel, die 180 Tage weder auf der Wishlist noch in der Sammlung stehen, verschwinden aus den
Abgleichsdaten (die eigene Preisaufzeichnung bleibt).

## Tiefstpreise und Verlauf

Nach dem Preisabruf lädt das Tool je Titel und Land den digitalen Tiefstpreis
von der DekuDeals-Artikelseite nach (ein Abruf alle 2,5 Sekunden, Angebote
zuerst) und führt ihn danach selbst fort, auch dort, wo DekuDeals keinen Wert
hat. Jeder Preiswechsel landet zusätzlich in `data/history.json`.

"Abgleichsdaten herunterladen" unter Einstellungen, Sicherung und Protokoll, lädt die
gesamten Abgleichsdaten (IDs, Sprachen, Preise, `data.json`) und das Protokoll als Datei,
ohne Einstellungen. Damit lässt sich der Stand des Abgleichs genau nachprüfen.

"Fall exportieren" im Verlauf-Fenster lädt alle Daten dieses Titels als Datei
(Preise, Tiefstwerte, Verlauf, Karten, Kurse, Einstellungen ohne Wishlist- und
Sammlungslink). Damit lässt sich ein auffälliger Fall genau nachrechnen.

"Verlauf" in den Einzelheiten jedes Titels zeigt diese Aufzeichnung
als Kurve je Land und dazu: Preis jetzt, Normalpreis, tiefster
aufgezeichneter Preis mit Datum, Zahl der Angebote (laut DekuDeals in den letzten
24 Monaten, ohne diese Angabe aus der eigenen Aufzeichnung), typische Dauer, Anteil der
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

Aus denselben Phasen zeigen die Einzelheiten unter "Angebote" den Rhythmus je
Land: wie viele Angebote es gab, in welchen Abständen, wann das letzte lief und
in welche Monate sie meist fielen. Eine Vorhersage ist das nicht. Nur wenn es
mindestens vier Angebote gab und alle Abstände höchstens 30 % vom Schnitt
abweichen, steht dabei, wann das nächste nach diesem Muster üblich wäre, als
Schätzung gekennzeichnet. Das Ende eines Angebots kennt das Tool ab 0.31, für
ältere Einträge erst, wenn es die Seite wieder liest.

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
auch für die erste Guthabenkarte mit Link (liest die Seite einen Preis?). Seit 0.53.2
prüft er auch, woher Preise der Online-Mitgliedschaft kommen könnten: die
12-Monats-Einzelmitgliedschaft bei DekuDeals für Deutschland und Brasilien und
mit den eShop-IDs, die DekuDeals im Link der Preistabelle nennt, die Preise bei Nintendo
(seit 0.53.6). Gespeichert wird nichts. Protokoll und Testergebnis lassen sich kopieren.

Die Oberfläche nimmt Änderungen nur als JSON an. Eine fremde Webseite kann so
keine Einstellungen überschreiben. Eine Anmeldung gibt es nicht, nach außen
freigeben solltest du das Tool deshalb nicht.

## Datenquellen

- Wishlist, Sammlung und Titel-IDs: dekudeals.com (öffentliche Wishlist, IDs werden dauerhaft gespeichert)
- Preise und Verfügbarkeit: api.ec.nintendo.com/v1/price (inoffiziell; nach einem kurzen Netzfehler
  ein zweiter Versuch, sonst bleiben die alten Preise des Landes)
- Sprachen: search.nintendo-europe.com (Europa), store-jp.nintendo.com und titledb
  (raw.githubusercontent.com/blawar/titledb, Japan), nintendo.com-Produktseiten über
  ec.nintendo.com (Amerika), sonst deine Bestätigung
- Japan- und Amerika-IDs fehlender DLC: titledb (Programm-ID), sonst DekuDeals
- Wechselkurse: open.er-api.com, ersatzweise frankfurter.dev (EZB)
- Eigene Käufe: Kaufverlauf bei Nintendo, gelesen nur in deinem Browser über das Lesezeichen
  „Käufe lesen“; der Server meldet sich nie bei Nintendo an

## Tests

    python3 -m unittest tests.test_all

## Prüfumgebung

`tools/replay.py` rechnet eine Momentaufnahme ohne Netz durch: Bewertung, Kaufplan,
Sprachen prüfen und Sammlung, so wie die Oberfläche sie zeigt. Eingaben sind die Dateien
aus "Abgleichsdaten herunterladen" und "Sicherung herunterladen". Die Abgleichsdaten
enthalten auch die Verbindungen der Pakete, die DLC-Seiten und den Kaufverlauf aus dem eShop.
Sie enthalten deine Wishlist und gehören nicht ins Repository.

    python3 -m tools.replay --abgleich abgleich.json --sicherung sicherung.json
    python3 -m tools.replay ... --szenario konto=PL --szenario kurs=JPY*1.1
    python3 -m tools.replay ... --vergleich main

Es prüft Regeln, die nie verletzt sein dürfen (kein Titel doppelt im Plan oder trotz
Sammlung, jede offene Sprachzeile mit Link, Pakete unter bundles, gültige IDs, kein Kauf
ohne Preis), und endet mit Fehlercode 1, wenn eine verletzt ist. `--vergleich` rechnet
dieselben Daten zum selben Zeitpunkt mit einem anderen Git-Stand und listet, was sich an
Urteilen, Plan, offenen Sprachen und Sammlung ändert. Szenarien: `konto=`, `guthaben=BR:20`,
`kurs=JPY*1.1`, `land-aus=`/`land-an=`, `ohne-preis=SLUG`, `angebot-endet=SLUG`.
