# Abrufe und Daten

Verbindliche Übersicht, was das Tool woher holt, wann, wie oft und wohin es das Ergebnis
legt. Wer einen Abruf, eine Grenze oder eine Ablage ändert, passt diese Datei im selben
Commit an. Stand: 0.68.0. Maßgeblich bleibt der Code; Konstanten stehen in `app/sync.py`.

## Grundregeln

- **Kennung:** Alle Abrufe des Servers tragen die ehrliche Kennung
  (`eshop-kompass/<Version> (privates Wishlist-Tool)`). Seiten laufen über `sources.request`
  (gzip, 25 s Zeitlimit, höchstens 20 MB gepackt wie entpackt, ein Cookie-Speicher je Prozess), titledb gestreamt mit 60 s, Proben
  des Verbindungstests mit 20 s, Kopfdaten über `sources.head`.
- **Nur öffentliche Ziele:** `sources.blocked_target` lässt nur http und https ohne Zugangsdaten in der Adresse zu und nur Hosts, deren Adressen alle öffentlich sind. Weiterleitungen prüft `_SafeRedirect` genauso. Sonst heißt der Fehler „Adresse nicht öffentlich“.
- **Sperren:** HTTP 403 und 429 beenden den betroffenen Schritt sofort, nie den ganzen
  Abgleich, auch nicht bei der Wishlist: Dann gilt die zuletzt gelesene. Sperrt DekuDeals, fragt
  kein späterer Schritt desselben Abgleichs DekuDeals noch einmal (`sources.deku_blocked`), und
  die nächsten 24 Stunden (`DEKU_REST_SECONDS`, `data.deku_wait`) auch kein anderer Abgleich;
  Nintendo-Preise, Kurse und Karten laufen weiter. Warteräume und Bot-Schutz werden nicht
  umgangen; Amazon liefert seine Prüfseite oft mit 503, das gilt dort wie eine Sperre.
- **Nichts still löschen:** Ein Fehler auf einer Folgeseite von Wishlist oder Sammlung heißt
  „nicht lesbar“, nicht „Liste zu Ende“ (nur 404 und andere 4xx außer Sperren beenden das
  Blättern). Fehlt einer Artikelseite der Abschnitt „All time low“ oder der DLC-Abschnitt, obwohl
  Werte bekannt sind, bleiben die alten Werte, und das Protokoll warnt.
- **Schonend:** Pausen zwischen Seiten und Obergrenzen je Abgleich. Was nicht fällig ist,
  wird nicht geholt. Jede DekuDeals-Artikelseite kommt je Abgleich höchstens einmal
  (`sources.item_cache`), auch wenn IDs, Tiefstpreis und DLC sie alle brauchen.
- **Protokoll:** Jeder Schritt schreibt mindestens eine Zeile, auch wenn nichts fällig
  ist. So lassen sich Abgleiche vergleichen. Das Protokoll liegt nur im Speicher (200
  Zeilen) und ist nach einem Neustart leer.

## Zeitplan

| Was | Regel |
|---|---|
| Abgleich | alle `refresh_hours` Stunden (Einstellung, Vorgabe 6, mindestens 1) seit `last_sync` |
| Nach dem Start | ein Abgleich nach 5 Minuten (`BOOT_DELAY`), außer der letzte ist jünger als 30 Minuten |
| Nach Fehlschlag | eine Stunde Pause (nur im Speicher) |
| Von Hand | Knopf „Aktualisieren“; „Verbindung testen“ ruft nur Proben ab und speichert nichts. Ab 0.80 übergeht ein Abgleich von Hand die Ruhezeiten (`sync.manual`, `_quiet`): titledb einmal die Woche (11), Namen gekaufter Titel je Liste einmal die Woche (11b), titledb einen Tag nach Fehlschlag, Karten- und Angebotsseiten nur einmal am Tag (von Hand: was älter als eine Stunde ist, `MANUAL_CARD_SECONDS`). Immer gelten: DekuDeals-Sperre (`DEKU_REST_SECONDS`), Warteraum von store-jp (`JP_WAIT_SECONDS`), Seiten je Abgleich (`*_PER_SYNC`), Pausen, Wiederholung je Titel (`*_RECHECK*`) und Dateiprüfung von titledb (lädt nur geänderte Listen). Das Protokoll nennt am Ende, was übergangen wurde |
| `last_sync` | wird nach Preisen und Karten gesetzt; ab dann zeigt die Oberfläche den neuen Stand |

## Ablauf eines Abgleichs

Die Nummern entsprechen der Reihenfolge in `run_sync`.

| # | Daten | Quelle | Häufigkeit, Grenzen | Ablage | Protokoll |
|---|---|---|---|---|---|
| 1 | Wishlist | DekuDeals, Wishlist-Seiten | jeder Abgleich, bis 30 Seiten, 1 s Pause (`DEKU_PAUSE`); nicht lesbar: es gilt die zuletzt gelesene Liste, nur ohne jede bekannte Liste bricht der Abgleich ab | `data.items` (Titel bleiben, `active` wechselt), `data.wishlist_at` (zuletzt gelesen), `data.wishlist_err` (Fehler bis zum nächsten Lesen; Notbetrieb, ab 0.84) | `Wishlist: n Titel` / `Wishlist nicht lesbar (HTTP x), es gilt die zuletzt gelesene …` |
| 2 | Sammlung | DekuDeals, Sammlungsseiten | jeder Abgleich, bis 30 Seiten, 1 s Pause; ohne eigenen Link die Kennung der Wishlist; nicht lesbar: `owned` bleibt | `data.owned`, überschrieben; `data.collection_at` | `Sammlung: n Titel` / `Sammlung nicht lesbar (…)` |
| – | Aufräumen | kein Abruf | jeder Abgleich mit gelesener Sammlung: Titel, die 180 Tage (`PRUNE_DAYS`) weder auf der Wishlist noch in der Sammlung stehen, fallen aus `items`; Einträge in `lows`, `rel`, `lchk` ohne Bezug sofort (Bezug: Wishlist, Sammlung, fehlender DLC, Paket), etwa nach „habe ich“ oder „ignorieren“ bei einem DLC; das Protokoll nennt die Titel | – | `Aufräumen: …` / `nichts zu entfernen` |
| 3 | Fehlende eShop-IDs | DekuDeals-Artikelseite je Region | neu, nach 14 Tagen (`ID_RECHECK_SECONDS`) oder bei Verdacht; höchstens 120 Titel-Regionen (`IDS_PER_SYNC`), je Region bis zu drei Länderansichten (`countries.FAMILY_LOOKUP`), also bis 360 Seiten; 1 s Pause; Sperre beendet nur diesen Schritt | `items.ids`, dazu Tiefstpreis je Land | `Titel-IDs: n Seiten gelesen, x von y gefunden` / `alle bekannt` |
| 3a | eShop-IDs der Online-Mitgliedschaft je Region, alle sechs Varianten (ab 0.58) | Nintendos Mitgliedschaftsseite `ec.nintendo.com/{DE/de, US/en, JP/ja}/membership`, eine je Region mit aktivem Land; Zuordnung über Tarif und Laufzeit im Seitenzustand (`sources.parse_membership_page`) | monatlich (`NSO_RECHECK`), ohne Ergebnis wöchentlich (`NSO_RETRY`); 2,5 s Pause; Sperre beendet den Schritt samt DekuDeals-Teil | `data.nso.page[Region]` {ids {Variante: ID}, checked} | `Mitgliedschaft, Nintendos Seite: Europa 6 Varianten, …` |
| 3b | eShop-IDs der Online-Mitgliedschaft je Land, für die Varianten, die DekuDeals führt (3 Monate, 12 Monate, Erweiterungspaket, Familie; `planner.NSO_VARIANTS` mit slug). Ein Land fragt mit der eigenen ID, sonst mit der seiner Region von Nintendos Seite, sonst mit der eines Nachbarlands | DekuDeals-Artikelseite je Variante und aktivem Land (`eshop_xx:7008…` in der Preistabelle) | monatlich (`NSO_RECHECK`), Land ohne ID wöchentlich (`NSO_RETRY`), höchstens 20 Seiten je Abgleich (`NSO_PER_SYNC`); 2,5 s Pause; Sperre beendet den Schritt. Land ohne eigene ID fragt mit den IDs seiner Region (USA über Kanada, Mexiko, Brasilien) | `data.nso.v[Variante]` {ids, urls (eShop-Link je Land), checked, lows (Tiefstpreis der letzten 24 Monate je Land)}; die flache Form bis 0.56 wird zu `m12` | `Mitgliedschaft: n Seiten gelesen; IDs je Variante (eigene, sonst Region): …` / `DekuDeals nichts fällig; …` |
| 4 | Wechselkurse | open.er-api, Ersatz frankfurter (EZB) | nur, wenn der Stand der Quelle älter als 24 h ist (`FX_SOURCE_DAY`) und der letzte eigene Abruf über 20 h (`FX_RECHECK`) zurückliegt | `data.fx` {rates, updated, fetched, src}; fehlende Währungen behalten den alten Kurs | `Wechselkurse vom …, (Quelle)` |
| 5 | Preise | Nintendo-Preisschnittstelle, 50 IDs je Anfrage | jeder Abgleich, alle Länder (auch abgeschaltete, fürs Preisniveau); abgeschaltete ohne Antwort ruhen 7 Tage; 0,3 s Pause (`NINTENDO_PAUSE`); 403 beendet den Schritt für alle Länder; ohne Verbindung ein zweiter Versuch nach 5 s; bei HTTP 400 bis zu sechs Sprachparameter | `data.prices`, `data.xprices`, `data.nso_prices` (Mitgliedschaft je Variante, nur aktive Länder) überschrieben; Änderungen in `history.json`, für 1 Monat und Erweiterungspaket Familie unter `nso-<Variante>` mit Tiefstpreis der letzten 24 Monate in `data.nso.v[Variante].lows` und Beginn der Aufzeichnung in `own_since` (ab 0.87) | `XX: n von m Titeln kaufbar` je aktivem Land; `XX: n Tiefstpreise von DekuDeals verworfen, über dem Normalpreis: …` (ab 0.95). Jeder Preis trägt `fetched`; liegt der jüngste eines Lands mehr als 6 Stunden (`planner.PRICE_STALE_SECONDS`) hinter dem jüngsten aller Länder, zeigt die Oberfläche „Preise vom …“ |
| 6 | Guthabenkartenpreise | Shop-Links aus den Einstellungen (JSON-LD) | je Link höchstens alle 20 h (`CARD_RECHECK_SECONDS`), höchstens 12 Links je Abgleich (`CARDS_PER_SYNC`), Plan-Länder zuerst, dann die am längsten nicht gelesenen, 3 s Pause | `data.card_prices`; gelesener Preis gilt bis 14 Tage; Faktor-Verlauf `card_hist` 90 Tage | `Kartenpreise: g von n gelesen, k weitere aktuell, j folgen beim nächsten Abgleich; ohne Preis: …` / `alle n aktuell` |
| 6a | Eigene Angebote mit Link (Mitgliedschaft ab 0.61, Titel ab 0.62), etwa Codes bei Amazon Japan | Shop-Link aus den Einstellungen (`settings.nso_extra`, `settings.own_offers`); JSON-LD, bei Amazon das Hauptangebot der Produktseite mit seiner Währung (`sources.parse_shop_price`); an Amazon geht das Cookie `i18n-prefs` mit der Landeswährung (die Währungswahl der Seite, ab 0.62.1), sonst zeigt Amazon Besuchern aus Deutschland Europreise | je Link höchstens alle 20 h (`CARD_RECHECK_SECONDS`), höchstens 10 Links je Abgleich (`OFFERS_PER_SYNC`), 3 s Pause; Sperre (403/429, bei Amazon auch 503) oder Prüfseite (Captcha) beendet den Schritt, nichts wird umgangen; ohne Links keine Zeile | `data.offer_prices` {Link: price, currency, ok, checked, error}; gelesener Preis gilt bis 14 Tage, nur in der Währung des Landes und höchstens 40 % vom eingetragenen entfernt (`planner.read_offer`, ab 0.62.1), sonst der eingetragene; Links, die nicht mehr eingetragen sind, fallen weg; 0.68 liest einmal alle Links neu (`offer_prices_v`), weil 0.62.0 Europreise als Yen gespeichert hatte | `Eigene Angebote: g von n Preisen gelesen …; k nicht plausibel …` (dieselbe Prüfung wie die Rechnung) / `alle n Links aktuell` |
| 7 | Sprachen Europa | Nintendo-Europa-Suche, 40 IDs je Anfrage | ohne Angabe: 3 Versuche im Tagesabstand, dann monatlich; 0,3 s Pause zwischen den Anfragen; bei einem Fehler zählt, was vorher gelesen war, und 7b fragt nicht noch einmal | `.langs.EU` | `Sprachen Europa: x von n` / `nichts fällig` |
| 7 | Sprachen Amerika | nintendo.com-Titelseite | höchstens 40 Seiten je Abgleich (`LANG_PER_SYNC`, mit 7b zusammen), 1 s Pause, 3 Versuche, dann monatlich; nach 403/429 auch in 7b keine Seite mehr; nennen mindestens 3 gelesene Seiten (`AM_BLANK_ALARM`) und keine einzige Sprachen, zählen sie nicht als Versuch (Seite vermutlich umgebaut) | `.langs.AM` | `Sprachen Amerika: …` / `nichts fällig` / `Warnung: n Seiten gelesen, keine nannte Sprachen …` |
| 7 | Sprachen Japan | store-jp-Titelseite | Grenze und Pause wie Amerika, aber nach einem Versuch nur noch monatlich (die Sprachen kommen meist aus titledb und dem Browser-Helfer); nach einem Warteraum 7 Tage Ruhe (`JP_WAIT_SECONDS`) | `.langs.JP`, `data.lang_wait` | `Sprachen Japan: …`, Warteraum mit nächstem Versuch |
| 8 | Tiefstpreise, Angebotsverläufe | DekuDeals-Artikelseite je aktivem Land | jeder kaufbare Titel ohne bekannten Tiefstpreis, Angebote zuerst; Verläufe nur bei laufenden Angeboten auffrischen; Seiten ohne Tiefstpreis monatlich; Wishlist höchstens 60 (`LOWS_PER_SYNC`), Verläufe höchstens 40 (`SALES_PER_SYNC`), fehlende DLC 30 (`EXTRA_LOWS_PER_SYNC`); 2,5 s Pause | `data.lows` | `Tiefstpreise: … ; Wishlist x von n Titeln mit Tiefstpreis, k mit Angebotsverlauf` |
| 9 | DLC, Pakete, Inhalte | DekuDeals-Artikelseite | höchstens 40 Seiten (`REL_PER_SYNC`), monatlich erneut, Paketverbindungen fehlender DLC alle 90 Tage | `data.rel`, `data.links`, `data.lchk`; 2,5 s Pause | `DLC und Pakete: …` / `nichts fällig` |
| 10 | IDs fehlender DLC und ihrer Spiele; ab 0.68 auch der Spiele von DLC auf der Wishlist, deren Spiel nicht darauf steht (`planner.wish_dlc_parents`; ihre Seite je Region nennt die Sprachen, Schritt 7) | DekuDeals-Artikelseite | höchstens 40 Seiten (`EXTRA_PER_SYNC`), 14 oder 90 Tage, 2,5 s Pause | `data.extra`, `data.glangs` | `Fehlende DLC der Sammlung: …` |
| 11 | Sprachen und IDs Japan/Amerika; ab 0.61 auch die Fassung der DLC (Programm-ID in Europa gleich der in Japan bzw. Amerika?) | titledb (GitHub, Dateien zu rund 25 MB, gestreamt) | nur bei Bedarf, bis zu drei Dateien je Lauf (DE.de, JP.ja, US.en), höchstens wöchentlich, bei neuen IDs nach 1 h; DLC, die titledb nicht kennt, monatlich (`TITLEDB_RECHECK_SECONDS`); nach Fehlschlag 1 Tag Ruhe (`TITLEDB_FAIL_WAIT`); vorher Kopfdaten je Datei: Sind für reine Wiederholungen (keine neuen IDs) alle nötigen Dateien unverändert (ETag, sonst Datum und Größe in `titledb_files`), wird nichts geladen und erst nach einer Woche wieder geprüft | nur Treffer; Dateistand je Datei in `titledb_files`; Fassung je DLC und Region in `app_same` {Region: [ID, gleich]}, geprüft am `app_chk` | `titledb: …` / `titledb: Dateien seit dem letzten Laden unverändert …`, `DLC-Fassungen: g von n geprüft, …` |
| 11b | Englische Namen gekaufter Titel (ab 0.71) | titledb: Liste des Konto-Landes (JP.ja, BR.pt, MX.es, DE.de …), bei Kana im Titel immer JP.ja (ab 0.76), bei chinesischen Schriftzeichen ohne Kana HK.zh (ab 0.79), lateinische Titel zusätzlich in DE.de (ab 0.81: ein deutscher Kauf, gelesen, als das Konto woanders stand), erster Treffer in dieser Reihenfolge, und US.en, gestreamt; gemerkt wird je Name auch die Shop-ID und, ohne Programm-ID, das längste Spiel am Anfang des Namens (`sources.titledb_lookup`, ab 0.79), Käufe „A + B“ einzeln | nur wenn Käufe offen oder unbekannt sind, deren Titel noch nicht gesucht wurde; jede Liste höchstens einmal die Woche (`ESHOP_NAME_SECONDS`, `data.eshop_names_files` {Liste: Zeitpunkt}, ab 0.77; bis 0.76 galt die Woche für alle Listen zusammen, `data.eshop_names_at`, und hielt die japanische Liste auf, wenn vorher die des Konto-Landes geladen war), je Kauftitel ohne Treffer frühestens nach 30 Tagen wieder (`ESHOP_NAME_RECHECK`), sofort, wenn es jetzt andere Listen wären (gemerkt als „BR.pt,DE.de“, ab 0.81); nach Fehlschlag wie 11 | `data.eshop_names` {Kauftitel: [englischer Name oder null, Zeitpunkt, Liste, {ns, game, rest}]} (Einträge bis 0.75 ohne Liste, bis 0.78 ohne viertes Feld; `data.eshop_names_v` 1: Einträge ohne Namen einmal verworfen und alle Listen neu) | `Englische Namen gekaufter Titel aus titledb: g von n (Listen)`; wartet eine Liste: `n offen (Liste), titledb wieder ab TT.MM.` |
| 7b | Sprachen neu gefundener DLC | wie 7 | teilt die Seitengrenze mit 7 | wie 7 | nur bei Arbeit |

Dazu kommt `self_check` ohne Abruf: Er prüft die Ergebnisse auf Glaubhaftigkeit und
schreibt `Prüfung: …`.

## Im Browser (Lesezeichen)

| Helfer | Holt | Rückweg | Ablage |
|---|---|---|---|
| „Käufe lesen“ auf ec.nintendo.com | Kaufverlauf über die Schnittstelle der Seite, 1,2 s je Seite, bis zum Stand des letzten vollständigen Laufs; „alles neu lesen“ (ab 0.68.1) liest den ganzen Verlauf, bekannte Einträge bekommen nur fehlende Angaben | Adresse mit `#kaeufe=` oder Einfügen | `eshop_history.json`, bis 3000 Einträge |
| „JP-Sprachen lesen“ auf store-jp | Titelseiten der offenen Titel mit Preis in Japan und aller Titel mit Angabe aus titledb (ab 0.69, zur Bestätigung); IDs aus dem Link (`?ek-ids=` oder `#ek-ids=`; der Link legt sie auch in die Zwischenablage, ab Stand 4 liest das Lesezeichen sie dort selbst), sonst eingefügt, 2,5 s Pause | Adresse mit `#jpsprachen=` oder Einfügen | `.langs.JP` |

Beide Lesezeichen geben ihren Stand mit (`hv`). Ist er älter als nötig, meldet das Tool das
(gemerkt im Browser unter `ek.helpers`).

## Verbindungstest

Je eine Probe, nichts wird gespeichert. Zwischen DekuDeals-Proben 1 s Pause; nach einer Sperre
fragt der Test DekuDeals nicht weiter an und sagt das je Probe:

- Wishlist
- Artikelseite mit Verlauf
- Nintendo-Preise
- Sprachen Europa, Japan, Amerika
- Sammlung
- DLC-Abschnitte
- erste Guthabenkarte mit Link
- Wechselkurse und ihre Ersatzquelle
- titledb, nur Kopfdaten (Größe, Stand), ohne die Datei zu laden
- Online-Mitgliedschaft: Nintendos Mitgliedschaftsseite für JP, DE und US (je eine Seite: erkannte Varianten mit ihrer eShop-ID, dazu eine Preisabfrage für diese IDs), DekuDeals für DE, BR, JP und US (mit allen dort genannten Ländern und verlinkten Varianten), damit die Nintendo-Preise der dort genannten eShop-IDs
- Eigene Angebote (Mitgliedschaft ab 0.60, Titel ab 0.62): höchstens vier Links im Verbindungstest, je einer ein Abruf: gelesener Preis mit Fundstelle, Beträge auf der Seite, eingetragener Preis; eine Prüfseite (Captcha) wird gemeldet, nicht umgangen. Seit 0.61 liest auch der Abgleich diese Links (Zeile 6a).

## Dateien

| Datei | Inhalt | Lebensdauer |
|---|---|---|
| `settings.json` | nur Eingaben | dauerhaft |
| `data.json` | Abgleichsdaten | `prices`, `fx`, `owned`, `card_prices`, `offer_prices`, `checks` werden überschrieben; `items`, `lows` und `rel` verlieren Titel nach 180 Tagen ohne Wishlist und Sammlung; `extra`, `glangs`, `links` und `card_hist` räumen sich selbst auf |
| `history.json` | eigene Preisaufzeichnung | wächst, wird nie gekürzt, weil sie unersetzlich ist |
| `eshop_history.json` | Kaufverlauf | bis 3000 Einträge |
| `purchases.json`, `ui.json` | Kaufprotokoll, Ansicht | dauerhaft |

## Offene Punkte

Keine. Neue Ideen zu Abrufen kommen in die ROADMAP.md.
