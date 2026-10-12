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
  mit der gelesenen Angabe.
- [ ] 4.1 Prüfung mit echten Daten: Verbindungstest, Protokoll und Kaufplan nach dem
  Update. Danach Korrekturen, vor allem an den DLC-Abschnitten und der Switch-2-Zuordnung.
- [ ] 4.2 Füllartikel im Kaufplan, Stufe 1: Unter jedem Schritt mit Rest stehen bis zu drei
  Wishlist-Titel, deren Preis unter dem Rest und möglichst nahe daran liegt, auch ohne
  Urteil „kaufen“. Die Summe des Plans bleibt, erst ein Klick nimmt den Titel auf. Die
  Rechnung gibt es schon für die Länderkarten.
- [ ] 4.3 Angebotsrhythmus: In den Einzelheiten eines Titels je Land die Zahl der Angebote in
  24 Monaten, der übliche Abstand, das letzte Angebot und die Monate, in die sie meist
  fielen. Aus den vorhandenen DekuDeals-Verläufen, ohne neue Abrufe. Ein Hinweis auf das
  nächste übliche Angebot nur bei gleichmäßigen Abständen, als Schätzung gekennzeichnet.
- [ ] 4.4 DLC abhaken: In der Sammlung ein Haken je DLC für Inhalte, die die
  DekuDeals-Sammlung nicht kennt (etwa aus einem Paket). Eine Angabe der Sammlung geht vor.
- [ ] 4.5 DLC-Preise: Für fehlende DLC der Sammlung die Nintendo-IDs schonend über die
  Artikelseiten lesen. Daraus die Summe der fehlenden DLC je Spiel in der Sammlung und
  Füllartikel Stufe 2 (fehlende DLC deiner Spiele in den Rest).
- [ ] 4.6 Sprache in Japan: eine Probe für nintendo.co.jp in den Verbindungstest. Liefert
  sie Sprachangaben für einen guten Teil der Titel, wird dieser Teil automatisch, sonst
  bleibt es bei der Bestätigung von Hand.

Zurückgestellt: Füllartikel Stufe 3 (gute Spiele abseits der Wishlist). Es braucht dafür
eine Quelle für „gut“, und ein Vorschlag für ein Spiel, das niemand wollte, hilft wenig.

Gestrichen: Benachrichtigung, Wishlist aufräumen (geschieht in DekuDeals), Budget,
Vorhersage des nächsten Angebots (nicht verlässlich, siehe 4.3).

## Ohne Arbeit für uns

- **Sprache in Japan:** Eine vollständige Quelle gibt es nicht (der Store baut die Seite
  per JavaScript, die Suche ist per robots.txt gesperrt). Siehe 4.6.
- **Südafrika:** Ob Kartenzahlung dort geht, ist ungetestet. Bis dahin gilt „leicht, Karte“.
- **Tests der Oberfläche:** Es gibt keine automatischen Tests. Prüfung per Screenshots
  mit Testdaten, weil das Tool ohne Zusatzpakete auskommen soll.

## Eingang

Neue Wünsche, noch nicht eingeordnet.
