# Oberfläche: Farben, Marken, Wortwahl

Verbindliche Regeln für `app/static/index.html`. Wer dort Farben, Marken oder
Bezeichnungen ändert, passt diese Datei im selben Commit an. Die Legende in der
Oberfläche (das "?" oben rechts) und die README beschreiben dasselbe für Nutzer und
folgen dieser Datei.

## Grundsatz

Jede Farbe hat genau eine Bedeutung. Was nichts entscheidet, bleibt grau. Beide Ansichten,
hell und dunkel, müssen lesbar sein; jede Farbänderung wird in beiden geprüft.

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

Jeder Schritt hat unten wie die Länderkarten „als Korb vergleichen“ und „Titel
dazunehmen …“ (ab 0.68, Name ab 0.69; die letzte Gruppe „Online-Mitgliedschaft“ bietet alle Varianten an). Dazugenommenes ist ein Füllartikel des Schritts und trägt „dazugenommen ×“
(vorher „Füller ×“). Weglassen-Vorschläge gibt es im Plan nicht: Der Plan nimmt nur, was dort
kaufen heißt und dessen Wechsel sich rechnet.

## Käufe aus dem eShop

Ab 0.71 eine eigene Karte in den Einstellungen (`#eshophist`, Sprungleiste „Käufe“), nicht mehr im
Reiter Sammlung. Kopf: Zahl der Käufe, Lesedatum. Erklärung als
Satz, Anleitung zum Lesezeichen als eingeklappter Kasten wie der Browser-Helfer für Japan
(`details.box`, „**So liest du deine Käufe** Lesezeichen für deine Kaufhistorie bei Nintendo“, offen
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
Ablauf offen und eine Zeile unter „Zu erledigen“; Land und Preis darin und „ansehen“ springen zum Kasten). Eine einzige Auswahl (ab 0.61): Die
markierte Variante (fett, Zeile hinterlegt; der Chip „deine“ fiel 0.62.1 weg) ist deine; ein Klick auf eine andere macht
sie zu deiner und zeigt ihre Länder. Angebote von Hand (etwa Amazon-Codes) stehen als eigene Zeile
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
Gruppe an der Stelle ihres ersten Mitglieds; nach Preis, Abstand, Angebotsende oder Alternative flach.

Laden (ab 0.77): Die Seite zeichnet, sobald `/api/state` da ist; Kaufplan und Länderpläne holt sie
danach gleichzeitig und zeichnet noch einmal. Der Server rechnet die Länder je Anfrage nur einmal
(`planner.shared_contexts`).

## Sammlung: unentschiedene DLC

Fehlt ein DLC, steht er nicht auf der Wishlist und ist nicht ignoriert (ab 0.72): violetter Rand links
an der Zeile (`tr.undec`) und Chip „nicht auf der Wishlist“ (`.chip.und`, violett auf `--warn-bg`).
„Titel dazunehmen …“ bietet diese DLC in der Gruppe „Fehlende DLC deiner Spiele“ an („Spiel: DLC ·
Preis“), im Korb mit dem Spiel grau vor dem Namen.

## Rest füllen (Kaufplan)

„Passt dazu“ (Plan-Schritt, Länderkarte, Korb): „+ Titel **spart x €**“ rechnet mit heutigen Preisen;
dahinter klein grün „am Bestpreis“ oder rot „+x € über Bestpreis“ (`fillBest`, Preis hier gegen
Bestpreis der letzten 24 Monate, ab 0.77). Der Tooltip (`fillTip`) nennt beide Beträge. Ab 0.77.1
schlägt der Planer nur Titel vor, die höchstens „gut“ über ihrem Bestpreis liegen (`_fillers`, `ctx.grade`).

„Passt in den Rest (Betrag):“ zeigt höchstens vier Knöpfe, der kleinste verbleibende Rest zuerst:
einzelne Titel und Paare („+ A + B“, ein Klick nimmt beide), dazu die passende Mitgliedschaft.
Alles Weitere von der Wishlist im Auswahlfeld „alles, was passt (n) …“ mit „bleiben x“. Fehlende DLC,
die nicht auf der Wishlist stehen, folgen als höchstens zwei Knöpfe („+ Name DLC · Preis“), alle
übrigen im selben Auswahlfeld „alles, was passt (n) …“, das ab 0.78 zwei Gruppen hat (`optgroup`
„Wishlist“ und „DLC deiner Spiele, nicht auf der Wishlist“, nach Spiel sortiert). Alle Auswahlfelder
haben dieselbe Kartenfarbe und denselben feinen Rahmen (globales `select`, ab 0.78). Kostenloses
fehlt (ab 0.70). Preise in Auswahlfeldern „Titel dazunehmen …“ immer mit Währungszeichen (ab 0.70).

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
| Marke | `--brand` | `h1 .brand` | nur „eShop“ im Namen oben links, Nintendo-Rot. Sonst nirgends, damit Rot weiter „nein“ heißt |
| Betonung ohne Wertung | `--accent` | `.lvl-neg`, `.pct.m-low` | Kurs-/Preisniveau unter 1 bzw. günstiger, ohne Urteil |

## Marken und Zeichen

- ★ (gold): Einkaufspreis erreicht den Bestpreis (24 Monate, zählende Länder).
- ≈ (violett): geschätzter Wert, etwa Guthaben ohne gelesenen Kartenpreis. Geschätzte
  Werte entscheiden nichts und sind immer so gekennzeichnet.
- ? (violett): zählt nicht, weil Sprache ungeprüft oder ohne Guthabenkarte.
- "ca." vor Beträgen: aus anderen Angaben errechnet (etwa Pass-Preis).
- Nicht zählende Zeilen sind blass (`opacity`), nicht farbig.
- Violett: Angabe aus titledb, nicht von Nintendo (bis 0.81.1 zusätzlich gepunktet unterstrichen).
- „am Bestpreis“ (grün) an einem Schritt oder Land steht nur, wenn jeder Titel darin am
  Bestpreis ist; sonst der rote Betrag darüber (ab 0.65). So widersprechen sich Kopfzeile und
  rotes „+x“ einer Zeile nie.
- DLC mit gekürztem Namen tragen in Plan, Korb und Käufen das Hauptspiel klein und grau davor
  („Vampire Survivors: Ode to Castlevania“, `small.gm`, ab 0.65), damit „Pixel Pack“ nicht allein
  steht. In der Wishlist-Liste nicht: Dort stehen DLC immer unter einer Kopfzeile mit dem Namen
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
„vorhanden“ grau; sonst bei nichts Offenem nur die Zahl vorhandener grün, die Zahl ignorierter rot
(Entscheidung 13.10.2026, Wortlaut ab 0.56.3). Der Kopf der Sammlung steht als kompakter Kasten über den
Gruppen: Zahlen fett in zwei kurzen Zeilen, die Erklärung eingeklappt darunter. Filter und
Reihenfolge stehen direkt darunter, über den Spielen (ab 0.58).

## Flächen

Reiter (ab 0.61, „Titel“ heißt ab 0.72 „Wishlist“, intern weiter `titel`): Jetzt, Wishlist, Sammlung, Einstellungen, erst was ansteht, dann
Einkaufen, dann was du hast. Die Länderkarten sind ab 0.74 kein Reiter mehr (intern weiter `laender`):
„alle Länderkarten“ unter dem Kaufplan, „Andere Länder“ an jedem Schritt (`goland`, `S.landFocus`;
`S.landStep` ist die Karte mit den Titeln des Schritts, nur zum Ansehen, `p.ro`), oben „← Kaufplan“. Der Korb ist ab 0.73 kein Reiter mehr, sondern die dritte Ansicht der
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

„Zu erledigen“ (Jetzt): je Eintrag ein fetter Kern („7 fehlende DLC kostenlos holen“), Einzelheiten
klein dahinter, lange Listen eingeklappt („welche“). Die Legende erklärt jedes Zeichen, das die
Oberfläche zeigt, auch Chips, „ca.“, die DLC-Marken und Sammlung „fehlt“.
Auswahl „Konto steht in“ (Jetzt und Einstellungen): nur Länder mit eigenem Shop, ohne
„Deutschland (Guthaben)“.

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
die Online-Mitgliedschaft mit allen Varianten (ab 0.69; im Korb als Zeile mit Link zum Kasten, ohne Sprachmarke).
Sammlung: Der Filter ignoriert Akzente, Satzzeichen und Leerzeichen („pokemon“ findet „Pokémon“, ab 0.69)
und klappt „Ohne offene DLC“ und „Ohne Zusatzinhalte“ mit Treffern auf.
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
Der Preis öffnet den eShop, bei DLC den Verlauf bei DekuDeals (kein fester eShop-Link für DLC).
Neu zeichnen (etwa Sortieren) lässt jede Tabelle an ihrer Scrollstelle. Das Menü Hell/Dunkel liegt
über der Sprungleiste der Einstellungen (Kopfleiste `z-index` 7).

Preiszelle (Tabelle und Korb, `twoLine`, `cellMarks`; ab 0.81 auch in der Tabelle, die bis dahin eine
Zeile ohne Abstand zum Bestpreis hatte): oben ★/≈/? und Preis | kleines rotes „+x“ über dem Bestpreis,
die Fuge mittig in der Spalte; darunter mittig blauer Rabatt „−60 %“ (mit Leerzeichen wie überall),
Händler-, DLC- und Sprachmarke. Auf dunkelgrüner Zelle („kaufen“) bleiben „+x“ rot und Rabatt blau, nicht fett.
Im hellen Thema stehen sie auf kleinem hellem Grund (`--go-mark` = `--card`), weil Rot und Blau auf
dem dunklen Grün sonst nicht lesbar sind; im dunklen Thema ist die Füllung hell genug, dort ohne
Grund (`--go-mark` transparent, ab 0.82.1). 0.81.0 nahm die weiße Schrift der Zelle und brach damit
die Farbregel. Zellen oben ausgerichtet, Titelspalte 210 bis 260 px
breit, in beiden Ansichten gleich. Eine Zeile mit Grund statt Zellen („noch nicht erschienen“) steht
links (bis 0.80 rechtsbündig und damit außerhalb des Bildes). Wo nur ein Land gezeigt wird (Plan-Schritt,
Länderkarte), stehen dieselben Angaben in eigenen Spalten (Einkaufspreis mit Rabatt, „über Bestpreis“), in
der Wishlist-Liste zweizeilig je Spalte.

Länder-Karten: Die Knöpfe „als Korb vergleichen“ und „Titel hinzufügen“ stehen in einer Zeile, die
„Rechnung“ darunter in eigener Zeile; Aufklappen schiebt so nichts zur Seite (ab 0.58).

Einstellungen: Jeder Bereich (Länder, Regeln, Gebühren, Sprachen prüfen, Quellen, Sicherung und
Protokoll) ist eine eigene Karte (`.setc`), damit klar bleibt, wozu Eingeklapptes gehört.
Kästen in einer Karte haben den Seitenhintergrund (`--bg`). Jede Klappe und jeder Kasten einer Karte
hat 10 px Abstand zum Inhalt darüber (`.setc details`, ab 0.78; nicht in Listen und Tabellen). Das Protokollfeld steht unter der Zeile
„Protokoll des letzten Abgleichs · kopieren“ in einer Klappe „Protokoll anzeigen“ (offen von Haus aus,
`data-kc` logbox; „Protokoll öffnen“ klappt sie auf). Titel-Tabelle: Die Zahl der Bestpreise
steht neben dem Länderkürzel („JP 17★“), nicht darunter.

Kacheln und Kästen haben immer denselben Hintergrund (`--card`), auch die Länderkarten
(seit 0.53.6); Grün steht dort nur für „am Bestpreis“ in der Zeile Preis. Weniger Wichtiges wird über
gedämpften Text gezeigt, nie über Transparenz der ganzen Kachel.

## Eine Sache, mehrere Orte

Dieselbe Angabe steht in der Oberfläche oft an mehreren Stellen. Wer sie an einer Stelle ändert
oder ergänzt, geht diese Liste durch und ändert die anderen Stellen mit oder schreibt hierher,
warum eine Stelle anders bleibt. Funktionen in `app/static/index.html`.

| Was | Wo es vorkommt |
|---|---|
| Titelname mit DLC-Marke, Spiel grau davor (nicht in der Wishlist-Liste), Sprach- und Regionsmarke, eigenes Angebot | Wishlist-Liste (`titleRow`, `titleGroups`), Tabelle (`viewMatrix`), Korb (`viewCompare`), Plan-Schritt und Länderkarte (`planCard`), „Passt in den Rest“ und „Passt dazu“, Auswahl „Titel dazunehmen …“ (`wishOpts`, `extraOpts`, `nsoOpts`), Sammlung (`collGame`, `collDlc`), Käufe (`eshopBox`), „Nicht im Plan“ (`notPlanned`), Zu erledigen (`todos`) |
| Preis eines Titels: Einkaufspreis, ★, Rabatt, „ca.“, Abstand zum Bestpreis, Urteilsfarbe | Wishlist-Liste (`titleRow`), Tabelle und Korb (Preiszelle `twoLine`/`cellMarks` in `viewMatrix`, `viewCompare`), Plan-Schritt und Länderkarte (`planCard`, `priceLine`), Mitgliedschaft (`nsoPrice`), Verlauf (`drawVerlauf`), Legende (`openLegend`) |
| Summe eines Landes: Preis, Wechsel, Rest, Karten | Plan-Schritt und Länderkarte (`planCard`, `switchLine`, `restLine`, `billHtml`), Korb-Fußzeilen (`viewCompare`), Kopf des Kaufplans (`viewKauf`), „Andere Länder“ (`othersHtml`) |
| Titel dazunehmen, weglassen, „Passt dazu“, „Passt in den Rest“ | Plan-Schritt (`planpick`, `planfill`), Länderkarte (`pick`, `add`, `trim`), Korb (`add`, Auswahl im Kopf), Erklärung `fillTip`, Abstand zum Bestpreis `fillBest` |
| Suchfelder | `hits()` für Wishlist-Liste, Tabelle, Sammlung und „anderer …“ bei den Käufen |
| Sortierbare Tabellen | `sth()` und `sortRows()`; neue Spalten bekommen beides, die README nennt die Tabellen unter „Sortieren“ |
| Zahlenzeilen in Klappzeilen | „Geprüft: …“ (`langSection`), Käufe (`eshopBox`), Sammlung (`collGame`): Zahl fett, violett, was dich braucht, grün, was erledigt ist |
| Ansichten und Reiter | `TABS`, `render()`, `viewSeg()`, `go()`/`goKorb()`; der Handy-Test `tests/ui_selbsttest.html` zählt jede Ansicht einzeln auf |
| Felder vom Server | Vertrag `UiContractTest.CONTRACT` in `tests/test_all.py` |

Dazu immer: README (Abschnitt „Nachschlagen“ zum Reiter), diese Datei und bei Abrufen `docs/abrufe.md`.

## Prüfung

Was die Oberfläche vom Server liest, steht als Vertrag in `tests/test_all.py`
(`UiContractTest.CONTRACT`); wer ein neues Feld liest, trägt es dort ein. Jede Änderung an der
Oberfläche muss den Selbsttest bei 390 px bestehen: keine Ansicht scrollt seitlich, kein
Skriptfehler (`tests/ui_selbsttest.html`).

## Wortwahl

- Namen bleiben stabil, keine Versionsnummern in sichtbaren Bezeichnungen.
- Kurz und ohne Fachbegriffe; Erklärungen gehören in `title`-Tooltips oder Hinweise.
