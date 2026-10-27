# Oberfläche: Farben, Marken, Wortwahl

Verbindliche Regeln für die Oberfläche in `app/static/` (`index.html`, `style.css`, `js/*.js`). Wer dort Farben, Marken oder
Bezeichnungen ändert, passt diese Datei im selben Commit an. Die Legende in der
Oberfläche (das "?" oben rechts) und die README beschreiben dasselbe für Nutzer und
folgen dieser Datei.

## Grundsatz

Jede Farbe hat genau eine Bedeutung. Was nichts entscheidet, bleibt grau. Beide Ansichten,
hell und dunkel, müssen lesbar sein; jede Farbänderung wird in beiden geprüft.

## Checkliste für jede neue oder umgebaute Ansicht

Gilt für jede Liste, Tabelle oder Karte, die Titel zeigt (Entscheidung 20.10.2026, nach „Nicht im
Plan“ 0.96/0.97). Vor dem Commit Punkt für Punkt prüfen und mit Bildschirmfotos (breit und 390 px)
gegen eine bestehende Ansicht derselben Art halten, etwa die Wishlist-Liste oder einen Plan-Schritt.

1. **Titelnamen:** voller Name in normaler Größe, DLC mit Marke `DLC` davor. Das Spiel klein und grau
   vor dem DLC-Namen nur dort, wo Spiel und DLC wie in den Schritt-Tabellen eng untereinander stehen.
   Mehrere Titel eines Spiels unter einer eigenen Zeile mit dem Spielnamen (fett, „n Titel“), die
   Titel darunter eingerückt ohne Spielnamen (`titleGroups`, `npTitles`). Klick auf den Namen:
   Einzelheiten (`gotitle`).
2. **Preise:** jeder Preis ist ein Link, in den eShop des Lands (`buyLink`), ohne eShop-Seite (DLC) zum
   Preisverlauf bei DekuDeals (`priceLink`). ★ vor einem Bestpreis, „≈“ vor geschätzten Werten.
   Preise stehen rechtsbündig untereinander, Rabatt, Land und Zusatzangaben in eigenen Spalten, nie
   als Anhang hinter dem Preis.
3. **Farben:** nur der Betrag ist rot (`.bad`/`.abv`), nicht der ganze Satz („kostet **0,08 €** mehr“).
   Grün nur fürs Urteil und für das, was gelingt, Gold nur für den Bestpreis, violett heißt prüfen.
4. **Gruppen:** jede Ebene mit mehr als einer Zeile klappbar (`details` mit `data-kc`, offen als
   Vorgabe, gemerkt wird das Zuklappen), Kopfzeile mit fettem Namen und grauer Zahl, bei mehreren
   Gruppen „alle aufklappen · alle zuklappen“ (`foldall`).
5. **Handlungen:** was man mit einem Titel tun kann, steht in seiner Zeile, wie am Schritt: Auswahl
   „dazunehmen …“ mit Ziel und Preis dort, „zurück“, „entfernen“, Link zur Länderkarte oder zu
   DekuDeals. Geht nichts, sagt die Zeile warum („in keinem Schritt“), statt leer zu bleiben.
6. **Nichts still:** was das Tool selbst entscheidet, steht sichtbar da, mit Grund. Es nimmt nie von
   selbst Titel in einen Schritt; Vorschläge stehen unter „Passt in den Rest“ oder „Passt dazu“.
7. **Wiederverwenden:** bestehende Bausteine nehmen (`pill`, `star`, `ax`, `buyLink`, `priceLink`,
   `overBest`, `endCell`, `tierTag`, `needMark`, `langTag`, `.chip`), keine eigene Form für dasselbe.
8. **Mitpflegen:** Legende, README, diese Datei und „Eine Sache, mehrere Orte“ im selben Commit.

## Hell, dunkel, System

- Umschalter oben rechts, rechts vom "?": rund, zeigt nur das Zeichen der aktuellen Wahl
  (halber Kreis System, Sonne Hell, Mond Dunkel); ein Klick öffnet die drei Stufen, ein Klick
  daneben oder Esc schließt sie. Vorgabe ist System.
- Technik: `data-theme="light|dark"` am `html`-Element, ohne Angabe gilt
  `prefers-color-scheme`. Gemerkt in `localStorage` unter `ek.theme`; ein kleines Skript im
  Kopf setzt es vor dem ersten Zeichnen.
- Die dunklen Tokens stehen zweimal (Gerät dunkel, Wahl dunkel) und müssen gleich bleiben;
  ein Test prüft das.

## Favicon und Einstellungen

Favicon (ab 0.70): rotes, fettes „e“ in Nintendo-Rot (`#e60012`, wie `--brand` hell) als SVG im Kopf
der Seite. Alle Karten der Einstellungen sind ab 0.76 so breit wie der Bildschirm und damit
gleich breit; so scrollt auch „Sprachen prüfen“ auf großen Bildschirmen nicht seitlich (vorher
höchstens 1280 px, nur diese Karte breiter).

## Kaufplan (Jetzt)

„Andere Länder“ (ab 0.74) steht zugeklappt wie „Rechnung“ unter jedem Schritt, in der Zusammenfassung
das nächstgünstigste Land. Je Land eine Zeile: Name als Link, Stufe, darunter klein „ohne …“ oder
„Konto steht dort“, rechts der Betrag: rot `.abv` „+x €“ teurer, grün `.gn` „−x €“ günstiger.
Ab 0.94 klappt ein Klick auf ein Land dessen Karte mit den Titeln des Schritts direkt darunter auf
(`olshow`, `S.olInline`, nur zum Ansehen), darunter „Länderkarte von … öffnen · zuklappen“. Ab 1.0.4
steht sie direkt unter der Zeile des Landes (`tr.olrow`) und rollt ins Bild; am Ende der Liste lag sie
unter langen Listen außer Sicht, der Klick schien nichts zu tun.

Jeder Schritt hat unten wie die Länderkarten „als Korb vergleichen“ und „Titel
dazunehmen …“ (ab 0.68, Name ab 0.69; die letzte Gruppe „Online-Mitgliedschaft“ bietet alle Varianten an). Dazugenommenes ist ein Füllartikel des Schritts und trägt klein grau „dazugenommen“. Steht ein Titel schon in
einem anderen Schritt, nennt die Auswahl „, jetzt in Land“, und er zieht um (ab 1.2.0, `fillStep`, Hinweis
„… von A nach B verschoben“); er steht danach nur in einem `plan_fill`, ein früheres × in diesem Schritt gilt nicht mehr.
Vorher nahm die Auswahl ihn an, der Plan ließ ihn aber im anderen Schritt.

Ab 1.3.0:
- **Suche in Auswahlfeldern:** Vor jedem „Titel dazunehmen …“ und „alles, was passt …“ (Schritt,
  Länderkarte, Korb) steht ein Feld „suchen …“ (`pickWrap`, `.pk`, `input.pkq`). Tippen blendet nicht
  passende Einträge und leere Gruppen aus (`hits`, ohne Akzente) und öffnet die Auswahl als Liste unter dem
  Feld (`.pk.open`, `size` bis 8); Enter nimmt den ersten Treffer (`pickFirst`), Esc leert. Ohne Treffer
  bleibt die Liste zu, das Feld ist rot umrandet (`.pk.none`, `--stop`).
- **Hinweise** (`saleNews`) als `p.restline.news` unter der Zusammenfassung, nur mit Inhalt: „n Angebote
  enden bald:“ fett, ab 1.5.2 die Zahl und bei „Neu im Angebot“ das „Neu“ im Angebots-Blau (`.dealn`, `--deal`), Titel als Link zu den Einzelheiten mit `endCell` (heute/morgen/bis TT.MM.), Angebote im
  Plan und mit Urteil kaufen/gut, weniger als 7 Tage; „Neu im Angebot“ mit grauem „seit höchstens drei
  Tagen“ (Beginn aus `start` der Zelle). Ab 1.3.1 ist jede Zeile selbst klappbar (`details.newsd`,
  gemerkt unter `newssoon`/`newsfresh`): zu nennt sie fett die Überschrift, dahinter grau die ersten drei
  Titel (DLC ohne Spielnamen, ab 1.5.1 in `--ink` wie normaler Text, `.news .ink`, damit sie sich vom
  Grau abheben) und „und n weitere“, jedes Enddatum hervorgehoben (`.soon`, `endCell` mit `mark`, ab
  1.5.1; „heute“ bleibt `.today`); auf verschwindet diese Aufzählung, und alle Titel stehen
  im Raster von „Wartet“ (`npRow`, `NP_COLS`), geplante mit Chip „im Plan“ und Schritt. Abstand
  oben 6 px, unten 10 px (vorher klebte „Neu im Angebot“ an den Karten). Vorher eine zweite, auffälligere
  Zeile „und n weitere“ mit unterstrichenen Links.
  Ab 1.5.3 steht aufgeklappt unter „enden bald“ eine gestrichelt abgesetzte Zeile `p.npmore` „Alle
  Angebote zeigen“ (Link) mit grauem „noch n weitere …“; ein Klick hängt alle übrigen Angebote der
  Wishlist nach Enddatum ins selbe Raster („weniger zeigen“ nimmt sie wieder weg). Nicht klappbar und
  nicht gemerkt (`S.allSale`): Zuklappen von „enden bald“ setzt es zurück.
- **Verweise ohne Unterstreichung** (ab 1.3.1, `.plain`, unterstrichen erst beim Darüberfahren wie
  `a.pl`): Titelname in Schritt, Länderkarte und Korb öffnet die Einzelheiten (`titleBtn`, ein `span`
  mit `role=link`, weil ein Knopf den zweizeiligen DLC-Namen umbrach; Enter und Leertaste gehen),
  „normal“ und Angebotsende in der Spalte „bis“ öffnen den Preisverlauf (`endBtn`; `endCell` hängt
  „· Klick öffnet den Preisverlauf“ an das genaue Ende im Tooltip). Ab 1.5.1 öffnet auch das Urteil
  (`vdBtn`, `button.vdb`, unterstrichen beim Darüberfahren) den Preisverlauf: im Raster von „Wartet“,
  „enden bald“ und „Neu im Angebot“ (`npRow`), in „Am nächsten dran“ (`emptyPlan`), in der
  Wishlist-Liste und in deren Einzelheiten; in der Sammlung bleibt es der Link zu den Einzelheiten
  (1.0.1). Der Einkaufspreis eines DLC ohne
  eShop-Seite führt wie überall zu DekuDeals (`shopLink` statt `buyLink`).
- **Was wäre, wenn** (`assumeBtn`, `assumedLine`): graues ✎ (`.asmb`) hinter dem Einkaufspreis im Schritt
  und vor „dazunehmen …“ unter „Wartet“; es fragt mit `prompt` nach dem Preis in Landeswährung
  (Vorschlag: Tiefstpreis dort). Angenommene Preise violett (`.asm`, `--warn`, prüfen), ohne Link, mit
  kleinem „angenommen“ und ×; oben `p.restline.asmline` mit violettem „Was wäre, wenn:“, je Annahme
  Titel, Preis, Land, „(nicht im Plan)“ wenn sie in keinen Schritt kam, × und „alle verwerfen“. „gekauft“
  meldet bei angenommenen Preisen nur einen Hinweis. Gespeichert in `ui.plan_assume`.
- **Korb in Jetzt** (`jetztBtn`): Fußzeile „Jetzt“ im Korb (am Handy unter den Summen) mit „In „Jetzt“
  übernehmen“ je Land; nimmt dessen Titel per `fillStep` in den Plan, wechselt zu Jetzt und rollt zur Karte.

Eine Karte überall (ab 0.94, Entscheidung 20.10.2026): Schritt und Länderkarte haben dieselben
Werkzeuge. Vor jedem Titel ein graues × (`xBtn`; wie im Korb, statt der Häkchen der Länderkarten):
im Schritt `planskip` (Titel nicht in diesem Schritt, `ui.plan_skip`), bei Dazugenommenem
`planunfill`, auf der Länderkarte `drop`. Unter der Tabelle „Herausgenommen: Titel jetzt in Land
zurück“ (`removedLine`; ab 0.99.4 mit vollem Namen und DLC-Marke, in Schritt und Länderkarte gleich; ohne Schritt unter „Wartet“), am Schritt „zurücksetzen“
(`planreset`), für alle Schritte „Plan zurücksetzen“ rechts in der Kopfzeile des Kaufplans, nur wenn
etwas geändert ist (`planresetall`, `planMine`, Hinweis mit „Rückgängig“, ab 1.0.3). Ein Land unter
„Andere Länder“ rechnet der Server allein (`/api/plans` mit `only`, ab 1.0.3). Darunter bis zu drei Zeilen `.fillrow` (`suggestHtml`): „Passt in den Rest (x):“
(Knöpfe, Paare, Mitgliedschaft, fehlende DLC, Auswahlfeld; ohne Treffer grau „nichts von deiner
Wishlist …“), darunter, wo ein Rest stört, klappbar „Genau Null für x € mehr (statt y Rest)“ und
„Fast Null …“ (`zeroHtml`, ab 1.1.0), „Passt dazu:“ (bis zu zwei, Raster einer) und „Weglassen spart:“ (bis zu zwei). Im
Schritt wirken sie auf den Plan, auf der Länderkarte auf ihren Korb. Die alte Knopfreihe der
Länderkarten (`.sugg`) ist weg. „Passt dazu“ steht immer, als Alternative zum Auffüllen,
aber ohne Titel, die schon unter „Passt in den Rest“ stehen (0.98.1). Was du an der Karte mit × herausgenommen hast, schlägt keine der
drei Zeilen wieder vor (ab 0.95.1; Schritt `p.skipped`, Länderkarte `overrides.remove`). Die Zeile
„Passt in den Rest“ gibt es nur mit Rest, also nie bei Kartenzahlung; „Passt dazu“ steht unabhängig
davon.

## Käufe aus dem eShop

Ab 0.71 eine eigene Karte in den Einstellungen (`#eshophist`, Sprungleiste „Käufe“), nicht mehr im
Reiter Sammlung. Kopf: Zahl der Käufe, Lesedatum. Erklärung als
Satz, Anleitung zum Lesezeichen als eingeklappter Kasten wie der Browser-Helfer für Japan
(`details.box`, „**So liest du deine Käufe aus:** Lesezeichen für deine Kaufhistorie bei Nintendo“, ebenso „**Browser-Helfer für Japan:**“, Doppelpunkt ab 0.90, offen
ohne Käufe, ab 0.78).
Ab 0.76 darunter eine Zahlenzeile wie „Geprüft“ bei den Sprachen („**12 Käufe:** **3** offen, **2** bei
DekuDeals nachtragen, **54** in der Sammlung …“; „12 Käufe:“ fett in Textfarbe, offen und nachtragen
violett, Sammlung grün, nicht in der Sammlung rot `.bad`, Mitgliedschaft und erstattet grau, ab 0.77), dann
die drei Abschnitte als Klappzeilen (`details.eqf`, 13 px, kleiner als die Kartenüberschrift, ab 0.77) mit
normalem, grauem Namen und fetter Zahl (ab 0.78; vorher alles fett; grau ab 0.81, nur die Zahl trägt Farbe, bei „Alle Käufe“ Textfarbe) („Welcher Titel ist das? **3**“, „Bei DekuDeals nachtragen: **2**“, „Alle Käufe:
**122** (zum Nachsehen und Zuweisen)“): „Welcher Titel ist
das?“ und „Bei DekuDeals nachtragen“ von Haus aus offen (gemerkt wird das Zuklappen, `data-kc`),
„Alle Käufe“ zu. Ab 0.81.3 steht ganz oben „Nicht in der Sammlung: **3**“ (Zahl rot, offen von Haus aus,
`data-kc` eshopunk) mit „zuweisen“ bzw. „zurücknehmen · zuweisen“, damit alles Offene über „Alle
Käufe“ steht; die Zahlenzeile nennt die Gruppen in derselben Reihenfolge (nicht in der Sammlung,
nachtragen, offen, Sammlung, Mitgliedschaft, erstattet).
Spalten „Zählt als“ und „Titel“ (ab 1.1.8, `named`): DLC wie in Schritt und Länderkarte, DLC-Marke und
Spiel (`small.gm`, grau) in der ersten Zeile, der DLC-Name als Link darunter; ein DLC ohne bekanntes
Spiel trennt der erste Gedankenstrich, sonst der erste Doppelpunkt (Upgrade-Pässe zur Switch-2-Edition,
ab 1.1.9), das Spiel steht ohne „– Nintendo Switch 2 Edition …“. Spiel und DLC vergleichen Oberfläche und
Server ohne Groß- und Kleinschreibung und mit gleichen Apostrophen (`sameT`, `planner.short`). Sortiert nach Titel zählt das Spiel mit (DLC stehen bei ihrem Spiel). Die
Spalte „Kauf“ bleibt der Text von Nintendo.
„Welcher Titel ist das?“: eine Tabellenzeile je offenem Kauf, links Kauf mit grauer Zeile (Datum,
Art, Plattform, Betrag), rechts die Kandidaten als kleine Knöpfe (`button.cand`, Spiel grau, DLC fett;
Klick = ja), „keiner“ und „anderer …“ (ab 0.76 eine eigene Zeile unter dem Kauf, `tr.eqrow`, damit sich nichts
seitlich verschiebt: Suchfeld, Treffer als Knöpfe beim Tippen über `hits()`, ohne Akzente, höchstens
zwölf; oder DekuDeals-Link mit Knopf „zuordnen“; der Link heißt dann „schließen“). „Bei DekuDeals nachtragen“:
sortierbare Tabelle Kauf, Zählt als (Link), Woher, „stimmt nicht“ oder „zurücknehmen“. „Alle Käufe“
eingeklappt, Zusammenfassung je Gruppe; Spalte Einordnung in denselben Farben wie die Zahlenzeile, sortiert nach Dringlichkeit statt Alphabet (ab 0.81.2: nicht in der Sammlung, nachtragen, offen, Sammlung, Mitgliedschaft, erstattet)
(`ESHOP_CLS`, ab 0.78); dort heißt „anderer …“ „zuweisen“, bei Käufen, die einem Titel
der Sammlung zugeordnet sind, „neu zuweisen“ (ab 0.77); Zeilen „in der Sammlung“, „Mitgliedschaft oder Gutschein“
und „erstattet“ grau (`tr.mutr`). Ein englischer Name aus titledb steht grau in Klammern hinter dem
Kauftitel; bei Pässen ohne eigenen Namen „Spiel: Upgrade Pack“ (ab 0.79). Namen nie als roher Slug (sonst lesbar gemacht). „Zu erledigen“: „n Käufe zuordnen“ und
„n Käufe bei DekuDeals nachtragen“, beide springen zur Karte.

## Online-Mitgliedschaft

Kasten unter dem Kaufplan, zugeklappt, solange die Verlängerung nicht ansteht (30 Tage vor
Ablauf offen und eine Zeile unter „Zu erledigen“; das Wort „Online-Mitgliedschaft“ darin und „ansehen“ springen zum Kasten, Land und Preis sind ab 0.90 kein Link mehr). Eine einzige Auswahl (ab 0.61): Die
markierte Variante (fett, Zeile hinterlegt; der Chip „deine“ fiel 0.62.1 weg) ist deine; ein Klick auf eine andere macht
sie zu deiner und zeigt ihre Länder. Nach einem vermerkten Kauf mit Mitgliedschaft (ab 0.88, `nsoSuggest`) steht unter „Zu erledigen“ statt der Erinnerung und im Kasten hinter dem Datumsfeld „Mitgliedschaft gekauft · läuft damit bis TT.MM.JJJJ (Variante am TT.MM.JJJJ) übernehmen · verwerfen“; beides setzt den Stand `nso_until_set`. Der Tooltip am Preis nennt den Tiefstpreis der letzten 24 Monate; bei 1 Monat und Erweiterungspaket Familie kommt er aus der eigenen Aufzeichnung und trägt „(eigene Aufzeichnung seit TT.MM.JJJJ)“ (ab 0.87, `nsoPrice`). Angebote von Hand (etwa Amazon-Codes) stehen als eigene Zeile
mit Chip „Amazon-Code“ und dem Prüfstand des Links (ab 0.62.1, `offerNote`, überall gleich): grau
„gelesen TT.MM.“ oder „wird gelesen“; violett „Link zeigt 45,66 €“ (andere Währung), „Link liest x,
passt nicht“ (mehr als 40 % Abstand), „Link nicht lesbar“, „Link länger nicht gelesen“, jeweils mit
Tooltip „Es gilt dein eingetragener Preis“; das Wort „Link“ führt zur Seite (ab 0.68). Ein kleines × zum Entfernen
steht gleich hinter dem Preis, in der Titelliste mit Quelle, Land und Preis in einer nicht umbrechenden Gruppe (`.nw`).
Die Kopfzeile nennt die Variante als „ausgewählt: …“ (ab 0.68, vorher „deine“). Der Wechsel der Variante rechnet nicht
neu: Alle Varianten kommen mit dem Stand, die Oberfläche schaltet sofort um und speichert die Wahl danach. Namen der Varianten mit Laufzeit in Klammern („Familie (12 Monate)“); in der
Variantentabelle ist nur der Name der Link, die Klammer steht grau daneben. Tabellenköpfe mit
Klasse `l` stehen linksbündig über ihrer Spalte. Beide Tabellen
sind sortierbar wie alle anderen; die Ländertabelle hat die Wechselstufe als eigene Spalte nach
dem Land, damit die Chips „Konto“ und „im Plan“ allein am Namen stehen. Die Variantentabelle trägt Links, Tooltip, Chips und die Spalte „im Shop“ (ab 0.69); die
Ländertabelle darunter ist zugeklappt („Alle Länder für …“). Über der Ländertabelle
und im Tooltip steht, in welchem Land der Bestpreis war, auch wenn er gerade nirgends zu haben
ist. Passt eine Variante in den Rest eines Kaufplan-Schritts, steht sie dort unter „Passt in den
Rest“ als Hinweis, der zum Kasten führt. Oben steht je Variante das beste Land; der günstigste Preis je Monat ist fett, die
Familie zeigt ihn je Konto und zählt dafür nicht mit (Chip „kauft der Verwalter“). Ein Klick auf
eine Variante zeigt ihre Länder darunter, die Zeile ist dann hinterlegt (`--best`). Es gelten die Farben der Titel (ab 0.56.1):
★ gold am Bestpreis (niedrigster Einkaufspreis der letzten 24 Monate über alle zählenden
Länder, 2 % Spielraum), Preis grün nach Urteil „kaufen“ oder „gut“, Abstand zum Bestpreis rot
`+x €`, Rabatt blau. Der Preis führt in den eShop des Landes, daneben „DekuDeals“ zum Verlauf.
Das günstigste zählende Land fett. Chips „Konto“ und „im Plan“ neutral und mit Tooltip direkt am
Land, damit die Preise rechtsbündig untereinander stehen; Rabatt, Abstand und Link rechts daneben.
Länder ohne Guthabenkarte blass mit violettem Grund.

## Wishlist (Liste)

DLC unter ihrem Spiel (ab 0.72, `titleGroups`): eingerückt (`tr.sub`), Name ohne Spiel davor; ohne Spiel
auf der Wishlist eine Kopfzeile (`tr.tgrp`, Spiel fett, grau „n DLC, das Spiel hast du“), ab 0.77 auch
für einen einzelnen DLC (0.76 schrieb ihn ohne Kopfzeile mit dem Spiel grau davor; das war unruhig).
Gruppe an der Stelle ihres ersten Mitglieds; nach Preis, Abstand, Angebotsende oder Alternative flach, dort steht ein DLC zweizeilig wie in den Karten (Spiel grau `small.gm` mit Doppelpunkt, darunter der DLC-Name, ab 1.1.10). Die Titelspalte steht vertikal mittig (`td.tn`, ab 1.1.11), damit ein einzeiliges Spiel nicht direkt unter dem fetten DLC-Namen der Zeile darüber klebt. Gruppiert steht unter dem Spielnamen (Spiel- oder Kopfzeile) eine graue Zeile „▾ **53** DLC, das Spiel hast du · **4** kaufen, **1** gut“ (`button.dlctog`, 11 px, ohne Unterstreichung, Zahlen fett, kaufen `.g-buy`, gut `.g-good`, ab 1.1.13); ein Klick klappt die DLC zu (▸), gemerkt als `wl:<Spiel>` in den Klappzuständen, die Suche zeigt Treffer immer (ab 1.1.12). Im Kopf der Titelspalte steht grau „alle DLC aufklappen · zuklappen“ (`.dlcall`, nur gruppiert und wenn DLC da sind, ab 1.1.14). Eingerückte DLC (`tr.sub`) stehen in normaler Schrift, Spiele und Kopfzeilen fett (ab 1.1.15); flach sortiert bleibt der DLC-Name fett.
„ohne DLC“ (ab 1.1.8, Kästchen hinter den Urteilsfiltern, `S.noDlc`, gemerkt in `ek.view`): Liste und
Tabelle nur mit Spielen, Kopfzeilen nur mit DLC fallen mit weg, die Zahlen der Filter zählen nur
Spiele; darunter `.restline` „n DLC ausgeblendet · zeigen“ (`noDlcLine`), nichts verschwindet still.
Spaltenbreiten (ab 1.1.1): Titel bis 380 px, das Urteil (`td.vdc`) etwa 170 px und bricht seine
kleine Zeile („nicht im Plan: …“) um, damit Titel seltener umbrechen. Die kleine Zeile unter dem
Einkaufspreis bleibt einzeilig.

Laden (ab 0.77): Die Seite zeichnet, sobald `/api/state` da ist; Länderpläne, Korb und Kaufplan holt
sie danach und zeichnet noch einmal. Ab 0.99 in einer Anfrage (`POST /api/plaene`, `loadPlans`): ein
Datenstand und ein Zwischenspeicher (`planner.shared_contexts`) für alle drei, und nach einer Änderung
speichert dieselbe Anfrage die Auswahl vorher (`ui`). Drei gleichzeitige Anfragen bremsten sich im
Server gegenseitig. Große Antworten kommen gepackt (gzip). Gemessen mit echten Daten: Seite bis
fertig 1,7 s → 0,9 s, Neurechnen nach × 1,6 s → 0,4 s.

## Sammlung: unentschiedene DLC

Fehlt ein DLC, steht er nicht auf der Wishlist und ist nicht ignoriert (ab 0.72): violetter Rand links
an der Zeile (`.cdr.undec`) und Chip „nicht auf der Wishlist“ (`.chip.und`, violett auf `--warn-bg`).
Ein fehlender Pass, dessen Teile nicht alle einzeln einen Preis haben, zeigt statt „einzeln … · als Pass …“ grau
„einzeln nicht alle kaufbar“ (ab 0.90). „Titel dazunehmen …“ bietet diese DLC in der Gruppe „Fehlende DLC deiner Spiele“ an („Spiel: DLC ·
Preis“).
Die Aktionen einer DLC-Zeile („habe ich · ignorieren“) stehen rechtsbündig, bündig unter „alle DLC
ignorieren“ in der Kopfzeile des Spiels (ab 1.1.7, seit 1.3.1 durch `display:flex` verloren, ab 1.7.5 wieder
mit `justify-content:flex-end`); am Handy links in eigener Zeile.

Ab 0.99.6 nach der Checkliste (Entscheidung 20.10.2026): je DLC eine Rasterzeile wie unter „Nicht im
Plan“ (`.npr.cdr`, `collDlc`), Spalten Name (darunter klein Pass-Vergleich oder Paket), Stand („fehlt“
violett, Urteil-Pill auf der Wishlist, ab 1.0.1 als Link zu den Einzelheiten in der Wishlist statt
eines eigenen Links „Einzelheiten“, damit „habe ich · ignorieren“ immer an derselben Stelle stehen, „✓ hast du“ grau, „ignoriert“ rot), Preis als Link zu
DekuDeals für das Land, Rabatt, Land, bis, Handlungen mit „·“. Teile eines Passes stehen mit „↳“
eingerückt unter ihm (`.cdr.part`, `collBlocks`). Je Spiel mit offenen DLC ein klappbarer Kasten
(`details.cgo`, von Haus aus offen, gemerkt wird das Zuklappen); oben das Offene, darunter
eingeklappt „x vorhanden“, „x ignoriert“, „x nicht mehr erhältlich“ (`details.cgs`). „alle aufklappen
· alle zuklappen“ in der Werkzeugzeile gilt für diese Kästen (`data-scope="#collopen"`). Am Handy
brechen die Zeilen um wie unter „Wartet“.

## Sammlung: Ansicht „Spiele“

Ab 1.6.1 (Entscheidung 26.10.2026: Umschalter statt eigener Reiter, Name „Spiele“, erst einmal alle
Angaben zeigen). Umschalter `collSeg` „DLC | Spiele“, gemerkt je Browser (`S.cview`, `ek.view`). Ab 1.6.2
steht er in beiden Ansichten in derselben Kopfzeile `collTop` (`.ctop`) ganz oben, damit er beim Wechseln
nicht springt; links daneben „95 Spiele (119 Einträge bei DekuDeals, davon 30 DLC, 6 Spiele nur in
Paketen)“. Der Kasten der DLC-Ansicht nennt deshalb nicht mehr „119 Spiele in der Sammlung“ (das waren
Einträge samt DLC). Ab 1.7.3 hat die DLC-Ansicht keinen eigenen Kasten mehr: Die Zeile „90 Spiele (…)“ ist
die Kopfzeile einer Klappe (`details.cfold`, `data-kc="ctop"`, offen als Vorgabe; ab 1.7.5 in beiden
Ansichten gleich, damit die Zeile nicht springt; Pfeil ▾/▸ davor als eigenes Zeichen, 1.7.5 kurz dahinter), darunter die
Zahlen (`collStats`: mit DLC, ohne DLC, fehlen, Preis, im Angebot; ab 1.7.4 farbig: „mit offenen“ und „DLC
fehlen“ violett, „ohne“ und ab 1.7.5 „ohne DLC“ grün, „im Angebot“ blau; Schrift 13 px wie die Kopfzeile).
„So funktioniert die Sammlung“ nur in der DLC-Ansicht und „So funktioniert die Sammlung“. Code in `js/spiele.js`
(`viewGames`), Daten aus `state.spiele` (`planner.game_infos`).

- **Werkzeugzeile:** eigenes Suchfeld `#gq` (Name, Genre, Verlag, Entwickler; `fold1` wie `hits`),
  Sortieren (Name, Wertung, Spielzeit kurz zuerst, Erscheinen neu zuerst, Spieler, Zufall mit „Neu
  mischen“; „zuletzt gekauft“ entfiel in 1.7.0, zu wenige Kaufdaten). Sortiert ein Spaltenkopf, zeigt
  das Menü „nach Spalte“; eine Wahl im Menü, eine Mischung oder „alle Filter zurücksetzen“ hebt die
  Spaltensortierung auf.
- **Mischungen** als Zeile von `.fb`-Knöpfen, am Handy seitlich wischbar (`.chips.gmix`): Überrasch mich,
  Couch-Abend, Koop zu zweit, Große Runde, Online mit Freunden, Kurz und gut, Für unterwegs. Ein Klick
  setzt Filter und Sortierung, ein zweiter nimmt sie zurück. „Überrasch mich“ zeigt einen Kasten
  „Vorschlag“ mit drei Spielen (gewichtet nach Wertung), „Noch mal“ und „Schließen“.
- **Filter:** System (alle, Switch 2, nur Switch), Genre und Spielweise als Menüs mit Häkchen
  (`details.gmenu`, eine Zahl je Eintrag: Treffer unter den übrigen Filtern; offen bleibt das Menü beim
  Anhaken, `S.gMenu`; am Handy über die ganze Breite), Spieler ab n, Wertung ab, Spielzeit, USK (ab 1.7.6: bis 0, 6, 12 oder 16; ohne USK zählt PEGI, ohne Angabe
  fällt das Spiel heraus). Gesetzte
  Genres und Spielweisen stehen darunter als Knöpfe mit ×, dazu klein und grau „alle Filter
  zurücksetzen“ (`.gres`, ab 1.7.3). Alle Filter
  stehen in der Adresse (`#spiele?…`, `gHash`), nur solange die Ansicht offen ist.
- **Raster** `.gr` (ab 1.7.0, Entscheidung 27.10.2026): jede Zeile einzeilig und gleich hoch. Spalten
  (ab 1.7.3) Spiel (breiteste Spalte, 1,5 Teile gegen 1 Teil Genre, normale Schrift in Textfarbe, zu
  lang mit „…“, voller Name im Tooltip; fett nur, solange die Einzelheiten offen sind) · Spieler
  (Konsole | Lokal | Online unter einem gemeinsamen Kopf `.gh-sp`) · Koop · Metacritic · Spielzeit ·
  Genre · Jahr (ab 1.7.4 Spielzeit vor Genre, trennt die bunten Genres von der bunten Wertung; Breiten
  in `--gcols`, die Einzelheiten nutzen dasselbe Raster). Die Köpfe sortieren per Klick (`gTh`, wie `sth`, `S.sorts.spiele`); Spieler, Koop,
  Metacritic und Jahr zuerst absteigend (`data-d0="-1"`). Spieler sortieren nach der Höchstzahl, bei
  gleicher die kleinere Mindestzahl zuerst (1–8 vor 4–8, `gPlKey`). Leere Zellen: grauer Strich `G_NIL`.
- **Marken am Namen** im Stil von DE✓ (`.lgt.de`): „Switch 2“ oder „S2-Upgrade“ (Upgrade-Paket in der
  Sammlung; die Switch 2 Edition steht schon im Namen), „ohne Handheld“ oder „nur TV, Tisch“, wenn nicht
  alle drei Spielmodi gehen, Tooltip nennt beide Seiten. Dahinter klein grau „aus: …“, ab 1.7.3 nur
  der Unterschied zum Spielnamen („Ultimate Edition“, „Snipperclips Plus“, `gPackShort`), Pakete mit
  „+“ oder „&“ ganz; kürzt sich vor dem Namen.
- **Genre** als Blasen (`.gtags .chip.gg`), ab 1.7.3 alle und farbig: Farbton je Genre (`G_HUE`) nach
  Verwandtschaft, Action und Kampf rot, Tempo (Arcade, Rennen, Sport) orange bis gelbgrün, Plattformer
  gelb, ruhiges Leben (Simulation, Tiere, Alltag) grün, Erkunden (Abenteuer, Rollenspiel) türkis bis
  cyan, Denken (Puzzle, Strategie, Brett, Karten, Lernen) blau bis indigo, Gesellig (Party, Musik,
  Kommunikation) rosa bis magenta, Sonstiges und Unbekanntes grau. Violett bleibt frei (Widerspruch).
  Sanft: heller Grund, dunkle Schrift; im Dunkeln umgekehrt (Tokens `--gg-*`). Feste
  Reihenfolge in jeder Zeile: das seltenere Genre zuerst, gleich häufige nach dem Alphabet, „Sonstiges“
  zuletzt (`planner.game_infos`). Nintendo Europa zuerst, ohne Nintendo-Angabe DekuDeals, ohne Marke.
- **Metacritic** ab 1.7.3 fein gestuft von Rot über Gelb nach Grün (`.gsc`, `gScoreHue`, Farbton 0 bis
  125 für Wertungen 50 bis 95, Tokens `--sc-*`), halbfett. Fehlt Metacritic, steht OpenCritic grau und kursiv (`.galt`), der Tooltip
  sagt es. Filter, Sortierung und „Kurz und gut“ nehmen denselben Wert.
- **Pakete** (Entscheidung 27.10.2026, Variante a): Ein Paket der Sammlung, dessen Teile Spiele sind,
  steht nicht als eigene Zeile da. Jedes Spiel daraus trägt „aus: …“; fehlt eine Angabe auf seiner
  Seite, kommt sie von der Seite des Pakets („Angaben teils vom Paket“ in den Einzelheiten, Tooltip
  nennt welche). Oben: „90 Spiele (119 Einträge bei DekuDeals, davon 30 DLC und 5 Pakete mit 6 Spielen)“.
- Am Handy brechen die Zeilen um, jede Angabe mit kleinem grauem Namen davor, leere fallen weg. Noch
  nicht gelesene Spiele: Genre „folgt“.
- **Herkunft:** 1.6.1 setzte „≈“ hinter jede Angabe aus nur einer Quelle; ab 1.6.2 kein Zeichen mehr
  (Entscheidung 27.10.2026: „≈ ungern dauerhaft“). DekuDeals gilt, nennt Nintendo etwas anderes, ist
  der Wert dezent violett (`.gxc`, `gVal`), der Tooltip nennt beide. Koop „ja“ bis IGDB nur aus einer
  Koop-Spielzeit bei HowLongToBeat.
- **Vollständig:** alle Spiele auf einmal, kein „weitere zeigen“ (Entscheidung 27.10.2026).
- **Aufklappen** (ab 1.7.6): Reichen die Einzelheiten unter den Fensterrand, rückt die Seite nach; wer ganz
  unten war, bleibt beim Zuklappen unten.
- **Einzelheiten** (`gDetail`, ab 1.7.0, ab 1.7.3 wieder untereinander, Entscheidung 27.10.2026): links
  die Fakten als Name und Wert (`.gdf`, Spalte Spiel), Mein Stand (`.gdm`) ab 1.7.4 unter den mittleren
  Spalten ab den Spielern, darunter klein der Rest. Offene Zeile und Einzelheiten liegen ab 1.7.4 auf
  abgesetztem Grund, ab 1.7.5 dunkler als die Liste (`--open`, ab 1.7.7 im Dunkeln der Seitengrund `--bg`, im Hellen zwischen Liste und Seitengrund;
  `--best` war im Dunkeln heller). Knöpfe von Mein Stand auf Kartengrund, gewählt mit leichtem Grau statt
  Akzent und nicht fett (sonst wächst der Knopf), damit die farbigen Symbole sichtbar bleiben. USK 16 blau, USK 18 rot (ab
  1.7.5, `.usk16`, `.usk18`, wie die Farben der USK). Wertungen in denselben Farben wie die Tabelle (`.gsc`, Nutzer mal
  zehn). Mit Upgrade-Paket ab 1.7.11 nur noch in der kleinen Zeile „Angaben der Switch-2-Edition“ (Link),
  was die Switch-1-Seite anders nennt, im Tooltip (1.7.4 bis 1.7.10 als erste Zeile, Entscheidung 27.10.2026:
  zu prominent). Unter Mein Stand die Kurzbeschreibung von Nintendo Europa (ab 1.7.11, `.gdesc`, höchstens
  68 Zeichen breit, vier Zeilen, ein Klick zeigt alles, `S.gDesc`; ohne deutsche die englische, Tooltip sagt es). Wertung (ab 1.7.9, Entscheidung 27.10.2026): Metacritic geht immer vor (Edition, sonst
  Switch-1-Seite), OpenCritic nur ohne Metacritic, das der Edition zuerst.
  Reihenfolge: Wertung (Metacritic fett, Nutzer, OpenCritic), Spielzeit („Story“, „mit
  Nebenaufgaben“, „insgesamt“, „Koop“ …), DLC mit den Farben der DLC-Ansicht (`collSum`: grün vorhanden,
  violett fehlt, rot ignoriert) und „zu den DLC“, Erschienen (Tooltip: Entwickler und Verlag), USK (nur
  die Zahl, PEGI im Tooltip; ohne USK „PEGI n“). Spieler nur, wenn Nintendo andere Zahlen nennt; „Online
  mit Mitgliedschaft“, wenn Nintendo das sagt. Darunter eine kleine graue Zeile: Größe, Kaufdatum,
  Paket, Link zu DekuDeals und ob Nintendo geprüft hat. Spielmodi stehen nicht mehr da (nur die Marke am
  Namen bei Abweichung).
- **Mein Stand** (ab 1.7.1): in den Einzelheiten, `.seg.gmark` „○ Backlog | ▷ angefangen |
  ✓ durchgespielt“ (Klick auf den gewählten nimmt ihn zurück) und daneben als zweite Gruppe gleicher Höhe
  „☆ Favorit“ (an: „★“). Ab 1.7.4 farbig, in Knöpfen und Zeile gleich (`.gst`, `.gfav`): ○ rot (`--stop`),
  ▷ blau und nicht gefüllt (`--deal`), ✓ grün, ★ gelb (Gold); ○ und ▷ ab 1.7.5 höher (in Knöpfen 1,5 px), sonst hängen sie durch. Hinter dem Titel ab 1.7.7 in einem
  Kasten fester Höhe (14 px), mittig zur Zeile statt an der Grundlinie, damit die Zeile nicht springt, auch
  wenn eine Ersatzschrift die Zeichen größer zeichnet; ✓ und ★ dort etwas größer (15 px); ab 1.7.6
  mit feiner Kontur kräftiger (`-webkit-text-stroke`, fett ändert diese Zeichen kaum). In der Zeile hinter dem Namen nur, was
  gesetzt ist (`.gme`), Tooltip sagt es. Filter „Mein Stand“ (egal, nicht durchgespielt, Backlog, angefangen,
  durchgespielt, Favoriten, ohne Stand), Mischung „Aus dem Backlog“. Gespeichert in den Einstellungen
  (`game_marks`), damit in der Sicherung; die Oberfläche zeigt den Klick sofort und speichert dann.
- **Sprachen** (ab 1.7.1, Nintendo Europa): markiert wird nur die Ausnahme, „ohne Deutsch“ (`.lgt.no`)
  hinter dem Namen; in den Einzelheiten klein „Deutsch und n weitere Sprachen“, alle im Tooltip.
- **Koop** (ab 1.7.2): von IGDB „lokal“, „online“ oder „beides“, Höchstzahl und geteilter Bildschirm im
  Tooltip (`gCoop`, `gCoopTip`) und in den Einzelheiten; ohne IGDB „ja“, nur als Hinweis von
  HowLongToBeat. Spielweisen „Koop an einer Konsole“ und „Koop online“ nur mit IGDB.
- **GameShare** (ab 1.7.2): Marke „GameShare“ (ab 1.7.4 `.lgt.gsh`, ab 1.7.5 ohne Rand: blaue Schrift auf leichtem blauem Hauch) hinter dem Namen, Tooltip lokal und/oder
  online; Spielweise „GameShare“; in den Einzelheiten. Quelle ist Nintendos Liste der hervorgehobenen
  Spiele, fehlt die Marke, heißt das nicht „kein GameShare“.
- **Widersprüche** (ab 1.7.2, `contraBox` in Einstellungen, Quellen und Abgleich, unter „Zustand der
  Quellen“): klappbar, Zahl offen violett (`.warnc`), „keine offen“ grün, „Liste kopieren“; Tabelle
  Spiel, Angabe, DekuDeals, Nintendo (violett). Geklärte Fälle stehen in `app/klarstellungen.json`.
- **Mitgliedschaft:** Sagt Nintendo, das Online-Spiel braucht sie, steht es im Tooltip der Spalte
  Online und in den Einzelheiten („Online: mit Mitgliedschaft“).

## Rest füllen (Kaufplan)

„Passt dazu“ (Plan-Schritt, Länderkarte, Korb): „+ Titel **spart x €**“ rechnet mit heutigen Preisen;
dahinter klein grün „am Bestpreis“ oder rot „+x € über Bestpreis“ (`fillBest`, Preis hier gegen
Bestpreis der letzten 24 Monate, ab 0.77). Der Tooltip (`fillTip`) nennt beide Beträge. Ab 0.77.1
schlägt der Planer nur Titel vor, die höchstens „gut“ über ihrem Bestpreis liegen (`_fillers`, `ctx.grade`).

„Genau Null für **x €** mehr (statt y Rest)“ und „Fast Null für **x €** mehr (Rest z statt y)“
(ab 1.1.0, `zeroHtml`, Daten `p.fill_zero`): nur bei Rest in einem Land, wo er stört (verfällt beim
nächsten Wechsel, Stufe schwer, „Rest blockiert“). Ab 1.1.1 klappbar wie „Rechnung“ (`details.zero`,
`data-k`, zu als Vorgabe), Kopfzeile ohne Doppelpunkt in einer Größe, nur der Betrag fett. „statt y
Rest“: verfällt er im Plan, sein Wert in Euro (`rest_lost`), sonst der Rest in Landeswährung; der
Rest z bei „Fast Null“ in derselben Einheit, zum selben Kurs (ab 1.1.2). Die Beträge in Landeswährung
und die Karten nennt der Tooltip der Kopfzeile (ab 1.1.6) und von „alle dazunehmen“.
Aufgeklappt „n Titel:“ mit DLC-Marke und Preis als Link (`shopLink`), dahinter klein „n von m am
Bestpreis, zusammen **+x €** über Bestpreis“ (nur der Betrag rot) und der Knopf „alle dazunehmen“
(Schritt `planfill`, Länderkarte `add`). Ohne Zuzahlung steht „ohne Zuzahlung“ fett. Gibt es keinen
Weg auf genau Null, sagt eine graue Zeile das („mit deiner Wishlist und den DLC deiner Spiele kein
Weg“). Fast Null ohne Zuzahlung fehlt, das zeigt schon „Passt in den Rest“.

„Passt in den Rest (Betrag):“ zeigt höchstens vier Knöpfe, der kleinste verbleibende Rest zuerst:
einzelne Titel und Paare („+ A + B“, ein Klick nimmt beide), dazu die passende Mitgliedschaft.
Alles Weitere von der Wishlist im Auswahlfeld „alles, was passt (n) …“ mit „bleiben x“. Fehlende DLC,
die nicht auf der Wishlist stehen, folgen als höchstens zwei Knöpfe („+ DLC-Marke Name · Preis“; ab
0.99.4 steht die Marke wie überall vor dem Namen, auch bei DLC von der Wishlist), alle
übrigen im selben Auswahlfeld „alles, was passt (n) …“, das ab 0.78 zwei Gruppen hat (`optgroup`
„Wishlist“ und „DLC deiner Spiele, nicht auf der Wishlist“, nach Spiel sortiert). Alle Auswahlfelder
haben dieselbe Kartenfarbe und denselben feinen Rahmen (globales `select`, ab 0.78). Kostenloses
fehlt (ab 0.70). Preise in Auswahlfeldern „Titel dazunehmen …“ immer mit Währungszeichen (ab 0.70).

Kleinkram (ab 0.92, Entscheidung 19.10.2026): Titel mit Bestpreis unter `deal_eur.mini` (2 €)
machen keine Karte größer. Ab 0.98 (Entscheidung 20.10.2026) kommen sie nie von selbst in einen
Schritt: Lässt ein Schritt Rest, stehen sie unter „Passt in den Rest“ zur Auswahl; sonst unter
„Wartet“ mit dem Grund „Kleinkram unter 2,00 €: kommt über „Passt in den Rest“ dazu“ und „dazunehmen …“
je Titel (Felder `small` und `small_groups`; ab 1.4.0 ohne eigene Gruppe, Entscheidung 26.10.2026: Regel
bleibt, nur als Grund). Füllt er in einem Land eine Karte bis auf höchstens 10 %, steht oben in „Wartet“
eine Zeile „Kleinkram in Land: n Titel, zusammen …“ mit grün „reicht für eine eigene Karte“ und Knopf
„alle dazunehmen“ (ohne Schritt: „in die Länderkarte“). Die Grenze steht
in Einstellungen, Regeln („Kleinkram unter … €“), im Regelsatz darüber und in der Legende bei „kaufen“.

## Kopfleiste

Kopf und Reiter kommen beim Scrollen mit. Erst nach 300 px weiter nach unten blenden sie sich
aus, 40 px nach oben oder nahe am Seitenanfang zeigen sie sich wieder; Zittern unter 8 px zählt
nicht. Die Bewegung dauert 0,8 s, sanft an- und auslaufend, bei „Bewegung reduzieren“ springt sie.
Tabellenköpfe und die Sprungleiste halten über `--stick` Abstand und gleiten im selben Takt mit.
Kein `will-change` an der Leiste, sonst zeichnen Browser den Text dünner.

Titel-Tabelle (ab 0.56.3) und Korb (ab 0.61), breiter als 700 px, Klasse `.fitbox`: Die Seite ist genau fensterhoch (`body.fit`), es
scrollt nur die Tabelle. Ihr Scrollen steuert die Leiste. Ausgeblendet klappt die Leiste weg
(negativer Rand statt Verschieben), und die Tabelle wächst im selben Takt um ihre Höhe. So bleibt
kein leerer Streifen, und die zurückkehrende Leiste verdeckt nie die Filterzeile. Die zweite
Kopfzeile sitzt an der gemessenen Höhe der ersten (`--grp`), ohne Spalt.

Name oben links 23 px, „Aktualisieren“ 14 px, damit der Name sich vom Menü abhebt.

Hinweise über den Ansichten (`.banner`, `banners()`), in dieser Reihenfolge: fehlender
Wishlist-Link oder noch kein Abgleich, „**Notbetrieb:**“ (ab 0.84, `S.state.fallback`: DekuDeals
gesperrt bis Datum und Uhrzeit, nicht lesbar mit Fehler oder Wishlist länger als drei Tage nicht
gelesen; nennt das Datum der Listen und dass Preise, Kurse und Kartenpreise aktuell sind),
Selbstprüfung, fehlgeschlagener Abgleich. Jeder mit „Protokoll öffnen“.

## Lesezeichen

- Ein Lesezeichen erscheint als Knopf zum Ziehen mit durchgezogenem Rahmen (⠿ Name) mit „Code kopieren“
  daneben und „So legst du es an“ eingeklappt darunter.
- Länderliste im aufgeklappten Titel: ★ steht direkt vor den Angaben des Landes, ? vor dem Grund,
  warum ein Land nicht zählt; keine eigene Spalte dafür.
- Hauptweg zurück ist „Im eShop-Kompass übernehmen“; Textfelder zum Kopieren und Einfügen
  stehen eingeklappt unter „Geht das nicht?“.
- Hin zum Lesezeichen gehen Daten über den Link, sonst über ein kleines Fenster des Tools, das
  sie per postMessage übergibt und sich schließt (JP-Lesezeichen ab 0.58). Die Zwischenablage ist
  nur noch Rückfall, denn Browser lassen sie aus einem Lesezeichen kaum lesen.
- Namen der Lesezeichen bleiben stabil, ohne Versionsnummer. Ein veraltetes Lesezeichen meldet
  sich beim Übernehmen und mit einem violetten Satz am Knopf; daneben ein kleiner Knopf
  „Neu angelegt ✓“, der den Hinweis ausblendet.

## Farben

| Bedeutung | Token | Klassen | Wofür, Beispiele |
|---|---|---|---|
| Bestpreis | `--gold`, `--gold-ink` | `.ok`, `.star` (★), `td.champ` (Umrandung), `.pct.m-best` | nur der Bestpreis: ★ am Bestpreis, goldene Umrandung des Bestpreis-Landes, "Bestpreis" in Texten. Nie für anderes Lob |
| Urteil und positiv | `--go`, `--go-bg`, `--go-fill`, `--on-go`, `--go-mark` | `.vd.buy`/`td.c-buy` (Füllung "kaufen"), `.vd.good`/`td.c-good` (hell "gut"), `.g-buy` (fett), `.g-good` (normal), `.gn` | Urteil "kaufen"/"gut", Ersparnis, vollständig, gute Kartenbewertung (Top, gut, günstiger). „am Bestpreis“ bei Körben: fett, wenn jeder Titel „kaufen“ ist, normal, wenn die Summe am Bestpreis liegt, aber ein Titel nur „gut“ ist |
| Rabatt | `--deal` | `.pct` | Rabatt im Shop (−x %), immer dezent blau, auch in Tabellen |
| Prüfen, Hinweis (violett; bis 0.57 Bernstein, kaum vom Gold zu unterscheiden) | `--warn`, `--warn-bg` | `.warnc`, `.chip.w`, `.q` (?), `.approx` (≈), `.soon`, `.today`, `.dlc.need` | Sprache ungeprüft, zählt nicht, Schätzung, endet bald, DLC ohne Hauptspiel, Kartenbewertung "teuer" |
| Nein, teurer | `--stop`, `--stop-bg`, `--sale` | `.bad`, `.abv`, `.over`, `.lgt.no`, `.save.neg` | ohne Deutsch, Wechsel lohnt nicht, über dem Bestpreis (+x €), ignorierte Anzahl, Guthabenkarte teurer als Kreditkarte (Faktor und Bewertung) |
| Neutral | `--muted`, `--chip`, `--line` | `.mut`, `.chip`, `.dlc`, `.lgt.de`, `.pct.np` | Beschriftungen, Normalpreis, "DLC"-Etikett (immer grau), "Deutsch ✓" |
| Marke | `--brand` | `h1 .brand`, `nav button.on` | „eShop“ im Namen oben links, Nintendo-Rot, und ab 1.7.5 die Unterstreichung des aktiven Reiters (wie im VR-Navigator, Entscheidung 27.10.2026). Sonst nirgends, damit Rot weiter „nein“ heißt |
| Gewählt, hervorgehoben | `--accent` | `button.primary`, `.seg button.on`, `.fb.on`, `.kb.on` | Hauptknopf und gewählter Knopf, alle gleich hell (ab 1.7.5; `.fb.on` war in Textfarbe und blendete im Dunkeln, etwa „alle 119“). `.fb.on` nicht fett, sonst springt die Zeile |
| Betonung ohne Wertung | `--accent` | `.lvl-neg`, `.pct.m-low` | Kurs-/Preisniveau unter 1 bzw. günstiger, ohne Urteil |

## Marken und Zeichen

- ★ (gold): Einkaufspreis erreicht den Bestpreis (24 Monate, zählende Länder).
- ≈ (violett): geschätzter Wert, etwa Guthaben ohne gelesenen Kartenpreis. Geschätzte
  Werte entscheiden nichts und sind immer so gekennzeichnet.
- ? (violett): zählt nicht, weil Sprache ungeprüft oder ohne Guthabenkarte.
- "ca." vor Beträgen: geschätzt oder aus anderen Angaben errechnet (etwa Pass-Preis), so auch in der Legende.
- ✱ (blau, `.cb`, ab 0.99.4 nicht mehr gold): mit Cashback des Kartenshops wäre es der Bestpreis.
- Preise sind überall Links in den eShop des Lands (`shopLink`, ab 0.99.4 auch in der Tabelle), ohne
  eShop-Seite zum Verlauf bei DekuDeals.
- Titel, die du mit × aus einem Schritt genommen hast, tragen unter „Wartet“ den Grund „von dir
  aus Land genommen“ mit „zurück“ (`waitBox`).
- Nicht zählende Zeilen sind blass (`opacity`), nicht farbig.
- Violett: Angabe aus titledb, nicht von Nintendo (bis 0.81.1 zusätzlich gepunktet unterstrichen).
- „am Bestpreis“ (grün) an einem Schritt oder Land steht nur, wenn jeder Titel darin am
  Bestpreis ist; sonst der rote Betrag darüber (ab 0.65). So widersprechen sich Kopfzeile und
  rotes „+x“ einer Zeile nie.
- DLC mit gekürztem Namen tragen in den Tabellen der Plan-Schritte und Länderkarten und in Käufen
  das Hauptspiel klein und grau darüber (`small.gm`, ab 0.65), damit „Pixel Pack“ nicht allein
  steht. In Schritt und Länderkarte steht ab 1.1.4 das Spiel immer in der ersten Zeile (mit DLC-Marke),
  der DLC-Name in der zweiten. Überall sonst (Korb, „Wartet“, „Gekauft“, Herausgenommen) steht der volle Name in normaler Größe
  mit DLC-Marke davor (Checkliste, Punkt 1). In der Wishlist-Liste nicht: Dort stehen DLC immer unter einer Kopfzeile mit dem Namen
  des Spiels, auch ein einzelner DLC (ab 0.77).
- Links sind ruhig in der Textfarbe (`a` mit `--accent`), nie browser-blau: Blau heißt Rabatt.

## Vergleiche

- Ersparnis wird gegen den nächstbesten zählenden Preis genannt, wie bei der
  Kaufentscheidung. Deutschland erscheint nur als Information ("in Deutschland jetzt").
- Abstand zum Bestpreis: `+x €` rot, am Bestpreis ★. In der Liste aller Länder eines Titels
  ist nur der Betrag rot, „über Bestpreis“ grau.
- Landestief (Tiefstpreis eines Landes) ist nur Auskunft und immer grau; entschieden wird am
  Bestpreis aller zählenden Länder.
- Faktor einer Guthabenkarte trägt die Farbe ihrer Bewertung. Dieselben Regeln gelten für jedes
  Land, auch neu hinzugefügte. Grau heißt: noch keine Bewertung möglich (etwa „Bewertung ab …“,
  solange der eigene Verlauf einer Karte kürzer als 14 Tage ist, oder Guthaben zum Kurs).

## Zahlen in Sätzen

Eingabefelder für Beträge und Prozente nehmen Komma und Punkt und zeigen das Komma („7,75“,
ab 0.65); sie sind Textfelder mit `inputmode="decimal"`, damit kein Browser „7.75“ zeigt.
Was überall gleich ist, steht nur einmal: Kostet ein Titel überall 0,00 €, zeigt die Titel-Tabelle
„kostenlos in allen 16 Ländern mit Preis“ statt lauter Nullen; hat er nirgends einen Preis, steht dort der Grund
(etwa „noch nicht erschienen“) statt einer Reihe aus „–“. Fehlende DLC, die nichts kosten, heißen
„kostenlos“, nicht „0,00 €“.

Nur die Zahl trägt die Farbe, Verbindungswörter bleiben grau. Sammlung je Spiel: eine Zahl je
Art, wie ein Satz aufgezählt und ohne Gesamtzahl („10 vorhanden und 7 ignoriert“, „3 vorhanden,
2 fehlen und 1 ignoriert“; die Gesamtzahl steht im Tooltip), damit nichts wie „17,7“ liest. Der
Betrag dahinter folgt mit „·“. Ist alles da, steht „5 von 5“ grün und
„vorhanden“ grau; sonst die Zahl vorhandener grün, fehlender violett, ignorierter rot (`collSum`;
Entscheidung 13.10.2026, Wortlaut ab 0.56.3, „fehlen“ violett auch bei offenen Spielen ab 0.99.6).
Die Zahlen hinter „Ohne offene DLC“ und „Ohne Zusatzinhalte“ sind grün, dort ist nichts offen (ab 1.0.2). Der Kopf der Sammlung steht als kompakter Kasten über den
Gruppen: Zahlen fett in zwei kurzen Zeilen, die Erklärung eingeklappt darunter. Filter und
Reihenfolge stehen direkt darunter, über den Spielen (ab 0.58).

## Flächen

Reiter (ab 0.61, „Titel“ heißt ab 0.72 „Wishlist“, intern weiter `titel`): Jetzt, Wishlist, Sammlung, Einstellungen, erst was ansteht, dann
Einkaufen, dann was du hast. Die Länderkarten sind ab 0.74 kein Reiter mehr (intern weiter `laender`):
„alle Länderkarten“ unter dem Kaufplan, „Länderkarte von … öffnen“ unter einem aufgeklappten Land
in „Andere Länder“ (`goland`, `S.landFocus`), oben „← Kaufplan“. Der Korb ist ab 0.73 kein Reiter mehr, sondern die dritte Ansicht der
Wishlist (`S.tview = "korb"`, `goKorb()`; ein gemerkter Reiter `korb` wird dorthin umgeleitet).
Am Knopf Korb steht grau die Zahl seiner Titel. In der Tabelle steht vor jedem Titel „+“ bzw. „✓“
(`.kb`, in den Korb oder heraus). Werkzeugzeile in jedem Reiter gleich: links Filter und Reihenfolge, rechts
der Ansichtsschalter (`.tools .seg`, Wishlist: Liste | Tabelle | Korb, Länder: Raster | Liste). Ansicht und
Reihenfolge merkt sich der Browser (`ek.view`, ab 0.65 auch für Länder), nie der Server.

Handy (ab 0.65): Die Reiterleiste scrollt seitlich und blendet am Rand weich aus, solange rechts
noch Reiter folgen (`nav.more`). Formulare, Vorschläge „Passt in den Rest“ und die Tabellen der
Mitgliedschaft brechen um oder scrollen in sich; die Seite selbst scrollt nie seitlich (geprüft bei 390 px).
Ab 0.75 sind die Titel eines Schritts und einer Länderkarte unter 520 px kleine Karten statt
Tabellenzeilen (`.pc table.it` mit `display:flex`): oben der Name, darunter fett der Einkaufspreis,
der Abstand zum Bestpreis, dann grau beschriftet „bis“, „Shop“ und „sonst“ (`td[data-l]`).
Ohne Angebot fällt „normal“ weg; die Spaltenköpfe und damit das Sortieren gibt es dort nicht.
Ab 0.85 zeigt der Korb unter 641 px statt der Tabelle `korbPhone()` (`.kphone`, die Tabelle
`.cmp.fitbox` ist dort ausgeblendet): Auswahl des Landes (`S.korbLand`, nicht gemerkt, sonst das
günstigste; ohne eigene Beschriftung, ab 0.99.7, der Eintrag nennt das Land), Titel mit „×“ und derselben Preiszelle `twoLine`/`cellMarks`, darunter die Summen als
Zeilen; „Einkaufspreis“ ist eine Klappzeile mit der Rechnung aus `costTip()`, die sonst nur im
Tooltip steht. Sortieren gibt es dort nicht.

Karten ohne Lücken (ab 0.96): Schritte des Kaufplans und die Länderkarten in mehreren Spalten
(`.grid.masonry`) belegen je so viele 1-px-Zeilen, wie sie hoch sind (`masonry()`, `spanCard()` in
`grund.js`, nach jedem `render()`; ein ResizeObserver passt beim Auf- und Zuklappen an). Schritt 3 rückt
so unter den kürzeren der beiden ersten. „Wartet“ (`waitBox`, ab 1.4.0, Entscheidung 26.10.2026; vorher „Nicht im Plan“ mit sechs Gruppen, darin Länder,
darin Spiele) steht direkt unter den Schritten, vor „alle Länderkarten“ (`.np`, gemerkt unter `notplan`):
was du kaufen würdest, der Plan aber gerade nicht kauft. Jeder Titel genau einmal, nach Spiel (`npTitles`:
voller Name, zwei und mehr Titel eines Spiels unter klappbarer Spielzeile ohne Spielnamen), im Raster der
Kopfzeile (`npRow`, `.npr`; Spalten Titel, Urteil, Einkaufspreis, Rabatt, Land, über Bestpreis, bis,
Handlung). Darunter klein grau der Grund, mehrere mit „·“: „Wechsel nach Land [Stufe] lohnt nicht: spart
1,52 €, lohnt ab 20,00 € · Länderkarte“, „Kleinkram unter 2,00 €: kommt über „Passt in den Rest“ dazu“,
„Lieber warten: …“, „von dir aus Land genommen“ (mit „zurück“), „für Land übernommen …“ (mit „entfernen“),
„nur ein Weg zur Switch 2: …“, „steckt in …, das ebenfalls zum Kauf ansteht“, „nirgends kaufbar, wo es
zählt“. Oben Filterknöpfe nach Grund mit Zahl (`.fb` wie in der Wishlist, `waitf`, `S.wf` nur für die
Sitzung; erst ab zwei Gründen): Wechsel, Kleinkram, Lieber warten, von dir, sonst. Preis mit ★ als Link in
den eShop, bei DLC zu DekuDeals; Land als Link zum Preisverlauf. Handlung: Auswahl „dazunehmen …“ mit
„Schritt n, Land · Preis (+Aufpreis)“ (`npadd`), sonst grau „in keinem Schritt“, „zurück“ oder
„entfernen“. Am Handy je Titel eine kleine Karte. Zugeklappt nennt die Kopfzeile Titelzahl und Gründe
(„7 Titel: Wechsel 2 · Kleinkram 3 · von dir 4“; ein Titel mit zwei Gründen zählt bei beiden).

„Gekauft“ (`boughtBox`, ab 1.4.0, gemerkt unter `bought`): die letzten fünf Käufe als Raster (`.bk-grid`,
`.bkr`; Datum, Land, „n Titel ▾“, bezahlt mit Tooltip Spiele/Karten, grau „statt … in DE“, Rest in
Landeswährung), jede Zeile klappt die Titel auf (`details.bkf`, Namen als `titleBtn`), darunter „letzten
Kauf zurücknehmen“. Dann „Noch auf der Wishlist: n“ im Raster von „Wartet“, Grund grau: „im Kaufplan
als gekauft vermerkt“, „in deiner Sammlung“, „laut eShop-Kaufverlauf gekauft“, „steckt in …, das du
schon hast“; Handlung „bei DekuDeals“. Zugeklappt: „n Käufe, insgesamt x € unter dem deutschen Preis ·
m noch auf der Wishlist“. Am Handy bricht eine Kaufzeile in zwei Zeilen um.

Nichts still im Hintergrund (ab 0.95, Entscheidung 20.10.2026): Was das Tool von selbst entscheidet,
steht sichtbar da. „Wartet“ (`waitBox`) nennt am Titel, warum der Plan ihn nicht kauft; was der Plan
in einem anderen Land kauft (`dropped[].moved`), steht ab 1.4.0 nicht mehr dort, sondern am Titel im Schritt
und unter „Andere Länder“. „Gekauft“ (`boughtBox`) nennt Besitz, der noch auf der Wishlist steht, mit Quelle
(`bought_how`: im Kaufplan vermerkt, Sammlung, eShop-Kaufverlauf, „steckt in …, das du schon hast“;
ebenso `planState` in der Wishlist) und übernommene Füllartikel ohne Schritt (`fill_idle`, „übernommen,
gerade nicht im Plan“ mit ×). Alte Preise eines Lands (`price_stale`, `price_at`): oben im Kaufplan
„Preise nicht aktuell: Land vom …“ mit Link ins Protokoll, an Schritt und Länderkarte `.warnc` „Preise
vom …“ (`hurdles`). Ein Urteil ohne DekuDeals-Tiefstpreis trägt `.nohist` „ohne Verlauf“ (grau,
gestrichelt wie der Zielpreis) in der Wishlist neben dem Urteil, in den Einzelheiten und am
„am Bestpreis“ der Plan-Tabelle, dort ab 1.1.3 in einer eigenen Zeile darunter, damit „am Bestpreis“
mit den anderen Zeilen bündig bleibt. „gekauft“ nennt in der Rückfrage die Guthaben, die es auf 0 setzt.
„Zu erledigen“ und die Hürde am Schritt sagen nach Ursache „Guthabenkarte eintragen“, „keine Karte
vorrätig“ oder „kein Kartenpreis“ (`no_cards_warning`).

„Zu erledigen“ (Jetzt): je Eintrag ein fetter Kern („7 fehlende DLC kostenlos holen“), Einzelheiten
klein dahinter, lange Listen eingeklappt („welche“). Die Legende erklärt jedes Zeichen, das die
Oberfläche zeigt, auch Chips, „ca.“, die DLC-Marken, „Rest“, Sammlung „fehlt“, „nicht auf der Wishlist“
und „↳“ (ab 0.91 geprüft: Sprachmarken „DE✓“ und „andere Fassung“ wie in den Tabellen, beide „Wechsel“-Zeilen
zusammengelegt, alle Chips der Wishlist und des Korbs). Neue Chips oder Marken kommen im selben Commit in die Legende.
Auswahl „Konto steht in:“ (Jetzt und Einstellungen): nur Länder mit eigenem Shop, ohne
„Deutschland (Guthaben)“. Auf Jetzt stehen „Konto steht in:“ und „Guthaben dort:“ mit Doppelpunkt
und etwas Abstand nebeneinander, ohne „·“ dazwischen (ab 0.91).

DLC außerhalb Europas (ab 0.61 nach Programm-ID): Hat er dort eine eigene Fassung, steht hinter
dem Land das violette „DLC“-Kästchen (`.dlc.need`), in den Tabellen ein violetter Strich am linken
Zellrand (`td.needr`); ungeprüft ein gestricheltes graues „DLC?“ (`.dlc.open`); passt er, nichts.
Überall gleich: Kaufplan, Länder, Korb, Titelliste, Titel-Tabelle, Sammlung („14,12 € in Japan DLC?“).
Auswahlfelder hängen „(DLC)“ an den Titel.

Eigene Angebote für Titel (ab 0.62): Stammt ein Preis aus einem eigenen Angebot, steht die Quelle
als kleines graues Kästchen daneben (`.dlc.ownm`, etwa „Amazon“), überall wo Preise stehen; der
Preis verlinkt den Händler, der Tooltip nennt Code-Preis, Kreditkarte, Kurs und den eShop-Preis.
Eintragen und Entfernen in den Einzelheiten des Titels, Zeile „Eigene Angebote“: grün „zählt“,
grau „zählt nicht: der eShop ist dort günstiger“, mit Link dahinter der Prüfstand wie bei der Mitgliedschaft.

Werkzeugzeile, Reihenfolge in jedem Reiter: Suche, Sortierung, Filter; das Suchfeld hat ein eigenes
graues × (ab 0.62.1, `searchBox`, das × des Browsers ist ausgeblendet), Esc leert ebenso; rechts die Ansicht oder eine
Aktion (Korb leeren). Auswahlfelder „Titel dazunehmen …“ gruppieren nach Urteil, darin A–Z, zuletzt
die Online-Mitgliedschaft mit allen Varianten (ab 0.69; im Korb als Zeile mit Link zum Kasten, ohne Sprachmarke). Am Fuß eines Schritts ist das Feld mindestens 11em breit und bricht sonst in
eine eigene Zeile um, statt abgeschnitten zu werden (ab 0.99.7).
Sammlung: Der Filter ignoriert Akzente, Satzzeichen und Leerzeichen („pokemon“ findet „Pokémon“, ab 0.69)
und klappt „Ohne offene DLC“ und „Ohne Zusatzinhalte“ mit Treffern auf. In „Ohne offene DLC“ stehen
hinter der Erklärung klein „alle aufklappen · alle zuklappen“ für die Spiele darin (ab 0.91); sonst
gibt es keine lange Reihe gleicher Klappzeilen, deshalb nur dort.
Sprachen prüfen: „Geprüft: 94 von Nintendo gelesen, 6 laut titledb, 2 von dir bestätigt“, Zahlen von
Nintendo und von dir grün, laut titledb violett (ab 0.81; vorher „von dir“ violett). Dieselben Farben
in der Spalte der Tabelle darunter: „Deutsch ✓“ grün von Nintendo oder dir, violett laut titledb (ohne Punktlinie ab 0.81.2), „ohne Deutsch“ rot (bis 0.80 immer gold). Der Browser-Helfer für Japan zählt
Einträge und Seiten („6 Einträge ohne Angabe von Nintendo auf 2 Seiten“): DLC ohne eigene Seite
lesen die Seite ihres Spiels mit, die Liste nennt je Seite alle Titel. Dort gerade nicht Kaufbares steht eingeklappt und zählt nicht als offen.
Korb-Tabelle: Erklärung zugeklappt („So liest du den Korb“, ab 0.62.1), Spalte Bestpreis,
Länder von leicht über mittel bis schwer, darin nach fehlenden Titeln und Preis (ab 0.69, vorher
nur nach Preis), Vergleichsland vorn; Spaltenköpfe sortieren, Kopfzeile bleibt stehen und ist deckend: Länder ohne den ganzen Korb haben
grauen Kopftext, nur ihre Zellen sind blass (bis 0.62 schien die Tabelle durch den Kopf); grün hinterlegte Zellen
nicht, sonst trübt die Deckkraft ihre weiße Schrift (ab 0.68). Zwei Zeilen je Zelle (ab 0.70, vorher
eine): oben Preis | kleines rotes „+x“ über dem Bestpreis (`.kc`, Raster aus zwei gleichen Hälften, die
Fuge mittig, damit Preise und Abstände untereinander stehen; `.abv.gap`), darunter mittig blauer Rabatt,
Code-, DLC- und Sprachmarke (`.kl`); Zelle
dunkel-/hellgrün nach Urteil, gold umrandet am Bestpreis. Landeswährung, Zahlweg und Ende im Tooltip.
Die Zelle ist die Preiszelle (siehe unten), dieselbe wie in der Tabelle.
Der Stern im Korb gilt dem Preis im Korb, nicht dem Einzelpreis (ab 0.65; in Ländern ohne
eigenen Shop können beide abweichen).
Links zu DekuDeals: ohne Land (Titelnamen, Sammlung, Käufe) ohne `?country=`, dann gilt die bei DekuDeals
eingestellte Länderansicht; an einem Preis einer Länderspalte mit dem Land dieses Shops (ab 0.82.3).
Der Preis öffnet den eShop, bei DLC den Verlauf bei DekuDeals (kein fester eShop-Link für DLC). In der
Sammlung (ab 0.90) führt jeder DLC-Name zu DekuDeals ohne Land und der Preis „x € in Land“ zu DekuDeals für
dieses Land; der eigene Link „bei DekuDeals ansehen“ fiel weg.
Neu zeichnen (etwa Sortieren) lässt jede Tabelle an ihrer Scrollstelle. Das Menü Hell/Dunkel liegt
über der Sprungleiste der Einstellungen (Kopfleiste `z-index` 7).

Preiszelle (Tabelle und Korb, `twoLine`, `cellMarks`; ab 0.81 auch in der Tabelle, die bis dahin eine
Zeile ohne Abstand zum Bestpreis hatte): oben ★/≈/? und Preis | kleines rotes „+x“ über dem Bestpreis,
die Fuge mittig in der Spalte; darunter mittig blauer Rabatt „−60 %“ (mit Leerzeichen wie überall),
Händler-, DLC- und Sprachmarke. Auf dunkelgrüner Zelle („kaufen“) bleiben „+x“ rot und Rabatt blau, nicht fett.
Im hellen Thema stehen sie auf kleinem hellem Grund (`--go-mark` = `--card`), weil Rot und Blau auf
dem dunklen Grün sonst nicht lesbar sind; im dunklen Thema ist die Füllung hell genug, dort ohne
Grund (`--go-mark` transparent, ab 0.82.1). 0.81.0 nahm die weiße Schrift der Zelle und brach damit
die Farbregel. DLC-Marken ohne Violett („DLC“, „DLC?“) stehen dort in der Zellschrift (ab 0.99.7, vorher
grau auf dunkelgrün kaum lesbar); „braucht Hauptspiel“ behält Violett auf hellem Grund. Zellen oben ausgerichtet, Titelspalte 210 bis 260 px
breit, in beiden Ansichten gleich. Ab 1.2.0 bleibt neben ihr die Bestpreisspalte stehen (zweite Spalte
`position:sticky`, `left` aus `--c1`, der gemessenen Breite der Titelspalte, `stickCols`; nur ab 641 px).
Das rote „+x“ hat einen eigenen Tooltip (`gapTip`): „x € über dem Bestpreis y € in Land“, darunter
„Tiefstpreise der Länder, 24 Monate:“ je Land mit Landestief und Abstand, günstigste zuerst, höchstens
zehn; der Zell-Tooltip nennt den Abstand nicht mehr (vorher deckten sich Preis-, Zell- und Abstandstooltip
größtenteils). DLC-Namen stehen in Tabelle und Korb wie in der flachen Liste zweizeilig (`dlcLabel`). Eine Zeile mit Grund statt Zellen („noch nicht erschienen“) steht
links (bis 0.80 rechtsbündig und damit außerhalb des Bildes). Wo nur ein Land gezeigt wird (Plan-Schritt,
Länderkarte), stehen dieselben Angaben in eigenen Spalten (Einkaufspreis mit Rabatt, „über Bestpreis“), in
der Wishlist-Liste zweizeilig je Spalte.

Länder-Karten: Die Knöpfe „als Korb vergleichen“ und „Titel dazunehmen …“ stehen in einer Zeile, die
„Rechnung“ darunter in eigener Zeile; Aufklappen schiebt so nichts zur Seite (ab 0.58).

Einstellungen (Aufbau ab 1.5.0, nach dem VR-Navigator): wenige Karten (`.setc`) Länder, Regeln und
Gebühren, Sprachen prüfen, Käufe aus dem eShop, Quellen und Abgleich, Sicherung. Klappbar sind die Teile
darin, nicht die Karten; jede Klappzeile nennt zugeklappt das Nötigste. Die Sprungleiste trägt hinter
Länder (Kartenpreise älter als 30 Tage), Sprachen (offen), Käufe (nicht in der Sammlung, zuordnen,
nachtragen) und Quellen (mit Problem) eine violette Zahl (`.warnc`), wenn dort etwas offen ist; die
Werkzeuge bleiben in ihren Karten (Entscheidung 26.10.2026). Regeln und Gebühren stehen je als Satz,
die Felder in „Grenzen anpassen“ und „Gebühren anpassen“. „Quellen und Abgleich“: Klappen „DekuDeals“
(Links; offen, solange keine Wishlist eingetragen ist), „IGDB-Schlüssel für Spielinfos“ (`data-k`
igdbkey, ab 1.4.3: Kopf „eingetragen“ grün oder „keiner“, Passwortfelder ohne gespeicherten Wert),
„Zustand der Quellen“ (`data-k` srcstate, zu von Haus aus; Kopf „n ok, m mit Problem (…)“, Zahl ok
grün, Problem violett; Tabelle je Quelle mit Zustand, Zeit und Zeile aus dem Protokoll), dann
„☑ automatisch alle [6] Stunden“ (ab 1.7.4 wie im VR-Navigator: Häkchen `auto_sync`, schmales Zahlenfeld
`.numh`; ohne Häkchen zeigt die Kopfzeile „Abgleich nur von Hand“), „Aktualisieren“ (ab 1.5.2, wie der
Knopf oben, ab 1.7.4 so flach wie „Verbindung testen“, `.slimp`) und „Verbindung testen“, die Klappe „Verbindungstest“ (erst nach einem Test) und
„Protokoll des letzten Abgleichs · kopieren“ (offen von Haus aus, `data-kc` logbox). Ein Knopf in
einer Klappzeile schaltet die Klappe nicht um.
Kästen in einer Karte haben den Seitenhintergrund (`--bg`). Jede Klappe und jeder Kasten einer Karte
hat 10 px Abstand zum Inhalt darüber (`.setc details`, ab 0.78; nicht in Listen und Tabellen). Titel-Tabelle: Die Zahl der Bestpreise
steht neben dem Länderkürzel („JP 17★“), nicht darunter.

Kacheln und Kästen haben immer denselben Hintergrund (`--card`), auch die Länderkarten
(seit 0.53.6); Grün steht dort nur für „am Bestpreis“ in der Zeile Preis. Weniger Wichtiges wird über
gedämpften Text gezeigt, nie über Transparenz der ganzen Kachel.

## Eine Sache, mehrere Orte

Dieselbe Angabe steht in der Oberfläche oft an mehreren Stellen. Wer sie an einer Stelle ändert
oder ergänzt, geht diese Liste durch und ändert die anderen Stellen mit oder schreibt hierher,
warum eine Stelle anders bleibt. Funktionen in `app/static/js/*.js`.

| Was | Wo es vorkommt |
|---|---|
| Titelname mit DLC-Marke, Spiel grau zweizeilig davor (`dlcLabel`: flache Wishlist-Liste, Tabelle, Korb; gruppiert in der Liste ohne Spiel), Sprach- und Regionsmarke, eigenes Angebot | Wishlist-Liste (`titleRow`, `titleGroups`), Tabelle (`viewMatrix`), Korb (`viewCompare`, am Handy `korbPhone`), Plan-Schritt und Länderkarte (`planCard`), „Passt in den Rest“ und „Passt dazu“, Auswahl „Titel dazunehmen …“ (`wishOpts`, `extraOpts`, `nsoOpts`), Sammlung (`collGame`, `collDlc`), Käufe (`eshopBox`), „Wartet“ (`waitBox`), „Gekauft“ (`boughtBox`), Zu erledigen (`todos`) |
| Urteil ohne Verlauf (`nohist`) | Wishlist-Liste (`titleRow`), Einzelheiten, Plan-Tabelle („am Bestpreis“), Legende |
| Preis eines Titels: Einkaufspreis, ★, Rabatt, „ca.“, Abstand zum Bestpreis, Urteilsfarbe | Wishlist-Liste (`titleRow`), Tabelle und Korb (Preiszelle `twoLine`/`cellMarks` in `viewMatrix`, `viewCompare`, am Handy `korbPhone`), Plan-Schritt und Länderkarte (`planCard`, `priceLine`), Mitgliedschaft (`nsoPrice`), Verlauf (`drawVerlauf`), Legende (`openLegend`) |
| Summe eines Landes: Preis, Wechsel, Rest, Karten | Plan-Schritt und Länderkarte (`planCard`, `switchLine`, `restLine`, `billHtml`), Korb-Fußzeilen (`viewCompare`, am Handy `korbPhone`), Kopf des Kaufplans (`viewKauf`), „Andere Länder“ (`othersHtml`) |
| Titel dazunehmen, weglassen, „Passt dazu“, „Passt in den Rest“, „Genau Null“/„Fast Null“ | Plan-Schritt und Länderkarte gemeinsam in `suggestHtml` (Null-Zeilen `zeroHtml`), `xBtn`, `removedLine` (Schritt `planpick`, `planfill`, `planskip`; Länderkarte `pick`, `add`, `trim`, `drop`), Korb (`add`, Auswahl im Kopf, „In „Jetzt“ übernehmen“ `jetztBtn`), Erklärung `fillTip`, Abstand zum Bestpreis `fillBest`; Suchfeld vor jeder Auswahl `pickWrap` |
| Angenommener Preis (Was wäre, wenn) | Plan-Schritt (`planCard`, Zelle Einkaufspreis), „Wartet“ (`npRow`), Zeile oben (`assumedLine`), Legende (`openLegend`) |
| Angebotsende und Angebotsbeginn | Hinweise oben im Kaufplan (`saleNews`), Plan-Schritt (`endCell`), Tabelle mit „Details“, Tooltips in Tabelle und Korb, „Wartet“ und „Noch auf der Wishlist“ (`npRow`) |
| Suchfelder | `hits()` für Wishlist-Liste, Tabelle, Sammlung und „anderer …“ bei den Käufen; „Spiele“ eigenes Feld `#gq` mit `fold1` |
| Spielinfos (Genre, Spieler, Koop, Wertung, Spielzeit, violett bei Widerspruch, grau-kursiv OpenCritic) | Sammlung „Spiele“ (`gRow`, `gDetail`), Legende (`openLegend`), Widersprüche in den Einstellungen (`contraBox`); Daten nur aus `planner.game_infos` |
| Sortierbare Tabellen | `sth()` und `sortRows()`; neue Spalten bekommen beides, die README nennt die Tabellen unter „Sortieren“ |
| Zahlenzeilen in Klappzeilen | „Geprüft: …“ (`langSection`), Käufe (`eshopBox`), Sammlung (`collGame`): Zahl fett, violett, was dich braucht, grün, was erledigt ist |
| Ansichten und Reiter | `TABS`, `render()`, `viewSeg()`, `collSeg()` (Sammlung DLC | Spiele), `go()`/`goKorb()`; der Handy-Test `tests/ui_selbsttest.html` zählt jede Ansicht einzeln auf |
| Felder vom Server | Vertrag `UiContractTest.CONTRACT` in `tests/test_all.py` |

Dazu immer: README (Abschnitt „Nachschlagen“ zum Reiter), diese Datei und bei Abrufen `docs/abrufe.md`.

## Prüfung

Was die Oberfläche vom Server liest, steht als Vertrag in `tests/test_all.py`
(`UiContractTest.CONTRACT`); wer ein neues Feld liest, trägt es dort ein. Jede Änderung an der
Oberfläche muss den Selbsttest bei 390 px bestehen: keine Ansicht scrollt seitlich, kein
Skriptfehler (`tests/ui_selbsttest.html`).

## Tastatur und Bildschirmleser

Ab 0.89: Sortierbare Spaltenköpfe haben `tabindex="0"` (in `sth()` und im Korb), Enter und
Leertaste sortieren, der Fokus bleibt danach auf dem Kopf. Knöpfe ohne Wort (nur Zeichen oder
Symbol) bekommen ihren Tooltip als `aria-label` (`nameButtons`, über einen MutationObserver für
alles, was gezeichnet wird); neue Zeichenknöpfe brauchen deshalb immer ein `title`. Dialoge
öffnen mit `autofocus` auf „Schließen“. Ab 0.99.4 bekommen auch Eingabefelder ohne eigenes
Etikett einen Namen (`nameButtons`: Titel, Platzhalter oder Spaltenkopf, in Tabellen mit dem Land
davor). Der Selbsttest bei 390 px schlägt fehl, wenn ein Knopf oder Link ohne Wort oder ein
Eingabefeld keinen Namen hat.

## Wortwahl

- Namen bleiben stabil, keine Versionsnummern in sichtbaren Bezeichnungen.
- Kurz und ohne Fachbegriffe; Erklärungen gehören in `title`-Tooltips oder Hinweise.
