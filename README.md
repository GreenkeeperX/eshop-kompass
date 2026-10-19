# eShop-Kompass

Vergleicht die Titel deiner DekuDeals-Wishlist über mehrere Nintendo-eShops,
rechnet in Euro um und schnürt je Land das günstigste Paket inklusive
Guthabenkarten, Rest und Füllartikeln.

Diese Anleitung hat drei Teile: die **Kurzanleitung** für den Alltag, **Begriffe und
Regeln**, nach denen das Tool rechnet, und **Nachschlagen** je Reiter. Am Ende stehen
Betrieb, Abrufe und Prüfung. Was wann dazukam, steht in der Git-Geschichte, Geplantes in
der [ROADMAP](ROADMAP.md).

## Kurzanleitung

### Starten

Jeder Push auf `main` lässt die Tests laufen und baut danach das Image. Es liegt unter
`ghcr.io/OWNER/eshop-kompass:latest`, zusätzlich mit der Versionsnummer (etwa `:0.66.0`) und
dem kurzen Commit als Tag. Die `docker-compose.yml` zeigt den Betrieb als unprivilegierter
Benutzer mit schreibgeschütztem Dateisystem.

    docker compose up -d

Danach `http://<server>:8787` öffnen. Ohne Docker: `python3 -m app.server` (Python 3.10+,
keine Zusatzpakete, Daten in `./data/`).

### Einrichten in fünf Schritten

1. **Wishlist:** Unter Einstellungen, Quellen, den Link deiner öffentlichen
   DekuDeals-Wishlist eintragen, auf Wunsch auch den deiner Sammlung.
2. **Länder:** Unter Einstellungen, Länder, die Länder einschalten, in denen du kaufen
   würdest, und je Land den Zahlweg wählen (Karte, Guthabenkarte oder das Günstigere).
3. **Guthabenkarten:** Für Länder ohne Kartenzahlung die Karten eintragen, die du kaufen
   kannst, mit Preis oder Link zum Shop (Format unter [Guthabenkarten](#guthabenkarten)).
4. **Gebühr:** Die Fremdwährungsgebühr deiner Kreditkarte eintragen (0 bei Karten ohne
   Auslandseinsatzentgelt).
5. **Konto:** Oben im Reiter Jetzt einstellen, in welchem Land dein Konto gerade steht und
   wie viel Guthaben dort liegt.

Der erste Abgleich startet von selbst. Er sucht je Titel die Nintendo-IDs, liest Sprachen und
Tiefstpreise und braucht dafür einige Minuten; was in einem Lauf nicht fertig wird, folgt beim
nächsten. Danach gleicht das Tool im eingestellten Abstand ab (Vorgabe 6 Stunden) und
zusätzlich fünf Minuten nach jedem Start, etwa nach einem Update. Lief der letzte Abgleich
vor weniger als 30 Minuten, entfällt der beim Start.

„Aktualisieren“ startet einen Abgleich von Hand. Der wartet nicht auf Ruhezeiten, die nur sagen,
dass vermutlich nichts Neues da ist (titledb einmal die Woche, Kartenpreise einmal am Tag; von
Hand liest er Karten neu, die älter als eine Stunde sind). Was die Quellen schont, gilt immer:
die Pause nach einer Sperre, der Warteraum von Japan und die Zahl der Seiten je Abgleich. Das
Protokoll nennt am Ende, was übergangen wurde.

### Der tägliche Blick

1. **Jetzt** öffnen. Oben steht „Zu erledigen“: Sprachen, die du prüfen solltest, Karten
   ohne Preis, kostenlose DLC, die Verlängerung der Online-Mitgliedschaft. Jede Zeile
   springt an die richtige Stelle.
2. **Kaufplan** darunter lesen: welche Titel du jetzt in welchem Land kaufst, in welcher
   Reihenfolge, was es kostet und was als Rest bleibt.
3. Kaufen und am Land **„gekauft“** drücken. Das Tool stellt danach Konto und Guthaben selbst
   um und nimmt die Titel aus dem Plan.

Alles Weitere ist Nachschlagen: „Andere Länder“ an jedem Schritt, die Wishlist für Einzelheiten
und Verlauf, ihr Korb und die Länderkarten zum Durchspielen eigener Zusammenstellungen,
Sammlung für fehlende DLC.

## Begriffe und Regeln

### Preise

- **Einkaufspreis:** was du zahlst, in Euro, mit Steuer, Kurs, Guthabenkarten und Gebühr.
  Der Tooltip am Preis zeigt die Rechnung samt Stand des Wechselkurses.
- **Bestpreis:** der niedrigste Einkaufspreis der letzten 24 Monate in einem zählenden Land,
  mit deinem heutigen Einkaufsweg gerechnet. Normalpreise zählen mit.
- **Landestief:** der niedrigste Preis eines Landes in denselben 24 Monaten. Nur Auskunft,
  immer grau; entschieden wird am Bestpreis.
- **Am Bestpreis:** bis 2 % darüber. Eine Summe (ein Schritt, ein Land, der Kaufplan) heißt
  nur „am Bestpreis“, wenn jeder Titel darin es ist.
- **Typischer Angebotspreis:** der Median der Tiefstwerte vergangener Angebote, nur zur
  Information (siehe [Verlauf](#verlauf-und-typischer-angebotspreis)).
- Eurobeträge tragen immer das €-Zeichen. Beträge in Landeswährung stehen ohne Zeichen in
  Spalten mit der Währung im Kopf oder mit Kürzel daneben.

### Urteil

Das Urteil misst nur die Preisgüte des günstigsten zählenden Preises jetzt, mit oder ohne
Rabatt, mit denselben Grenzen für jedes Land:

- **kaufen:** Zielpreis erreicht, am Bestpreis (bis 2 % darüber) oder höchstens 0,50 € darüber,
- **gut:** bis 15 % oder höchstens 2 € darüber,
- **warten:** weiter weg.

Ein dauerhaft günstiger Normalpreis am Bestpreis ist also „kaufen“ wie ein Angebot (der Grund
nennt dann „Normalpreis“), und ein teureres Angebot in einem anderen Land macht daraus kein
„warten“. Rabatt und Angebotsende stehen nur daneben. Die beiden Euro-Grenzen sind unter
Einstellungen, Regeln, änderbar.

„kein Urteil“ heißt: nirgends kaufbar, wo es zählt, oder der Bestpreis ist noch nicht
bekannt. Der Grund sagt, was Nintendo meldet: „noch nicht erschienen“, „nicht mehr im
Verkauf“, „im eShop nicht einzeln kaufbar“ (etwa nur im Abo wie N64-Spiele oder nur in einem
Paket), „nicht im eShop gefunden“ (keine Nintendo-Kennung) oder „kostenlos“.

### Was zählt

Ein Angebot zählt für Bestpreis, Urteil und Kaufplan nur, wenn es dort wirklich zu bekommen
ist:

- **Sprache:** Gibt es in Deutschland eine deutsche Fassung, fallen Regionen ohne sie weg.
  Ist für eine Region unbekannt, ob es Deutsch gibt, bleibt das Angebot sichtbar
  („Sprache?“), zählt aber nicht. Mit der Sprachregel „nur warnen“ zählen solche Angebote mit.
- **Guthaben:** Ein Guthabenland ohne Karte mit Preis (weder eingetragen noch gelesen) zählt
  nicht: Dort ist Guthaben nicht zu bekommen, der Europreis wäre geraten. Die Angebote bleiben
  sichtbar („ohne Karte“).
- **Geschätzt:** Ein ≈ vor dem Preis heißt geschätzt. Geschätzte Werte entscheiden nichts.

### Wechsel und Stufen

Ob sich der Weg in ein Land lohnt, sagt getrennt vom Urteil die Zeile **Wechsel**. Jedes
Land hat eine Stufe:

- **leicht:** Kartenzahlung, kein Rest,
- **mittel:** Guthabenkarten, ein Rest verfällt beim Wechsel,
- **schwer:** Guthabenkarten, ein Wechsel mit Guthaben geht nur über den Support (Amerika:
  Guthaben muss vor dem Wechsel 0 sein).

**Wechselgewinn** ist, was dieselben Titel ohne diesen Wechsel kosten („sonst“: das
günstigste zählende Land gleicher oder leichterer Stufe oder das Land, in dem dein Konto
steht), minus was sie hier kosten. Ein Land lohnt sich, wenn der Gewinn die
Mindestersparnis seiner Stufe schafft (Einstellungen, Regeln). Das gilt auch für den Weg
zurück nach Deutschland, wenn dein Konto woanders steht. Ohne eingetragenes Kontoland gilt
Deutschland als Konto.

„Sonst“ rechnet der Plan auf zwei Arten und nimmt die günstigere: je Titel geschätzt und als
ganzes Paket mit Karten, Gebühr und Rest in einem anderen Land, wie „Andere Länder“ unter dem
Schritt. Ist ein Schritt als Paket in einem Land gleicher oder leichterer Stufe günstiger, das
noch kein Schritt ist, kommen seine Titel dorthin. So werfen sich fast gleich teure Länder nicht
gegenseitig aus dem Plan, bis ein teureres übrig bleibt.

### Rest

Ein Rest ist kein Verlust, solange du im Land bleibst. Folgt im Plan noch ein Wechsel,
verfällt er (Nintendo nimmt Guthaben nicht mit) und zählt dort als Kosten („Rest
verfällt“). Das gilt auch für Guthaben, das im Land deines Kontos liegt, wenn der Plan es
verlässt. Gewinn und Schwelle rechnen deshalb mit dem, was die Spiele selbst kosten
(„Spiele X €“). Vorhandenes Guthaben ist schon bezahlt, zählt aber zum Kurs mit.

Ab Werk blockiert ein Rest nirgends den Wechsel: Er geht auch mit Guthaben, über den
Support, und der Rest verfällt oder wartet auf den nächsten Wechsel dorthin. Wer es anders
will, setzt in den Einstellungen je Land „Rest blockiert“. So ein Land kommt nur als letzter
Schritt, höchstens eins je Plan; das schwächere fällt heraus („nur ein Land mit
blockierendem Rest je Plan“). Steht dein Konto in so einem Land und liegt dort Guthaben,
plant der Plan nur dort, nennt, was hineinpasst, und führt die übrigen Titel unter „Nicht im
Plan“ („Wechsel blockiert“), bis das Guthaben aufgebraucht ist oder der Support es löst.

### Guthabenkarten im Preis

Jeder Europreis eines Guthabenlandes rechnet mit den Karten, die du für genau diesen Betrag
kaufen würdest (die günstigste Kombination, die ihn deckt), anteilig. Für ein Spiel zu
60 MXN zählt also die 100er Karte, nicht der bessere Kurs einer 1000er. Im Paket teilen sich
die Titel die Karten. Kaufst du einen Titel allein, brauchst du meist mehr Guthaben, als er
kostet; was das kostet, nennt der Tooltip als „allein gekauft“ mit Karten und Rest.

Den Preis einer Karte nimmt das Tool in dieser Reihenfolge:

1. den gelesenen Preis vom Link (scheitert ein Abruf, gilt der zuletzt gelesene bis zu
   14 Tage weiter, mit Datum),
2. deinen eingetragenen Preis,
3. bei Werten ohne Link Guthaben zum Kurs, bezahlt mit Kreditkarte.

Eine Karte mit Link, deren Preis noch nicht gelesen ist, rechnet nicht mit. Gibt es für keine
Karte einen Preis, ist der Europreis geschätzt (Kurs plus der Wert unter Gebühren, Erweitert):
Er entscheidet nichts, „das Günstigere“ nimmt dann die Kreditkarte, und „Zu erledigen“ nennt
das Land. Auch Kartenzahlung ist eine Näherung (Mittelkurs plus Fremdwährungsgebühr), die
Bank rechnet mit ihrem eigenen Kurs.

**Faktor:** Preis einer Guthabenkarte in Euro geteilt durch ihren Wert zum Mittelkurs. 1,00
heißt zum Kurs, 1,08 heißt 8 % teurer, 0,85 heißt: 100 € Guthaben kosten 85 €. „Das
Günstigere“ nimmt Guthabenkarten nur, wenn sie weniger kosten als die Kreditkarte. Bewertet
wird der Faktor je nach Land (Entscheidung 13.10.2026):

- **Kreditkarte möglich** („das Günstigere“, „Karte“): gegen den Faktor der Kreditkarte
  (1 plus Fremdwährungsgebühr): „günstiger als Kreditkarte“ oder „teurer als Kreditkarte,
  nicht genutzt“.
- **Nur Guthaben** (Amerika, Australien): gegen den besten Faktor derselben Karte in den
  letzten 90 Tagen. Am Bestwert Top, bis 2 % darüber gut, bis 5 % okay, darüber teuer. Das
  Tool merkt sich dafür je Karten-Link einen Faktor am Tag (den niedrigsten). Bis der Verlauf
  zwei Wochen umfasst, steht grau „Bewertung ab“ mit dem Tag, ab dem verglichen wird.
- **Euro-Guthaben** („Deutschland (Guthaben)“): feste Stufen, Top bis 0,81, gut bis 0,83, okay
  bis 0,86, darüber teuer; einstellbar unter Gebühren, Erweitert.

Liegt Guthaben in einem reinen Guthabenland gerade über „okay“, zeigt der Schritt im Kaufplan
„Guthaben teuer“: Drängen die Titel nicht, lohnt Warten eher wegen des Guthabens.

**Servicegebühr:** Die Servicegebühr eines Kartenshops (Vorgabe 0,40 € plus 7,75 % je
Bestellung) steckt in jeder gelesenen Karte, denn die Seite zeigt den Preis ohne sie. Besteht
ein Paket aus mehreren Karten, zählt der feste Teil nur einmal. Von Hand eingetragene Preise
bleiben, wie du sie einträgst. Cashback des Shops steht nicht in den Preisen; mit „Mögliches
Cashback“ unter Einstellungen markiert die Titelliste mit ✱, wo es ein Angebot zum Bestpreis
machen könnte.

### Eigene Angebote (Codes)

Angebote außerhalb des eShops, etwa Codes bei Amazon Japan, trägst du bei einem Titel (in
seinen Einzelheiten unter „Eigene Angebote“) oder bei der Online-Mitgliedschaft ein: Land,
Preis in Landeswährung, Quelle und auf Wunsch ein Link. Der Preis gilt als Endpreis, ohne
Steuer obendrauf.

- Bezahlt wird ein Code mit Kreditkarte zum Mittelkurs plus Gebühr, in einem Euro-Land genau
  zum Betrag, nie zum Faktor der Guthabenkarten. Eingelöst wird er im Konto des Landes.
- Ist er günstiger als der eShop dort, tritt er an dessen Stelle: Er zählt für Bestpreis,
  Urteil, Korb und Kaufplan wie jedes Angebot, trägt die Marke der Quelle („Amazon“), und sein
  Preis verlinkt den Händler. Die Sprachregel gilt wie für den eShop des Landes.
- Im Kaufplan läuft er nicht über Guthaben, also ohne Karten und Rest; die Kosten nennen ihn
  eigens. Als Füllartikel für einen Rest erscheint er deshalb nie.
- Mit Link liest der Abgleich den Preis einmal am Tag selbst (bei Amazon das Hauptangebot der
  Produktseite). Zeigt der Shop eine Prüfseite (Captcha), wird sie nicht umgangen; dann gilt
  dein eingetragener Preis.
- **Plausibilität:** Ein gelesener Preis gilt nur in der Währung des Landes und höchstens 40 %
  von deinem eingetragenen entfernt. Sonst gilt dein Preis, und neben dem Angebot steht
  violett, was der Link liefert („Link zeigt 12,34 €“, „Link liest 1.000 ¥, passt nicht“): ein
  Hinweis auf einen falschen Link oder Tippfehler. Amazon zeigt Besuchern aus Deutschland
  umgerechnete Europreise; das Tool wählt deshalb über die Währungswahl der Seite (Cookie) die
  Landeswährung und erkennt die Währung am Preis.

### DLC und Regionen

Ein DLC gilt nur in der Region, in der du das Hauptspiel hast. Ob ein DLC aus Japan oder
Amerika zu deinem Spiel aus Europa passt, hängt an der Programm-ID, nicht am Shop: Die meisten
Spiele haben weltweit eine, dann passt auch der DLC von dort. Der Abgleich vergleicht dafür die
Programm-IDs des DLC in titledb (Europa gegen Japan und Amerika). Nur bei einer eigenen
Fassung in der Region steht das violette „DLC“ hinter dem Land (in Tabellen ein violetter
Strich am linken Zellrand); ungeprüft steht ein gestricheltes „DLC?“. Am Rechnen ändert die
Marke nichts.

### Besitz und Pakete

Was du hast, rechnet das Tool jedes Mal neu aus deiner DekuDeals-Sammlung, dem gelesenen
Kaufverlauf, deinen Haken und den Verbindungen der Pakete. Gekauftes und Vorhandenes fällt aus
dem Kaufplan, auch solange es noch auf der Wishlist steht.

Wer ein Paket hat (Editionen, Season und Expansion Passes, DLC-Bundles), hat seine Teile,
auch über mehrere Stufen (Edition → Pass → DLC), nur abwärts: Ein Teil macht nie das Paket.
Die Verbindungen kommen aus den Abschnitten „Contains“ (Paketseite) und „Included In“ (Seite
eines Teils) bei DekuDeals und werden gespeichert. Neue Verbindungen gelten sofort, eine
Verbindung fällt erst weg, wenn sie zweimal hintereinander fehlt; fehlt ein Abschnitt ganz,
ändert sich nichts. Änderungen nennt das Protokoll.

### Farben und Zeichen

Die Farben haben je eine Bedeutung: Grün fürs Urteil und für Positives (Ersparnis,
vollständig), Gold (★, Umrandung) nur für den Bestpreis, Violett heißt prüfen, Rot heißt nein
oder teurer (Wechsel lohnt nicht, Rest blockiert, Betrag über dem Bestpreis). Rabatte stehen
dezent blau daneben. Das „?“ oben rechts öffnet die Legende mit allen Farben, Marken und
Begriffen; jede Spalte und jedes Feld erklärt sich außerdem im Tooltip. Die verbindlichen
Regeln für die Oberfläche stehen in [`docs/oberflaeche.md`](docs/oberflaeche.md).

## Nachschlagen

### Allgemein

Vier Reiter: Jetzt, Wishlist, Sammlung, Einstellungen, erst was ansteht, dann
die Wishlist zum Einkaufen, dann was du hast. Die Wishlist hat drei Ansichten: Liste,
Tabelle und Korb. Die Länderkarten öffnen sich aus dem Kaufplan. Ein Klick auf den Namen oben links
lädt die Startseite neu.

- **Hell oder dunkel:** Der runde Knopf rechts vom „?“ zeigt die aktuelle Ansicht (System,
  Hell oder Dunkel); ein Klick öffnet die Auswahl. Vorgabe ist System, also wie das Gerät.
- **Kopfleiste:** Kopf und Reiter blenden sich beim Scrollen nach unten aus und beim
  Hochscrollen wieder ein. Auf dem Handy scrollt die Reiterleiste seitlich und blendet am Rand
  aus, solange weitere Reiter folgen.
- **Handy:** Die Titel im Kaufplan und auf den Länderkarten stehen als kleine Karten
  untereinander, der Einkaufspreis vorn; sortieren lassen sie sich dort nicht.
- **Sortieren:** Ein Klick auf einen Spaltenkopf sortiert aufsteigend, der zweite absteigend,
  der dritte stellt die gewohnte Reihenfolge wieder her; leere Werte stehen am Ende. Das geht in
  Titel-Liste und -Tabelle, in den Warenkörben von Kaufplan, Korb und Ländern, im Verlauf, in
  der Länderliste der Einstellungen, in der Sprachliste und bei der Online-Mitgliedschaft.
  Neu zeichnen lässt jede Tabelle dort stehen, wohin du gescrollt hast.
- **Tastatur:** Spaltenköpfe erreichst du mit Tab und sortierst mit Enter oder Leertaste. Legende
  und Preisverlauf öffnen mit dem Fokus auf „Schließen“, Esc schließt sie. Knöpfe, die nur ein
  Zeichen zeigen (+, ✓, ×, ↺, ✎), lesen Bildschirmleser mit ihrem Tooltip vor.
- **Suchen:** Jedes Suchfeld hat ein ×, Esc leert es ebenso. Gesucht wird ohne Akzente und
  Satzzeichen: „pokemon“ findet „Pokémon“.
- **Merken:** Die Ansicht (Reiter, Liste, Tabelle oder Korb, Raster oder Liste der Länder und deren
  Reihenfolge, Filter, aufgeklappte Kästen, Hell oder Dunkel) merkt sich der Browser. Korb,
  Auswahl, Zielpreise und Einstellungen speichert der Server.
- **Zahlen eingeben:** Beträge und Prozente nehmen Komma und Punkt.
- **Lesezeichen** (Käufe lesen, JP-Sprachen lesen): Webseiten dürfen selbst keine Lesezeichen
  anlegen. Den Knopf zieht man deshalb in die Lesezeichenleiste; „Code kopieren“ ist der Weg
  ohne Ziehen, auch am Handy (Lesezeichen anlegen, Code als Adresse einfügen). Beide geben ihr
  Ergebnis mit „Im eShop-Kompass übernehmen“ direkt ans Tool; die Textfelder zum Kopieren
  stehen eingeklappt unter „Geht das nicht?“. Ist ein angelegtes Lesezeichen älter als nötig,
  meldet das Tool es beim Übernehmen und am Knopf.

### Jetzt

**Konto:** oben, in welchem Land dein Konto steht und mit wie viel Guthaben, direkt änderbar.
Zur Wahl stehen Länder mit eigenem Shop; „Deutschland (Guthaben)“ ist dasselbe deutsche Konto
und steht deshalb nicht zur Wahl.

**Zu erledigen**, je Aufgabe eine kurze Zeile mit Sprung an die richtige Stelle:

- ungeprüfte Sprachen, die etwas ändern würden (die Fassung wäre günstiger; alle offenen
  stehen unter Einstellungen, „Sprachen prüfen“),
- Länder ohne Guthabenkarte mit Preis und Kartenpreise, die älter als 30 Tage sind,
- fehlende DLC deiner Spiele, die gerade kostenlos sind (eingeklappt unter „welche“),
- ein Pass, der günstiger ist als seine fehlenden Teile, wenn Teile davon auf der Wishlist
  stehen, er selbst aber nicht (auf die Wishlist gesetzt, plant der Kaufplan ihn statt der
  Teile),
- „Käufe lesen“, wenn der letzte Lauf älter als 30 Tage ist und du seitdem gekauft hast
  (vermerkter Kauf oder größere DekuDeals-Sammlung),
- Käufe zuordnen, die einem Wishlist-Titel oder fehlenden DLC nur ähneln, und gekaufte Titel, die
  bei DekuDeals noch nachzutragen sind (siehe Einstellungen, Käufe aus dem eShop),
- 30 Tage vor Ablauf die Verlängerung der Online-Mitgliedschaft mit dem günstigsten Land; „Online-Mitgliedschaft“ und „ansehen“ springen zum Kasten. Nach einem vermerkten Kauf mit Mitgliedschaft steht dort stattdessen das neue Ablaufdatum zum Übernehmen.

**Kaufplan:** ein Gesamtvorschlag, welche Titel du jetzt in welchem Land kaufst. Kandidaten
sind die Titel mit dem Urteil „kaufen“, per Schalter auch „gut“. Jeder Titel geht ins Land, wo
er am wenigsten kostet. Ein Land bleibt nur im Plan, wenn sich der Wechsel lohnt (siehe
[Wechsel und Stufen](#wechsel-und-stufen)); sonst wandern seine Titel ins nächstbeste Land.
Sind sie dort kein Kauf mehr, stehen sie unter „Nicht im Plan“ (zugeklappt), mit Grund, jeder
Titel nur einmal. Reihenfolge: zuerst das Land, in dem dein Konto steht (ohne Angabe
Deutschland), dann leicht, mittel, schwer, innerhalb einer Stufe nach Angebotsende. Ist heute
nichts auf „kaufen“, nennt die Seite die Angebote, die am nächsten am Bestpreis liegen.

Jeder Schritt ist eine Karte wie die Länderkarten (siehe dort) mit Preis, Wechsel, Rest und
der Tabelle der Titel. DLC mit gekürztem Namen tragen das Hauptspiel klein davor.

**Andere Länder:** Zugeklappt unter jedem Schritt steht, was dieselben Titel in den anderen
Ländern kosten, als Betrag über oder unter diesem Schritt, die günstigsten zuerst; Länder, in
denen Titel fehlen, folgen mit „ohne …“ und vergleichen nur die übrigen. Wie bei „Preis“ zählt,
was die Spiele kosten, ein Rest bleibt auf beiden Seiten Guthaben. Grün heißt günstiger: Dann
lohnt der Wechsel dorthin nicht, oder der Plan hat jeden Titel einzeln dem Land gegeben, in dem
er am wenigsten kostet, und im Paket teilen sich die Titel die Karten anders. Ein Klick auf ein
Land zeigt die Titel des Schritts dort als Karte mit Rechnung und darunter die Karte des Landes
mit seinem eigenen Korb.

**Füllartikel:** Bleibt in einem Schritt ein Rest, stehen darunter Wishlist-Titel, die
hineinpassen, der kleinste verbleibende Rest zuerst, auch zwei Titel zusammen, wenn sie den
Rest besser füllen als jeder einzelne. Alles andere, was passt, steht im Auswahlfeld „alles, was
passt …“ mit dem, was danach bleibt. Das Urteil zählt dabei nicht; Titel aus der Sammlung,
gekaufte, kostenlose, DLC ohne Hauptspiel und eigene Angebote (die zahlt die Kreditkarte)
fehlen. Ein Klick nimmt den Titel in den Schritt, „dazugenommen ×“ nimmt ihn wieder heraus. Fehlende
DLC deiner Spiele, die nicht auf der Wishlist stehen, erscheinen dahinter: die zwei kleinsten als
Knopf, alle im selben Auswahlfeld „alles, was passt …“ unter „DLC deiner Spiele, nicht auf der
Wishlist“; ein Klick nimmt auch sie in den Schritt. Passt eine Online-Mitgliedschaft (nicht die Familie) in den Rest,
steht sie dort als Hinweis, mit ihrem eShop-Preis. Jeden anderen Wishlist-Titel, den es dort
gibt, nimmt „Titel dazunehmen …“ unter der Karte in den Schritt, ebenso fehlende DLC deiner
Spiele, die nicht auf der Wishlist stehen, und jede Variante der Online-Mitgliedschaft (auch im
Korb; von selbst nimmt der Plan beides nie); „als Korb
vergleichen“ übernimmt die Titel des Schritts in den Korb. Nach „gekauft“ sind die
dazugenommenen Titel dieses Landes vergessen.

**Passt dazu:** Passt nichts in den Rest, schlägt ein Schritt (wie der Korb und jede Länderkarte)
den Wishlist-Titel vor, der zusätzlich am meisten spart. „spart“ ist, was der Titel ohne den
Wechsel hierher kosten würde (im günstigsten zählenden Land gleicher oder leichterer Stufe oder im
Kontoland), minus dem, was der Kauf hier mit ihm mehr kostet. Der Aufpreis ist oft kleiner als der
Shop-Preis, weil die Guthabenkarten und der Rest einen Teil decken. Ein Klick nimmt ihn in den
Schritt. „spart“ rechnet mit heutigen Preisen. Vorgeschlagen werden nur Titel, die hier
höchstens „gut“ über ihrem Bestpreis liegen (bis 15 % oder bis zur Grenze „gut“ unter Regeln);
was heute spart, aber weit darüber liegt, wäre im nächsten Angebot günstiger. Klein hinter
„spart“ steht, ob der Titel am Bestpreis ist oder wie viel darüber („+x € über Bestpreis“).

**Gekauft:** „gekauft“ an einem Land vermerkt den Kauf im Kaufprotokoll
(`data/purchases.json`): Dein Konto steht danach dort, ein Rest bleibt dort als Guthaben,
Guthaben anderer Länder gilt als weg. Gekaufte Titel verschwinden aus dem Plan. Unter
„Gekauft“ stehen die letzten Käufe; die Ersparnis rechnet wie der Plan mit dem, was die Spiele
kosten. „letzten Kauf zurücknehmen“ stellt Land und Guthaben wieder her. „als Korb
vergleichen“ übernimmt die Titel in den gemeinsamen Korb.

**Online-Mitgliedschaft** (unter dem Kaufplan, zugeklappt; 30 Tage vor Ablauf offen): sechs
Varianten, 1 Monat, 3 Monate, 12 Monate, Erweiterungspaket, Familie und Erweiterungspaket
Familie (die beiden Familien nur zum Vergleich, kaufen kann, wer die Gruppe verwaltet). Oben
je Variante das beste Land mit Einkaufspreis, Preis je Monat und Shop-Preis; ein Klick wählt
eine Variante aus, sie gilt für Kopfzeile („ausgewählt“), Erinnerung und Länderliste. Die
Länderliste („Alle Länder für …“) ist zugeklappt: je aktivem Land der Einkaufspreis mit deinem Zahlweg wie
bei Spielen, je Monat, der Shop-Preis, Angebote und ob das Land dein Konto ist oder im
Kaufplan steht. Zeichen wie bei Titeln: ★ am Bestpreis der letzten 24 Monate, Preis grün nach
Urteil, Abstand zum Bestpreis rot; der Preis führt in den eShop des Landes, „DekuDeals“ zum
Preisverlauf. 1 Monat und Erweiterungspaket Familie führt DekuDeals nicht; ihren Tiefstpreis
zeichnet das Tool selbst auf, der Tooltip nennt, seit wann. Das Ablaufdatum trägst du im Kasten
ein. Vermerkst du einen Kaufplan-Schritt mit einer Variante als „gekauft“, schlägt „Zu erledigen“
das neue Datum vor (ab Ablauf, sonst ab dem Kauftag; 1 Monat zählt 30 Tage, 3 Monate 90,
12 Monate 365): „übernehmen“ oder „verwerfen“. Käufe aus dem eShop-Kaufverlauf zählen dafür
nicht, dort steht keine Laufzeit. Im Kasten trägst du auch weitere Angebote ein („Weiteres
Angebot eintragen“, siehe [Eigene Angebote](#eigene-angebote-codes)). In den Korb oder in einen
Kaufplan-Schritt kommt eine Variante über „Titel dazunehmen …“; von selbst nimmt der Plan sie
nie auf.

### Wishlist

**Liste:** eine Zeile je Wishlist-Titel mit Urteil, Einkaufspreis samt Land und Stufe,
Abstand zum Bestpreis und, wenn das beste Angebot in einem schweren Land liegt, der
Alternative in einem leichten oder mittleren Land. Steht der Titel im Kaufplan, zeigt die
Zeile den Preis im Land des Plans; ist er anderswo günstiger, steht dieses Land als
Alternative daneben. Unter dem Urteil steht, ob der Titel im Plan ist oder warum nicht.
Filter nach Urteil und Suche stehen oben, dazu eine Sortierung, auch nach Angebotsende. DLC
stehen direkt unter ihrem Spiel, eingerückt und ohne den Namen des Spiels davor; eine Ausgabe
des Spiels („+ Rayman Edition“) gilt dabei als das Spiel. Steht das Spiel nicht auf der Wishlist,
stehen seine DLC unter einer Kopfzeile mit seinem Namen, auch ein einzelner. Sortiert nach Preis, Abstand oder Angebotsende ist die Liste flach.

Ein Klick auf den Titel klappt die **Einzelheiten** auf:

- die Rechnung und alle Länder mit Preis, Stufe, Rabatt, Angebotsende, Abstand zum
  Bestpreis und Landestief (eine ungeprüfte Sprache lässt sich dort direkt bestätigen),
- Bestpreis, typischer Angebotspreis und die Ersparnis gegenüber dem nächstbesten zählenden
  Land (Deutschland steht nur zur Information daneben),
- Zielpreis (leer heißt: das Urteil misst am Bestpreis; „Bestpreis übernehmen“ setzt ihn),
- Eigene Angebote: grün „zählt“, grau „zählt nicht: der eShop ist dort günstiger“, mit Link
  dahinter der Stand der Prüfung,
- Pakete: Steht eine Komplett-Edition oder ein Paket auf der Wishlist, nennen die
  Einzelheiten die bekannten Teile und vergleichen den Paketpreis mit dem, was die fehlenden
  Teile einzeln jetzt kosten („Paket spart“ oder „einzeln günstiger“). Teile in deiner
  Sammlung zählen nicht („hättest du doppelt“). Ist nur ein Teil bekannt oder fehlt einem Teil
  der Preis, gibt es keinen Vergleich. Bei einem Titel steht außerdem, in welchen Paketen er
  steckt.
- Angebotsrhythmus je Land (siehe [Verlauf](#verlauf-und-typischer-angebotspreis)),
- Links zu DekuDeals, eShop-Prices und zum eigenen Verlauf.

**Switch 2:** Steht eine Nintendo Switch 2 Edition auf der Wishlist und die Switch-1-Fassung
in deiner Sammlung, trägt der Titel die Marke „Upgrade genügt“, und die Einzelheiten nennen
den Preis des Upgrade-Pakets und die Ersparnis gegenüber der Edition (wenn das Paket auf der
Wishlist steht). Ohne die Switch-1-Fassung vergleicht die Zeile „Spiel plus Paket“ mit der
Edition, sofern beides auf der Wishlist steht. Die Edition gehört zum Spiel, dessen Kürzel sie
bei DekuDeals um „nintendo-switch-2-edition“ verlängert; das Paket ist ein DLC dieses Spiels.
Der Kaufplan kauft nur einen Weg zur Switch 2: Hast du das Spiel, lässt er die Edition weg und
plant das Upgrade-Paket wie jeden Wishlist-Titel. Stehen Edition und Switch-1-Fassung beide
zum Kauf an, bleibt der günstigere Weg; ist der Preis des Pakets unbekannt, bleibt die
Edition. Was wegfällt, steht unter „Nicht im Plan“.

**Tabelle:** alle Titel mal alle Länder in Euro, Spalten nach Stufe gruppiert und darin nach
der Zahl der Bestpreise (im Spaltenkopf mit ★), wahlweise nur nach Bestpreisen oder nur nach
Stufe; Deutschland bleibt vorn, Länder, in denen gerade nichts zählt, am Ende. Angebote mit
dem Urteil „kaufen“ sind dunkelgrün hinterlegt, „gut“ hellgrün; gold umrandet ist das Land, in
dem es den Bestpreis gab. Jede Zelle hat zwei Zeilen wie im Korb: oben Preis und rot der
Abstand zum Bestpreis, darunter Rabatt und Marken. „Details“ zeigt in jeder Zelle Landestief, Angebotsende und Sprache.
Die Tabelle füllt das Fenster und scrollt in sich, Kopfzeile und Titelspalte bleiben stehen.
„nur Angebote“ blendet auch Länder ohne Angebot aus. Ist ein Titel überall kostenlos oder
nirgends zu haben, steht statt lauter gleicher Zellen eine Zeile mit dem Grund. Der Landespreis
verlinkt den Verlauf bei DekuDeals, der Europreis die eShop-Seite des Landes.

### Korb

Der Korb ist eine Ansicht der Wishlist, neben Liste und Tabelle; die Zahl am Knopf „Korb“ nennt
seine Titel. Ein gemeinsamer Korb, verglichen in allen Ländern: Titel als Zeilen, Länder als Spalten,
darunter Einkaufspreis, Preis, Wechsel und Rest wie auf den Länderkarten. Das günstigste Land
ist hervorgehoben, aber nur unter Ländern, die den ganzen Korb anbieten. „+“ in der Liste oder
vor dem Titel in der Tabelle legt einen Titel in den Korb, „✓“ nimmt ihn wieder heraus, „als Korb vergleichen“ auf einer Länderkarte übernimmt deren
Titel (der Kaufplan kauft in mehreren Ländern nacheinander und ist deshalb kein Korb).
„Korb leeren“ löst nur den gemeinsamen Korb auf. Die Länder stehen von leicht nach schwer,
darin vorn, wer mehr Titel anbietet und günstiger ist.

Die Tabelle ist fensterhoch mit fester Kopfzeile wie die Titel-Tabelle: Spalte Bestpreis,
je Zelle oben Preis und Abstand zum Bestpreis, darunter Rabatt und Marken; Preise grün nach
Urteil, rot nur der Abstand. Der Stern gilt dem Preis im Korb, denn die Titel teilen sich die Karten.
Landeswährung, Zahlweg und Angebotsende stehen im Tooltip. Der Preis öffnet den eShop, bei DLC
den Verlauf bei DekuDeals, weil es für DLC keinen festen eShop-Link gibt.

Am Handy (schmaler als 641 px) steht statt der breiten Tabelle ein Land nach dem anderen: oben die
Auswahl des Landes mit seinem Einkaufspreis, vorgewählt das günstigste, darunter die Titel mit
derselben Preiszelle und die Summen (Preis, Wechsel, Rest, Shop, Karten, Hinweise). Ein Tipp auf
„Einkaufspreis“ klappt die Rechnung auf, die am Rechner im Tooltip steht.

Unter dem Korb steht, was er kostet, wenn jeder Titel im günstigsten Land mit Kartenzahlung
gekauft wird, sofern das günstiger ist als alles in einem Land. Dort kostet der Wechsel nichts,
und es bleibt kein Rest.

### Länderkarten

Kein eigener Reiter: Die Karten öffnen sich über „Andere Länder“ an einem Schritt oder über
„alle Länderkarten“ unter dem Kaufplan; „← Kaufplan“ führt zurück.
Länderkarten als dichtes Raster oder große Liste. Das Land, in dem dein Konto steht, kommt
zuerst, dann die übrigen nach der gewählten Reihenfolge, Deutschland als Vergleich am Ende.
Jede Karte enthält die Angebote des Landes, die günstiger als in Deutschland sind, und
dauerhaft günstige Normalpreise mit dem Urteil „kaufen“, also dieselben Titel, mit denen auch
der Kaufplan rechnet. Steht das Land im Kaufplan, zeigt die Karte genau dessen Korb („Korb:
wie im Kaufplan“), denn der Einkaufspreis hängt an den Guthabenkarten für den ganzen Korb.
Änderst du die Karte, wird daraus ein eigener Korb; „alle zurücksetzen“ setzt alle auf einmal
zurück.

Die Kopfzahl ist der Einkaufspreis des Pakets. Bezahlst du ganz oder teils aus vorhandenem
Guthaben, steht das darunter. Dann drei Zeilen:

- **Preis:** Abstand der Spiele zur Summe ihrer Bestpreise (rot, grün nur „am Bestpreis“) und
  die Zahl der Urteile,
- **Wechsel:** ob sich der Weg hierher lohnt („✓ lohnt“ oder rot „lohnt nicht“, mit Gewinn
  gegenüber „sonst“ und der Schwelle der Stufe),
- **Rest:** was als Guthaben bleibt und was hineinpasst.

Hürden (Rest blockiert, Karten fehlen, DLC braucht eine andere Region als Europa) stehen
darunter; die betroffenen DLC sind in der Tabelle wie der Hinweis violett markiert. Die Tabelle
zeigt je Titel Einkaufspreis, Abstand zum Bestpreis und den Preis ohne diesen Wechsel
(„sonst“). Vorschläge zum Dazunehmen (+) oder Weglassen (−) stehen darunter, die ganze
Rechnung unter „Rechnung“.

### Sammlung

Alle Spiele deiner DekuDeals-Sammlung mit ihren Zusatzinhalten (Abschnitt „DLC“ der
DekuDeals-Artikelseite), je DLC „hast du“ oder „fehlt“. Ob du einen DLC hast, sagt deine
Sammlung bei DekuDeals; was sie nicht kennt, etwa einen DLC aus einem Paket, hakst du mit
„habe ich“ ab. „ignorieren“ (je DLC) und „alle DLC ignorieren“ (je Spiel) blenden Inhalte aus,
die dich nicht interessieren: Sie zählen nicht als fehlend und stehen eingeklappt unter dem
Spiel. Die DekuDeals-Sammlung geht vor, die Haken stecken in der Sicherung. Fehlende DLC, die
weder auf der Wishlist stehen noch ignoriert sind, tragen einen violetten Rand und den Hinweis
„nicht auf der Wishlist“: Über sie hast du noch nicht entschieden. Jeder DLC-Name führt zu
DekuDeals, der Preis „x € in Land“ zum Preisverlauf dort für dieses Land.

- **Aufbau:** Spiele mit fehlenden DLC stehen oben, je eines in einem Kasten. Darunter
  zugeklappt „Ohne offene DLC“ (alle DLC da, ignoriert oder nicht mehr erhältlich, je eine
  Zeile, die seine DLC aufklappt; „alle aufklappen“ und „alle zuklappen“ stehen in der Erklärung)
  und „Ohne Zusatzinhalte“, A–Z spaltenweise. Die Suche klappt
  Abschnitte mit Treffern auf. Noch nicht gelesene Spiele stehen offen am Ende. Filter und
  Reihenfolge (Name, Zahl, Preis oder Angebote fehlender DLC) stehen über den Spielen.
- **Preise fehlender DLC:** der günstigste Preis je DLC, je Spiel und insgesamt die Summe, mit
  denselben Zeichen wie die Titelliste (Stern am Bestpreis, grün bei „kaufen“ oder „gut“,
  Rabatt blau), soweit Tiefstpreise bekannt sind. Steht ein fehlender DLC auf deiner Wishlist,
  stehen Urteil, Einkaufspreis und Land dabei, sonst ein Link zu DekuDeals, um ihn auf die
  Wishlist zu setzen. Upgrade-Pakete für die Switch 2 sind markiert.
- **Pakete:** Spiele, die du nur über eine Edition hast, stehen mit „über …“, ihre neueren DLC
  als fehlend, enthaltene als „hast du, im Paket …“. Liegt DekuDeals bei einem Teil falsch,
  schaltet „stimmt nicht“ ihn wieder auf „fehlt“ (gilt auch für alles, was darin steckt). Ein
  fehlender Pass steht mit seinen Teilen eingerückt darunter („enthält 3 DLC, 1 schon da“) und
  vergleicht „einzeln … · als Pass …“ für die noch fehlenden Teile; ist ein Teil einzeln nicht
  kaufbar oder noch ohne Preis, steht dort „einzeln nicht alle kaufbar“. „fehlen“ zählt Inhalte,
  nicht Kaufwege; in die Summe geht der günstigere Weg. Stehen ein Pass und seine Teile zum
  Kauf an, kauft der Kaufplan den Pass, die Teile stehen unter „Nicht im Plan“ („steckt in …“).
- **Nicht mehr erhältlich:** Findet die ID-Suche einen fehlenden DLC in keiner gesuchten
  Region, jeweils zweimal, gibt es ihn meist nur im Spiel oder nicht mehr im eShop. Er zählt
  nicht als fehlend und steht eingeklappt unter „nicht mehr erhältlich“. Was in einer Region
  gerade nicht kaufbar ist, zählt dort ebenfalls nicht als offen.

### Einstellungen

Jede Änderung wird sofort gespeichert. Jeder Bereich ist eine eigene Karte, eine Leiste oben
springt zu Länder, Regeln, Gebühren, Sprachen, Käufe, Quellen sowie Sicherung und Protokoll.

**Käufe aus dem eShop** (eigene Karte): Deine Sammlung pflegst du bei DekuDeals. Der
Kaufverlauf von Nintendo sorgt nur dafür, dass der Plan nichts vorschlägt, was du schon gekauft
hast, und zeigt Käufe, die bei DekuDeals noch fehlen. Das Lesezeichen „Käufe lesen“ liest in
deinem Browser, angemeldet bei Nintendo, deinen Kaufverlauf (laut Nintendo zwei Jahre) auf
dieselbe Weise wie die Seite selbst, mit kurzen Pausen. „Im eShop-Kompass übernehmen“ öffnet das
Tool und gibt die Liste im Adressteil hinter # weiter (geht nicht übers Netz); ersatzweise Text
kopieren und einfügen. Der Kaufverlauf nennt keine Nintendo-ID, nur Titel, Datum, Art und
Betrag. Jeder Kauf landet von selbst in einer Gruppe:

- **Erstattet** und **Mitgliedschaft oder Gutschein** zählen nicht.
- **Bei DekuDeals nachtragen:** Der Titel passt genau auf einen Wishlist-Titel oder fehlenden
  DLC (bei DLC auch als „Spiel: DLC“). Er zählt als Besitz, fällt aus dem Kaufplan und steht
  unter „Zu erledigen“, bis du ihn bei DekuDeals eingetragen hast.
- **In der Sammlung:** Der Titel passt auf ein Spiel oder einen DLC deiner DekuDeals-Sammlung
  (genau oder sehr ähnlich). Nichts zu tun.
- **Offen:** Der Titel ähnelt einem Wishlist-Titel oder fehlenden DLC. Unter „Welcher Titel ist
  das?“ steht je Kauf eine Zeile mit bis zu drei Kandidaten; ein Klick auf einen Namen ordnet ihn
  zu, „keiner“ lässt ihn im Plan. „Zu erledigen“ zeigt, wie viele offen sind.
- **Nicht in der Sammlung:** Nichts passt. Meist kennt DekuDeals den Titel nicht.

Kauftitel aus Japan und anderen Ländern stehen in der Sprache des Shops. Für Käufe, die offen
oder unbekannt bleiben, sucht der Abgleich in titledb den Namen in der Liste des Konto-Landes
(Titel mit japanischen Schriftzeichen immer in der japanischen Liste, auch wenn das Konto beim
Lesen woanders stand; Titel in lateinischer Schrift zusätzlich in der deutschen Liste),
nimmt dessen Programm-ID und daraus den englischen Namen aus der US-Liste (jede Liste höchstens
einmal die Woche, je Kauf frühestens nach 30 Tagen wieder). Mit dem englischen Namen gleicht er dann wie
oben ab; er steht grau hinter dem Kauftitel. Titel nur aus chinesischen Schriftzeichen sucht er in
der Liste von Hongkong.

Pässe (Upgrade-Pass für die Switch 2, Erweiterungs- und Kämpfer-Pass) führt titledb oft ohne
Programm-ID. Dann zählt die Shop-ID, wenn ein fehlender DLC dieselbe hat, sonst der Spielname am
Anfang des Kauftitels und die Art des Passes: „Spiel: Upgrade Pack“ findet den DLC dieses Spiels,
auch wenn er als gekauft nicht mehr unter den fehlenden DLC steht (aus der DLC-Liste des Spiels).
Führt DekuDeals ein Spiel nur als „… – Nintendo Switch 2 Edition“, zählen Spiel und Upgrade-Pass
als dieser Eintrag. Käufe „A + B“ bekommen den englischen Namen aus beiden Teilen.

Namen gleichen ohne Akzente ab: „Pokemon“ im Kaufverlauf ist „Pokémon“. Ein DLC in deiner
Sammlung zählt auch, wenn titledb ihn „Spiel: DLC“ nennt und die Sammlung nur „DLC“, und auch
dann, wenn das Tool zu einem Eintrag der Sammlung keinen Namen kennt (dann aus der Kennung bei
DekuDeals). Die Zeile über den
Abschnitten zählt die Käufe je Gruppe, „nicht in der Sammlung“ rot: Diese Käufe kennt das Tool
nicht, der Plan könnte sie vorschlagen; sie stehen ganz oben unter „Nicht in der Sammlung“ zum
Zuweisen. „Nicht in der Sammlung“, „Welcher Titel ist das?“ und „Bei DekuDeals nachtragen“ sind
offen und lassen sich zuklappen, „Alle Käufe“ ist zu und sortiert die Einordnung nach
Dringlichkeit. Ein gekaufter DLC bleibt zugeordnet, auch wenn er nicht mehr unter den fehlenden
DLC steht: Das Tool vergleicht genaue Namen auch mit den DLC-Listen deiner Spiele.

„anderer …“ (in „Alle Käufe“: „zuweisen“, bei einem Kauf, den das Tool schon einem Titel der
Sammlung zugeordnet hat, „neu zuweisen“) öffnet unter dem Kauf eine Zeile mit Suchfeld: Treffer aus allen bekannten Titeln und
DLC erscheinen beim Tippen (ohne Akzente, „pokemon“ findet „Pokémon“), ein Klick ordnet zu; ein
DekuDeals-Link geht immer. „zurücknehmen“ hebt deine Zuordnung sofort auf,
„stimmt nicht“ eine automatische. „Alle Käufe“ zeigt jeden Kauf mit seiner Gruppe, sortierbar.
Zuordnungen bleiben und stecken in der Sicherung. Der Link zur Kaufhistorie im Tool gibt den
Stand des letzten lückenlosen Laufs mit; das Lesezeichen liest dann bis dorthin und zur
Sicherheit eine ganze Seite bereits bekannter Käufe weiter. Bricht ein Lauf ab, übernimmt das
Tool das Gelesene, behält aber den alten Stand, und der nächste Lauf liest wieder ab dort.
„alles neu lesen“ liest den ganzen Verlauf noch einmal: Bekannte Käufe bekommen nur fehlende
Angaben, deine Zuordnungen bleiben, kein Eintrag verschwindet. Der Abgleich läuft bei jedem
Öffnen über alle gespeicherten Käufe, bessere Regeln gelten also auch für alte.

- **Länder:** Die aktiven Länder stehen oben, eingeklappt mit Zahlweg, Steuer, Guthaben und
  Guthabenkarten; das Kontoland steht darüber. Die übrigen stehen unter „weitere Länder“, mit
  Schalter. Die Spalte Preisniveau zeigt für jedes Land, wie es zu deiner Wishlist steht, auch
  wenn es abgeschaltet ist. „Dein Faktor“ nennt je Land, was der Zahlweg ergibt („1,00
  Kreditkarte“, „0,98 Guthaben“); aufgeklappt stehen alle Karten mit Wert, Preis, Faktor und
  Bewertung.
- **Bezahlen:** Karte, Guthabenkarte oder das Günstigere von beiden.
- **Steuer:** Aufschlag in Prozent, wo der Shop Preise ohne Steuer zeigt (USA, Kanada).
- **Regeln:** Urteilsgrenzen, Mindestersparnis je Wechselstufe und die Sprachregel. Ein Satz
  fasst die aktuellen Werte zusammen, die Felder stehen eingeklappt unter „Grenzen anpassen“.
- **Gebühren:** Fremdwährungsgebühr deiner Kreditkarte, Servicegebühr des Kartenshops,
  mögliches Cashback; unter „Erweitert“ die Schätzung ohne Kartenpreis und die Stufen für
  Euro-Guthaben.
- **Deutschland (Guthaben):** Die Vergleichsbasis ist immer der Preis im deutschen eShop. Wer
  mit günstigen deutschen Guthabenkarten zahlt, schaltet „Deutschland (Guthaben)“ (DG) ein:
  dasselbe Konto und dieselben Preise, gerechnet wie jedes Guthabenland. Ein Rest bleibt auf
  dem Konto und wird ab 5 € gewarnt (Nintendo nimmt Guthaben bei keinem Länderwechsel mit).
- **Sammlung:** Titel aus deiner DekuDeals-Sammlung werden als vorhanden markiert, bei DLC
  steht dabei, ob du das Hauptspiel hast.
- **Sicherung:** Einstellungen, Karten, Zielpreise, Körbe, Kaufprotokoll, Haken und
  Zuordnungen sowie die eigene Preisaufzeichnung als eine Datei. Beim Einlesen wird die
  Aufzeichnung ergänzt, nicht ersetzt; alles andere holt das Tool beim Abgleich neu.
  „Abgleichsdaten herunterladen“ lädt die gesamten Abgleichsdaten (IDs, Sprachen, Preise,
  `data.json`) und das Protokoll als Datei, ohne Einstellungen.
- **Protokoll:** läuft während eines Abgleichs mit, nennt oben Start und Version des Laufs und
  zeigt die Uhrzeit deines Browsers. Jeder Schritt schreibt eine Zeile, auch wenn nichts fällig
  ist („nichts fällig“, „alle aktuell“), damit sich Abgleiche vergleichen lassen. „Verbindung
  testen“ schreibt in eine eigene Box darüber. Beides lässt sich kopieren; das Protokollfeld
  lässt sich unter „kopieren“ zuklappen und bleibt dann zu.

#### Guthabenkarten

Eine Karte je Zeile, `Wert = Preis in Euro | Link`. Ein vorangestelltes `x` heißt nicht
vorrätig. Kaufst du Guthaben zum Kurs (etwa Codes bei einem Händler, der in Landeswährung
abrechnet), genügen die Werte ohne Link, zum Beispiel `500 1000 2000 3000 5000 9000`: Dann
rechnet das Tool zum Kurs, bezahlt mit deiner Karte (also plus deiner Fremdwährungsgebühr), und
der Rest zählt mit.

- **Gelesene Preise:** Hat eine Karte einen Link, liest das Tool beim Abgleich höchstens einmal
  am Tag den Preis von der Shopseite (aus den Produktdaten der Seite; nennt sie mehrere
  Angebote, zählt das günstigste). Über dem Eingabefeld steht, was es gelesen hat. Sperrt der
  Shop nach einigen Abrufen, kommen zuerst die Karten der Länder dran, in denen der Kaufplan
  gerade kauft, danach die Links, die am längsten nicht gelesen wurden. So bleiben die Preise
  frisch, die gerade zählen, und kein Link bleibt dauerhaft liegen.
- **Glaubhaft:** Ein gelesener Kartenpreis zählt nur zwischen 70 und 160 % des Nennwerts zum
  Mittelkurs. Alles andere ist fast sicher ein Lesefehler, etwa ein Gebührenhinweis statt des
  Preises. Solche Werte stehen mit „unglaubhaft, ignoriert“ unter der Kartenliste und im
  Protokoll, es gilt dein Eintrag.
- **Datei einlesen:** Unter `countries.<Land>.cards_add` ergänzt eine Datei Karten, ohne
  vorhandene zu ersetzen. Gibt es den Kartenwert schon, bekommt die Zeile nur den Link.

#### Sprachen prüfen

Das Tool prüft jeden Wishlist-Titel und die fehlenden DLC deiner Spiele einmal je Region und
speichert das Ergebnis dauerhaft, unabhängig vom Preis. Europa gilt als dasselbe Produkt wie
Deutschland. DLC übernimmt die Sprache seines Spiels; für fehlende DLC reicht deshalb eine
Seite je Spiel und Region. Dasselbe gilt für DLC auf der Wishlist, deren Spiel nicht darauf
steht: Das Tool sucht die Seite des Spiels je Region und nimmt dessen Sprachen, denn eigene
Seiten von DLC fehlen in Amerika und Japan oft ganz.

Oben stehen alle offenen Titel, einmal je Region (fehlende DLC als ein Eintrag je Spiel; der
Preis nennt dann den günstigsten fehlenden DLC, „fehlende DLC dort ab“), mit Link in den Store
und „Deutsch ja“/„nein“. Wo die Fassung gerade günstiger wäre, steht „günstiger“ und der Titel
oben; was dort gerade nicht kaufbar ist, steht unten. Aufgeklappt folgen die geprüften,
gruppiert nach Quelle (von Nintendo gelesen, laut titledb, von dir bestätigt). Die Spalte zeigt
„✓ Deutsch“ oder „– ohne Deutsch“, der Tooltip nennt Quelle und gelesene Sprachen; „Deutsch“ ist
grün, wenn Nintendo oder du es bestätigt habt, violett, wenn es nur
laut titledb gilt. ✎ überschreibt eine gelesene Angabe, ↺ stellt sie wieder
her. Von Hand gilt dauerhaft und geht der Angabe von Nintendo vor. Steht ein Titel weder auf
der Wishlist noch in der Sammlung, löscht der Abgleich seine Angaben wieder.

**Japan:** store-jp steht hinter einem Warteraum mit Bot-Schutz, durch kommt nur ein Browser
mit JavaScript. Das Tool erkennt den Warteraum, hört auf und fragt die nächsten sieben Tage
nicht mehr an. Die Sprachen kommen stattdessen aus titledb (siehe [Abrufe](#abrufe)) und vom
Browser-Helfer „JP-Sprachen lesen“: einem Lesezeichen, das in deinem Browser die Shopseiten der
offenen Titel und der Titel mit Angabe aus titledb (zur Bestätigung) liest, die Liste steht
im Kasten, je Seite mit allen Titeln, die sie klärt (DLC ohne eigene Seite stehen auf der ihres
Spiels; deshalb können sechs Einträge zwei Seiten sein; eine Seite alle 2,5 Sekunden; die IDs bekommt es über den Link zu store-jp im
Tool oder, wenn der Store sie unterwegs verliert, über ein kleines Fenster des Tools) und das
Ergebnis ans Tool gibt. Zeigt eine DLC-Seite keine Sprachen, liest es die Seite des Spiels, auf
die sie verweist. Angaben von Nintendo gehen titledb vor. Findet der Helfer unter einer ID keine
Seite, meldet er „keine Seite“, und der nächste Abgleich sucht die ID neu.

## Betrieb

### Abrufe

Was das Tool woher, wann und wie oft holt und wo es die Daten ablegt, steht ausführlich in
[`docs/abrufe.md`](docs/abrufe.md). Die Grundregeln:

- **Ehrlich und schonend:** Das Tool fragt immer mit seiner eigenen Kennung an
  (`eshop-kompass/<Version>`), macht Pausen zwischen den Abrufen und hört bei einer Sperre
  (HTTP 403 oder 429) oder einer Prüfseite auf, statt sich als Browser auszugeben. Der Rest
  folgt beim nächsten Abgleich; nach einer Sperre von DekuDeals ruht DekuDeals 24 Stunden, und
  kein späterer Schritt desselben Abgleichs fragt dort noch einmal. Jede DekuDeals-Seite kommt
  je Abgleich höchstens einmal.
- **Melden statt raten:** Nennt keine gelesene Seite Amerikas Sprachen, hat sich vermutlich
  die Seite geändert; das Protokoll warnt, und die Versuche zählen nicht.
- **Nie alles auf einmal:** Jeder Schritt hat eine Obergrenze je Abgleich (etwa 40
  Artikelseiten, 40 Sprachseiten je Region); was nicht drankommt, folgt beim nächsten Lauf,
  das Älteste zuerst.
- **Eine Quelle bricht nie den ganzen Abgleich ab:** Ist die Wishlist nicht lesbar, rechnet
  das Tool mit der zuletzt gelesenen weiter.
- **Nichts still löschen:** Liefert eine Seite plötzlich keine Tiefstpreise oder DLC mehr,
  obwohl welche bekannt sind, bleiben die alten, und das Protokoll warnt. Titel, die 180 Tage
  weder auf der Wishlist noch in der Sammlung stehen, verschwinden aus den Abgleichsdaten (die
  eigene Preisaufzeichnung bleibt).
- **Kurse:** Die Wechselkurse erneuert die Quelle einmal am Tag; das Tool holt sie nur, wenn es
  Neues gibt.
- **titledb:** eine offene Titelliste auf GitHub, nicht von Nintendo (in der Oberfläche „laut
  titledb“). Je Region eine Datei von rund 25 MB, Stück für Stück gelesen, nur die eigenen IDs
  behalten. Geladen wird sie nur, wenn neue IDs zu suchen sind oder sich die Datei seit dem
  letzten Laden geändert hat. Sie liefert Sprachen für Japan, die Japan- und Amerika-IDs fehlender DLC über die
  Programm-ID und die Fassung von DLC je Region.

„Verbindung testen“ zeigt je Quelle, was zurückkommt, auch für die erste Guthabenkarte mit Link
(liest die Seite einen Preis?) und für die Online-Mitgliedschaft (DekuDeals und Nintendos
Mitgliedschaftsseiten für Japan, Deutschland und die USA). Gespeichert wird dabei nichts.

### Datenquellen

- Wishlist, Sammlung, Titel-IDs, Tiefstpreise, DLC und Pakete: dekudeals.com (öffentliche
  Wishlist, IDs werden dauerhaft gespeichert)
- Preise und Verfügbarkeit: api.ec.nintendo.com/v1/price (inoffiziell; nach einem kurzen
  Netzfehler ein zweiter Versuch, sonst bleiben die alten Preise des Landes)
- Sprachen: search.nintendo-europe.com (Europa), nintendo.com-Produktseiten über
  ec.nintendo.com (Amerika), store-jp.nintendo.com und titledb
  (raw.githubusercontent.com/blawar/titledb, Japan), sonst deine Bestätigung
- Japan- und Amerika-IDs fehlender DLC: titledb (Programm-ID), sonst DekuDeals
- Online-Mitgliedschaft: Nintendos Mitgliedschaftsseiten je Region und DekuDeals
- Wechselkurse: open.er-api.com, ersatzweise frankfurter.dev (EZB)
- Eigene Käufe: Kaufverlauf bei Nintendo, gelesen nur in deinem Browser über das Lesezeichen
  „Käufe lesen“; der Server meldet sich nie bei Nintendo an

### Verlauf und typischer Angebotspreis

Nach dem Preisabruf lädt das Tool je Titel und Land den digitalen Tiefstpreis von der
DekuDeals-Artikelseite nach (ein Abruf alle 2,5 Sekunden, Angebote zuerst) und führt ihn danach
selbst fort, auch dort, wo DekuDeals keinen Wert hat. Jeder Preiswechsel landet zusätzlich in
`data/history.json`. Für Titel, deren Tiefstpreis schon bekannt ist, holt es die Seite nur
während eines Angebots nach, höchstens 40 je Abgleich und danach einmal im Monat.

Bestpreis und Landestief kommen aus dem digitalen Tagesverlauf der DekuDeals-Artikelseite (das
Tool speichert je Monat den tiefsten Preis) und der eigenen Aufzeichnung, jeweils der letzten
24 Monate; ältere Tiefstwerte zum heutigen Kurs zeigten Preise, die es so nie gab. Nur wo der
Verlauf fehlt oder die Seite Tiefstpreise für Switch und Switch 2 nennt (dann ist offen, zu
welcher Fassung der Verlauf gehört), gilt der Allzeit-Tiefstpreis. Fehlt ein digitaler
Tiefstpreis (manchmal steht dort nur der eines Händlers), gilt der niedrigste Preis aus dem
digitalen Verlauf. Haben Switch und Switch 2 je einen Tiefstpreis, gilt der höchste, den der
Preis jetzt nicht übersteigt, also der der eigenen Fassung.

„Verlauf“ in den Einzelheiten zeigt die Aufzeichnung als Kurve je Land und dazu: Preis jetzt,
Normalpreis, tiefster aufgezeichneter Preis mit Datum, Zahl der Angebote (laut DekuDeals in den
letzten 24 Monaten, sonst aus der eigenen Aufzeichnung), typische Dauer, Anteil der Zeit im
Angebot und das letzte Angebot. Europreise rechnen mit dem heutigen Kurs und Zahlweg, damit
Länder und Zeitpunkte vergleichbar bleiben. Ein Angebot ist jede Strecke unter dem heutigen
Normalpreis. „Fall exportieren“ lädt alle Daten dieses Titels als Datei (Preise, Tiefstwerte,
Verlauf, Karten, Kurse, Einstellungen ohne Wishlist- und Sammlungslink).

**Typischer Angebotspreis:** Aus dem Tagesverlauf liest das Tool die Angebotsphasen der letzten
zwei Jahre (Normalpreis ist der häufigste Preis, ein Angebot jede Strecke mindestens 3 %
darunter) und merkt sich je Phase den tiefsten Preis. Der typische Angebotspreis ist der Median
dieser Tiefstwerte, ab zwei Phasen. War das letzte Angebot tiefer als der Median, gilt dieses:
Nintendo senkt Angebotspreise oft dauerhaft. Je Titel zählt das günstigste Land, in Euro zum
heutigen Kurs.

**Angebotsrhythmus:** Aus denselben Phasen zeigen die Einzelheiten je Land, wie viele Angebote
es gab, in welchen Abständen, wann das letzte lief und in welche Monate sie meist fielen. Eine
Vorhersage ist das nicht. Nur wenn es mindestens vier Angebote gab und alle Abstände höchstens
30 % vom Schnitt abweichen, steht dabei, wann das nächste nach diesem Muster üblich wäre, als
Schätzung gekennzeichnet.

### Selbstprüfung

Nach jedem Abgleich prüft das Tool seine Ergebnisse: unglaubhafte Kartenpreise, ein Preis je
Währungseinheit, der sich seit dem letzten Lauf um mehr als 15 % geändert hat, ein Land, in dem
plötzlich weniger als die Hälfte der Titel kaufbar ist, und Wechselkurse, die älter als drei
Tage sind. Auffälligkeiten stehen im Protokoll und als Hinweis über den Ansichten.

### Notbetrieb

Sperrt DekuDeals oder ist seine Wishlist nicht lesbar (etwa nach einem Umbau der Seiten), rechnet
das Tool mit der zuletzt gelesenen Wishlist und Sammlung weiter, ebenso mit den bekannten
Tiefstpreisen, DLC und Paketen. Preise, Wechselkurse und Kartenpreise kommen wie immer. Oben steht
dann ein Hinweis „Notbetrieb“ mit dem Grund (Sperre bis wann, oder der Fehler) und dem Datum der
Listen. Er erscheint auch, wenn die Wishlist länger als drei Tage nicht gelesen wurde, und
verschwindet beim ersten Abgleich, der sie wieder liest.

### Sicherheit

Die Oberfläche nimmt Änderungen nur als JSON an; eine fremde Webseite kann so keine
Einstellungen überschreiben. Eine Anmeldung gibt es nicht, nach außen freigeben solltest du das
Tool deshalb nicht.

Eigene Links (Kartenpreise, eigene Angebote) holt der Server nur von öffentlichen Adressen. Zeigt ein Link oder eine Weiterleitung auf eine private, lokale oder Loopback-Adresse, steht im Protokoll „Adresse nicht öffentlich“, und nichts wird abgerufen. Unerwartete Fehler zeigt die Oberfläche nur mit ihrer Art an, die Einzelheiten stehen im Protokoll des Containers (`docker logs`).

### Tests

    python3 -m unittest tests.test_all

Dazu gehören Tests der Oberfläche ohne Zusatzpakete: Ein Vertragstest prüft, dass der Server jedes
Feld liefert, das die Oberfläche liest (die Liste steht in `UiContractTest.CONTRACT`), und dass jede
Adresse unter `/api/` existiert. Ist ein Chromium da (in GitHub Actions immer, sonst über
`CHROME_BIN`), lädt ein weiterer Test die Seite mit Beispieldaten bei 390 px Breite, geht alle
Reiter und alle Ansichten von Wishlist und Ländern durch und schlägt fehl, wenn eine Ansicht seitlich
scrollt oder ein Skriptfehler auftritt. Ohne Chromium wird er übersprungen.

### Aufbau des Codes

Der Server (`app/server.py`) liefert die Oberfläche aus `app/static/`: `index.html`, `style.css`
und die Teile in `js/`, reines JavaScript ohne Build. Gerechnet wird in `app/planner.py` mit
`cards.py` (Guthabenkarten), `titles.py` (Namen, Käufe, Besitz), `kaufplan.py` und
`membership.py`; der Abgleich steht in `app/sync.py`, die Quellen in `app/sources.py`.

### Prüfumgebung

`tools/replay.py` rechnet eine Momentaufnahme ohne Netz durch: Bewertung, Kaufplan, Sprachen
prüfen und Sammlung, so wie die Oberfläche sie zeigt. Eingaben sind die Dateien aus
„Abgleichsdaten herunterladen“ und „Sicherung herunterladen“. Die Abgleichsdaten enthalten auch
die Verbindungen der Pakete, die DLC-Seiten und den Kaufverlauf aus dem eShop. Sie enthalten
deine Wishlist und gehören nicht ins Repository.

    python3 -m tools.replay --abgleich abgleich.json --sicherung sicherung.json
    python3 -m tools.replay ... --szenario konto=PL --szenario kurs=JPY*1.1
    python3 -m tools.replay ... --vergleich origin/main

Es prüft Regeln, die nie verletzt sein dürfen (kein Titel doppelt im Plan oder trotz Sammlung,
jede offene Sprachzeile mit Link, Pakete unter bundles, gültige IDs, kein Kauf ohne Preis, jeder
Füllartikel passt in den Rest), und endet mit Fehlercode 1, wenn eine verletzt ist.
`--vergleich` rechnet dieselben Daten zum selben Zeitpunkt mit einem anderen Git-Stand und
listet, was sich an Urteilen, Plan, offenen Sprachen und Sammlung ändert. Szenarien:
`konto=`, `guthaben=BR:20`, `kurs=JPY*1.1`, `land-aus=`/`land-an=`, `ohne-preis=SLUG`,
`angebot-endet=SLUG`.
