# Oberfläche: Farben, Marken, Wortwahl

Verbindliche Regeln für `app/static/index.html`. Wer dort Farben, Marken oder
Bezeichnungen ändert, passt diese Datei im selben Commit an. Die Legende in der
Oberfläche (das "?" oben rechts) und die README beschreiben dasselbe für Nutzer und
folgen dieser Datei.

## Grundsatz

Jede Farbe hat genau eine Bedeutung. Was nichts entscheidet, bleibt grau. Die
Oberfläche ist für den dunklen Modus abgestimmt; der helle Modus muss lesbar bleiben,
wird aber nicht eigens optimiert.

## Farben

| Bedeutung | Token | Klassen | Wofür, Beispiele |
|---|---|---|---|
| Bestpreis | `--gold`, `--gold-ink` | `.ok`, `.star` (★), `td.champ` (Umrandung), `.pct.m-best` | nur der Bestpreis: ★ am Bestpreis, goldene Umrandung des Bestpreis-Landes, "Bestpreis" in Texten. Nie für anderes Lob |
| Urteil und positiv | `--go`, `--go-bg`, `--go-fill`, `--on-go` | `.vd.buy`/`td.c-buy` (Füllung "kaufen"), `.vd.good`/`td.c-good` (hell "gut"), `.g-buy`, `.g-good`, `.gn` | Urteil "kaufen"/"gut", Ersparnis, vollständig, gute Kartenbewertung (Top, gut, günstiger) |
| Rabatt | `--deal` | `.pct` | Rabatt im Shop (−x %), immer dezent blau, auch in Tabellen |
| Prüfen, Hinweis | `--warn`, `--warn-bg` | `.warnc`, `.chip.w`, `.q` (?), `.approx` (≈), `.soon`, `.today`, `.dlc.need` | Sprache ungeprüft, zählt nicht, Schätzung, endet bald, DLC ohne Hauptspiel, Kartenbewertung "teuer" |
| Nein, teurer | `--stop`, `--stop-bg`, `--sale` | `.bad`, `.abv`, `.over`, `.lgt.no`, `.save.neg` | ohne Deutsch, Wechsel lohnt nicht, über dem Bestpreis (+x €), ignorierte Anzahl |
| Neutral | `--muted`, `--chip`, `--line` | `.mut`, `.chip`, `.dlc`, `.lgt.de`, `.pct.np` | Beschriftungen, Normalpreis, "DLC"-Etikett (immer grau), "Deutsch ✓" |
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
- Abstand zum Bestpreis: `+x €` rot, am Bestpreis ★.

## Wortwahl

- Namen bleiben stabil, keine Versionsnummern in sichtbaren Bezeichnungen.
- Kurz und ohne Fachbegriffe; Erklärungen gehören in `title`-Tooltips oder Hinweise.
