# Roadmap

Woran am eShop-Kompass als Nächstes gearbeitet wird. Jeder Schritt wird eine kleine
Version mit Tests, Prüfung der Oberfläche, Versionsnummer, README und Commit. Erledigte
Schritte bekommen ein Häkchen und die Version.

Diese Datei liegt in einem öffentlichen Repository. Sie enthält deshalb keine Namen,
Wishlist-Links oder -Kennungen, Hostnamen, Adressen und keine Angaben aus dem eigenen
Konto (siehe [CLAUDE.md](CLAUDE.md)).

## Phase 1 und 2: Aufräumen und Kaufprotokoll (0.20)

- [x] **Rückkehr nach Deutschland wie jedes leichte Land.** Steht das Konto in einem
  anderen Land, muss der Weg nach Deutschland dieselbe Schwelle schaffen wie jedes
  leichte Land, gemessen gegen die Alternative. Wechsel für ein paar Cent fallen weg. Ist
  kein Kontoland eingetragen, gilt Deutschland als Konto und braucht keine Schwelle. Die
  Anzeige „unter dem Normalpreis“ entfällt.
- [x] **gg.deals ausbauen.** Seit 0.9 sperrt Cloudflare jeden Abruf (HTTP 403), und eine
  Lösung ohne Tarnung gibt es nicht. Es kamen nie Daten. Kartenpreise kommen weiter
  über Shop-Links (Eneba) oder von Hand.
- [x] **„Deutschland mit Guthaben“ bleibt** und heißt künftig „Deutschland (Guthaben)“.
  Deutschland zum Shop-Preis bleibt die Vergleichsbasis. Das Guthaben-Land zeigt, ob
  deutsche Karten unter Nennwert sogar andere Länder schlagen.
- [x] **Kartenpreise reihum lesen.** Der Shop sperrt nach etwa elf Abrufen. Bisher kamen
  immer dieselben Links dran, künftig zuerst die am längsten nicht gelesenen.
- [x] **Kleinigkeiten:** Der Tooltip „Rest blockiert“ folgt der Regel seit 0.12, der Rest
  wird nur noch in einem Euro-Wert gezeigt, und „Nicht im Plan“ nennt jeden Titel nur
  einmal.
- [x] **Ersparnis im Kaufprotokoll ohne Rest.** Ein Rest bleibt als Guthaben und ist kein
  Verlust. Die Ersparnis rechnet deshalb wie der Kaufplan mit dem, was die Spiele kosten.

Gestrichen: Ein Feld für den tatsächlich bezahlten Betrag. Das Kaufprotokoll ist nur
Merkhilfe.

## Phase 3: Neue Funktionen

Reihenfolge und Begründung:

1. **Sammlung mit Zusatzinhalten** kommt zuerst. Sie beantwortet die wichtigste offene
   Frage: Welche DLC gibt es zu Spielen, die ich habe, und welche habe ich schon? Sie
   nutzt die Sammlung, die das Tool schon liest, und legt die Daten an, auf denen die
   beiden anderen Schritte aufbauen. Das sind die Abschnitte „DLC“, „Included In“ und
   „Contains“ der DekuDeals-Artikelseiten.
2. **Switch-2-Upgrade-Pfade** folgen, weil die Upgrade-Pakete in DekuDeals als DLC des
   Switch-1-Spiels geführt werden. Sie stecken also schon in den Daten aus Schritt 1.
   Neu ist der Vergleich: Für ein Switch-1-Spiel in der Sammlung reicht das
   Upgrade-Paket, statt die Switch-2-Edition zu kaufen.
3. **Komplett-Editionen gegen Einzelkauf** kommen zuletzt. Sie brauchen am meisten
   unsichere Daten: Was ein Paket enthält, nennt DekuDeals nur lückenhaft („Contains“
   zeigt oft nur das Hauptspiel). Verglichen wird deshalb nur, wo Paket und Teile
   bekannt sind und Preise haben, also auf der Wishlist stehen. Teile, die schon in der
   Sammlung sind, zählen nicht mit.

- [x] 3.1 Sammlung mit Zusatzinhalten (0.21): Artikelseiten der Sammlung schonend lesen
  (höchstens 40 je Abgleich, monatlich auffrischen), Filter „Sammlung“ im Reiter Titel
  mit „hast du / fehlt“ je DLC. Steht ein DLC auf der Wishlist, zeigt die Ansicht sein
  Urteil und seinen Preis.
- [x] 3.2 Switch-2-Upgrade-Pfade (0.22): Upgrade-Pakete als eigene Marke. Ein Hinweis erscheint,
  wenn eine Switch-2-Edition auf der Wishlist steht und das Switch-1-Spiel in der
  Sammlung ist. Mit Preisvergleich, wenn das Upgrade-Paket auf der Wishlist steht.
- [x] 3.3 Komplett-Editionen (0.23): Hinweis „auch enthalten in …“ am Titel und Vergleich von
  Paketpreis und Summe der fehlenden Teile, soweit beides bekannt ist.
- [x] 3.4 Ein Weg zur Switch 2 im Kaufplan (0.24): Hast du das Spiel, fällt die Edition
  weg und das Upgrade-Paket zählt. Ohne das Spiel bleibt der günstigere Weg, Edition oder
  Spiel plus Paket, nie beides.
- [x] Kartenpreise (0.25): zuerst die Karten der Länder im Kaufplan, mit den übrigen
  Abrufen die am längsten nicht gelesenen.

## Phase 4: Echte Daten, Rest nutzen, Sammlung vertiefen

- [x] 4.0 Sicherung mit eigener Preisaufzeichnung (0.26): Sie ist das Einzige, was das Tool
  nicht neu laden kann. Beim Einlesen wird sie ergänzt, nicht ersetzt. Weiter ein Knopf.
- [x] Kleinigkeiten aus dem Betrieb (0.27): €-Zeichen an jedem Eurobetrag, Grund bei
  „kein Urteil“ (nicht erschienen, nur im Abo, kostenlos), Sprachliste klarer gezählt und
  mit der gelesenen Angabe, Abo-Inhalte von Nintendo Switch Online zählen nicht als fehlende DLC.
- [x] Reiter „Sammlung“ (0.28): alle Spiele der Sammlung, oben die mit fehlenden DLC,
  darunter die ohne Zusatzinhalte und die noch nicht gelesenen. Vorher ein Filter im
  Reiter Titel, der schwer zu finden war.
  Dazu: Die Sprachliste trennt geprüfte und ungeprüfte Titel sichtbar in Gruppen.
- [x] Abgleich nach dem Start (0.29): fünf Minuten nach jedem Start, etwa nach einem
  Update, außer der letzte liegt keine 30 Minuten zurück. Das Intervall bleibt.
- [x] 4.1 Prüfung mit echten Daten (mit 0.26): Abgleich ohne Sperren, DLC-Abschnitte im
  echten HTML wie gebaut, Japan-Store weiter nur JavaScript. Korrekturen in 0.27.
- [x] 4.2 Füllartikel im Kaufplan, Stufe 1 (0.30): Unter jedem Schritt mit Rest stehen bis zu
  drei Wishlist-Titel, deren Preis unter dem Rest und möglichst nahe daran liegt, auch ohne
  Urteil „kaufen“. Ohne Titel aus der Sammlung, gekaufte und DLC ohne Hauptspiel. Erst ein
  Klick nimmt den Titel in den Schritt, „Füller ×“ nimmt ihn wieder heraus.
- [x] 4.3 Angebotsrhythmus (0.31): In den Einzelheiten eines Titels je Land die Zahl der Angebote in
  24 Monaten, der übliche Abstand, das letzte Angebot und die Monate, in die sie meist
  fielen. Aus den vorhandenen DekuDeals-Verläufen, ohne neue Abrufe. Ein Hinweis auf das
  nächste übliche Angebot nur bei gleichmäßigen Abständen, als Schätzung gekennzeichnet.
  Das Ende eines Angebots kennt das Tool erst, wenn es die Seite neu liest.
- [x] Titel als Link zur Startseite (0.31): Ein Klick lädt die Seite neu.
- [x] 4.4 DLC abhaken (0.32): In der Sammlung „habe ich“ je DLC für Inhalte, die die
  DekuDeals-Sammlung nicht kennt (etwa aus einem Paket), dazu „ignorieren“ je DLC und
  „alle DLC ignorieren“ je Spiel für Inhalte, die nicht interessieren (etwa kosmetische
  Pakete). Ignorierte zählen nicht als fehlend und stehen eingeklappt. Eine Angabe der
  Sammlung geht vor. Alles wird mitgesichert.
- [x] 4.5 DLC-Preise (0.33): Für fehlende DLC der Sammlung (ohne abgehakte, ignorierte und
  Wishlist-DLC) die Nintendo-IDs schonend über die Artikelseiten lesen, höchstens 40 Seiten
  je Abgleich. Die Preise kommen mit derselben Preisabfrage. Daraus die Summe der fehlenden
  DLC je Spiel und insgesamt in der Sammlung und Füllartikel Stufe 2: fehlende DLC deiner
  Spiele als Vorschlag für den Rest. Übernehmen lassen sie sich erst von der Wishlist.
- [ ] 4.6 Sprache in Japan: eine zuverlässige Quelle. Geprüft und verworfen: die
  store-jp-Produktseite (fast immer nur die JavaScript-Hülle, einmal eine volle Seite,
  vermutlich aus einem Zwischenspeicher), die Suche von nintendo.jp (robots.txt),
  nintendo.co.jp (Titelliste kennt nur einen kleinen Teil, kaum Titelseiten), DekuDeals (nicht
  je Region), eine Schätzung aus Amerika oder Europa (Entscheidung 13.10.2026). Bis dahin
  fragt das Tool store-jp je Titel nur monatlich (0.38.1). Offen: die Datenquelle, aus der
  die store-jp-Seite ihre Angaben lädt, sonst titledb (Sammlung der eShop-Daten je Region).
- [x] 4.7 Sprache einmal je Titel und Region (0.35): Jeder Titel wird einmal je Region
  geprüft und dauerhaft gespeichert, unabhängig vom Preis, auch die fehlenden DLC deiner
  Spiele (eine Seite je Spiel, DLC übernimmt die Sprache des Spiels). Die Liste zeigt alle
  offenen Titel, nicht nur die gerade günstigeren; die Gruppe „ungeprüft, aber egal“ entfällt.
  Angaben zu Titeln, die weder auf der Wishlist noch in der Sammlung stehen, räumt der
  Abgleich ab. Schonend (0.35.1): höchstens 40 Seiten je Region und Abgleich, Sperren zählen
  nicht als Versuch, Seiten ohne Sprachen werden noch zweimal am Folgetag gefragt.

Zurückgestellt: Füllartikel Stufe 3 (gute Spiele abseits der Wishlist). Es braucht dafür
eine Quelle für „gut“, und ein Vorschlag für ein Spiel, das niemand wollte, hilft wenig.

Gestrichen: Benachrichtigung, Wishlist aufräumen (geschieht in DekuDeals), Budget,
Vorhersage des nächsten Angebots (nicht verlässlich, siehe 4.3).

## Phase 5: Rückmeldungen nach dem ersten echten Abgleich

- [x] 5.1 Nach Review 0.35 und echtem Abgleich (0.36): Titel aus der Sammlung fallen aus dem
  Kaufplan. Ein Rest blockiert ab Werk nirgends mehr den Wechsel (Entscheidung 12.10.2026:
  Wechsel mit Guthaben geht über den Support), die Einstellung bleibt je Land. Japan-Titel
  mit drei leeren Seiten werden einmal neu gefragt; höchstens 40 Sprachseiten je Region im
  ganzen Abgleich. Verlauf zählt Angebote laut DekuDeals (24 Monate). eShop-Prices-Suche ohne
  Sonderzeichen. Planschritte und Raster laufen nicht mehr über den Rand, die gelesenen
  Sprachen stehen im Tooltip. Raster: Kontoland vorn, „alle zurücksetzen“.
- [x] 5.2 Sortieren (0.37): Klick auf einen Spaltenkopf sortiert aufsteigend, der zweite
  absteigend, der dritte stellt die gewohnte Reihenfolge wieder her; leere Werte stehen am
  Ende. Gilt für Titel-Liste, Titel-Tabelle (auch je Land), Warenkörbe in Kaufplan und Ländern,
  Verlauf, Länder-Einstellungen und Sprachliste; die Sammlung bekommt eine Auswahl. Die
  Länderspalten der Titel-Tabelle stehen ab Werk nach Stufe und darin nach Zahl der
  Bestpreise, wahlweise nur nach Bestpreisen oder nur nach Stufe; Deutschland bleibt vorn.
  Die Wahl merkt sich der Browser.
- [x] 5.3 Reste aus Review 0.35 (0.38): Ohne Kontoland kommt Deutschland im Kaufplan zuerst,
  wie mit Konto in Deutschland. Bezahlung aus vorhandenem Guthaben steht unter der Kopfzahl,
  ein Rest daraus ohne „(0,00 €)“. „Passt dazu“ nur, wo ein Rest bleibt. „Zu erledigen“ nennt
  nur offene Sprachen, die gerade Geld kosten. Kein DLC-Regionshinweis in Europa.
  Verbindungstest: robots.txt je Kennung gelesen, Preisverlauf wieder aus der Artikelseite.

## Ohne Arbeit für uns

- **Sprache in Japan:** Bis eine verlässliche Quelle gefunden ist, bestätigst du von Hand
  (siehe 4.6). Liefert store-jp eine Seite mit Sprachen, übernimmt das Tool sie.
- **Südafrika:** Ob Kartenzahlung dort geht, ist ungetestet. Bis dahin gilt „leicht, Karte“.
- **Tests der Oberfläche:** Es gibt keine automatischen Tests. Prüfung per Screenshots
  mit Testdaten, weil das Tool ohne Zusatzpakete auskommen soll.

## Eingang

Neue Wünsche, noch nicht eingeordnet.
