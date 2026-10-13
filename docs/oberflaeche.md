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

## Online-Mitgliedschaft

Kasten unter dem Kaufplan, zugeklappt, solange die Verlängerung nicht ansteht (30 Tage vor
Ablauf offen und eine Zeile unter „Zu erledigen“). Das günstigste zählende Land fett, die
anderen mit grauem Abstand `+x €` (kein Rot: das ist kein Urteil), Rabatt blau, Chips „Konto“
und „im Plan“ neutral. Länder ohne Guthabenkarte blass mit bernsteinfarbenem Grund.

## Kopfleiste

Kopf und Reiter kommen beim Scrollen mit. Nach 120 px weiter nach unten blenden sie sich aus,
ein Stück nach oben (30 px) zeigt sie wieder. Tabellenköpfe und die Sprungleiste halten über
`--stick` Abstand, solange die Leiste zu sehen ist.

## Lesezeichen

- Ein Lesezeichen erscheint als Knopf zum Ziehen mit durchgezogenem Rahmen (⠿ Name) mit „Code kopieren“
  daneben und „So legst du es an“ eingeklappt darunter.
- Länderliste im aufgeklappten Titel: ★ steht direkt vor den Angaben des Landes, ? vor dem Grund,
  warum ein Land nicht zählt; keine eigene Spalte dafür.
- Hauptweg zurück ist „Im eShop-Kompass übernehmen“; Textfelder zum Kopieren und Einfügen
  stehen eingeklappt unter „Geht das nicht?“.
- Namen der Lesezeichen bleiben stabil, ohne Versionsnummer. Ein veraltetes Lesezeichen meldet
  sich beim Übernehmen und mit einem bernsteinfarbenen Satz am Knopf.

## Farben

| Bedeutung | Token | Klassen | Wofür, Beispiele |
|---|---|---|---|
| Bestpreis | `--gold`, `--gold-ink` | `.ok`, `.star` (★), `td.champ` (Umrandung), `.pct.m-best` | nur der Bestpreis: ★ am Bestpreis, goldene Umrandung des Bestpreis-Landes, "Bestpreis" in Texten. Nie für anderes Lob |
| Urteil und positiv | `--go`, `--go-bg`, `--go-fill`, `--on-go` | `.vd.buy`/`td.c-buy` (Füllung "kaufen"), `.vd.good`/`td.c-good` (hell "gut"), `.g-buy` (fett), `.g-good` (normal), `.gn` | Urteil "kaufen"/"gut", Ersparnis, vollständig, gute Kartenbewertung (Top, gut, günstiger). „am Bestpreis“ bei Körben: fett, wenn jeder Titel „kaufen“ ist, normal, wenn die Summe am Bestpreis liegt, aber ein Titel nur „gut“ ist |
| Rabatt | `--deal` | `.pct` | Rabatt im Shop (−x %), immer dezent blau, auch in Tabellen |
| Prüfen, Hinweis | `--warn`, `--warn-bg` | `.warnc`, `.chip.w`, `.q` (?), `.approx` (≈), `.soon`, `.today`, `.dlc.need` | Sprache ungeprüft, zählt nicht, Schätzung, endet bald, DLC ohne Hauptspiel, Kartenbewertung "teuer" |
| Nein, teurer | `--stop`, `--stop-bg`, `--sale` | `.bad`, `.abv`, `.over`, `.lgt.no`, `.save.neg` | ohne Deutsch, Wechsel lohnt nicht, über dem Bestpreis (+x €), ignorierte Anzahl, Guthabenkarte teurer als Kreditkarte (Faktor und Bewertung) |
| Neutral | `--muted`, `--chip`, `--line` | `.mut`, `.chip`, `.dlc`, `.lgt.de`, `.pct.np` | Beschriftungen, Normalpreis, "DLC"-Etikett (immer grau), "Deutsch ✓" |
| Marke | `--brand` | `h1 .brand` | nur „eShop“ im Namen oben links, Nintendo-Rot. Sonst nirgends, damit Rot weiter „nein“ heißt |
| Betonung ohne Wertung | `--accent` | `.lvl-neg`, `.pct.m-low` | Kurs-/Preisniveau unter 1 bzw. günstiger, ohne Urteil |

## Marken und Zeichen

- ★ (gold): Einkaufspreis erreicht den Bestpreis (24 Monate, zählende Länder).
- ≈ (bernstein): geschätzter Wert, etwa Guthaben ohne gelesenen Kartenpreis. Geschätzte
  Werte entscheiden nichts und sind immer so gekennzeichnet.
- ? (bernstein): zählt nicht, weil Sprache ungeprüft oder ohne Guthabenkarte.
- "ca." vor Beträgen: aus anderen Angaben errechnet (etwa Pass-Preis).
- Nicht zählende Zeilen sind blass (`opacity`), nicht farbig.
- Gepunktete Unterstreichung: Angabe aus titledb, nicht von Nintendo.

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

Nur die Zahl trägt die Farbe, Verbindungswörter bleiben grau. Sammlung je Spiel: eine Zahl je
Art, mit „·“ getrennt und ohne Gesamtzahl („10 da · 7 ignoriert“, die Gesamtzahl steht im
Tooltip), damit nichts wie „17,7“ liest. „alle 5 da“ ganz grün, wenn alles da ist; sonst bei
nichts Offenem nur die Zahl vorhandener grün, die Zahl ignorierter rot (Entscheidung 13.10.2026,
Form ab 0.55.1). Der Kopf der Sammlung zeigt Zahlen fett in zwei kurzen Zeilen, die Erklärung
steht eingeklappt darunter.

## Flächen

Kacheln und Kästen haben immer denselben Hintergrund (`--card`), auch die Länderkarten im
Reiter Länder (seit 0.53.6); Grün steht dort nur für „am Bestpreis“ in der Zeile Preis. Weniger Wichtiges wird über
gedämpften Text gezeigt, nie über Transparenz der ganzen Kachel.

## Wortwahl

- Namen bleiben stabil, keine Versionsnummern in sichtbaren Bezeichnungen.
- Kurz und ohne Fachbegriffe; Erklärungen gehören in `title`-Tooltips oder Hinweise.
