"""Abgleich: Wishlist -> Titel-IDs je Region -> Preise je Land -> Wechselkurse."""
import json
import re
import threading
import time
import traceback
import urllib.parse
from datetime import datetime, timedelta, timezone

from . import countries, planner, sources, store

ID_RECHECK_SECONDS = 14 * 24 * 3600   # fehlende IDs alle zwei Wochen neu suchen
ID_RECHECK_LONG = 90 * 24 * 3600      # ... DLC, die auch titledb nicht kennt, nur alle drei Monate
ID_MISSES = 2                         # ... ebenso nach so vielen erfolglosen DekuDeals-Suchen
DEKU_PAUSE = 1.0                      # Sekunden zwischen DekuDeals-Abrufen
DEKU_REST_SECONDS = 24 * 3600        # nach einer Sperre fragt so lange kein Abgleich bei DekuDeals an (0.64)
NINTENDO_PAUSE = 0.3
EXTRA_LOWS_PER_SYNC = 30              # Tiefstpreis-Seiten fehlender DLC je Abgleich (0.53.3)
LOW_PAUSE = 2.5                       # Tiefstpreise gemächlich nachladen
LOW_RECHECK_SECONDS = 30 * 24 * 3600  # Seiten ohne Tiefstpreis monatlich neu prüfen
SALES_RECHECK_SECONDS = 30 * 24 * 3600  # Angebotsverlauf monatlich auffrischen
PRUNE_DAYS = 180                      # Daten von Titeln, die so lange weg sind, entfernen (0.54.1)
LOWS_PER_SYNC = 60                    # Tiefstpreis-Seiten der Wishlist je Abgleich, Angebote zuerst (0.54.1)
IDS_PER_SYNC = 120                    # Titel und Region für die ID-Suche je Abgleich; reicht für eine neue Wishlist (0.54.1)
SALES_PER_SYNC = 40                   # höchstens so viele Seiten nur für den Verlauf
SALES_MONTHS = 24                     # typischer Angebotspreis aus diesem Zeitraum
LOW_PAGE_V = 2                        # Seiten ohne Tiefstpreis: mit Verlauf-Ersatz gelesen
LOWS_VERSION = 3                      # 3: "Switch 2" wurde als Preis 2,00 gelesen                      # erhöht sich, wenn Tiefstpreise neu zu laden sind
# 1: Monatstiefstwerte aus dem Tagesverlauf gespeichert (Grundlage des Bestpreises, 0.16)
HIST_V = 1
LANG_RECHECK_SECONDS = 30 * 24 * 3600 # Seite gelesen, aber ohne Sprachen: monatlich neu prüfen
LANG_RETRY_SECONDS = 20 * 3600        # ... bei den ersten Versuchen schon am nächsten Tag
LANG_TRIES = 3                        # so viele Versuche, bevor nur noch monatlich gefragt wird
LANG_PER_SYNC = 40                    # Seiten je Region und Abgleich, ungeprüfte zuerst
AM_BLANK_ALARM = 3                    # so viele Seiten Amerika ohne Sprachen in einem Lauf: Seite geändert?
TITLEDB_SECONDS = 7 * 24 * 3600       # titledb höchstens wöchentlich laden ...
TITLEDB_RECHECK_SECONDS = 30 * 24 * 3600  # ... und je Titel ohne Angabe monatlich nachsehen
TITLEDB_FRESH_SECONDS = 3600          # noch nie nachgesehene IDs gleich im nächsten Abgleich
TDB_DLC_REGIONS = {"JP": "JP.ja", "AM": "US.en"}   # DLC-IDs dieser Regionen zuerst aus titledb
NET_RETRY_PAUSE = 5.0                 # nach einem kurzen Netzfehler einmal neu versuchen
PRICE_FAIL_PAUSE = 7 * 24 * 3600      # abgeschaltete Länder ohne Preisantwort ruhen lassen
CARD_RECHECK_SECONDS = 20 * 3600      # Kartenpreise höchstens einmal am Tag lesen
TITLEDB_FAIL_WAIT = 86400            # titledb nach einem Fehlschlag einen Tag ruhen lassen
JP_WAIT_SECONDS = 7 * 86400          # nach dem Warteraum von store-jp eine Woche Ruhe
FX_SOURCE_DAY = 24 * 3600            # die Kursquellen erneuern einmal am Tag
FX_RECHECK = 20 * 3600               # höchstens so oft selbst nachfragen, auch wenn die Quelle hängt
CARD_PAUSE = 3.0
REL_RECHECK_SECONDS = 30 * 24 * 3600  # DLC und Pakete eines Titels monatlich auffrischen
REL_PER_SYNC = 40                     # höchstens so viele Artikelseiten je Abgleich
LINK_MISSES = 2                       # so oft muss eine Verbindung fehlen, bis sie wegfällt
LINKS_RECHECK_SECONDS = 90 * 24 * 3600  # Pakete fehlender DLC vierteljährlich nachsehen
REL_V = 1                             # erhöht sich, wenn alle Seiten neu zu lesen sind
EXTRA_PER_SYNC = 40                   # Artikelseiten je Abgleich für IDs fehlender DLC der Sammlung
NSO_RECHECK = 30 * 24 * 3600          # eShop-IDs der Online-Mitgliedschaft: monatlich prüfen
NSO_RETRY = 7 * 24 * 3600             # Land ohne ID auf der Seite: wöchentlich erneut
NSO_PER_SYNC = 20                     # höchstens so viele Mitgliedschaftsseiten je Abgleich
# Nintendos Mitgliedschaftsseite je Region (ab 0.58): Land und Sprache der gelesenen Seite
NSO_PAGES = {"EU": ("DE", "de"), "AM": ("US", "en"), "JP": ("JP", "ja")}

status = {"running": False, "step": "", "done": 0, "total": 0,
          "log": [], "started": None, "finished": None, "ok": None, "boot_sync": None}
_lock = threading.Lock()


def _log(msg):
    stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    status["log"].append(f"{stamp} {msg}")
    del status["log"][:-200]


def _step(text, total=0):
    status.update(step=text, done=0, total=total)
    _log(text)


def needed_families(settings):
    fams = []
    for code, c in settings["countries"].items():
        if c["enabled"]:
            fam = countries.BY_CODE[code]["family"]
            if fam not in fams:
                fams.append(fam)
    return fams


def sync_wishlist(data, settings, fetch, sleep):
    try:
        slugs = sources.fetch_wishlist(settings["wishlist_url"], fetch=fetch,
                                       pause=lambda: sleep(DEKU_PAUSE))
    except sources.FetchError as e:
        for line in sources.attempts:      # was DekuDeals je Kennung geantwortet hat
            _log("  " + line)
        known = sum(1 for it in data["items"].values() if it.get("active"))
        if not known:
            raise RuntimeError("Wishlist nicht lesbar, Einzelheiten stehen darüber")
        # Eine Quelle bricht nie den ganzen Abgleich ab (0.64): Preise und Kurse kommen
        # trotzdem, mit der zuletzt gelesenen Liste
        _log(f"Wishlist nicht lesbar (HTTP {e.status or 'Fehler'}), es gilt die zuletzt gelesene mit {known} Titeln")
        return None
    if not slugs:
        raise RuntimeError("Wishlist ist leer")
    items = data["items"]
    for it in items.values():
        it["active"] = False
    for pos, slug in enumerate(slugs):
        it = items.setdefault(slug, {"title": slug, "parent": None, "ids": {},
                                     "ids_checked": {}})
        it["active"] = True
        it.pop("alias_of", None)
        it["order"] = pos
    _log(f"Wishlist: {len(slugs)} Titel")
    return slugs


def sync_collection(data, settings, fetch, sleep):
    """Liest die DekuDeals-Sammlung, damit Besitz und Hauptspiele bekannt sind.
    Fehlt sie oder ist sie nicht öffentlich, läuft der Abgleich ohne weiter."""
    source = settings.get("collection_url") or settings["wishlist_url"]
    try:
        owned = sources.fetch_wishlist(source, fetch=fetch, kind="collection",
                                       pause=lambda: sleep(DEKU_PAUSE))
    except (sources.FetchError, ValueError) as e:
        _log(f"Sammlung nicht lesbar ({str(e)[:80]})")
        return
    data["owned"] = owned
    both = [it["title"] for s, it in data["items"].items() if it.get("active") and s in set(owned)]
    _log(f"Sammlung: {len(owned)} Titel" +
         (f", davon noch auf der Wishlist: {', '.join(both[:8])}" if both else ""))


def sync_ids(data, settings, fetch, sleep, now=None):
    """Sucht fehlende Nintendo-IDs je Region über die DekuDeals-Artikelseiten."""
    now = now or time.time()
    fams = needed_families(settings)
    todo = []
    for slug, it in data["items"].items():
        if not it.get("active"):
            continue
        for fam in fams:
            if (it.get("ids_suspect") or {}).get(fam):
                todo.append((slug, fam))      # Sprache nicht gefunden: ID neu suchen
                continue
            if it["ids"].get(fam):
                continue
            if now - it["ids_checked"].get(fam, 0) < ID_RECHECK_SECONDS:
                continue
            todo.append((slug, fam))
    # Obergrenze wie bei den anderen Seitenschritten; der Rest folgt im nächsten Abgleich (0.54.1)
    later = max(0, len(todo) - IDS_PER_SYNC)
    todo = todo[:IDS_PER_SYNC]
    if todo:
        _step("Titel-IDs suchen", len(todo))
    misses, pages, got, stop = 0, 0, 0, None
    for slug, fam in todo:
        if stop:
            break
        it = data["items"][slug]
        found, reached = [], False
        for lookup in countries.FAMILY_LOOKUP[fam]:
            try:
                info = sources.fetch_item(slug, lookup, fetch=fetch)
            except sources.FetchError as e:
                _log(f"{slug} ({lookup}): {e}")
                misses += 1
                # Eine Sperre beendet nur diesen Schritt; Preise und Kurse kommen trotzdem (0.54)
                if e.status in sources.BLOCKED:
                    stop = f"DekuDeals lehnt Abrufe ab (HTTP {e.status})"
                    break
                if misses >= 6:            # nicht hundertfach gegen eine Sperre anrennen
                    for line in sources.attempts:
                        _log("  " + line)
                    stop = "Artikelseiten bei DekuDeals nicht lesbar"
                    break
                sleep(DEKU_PAUSE)
                continue
            reached, misses = True, 0
            pages += 1
            if info["title"]:
                it["title"] = info["title"]
            if info["parent"]:
                it["parent"] = info["parent"]
                if info["parent_title"]:
                    it["parent_title"] = info["parent_title"]
            if info.get("low_found", True):    # ohne Abschnitt bleibt der bekannte Wert (0.64)
                _store_low(data, settings, lookup.upper(), slug, info["low"], now,
                           info.get("history") or [], platforms=len(info.get("lows") or []))
            sleep(DEKU_PAUSE)
            if info["nsuids"]:
                found = info["nsuids"]
                break
        if stop and not reached:
            break
        got += bool(found)
        if (it.get("ids_suspect") or {}).get(fam):
            if reached:
                settle_ids(it, fam, found, now, it.get("title") or slug)
        else:
            it["ids"][fam] = found
        if reached:  # bei Netzfehlern beim nächsten Abgleich erneut versuchen
            it["ids_checked"][fam] = now
        status["done"] += 1
        if status["done"] % 10 == 0:
            store.save_data(data)
    merge_aliases(data)
    if stop:
        _log(f"Titel-IDs: {stop}, {len(todo)} offen, nächster Versuch beim nächsten Abgleich")
    _log(f"Titel-IDs: {pages} Seiten gelesen, {got} von {len(todo)} gefunden"
         + (f", {later} folgen beim nächsten Abgleich" if later else "") if todo
         else "Titel-IDs: alle bekannt, nichts zu suchen")
    missing = [it["title"] for it in data["items"].values()
               if it.get("active") and not any(it["ids"].values())]
    if missing:
        _log(f"Ohne eShop-ID ({len(missing)}): " + ", ".join(missing[:12])
             + (" …" if len(missing) > 12 else ""))
    store.save_data(data)


def merge_aliases(data):
    """Führt Einträge zusammen, die auf denselben Titel zeigen.

    DekuDeals kennt für manche Titel mehrere Adressen. Haben zwei aktive
    Einträge dieselben eShop-IDs, bleibt der mit der früheren Position.
    """
    seen, dropped = {}, 0
    active = sorted((s for s, it in data["items"].items() if it.get("active")),
                    key=lambda s: data["items"][s].get("order", 0))
    for slug in active:
        ids = data["items"][slug]["ids"]
        key = tuple(sorted((fam, tuple(sorted(v))) for fam, v in ids.items() if v))
        if not key:
            continue
        if key in seen:
            data["items"][slug]["active"] = False
            data["items"][slug]["alias_of"] = seen[key]
            dropped += 1
        else:
            seen[key] = slug
    if dropped:
        _log(f"{dropped} doppelte Einträge zusammengeführt")
    return dropped


def _store_low(data, settings, code, slug, low, now, history=None, platforms=1):
    """Merkt sich Tiefstpreis, Angebotsphasen und Monatstiefstwerte von DekuDeals für ein
    aktives Land. Nennt die Seite Tiefstpreise für mehrere Plattformen (Switch und Switch 2),
    ist offen, zu welcher Fassung der Verlauf gehört: Dann zählt er nicht für den Bestpreis."""
    cfg = settings["countries"].get(code)
    if not cfg or not cfg["enabled"]:
        return
    e = data.setdefault("lows", {}).setdefault(code, {}).setdefault(slug, {})
    e["checked"] = now
    e["lv"] = LOW_PAGE_V
    if low and low > 0:
        e.update(low=low, src="deku")
    else:
        e.pop("low", None)
        e.pop("src", None)
    if history is not None:            # Seite gelesen: Verlauf merken, auch wenn sie keinen hat
        e["sales_at"] = now
        e["hist_v"] = HIST_V
        if platforms > 1:
            e["hist_multi"] = True
            e.pop("hist", None)
        else:
            e.pop("hist_multi", None)
            e["hist"] = sources.month_lows(history)
        if history:
            since = datetime.fromtimestamp(now - SALES_MONTHS * 30.44 * 86400,
                                           timezone.utc).strftime("%Y-%m-%d")
            e.update(sales=sources.sale_runs(history, since), sales_from=max(history[0][0], since))


def _track(data, history, code, table, stamp):
    """Zeichnet Preiswechsel auf und senkt den Tiefstpreis, wenn er unterboten wird."""
    now = datetime.now(timezone.utc)
    lows = data.setdefault("lows", {}).setdefault(code, {})
    hist = history.setdefault(code, {})
    for slug, p in table.items():
        o = planner.offer(p, now)
        if not o:
            continue
        cur, regular = o["local"] / 100, o["regular"] / 100
        series = hist.setdefault(slug, [])
        if not series or series[-1][1] != cur:
            series.append([stamp, cur])
        e = lows.setdefault(slug, {})
        if "low" in e:
            if e["low"] > regular * 1.001:   # unplausibel, z. B. anderes Format
                del e["low"]
            elif cur < e["low"] - 1e-9:
                e.update(low=cur, src="own", since=stamp)
        # Eigener Tiefstwert, unabhängig von DekuDeals: zählt auch dort, wo
        # DekuDeals keinen Wert liefert
        if cur < e.get("own_low", float("inf")) - 1e-9:
            e.update(own_low=cur, own_since=stamp)


def nso_ids_for(data, code, key="m12"):
    """eShop-IDs einer Variante der Mitgliedschaft für ein Land: die eigenen von DekuDeals, sonst
    die von Nintendos Seite für die Region (ab 0.58), sonst die der Länder derselben Region."""
    ids = (planner.nso_variants(data).get(key) or {}).get("ids") or {}
    if ids.get(code):
        return ids[code]
    fam = countries.BY_CODE[code]["family"]
    page = (((data.get("nso") or {}).get("page") or {}).get(fam) or {}).get("ids") or {}
    if page.get(key):
        return [page[key]]
    out = []
    for other, lst in ids.items():
        if other in countries.BY_CODE and countries.BY_CODE[other]["family"] == fam:
            out += [n for n in lst if n not in out]
    return out[:3]


def sync_nso(data, settings, fetch, sleep, now=None):
    """Online-Mitgliedschaft in allen Varianten, die DekuDeals führt (ab 0.57): Ihre eShop-ID je
    Land steht in der Preistabelle der DekuDeals-Seite. Eine Seite je Variante und aktivem Land,
    monatlich, ohne ID wöchentlich, höchstens NSO_PER_SYNC je Abgleich. Die Preise holt danach
    der normale Preisabruf."""
    now = now or time.time()
    nso = data.setdefault("nso", {})
    var = nso.setdefault("v", {})
    old = {k: nso.pop(k) for k in ("ids", "checked", "lows", "urls") if k in nso}
    if old and "m12" not in var:                 # Daten bis 0.56: nur 12 Monate, flach
        var["m12"] = old
    shops = [c for c in countries.ORDER if countries.BY_CODE[c]["shop"] == c and settings["countries"][c]["enabled"]]
    if sync_nso_pages(data, shops, fetch, sleep, now) == "blocked":
        return
    due = []
    for v in planner.NSO_VARIANTS:
        e = var.setdefault(v["key"], {})
        ids, checked = e.setdefault("ids", {}), e.setdefault("checked", {})
        if v["slug"]:                            # nur Varianten, die DekuDeals führt
            due += [(v, c) for c in shops if now - checked.get(c, 0) > (NSO_RECHECK if ids.get(c) else NSO_RETRY)]

    def known():
        parts = [f"{v['label']} {sum(1 for c in shops if nso_ids_for(data, c, v['key']))}/{len(shops)}" for v in planner.NSO_VARIANTS]
        return "IDs je Variante (eigene, sonst Region): " + ", ".join(parts)
    if not due:
        _log(f"Mitgliedschaft: DekuDeals nichts fällig; {known()}")
        return
    rest = max(0, len(due) - NSO_PER_SYNC)
    due = due[:NSO_PER_SYNC]
    _step("Mitgliedschaft lesen", len(due))
    read = 0
    for i, (v, code) in enumerate(due):
        ids, checked = var[v["key"]]["ids"], var[v["key"]]["checked"]
        lows, urls = var[v["key"]].setdefault("lows", {}), var[v["key"]].setdefault("urls", {})
        if i and checked.get(code) == now:   # schon über die Seite eines anderen Landes gefunden
            status["done"] += 1
            continue
        if read:
            sleep(LOW_PAUSE)
        try:
            info = sources.fetch_item(v["slug"], code.lower(), fetch=fetch)
        except sources.FetchError as e:
            if e.status in sources.BLOCKED:
                _log(f"Mitgliedschaft: DekuDeals sperrt ({e.status}), weiter beim nächsten Abgleich")
                break
            checked[code] = now
            status["done"] += 1
            continue
        read += 1
        for cc, lst in (info.get("eshop_ids") or {}).items():
            if cc in shops and cc not in ids or cc == code:
                ids[cc] = lst[:3]
                checked[cc] = now
        for cc, u in (info.get("eshop_urls") or {}).items():
            if cc in shops:
                urls[cc] = u
        # Bestpreis wie bei Titeln: tiefster Preis der letzten 24 Monate laut Verlauf, sonst Allzeittief
        since = datetime.fromtimestamp(now - 730 * 86400, timezone.utc).strftime("%Y-%m-%d")
        recent = [x for d, x in info.get("history") or [] if d >= since and x]
        if recent or info.get("low") is not None:
            lows[code] = min(recent) if recent else info["low"]
        checked[code] = now
        status["done"] += 1
    _log(f"Mitgliedschaft: {read} Seiten gelesen{f', {rest} folgen im nächsten Abgleich' if rest else ''}; {known()}")


def sync_nso_pages(data, shops, fetch, sleep, now):
    """Nintendos Mitgliedschaftsseite je Region mit aktivem Land (ab 0.58): eShop-IDs aller
    Varianten, auch 1 Monat, Erweiterungspaket Familie und Japan, die DekuDeals nicht führt.
    Drei Seiten höchstens, monatlich, ohne Ergebnis wöchentlich."""
    pages = data["nso"].setdefault("page", {})
    fams = [f for f in NSO_PAGES if any(countries.BY_CODE[c]["family"] == f for c in shops)]
    read, notes = 0, []
    for fam in fams:
        e = pages.setdefault(fam, {})
        if now - e.get("checked", 0) <= (NSO_RECHECK if e.get("ids") else NSO_RETRY):
            continue
        code, lang = NSO_PAGES[fam]
        if read:
            sleep(LOW_PAUSE)
        read += 1
        try:
            found = sources.parse_membership_page(fetch(f"https://ec.nintendo.com/{code}/{lang}/membership"))
        except sources.FetchError as err:
            if err.status in sources.BLOCKED:
                _log(f"Mitgliedschaft: Nintendo sperrt die Mitgliedschaftsseite ({err.status}), weiter beim nächsten Abgleich")
                return "blocked"
            notes.append(f"{countries.FAMILIES[fam]} nicht lesbar ({err})")
            e["checked"] = now
            continue
        e["checked"] = now
        if found:
            e["ids"] = found
        notes.append(f"{countries.FAMILIES[fam]} {len(found)} Varianten")
    if read:
        _log("Mitgliedschaft, Nintendos Seite: " + ", ".join(notes))


def sync_prices(data, settings, fetch, sleep, history=None):
    # Abgeschaltete Länder laufen mit, solange die IDs ihrer Region bekannt sind:
    # ein Abruf je Land, dafür zeigt die Länderliste ihr Preisniveau.
    enabled = list(countries.ORDER)
    _step("Preise abrufen", len(enabled))
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    history = {} if history is None else history
    quiet = []
    for code in enabled:
        if countries.BY_CODE[code]["shop"] != code:   # kein eigener eShop
            status["done"] += 1
            continue
        fam = countries.BY_CODE[code]["family"]
        by_nsuid, extra_ids = {}, {}
        nso_ids = {n: v["key"] for v in planner.NSO_VARIANTS for n in nso_ids_for(data, code, v["key"])} \
            if settings["countries"][code]["enabled"] else {}
        for slug, it in data["items"].items():
            if it.get("active"):
                for n in it["ids"].get(fam, []):
                    by_nsuid[n] = slug
        if settings["countries"][code]["enabled"]:
            for slug, e in (data.get("extra") or {}).items():
                for n in e["ids"].get(fam, []):
                    if n not in by_nsuid:
                        extra_ids[n] = slug
        active = settings["countries"][code]["enabled"]
        failed = data.setdefault("price_fail", {})
        if not by_nsuid or (not active and time.time() - failed.get(code, 0) < PRICE_FAIL_PAUSE):
            status["done"] += 1
            continue
        def prices():
            return sources.fetch_prices(code, list(by_nsuid) + list(extra_ids) + list(nso_ids), fetch=fetch,
                                        lang=countries.BY_CODE[code]["lang"],
                                        pause=lambda: sleep(NINTENDO_PAUSE))
        try:
            try:
                res = prices()
            except sources.FetchError as e:
                # Kurzer Netzfehler (etwa Namensauflösung, Status 0): einmal nach einer Pause neu
                if e.status:
                    raise
                sleep(NET_RETRY_PAUSE)
                res = prices()
        except Exception as e:  # ein Land darf ausfallen, alte Preise bleiben
            if getattr(e, "status", None) in sources.BLOCKED:
                _log(f"Nintendo lehnt Preisabrufe ab ({e}), übrige Länder beim nächsten Abgleich")
                break
            if active:
                _log(f"{code}: Preisabruf fehlgeschlagen ({e})")
            else:
                quiet.append(code)
                failed[code] = time.time()    # abgeschaltetes Land: eine Woche Ruhe
            status["done"] += 1
            continue
        table, xtable, ntable = {}, {}, {}
        for nsuid, p in res.items():
            slug, t = (by_nsuid[nsuid], table) if nsuid in by_nsuid else \
                (extra_ids[nsuid], xtable) if nsuid in extra_ids else (nso_ids.get(nsuid), ntable)
            if not slug:
                continue
            p = dict(p, nsuid=nsuid, fetched=stamp)
            cur = t.get(slug)
            if cur is None or _better(p, cur):
                t[slug] = p
        data["prices"][code] = table
        data.setdefault("xprices", {})[code] = xtable     # fehlende DLC der Sammlung
        if nso_ids:
            data.setdefault("nso_prices", {})[code] = ntable  # Online-Mitgliedschaft
        _track(data, history, code, table, stamp)
        buyable = sum(1 for p in table.values() if p["status"] == "onsale")
        if settings["countries"][code]["enabled"]:
            _log(f"{code}: {buyable} von {len(table)} Titeln kaufbar")
        status["done"] += 1
    if quiet:
        _log("Ohne Preise (abgeschaltete Länder): " + ", ".join(quiet))


def _plan_card_urls(data, settings, now=None):
    """Kartenlinks der Länder, in denen der Kaufplan gerade kauft."""
    try:
        ui = store.load_ui()
        steps = planner.purchase_plan(data, settings, ui["targets"], include_good=ui["plan_good"],
                                      bought=store.load_purchases(), fill=ui.get("plan_fill"),
                                      now=datetime.fromtimestamp(now, timezone.utc) if now else None)["steps"]
    except Exception:
        return set()
    return {x["url"] for p in steps
            for x in planner.parse_card_list(settings["countries"][p["code"]].get("cards")) if x["url"]}


def _card_miss(old, now, error):
    """Abruf gescheitert: Fehler merken, den zuletzt gelesenen Preis behalten (0.52.1). Er gilt
    noch bis planner.CARD_PRICE_MAX_AGE nach dem letzten Erfolg, mit seinem Datum."""
    old = old or {}
    keep = {k: old[k] for k in ("price", "currency") if old.get("price") is not None}
    if keep:
        keep["ok"] = old.get("ok", old.get("checked", now))
    return dict(keep, checked=now, error=error)


def sync_card_prices(data, settings, fetch, sleep, now=None):
    """Liest die Preise der Guthabenkarten, die einen Link haben, von der Shopseite.

    Nur aktive Länder, höchstens einmal am Tag je Link. Liefert eine Seite
    keinen Preis, bleibt der von Hand eingetragene Wert.
    """
    now = now or time.time()
    prices = data.setdefault("card_prices", {})
    urls, label = [], {}
    for code in countries.ORDER:
        cfg = settings["countries"][code]
        if not cfg["enabled"]:
            continue
        for x in planner.parse_card_list(cfg.get("cards")):
            if x["url"] and x["stock"] and x["url"] not in urls:
                urls.append(x["url"])
                label[x["url"]] = f"{code} {x['face'] / 100:g}"
    for url in list(prices):                  # Links, die nicht mehr eingetragen sind
        if url not in urls:
            del prices[url]
    todo = [u for u in urls if now - (prices.get(u) or {}).get("checked", 0) >= CARD_RECHECK_SECONDS]
    # Der Shop sperrt nach einigen Abrufen: zuerst die Karten der Länder im Kaufplan, denn
    # deren Preise zählen gerade. Danach und innerhalb davon die Links, die am längsten
    # nicht gelesen wurden, sonst kämen immer dieselben dran und die hinteren nie
    first = _plan_card_urls(data, settings, now)
    todo.sort(key=lambda u: (u not in first, (prices.get(u) or {}).get("checked", 0)))
    fresh = len(urls) - len(todo)
    # Höchstens CARDS_PER_SYNC je Abgleich (0.64): Alle Links stehen oft beim selben Shop und
    # würden zusammen fällig; so verteilen sie sich auf die Abgleiche des Tages
    later = max(0, len(todo) - CARDS_PER_SYNC)
    todo = todo[:CARDS_PER_SYNC]
    if not todo:
        # Immer eine Zeile, auch ohne Abruf (0.54)
        _log(f"Kartenpreise: alle {len(urls)} aktuell (gelesen in den letzten 20 Stunden)" if urls
             else "Kartenpreise: keine Karte mit Link eingetragen")
        return
    _step("Kartenpreise lesen", len(todo))
    got, failed = 0, []
    for url in todo:
        try:
            found = sources.fetch_card_price(url, fetch=fetch)
        except sources.FetchError as e:
            if e.status in sources.BLOCKED:
                _log(f"Kartenpreise: Shop lehnt Abrufe ab ({e}), Werte von Hand gelten weiter")
                break
            prices[url] = _card_miss(prices.get(url), now, f"HTTP {e.status or 'Fehler'}")
            failed.append(f"{label[url]} (HTTP {e.status or 'Fehler'})")
        else:
            if found:
                prices[url] = {"checked": now, "ok": now, "price": found[0], "currency": found[1]}
                got += 1
            else:
                prices[url] = _card_miss(prices.get(url), now, "Seite nennt keinen Preis")
                failed.append(f"{label[url]} (kein Preis)")
        status["done"] += 1
        sleep(CARD_PAUSE)
    _log(f"Kartenpreise: {got} von {len(todo)} gelesen"
         + (f", {fresh} weitere aktuell" if fresh else "")
         + (f", {later} folgen beim nächsten Abgleich" if later else "")
         + (f"; ohne Preis: {', '.join(failed)}, dort gilt der letzte Preis bis 14 Tage, sonst der Wert von Hand" if failed else "")
         + ("; Rest nach Sperre nicht gelesen" if got + len(failed) < len(todo) else ""))


CARDS_PER_SYNC = 12       # Guthabenkarten mit Link, höchstens so viele Seiten je Abgleich (0.64)
OFFERS_PER_SYNC = 10      # eigene Angebote mit Link, höchstens so viele Seiten je Abgleich


def sync_offer_prices(data, settings, fetch, sleep, now=None):
    """Eigene Angebote mit Link, etwa Codes bei Amazon Japan (Mitgliedschaft ab 0.61, Titel ab
    0.62): Preis höchstens einmal
    am Tag je Link von der Shopseite lesen. Eine Prüfseite (Captcha) oder Sperre beendet den
    Schritt, sie wird nicht umgangen; dann gilt der eingetragene Preis."""
    now = now or time.time()
    known = data.setdefault("offer_prices", {})
    if data.get("offer_prices_v", 0) < 1:
        # 0.62.0 las Amazon-Preise in Euro als Yen (etwa 6 statt 1000). Solche Werte blieben bis
        # zum nächsten Lesen einen Tag stehen; einmal alle Links neu lesen (0.68)
        known.clear()
        data["offer_prices_v"] = 1
    entries = {}
    for x in (settings.get("nso_extra") or []) + (settings.get("own_offers") or []):
        if x.get("url"):
            entries.setdefault(x["url"], []).append(x)
    urls = list(entries)
    for url in list(known):
        if url not in urls:
            del known[url]
    if not urls:
        return
    todo = sorted((u for u in urls if now - (known.get(u) or {}).get("checked", 0) >= CARD_RECHECK_SECONDS),
                  key=lambda u: (known.get(u) or {}).get("checked", 0))[:OFFERS_PER_SYNC]
    if not todo:
        _log(f"Eigene Angebote: alle {len(urls)} Links aktuell")
        return
    _step("Eigene Angebote lesen", len(todo))
    pay = planner.pay_info(data, settings) if data.get("prices") else {}
    got, failed, stop, odd = 0, [], None, []
    for url in todo:
        try:
            page = fetch(url)
        except sources.FetchError as e:
            # Amazon liefert seine Prüfseite oft mit 503: wie eine Sperre, nicht weiter fragen (0.64)
            if e.status in sources.BLOCKED or (e.status == 503 and sources.is_amazon(url)):
                known[url] = _card_miss(known.get(url), now, f"HTTP {e.status}")
                stop = f"Shop lehnt Abrufe ab (HTTP {e.status})"
                break
            known[url] = _card_miss(known.get(url), now, f"HTTP {e.status or 'Fehler'}")
            failed.append(f"HTTP {e.status or 'Fehler'}")
        else:
            if sources.is_amazon(url) and sources.amazon_captcha(page):
                known[url] = _card_miss(known.get(url), now, "Prüfseite (Captcha)")
                stop = "Amazon zeigt eine Prüfseite (Captcha)"
                break
            found = sources.parse_shop_price(url, page)
            if found:
                known[url] = {"checked": now, "ok": now, "price": found[0], "currency": found[1]}
                got += 1
                # Plausibel? Dieselbe Regel wie die Rechnung (planner.read_offer, 0.63): Währung
                # des Landes, nah am eingetragenen Preis; sonst gilt der eingetragene
                for x in entries[url][:1]:
                    want = (pay.get(x["code"]) or {}).get("currency") or sources.amazon_currency(url)
                    check = planner.read_offer(x, known, want, now)["check"] if want else None
                    if check == "cur":
                        odd.append(f"{found[0]:g} {found[1]} statt {want}")
                    elif check == "off":
                        odd.append(f"{found[0]:g} {found[1]} statt eingetragen {x['price']:g}")
            else:
                known[url] = _card_miss(known.get(url), now, "Seite nennt keinen Preis")
                failed.append("kein Preis")
        status["done"] += 1
        sleep(CARD_PAUSE)
    _log(f"Eigene Angebote: {got} von {len(todo)} Preisen gelesen"
         + (f", {len(failed)} ohne Preis ({', '.join(sorted(set(failed)))})" if failed else "")
         + (f"; {len(odd)} nicht plausibel, dort gilt der eingetragene Preis ({'; '.join(odd[:5])})" if odd else "")
         + (f"; {stop}, Rest nicht gelesen, es gilt der eingetragene Preis" if stop else ""))


def record_card_factors(data, settings, now=None):
    """Verlauf der Faktoren je Karten-Link, einer je Tag (der niedrigste), für die
    Bewertung in reinen Guthabenländern. Älteres als CARD_HIST_DAYS fällt weg (0.53)."""
    now = now or time.time()
    when = datetime.fromtimestamp(now, timezone.utc)
    hist = data.setdefault("card_hist", {})
    for url, (day, factor) in planner.card_factors(data, settings, when).items():
        h = hist.setdefault(url, {})
        h[day] = min(factor, h.get(day, factor))
    known = data.get("card_prices") or {}
    for url in list(hist):
        hist[url] = planner.card_hist_window(hist[url], when)
        if url not in known or not hist[url]:
            del hist[url]


UNIT_JUMP = 0.15        # mehr Änderung je Währungseinheit seit dem letzten Abgleich ist auffällig
FX_MAX_AGE_DAYS = 3


def _fx_stamp(updated):
    """Kursstand als „13.10., 02:02“ (Ortszeit des Servers), sonst der Text der Quelle."""
    age = _fx_age_days(updated, datetime.now(timezone.utc))
    if age is None:
        return updated or "unbekannt"
    return (datetime.now(timezone.utc) - timedelta(days=age)).astimezone().strftime("%d.%m., %H:%M")


def sync_fx(data, fetch, now=None):
    """Wechselkurse. Die Quellen erneuern sie einmal am Tag: Abruf nur, wenn der Stand älter
    als FX_SOURCE_DAY ist und der letzte eigene Abruf länger als FX_RECHECK zurückliegt (0.54)."""
    now = now or time.time()
    fx = data.get("fx") or {}
    age = _fx_age_days(fx.get("updated"), datetime.fromtimestamp(now, timezone.utc))
    if fx.get("rates") and age is not None and (age * 86400 < FX_SOURCE_DAY
                                                 or now - fx.get("fetched", 0) < FX_RECHECK):
        _log(f"Wechselkurse vom {_fx_stamp(fx.get('updated'))} ({fx.get('src') or 'Quelle'}), aktuell, nicht abgerufen")
        return
    _step("Wechselkurse abrufen")
    try:
        rates, updated, src = sources.fetch_fx(fetch=fetch)
    except Exception as e:
        _log(f"Wechselkurse nicht aktualisiert ({e}), letzter Stand vom {_fx_stamp(fx.get('updated'))} gilt")
        return
    # Fehlt in der Antwort eine Währung (Ersatzquelle EZB kennt weniger), gilt der letzte Kurs
    old = fx.get("rates") or {}
    kept = sorted(set(old) - set(rates))
    data["fx"] = {"rates": dict(old, **rates), "updated": updated, "fetched": now, "src": src}
    _log(f"Wechselkurse vom {_fx_stamp(updated)} ({src})"
         + (f"; {len(kept)} Währungen ohne neuen Kurs, letzter Stand bleibt" if kept else ""))


def _fx_age_days(updated, now):
    """Alter des Kursstands in Tagen; None, wenn unlesbar."""
    from email.utils import parsedate_to_datetime
    for parse in (parsedate_to_datetime, lambda t: datetime.fromisoformat(t)):
        try:
            dt = parse(updated)
        except (TypeError, ValueError, IndexError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).total_seconds() / 86400
    return None


def self_check(data, settings, now=None):
    """Prüft nach dem Abgleich, ob die Ergebnisse glaubhaft sind, und merkt sich die
    Auffälligkeiten für Protokoll und Oberfläche. Vergleicht mit dem letzten Lauf."""
    now = now or datetime.now(timezone.utc)
    prev = data.get("checks") or {}
    warnings = []
    try:
        ctx = planner.Context(data, settings, now)
    except Exception as e:
        data["checks"] = {"at": now.isoformat(timespec="seconds"), "warnings": [f"Rechnung nicht möglich ({e})"]}
        return data["checks"]
    units, buyable = {}, {}
    for code, c in ctx.countries.items():
        name = c["meta"]["name"]
        for i in c["implausible"]:
            warnings.append(f"{name}: Kartenpreis {planner.num_txt(i['face'])} {c['currency'] or ''} für "
                            f"{planner._eur(i['price'])} vom Shop unglaubhaft, ignoriert")
        if c["unit"]:
            units[code] = c["unit"] * 100
            old = (prev.get("units") or {}).get(code)
            if old and abs(units[code] / old - 1) > UNIT_JUMP:
                warnings.append(f"{name}: Preis je {c['currency']} seit dem letzten Abgleich "
                                f"{round(100 * (units[code] / old - 1)):+d} %, bitte Kurs und Kartenpreise prüfen")
        n = sum(1 for p in data["prices"].get(code, {}).values() if p.get("status") == "onsale")
        if n and c["currency"] and not c["rate"]:
            warnings.append(f"{name}: kein Wechselkurs für {c['currency']}, Land fehlt in allen Vergleichen")
        if n and c.get("nocard"):
            _log(f"Prüfung: {name} hat keine Guthabenkarte mit Preis, Angebote dort zählen nicht")
        buyable[code] = n
        old_n = (prev.get("buyable") or {}).get(code)
        if old_n and old_n >= 5 and n < old_n / 2:
            warnings.append(f"{name}: nur noch {n} statt {old_n} Titel kaufbar, Preisabruf prüfen")
    age = _fx_age_days((data.get("fx") or {}).get("updated"), now)
    if age is not None and age > FX_MAX_AGE_DAYS:
        warnings.append(f"Wechselkurse sind {int(age)} Tage alt")
    if "JP" in ctx.countries and ctx.countries["JP"]["offers"]:
        unknown = sum(1 for o in ctx.countries["JP"]["offers"].values() if o.get("lang") == "unknown")
        if unknown and settings.get("lang_rule", "exclude") == "exclude":
            need = sum(1 for t in planner.lang_todo(data, settings) if t["family"] == "JP" and t["matters"] and t["state"] is None)
            _log(f"Prüfung: Japan, bei {unknown} Titeln ist die Sprache offen, sie zählen nicht für Urteil und Kaufplan, "
                 "bis du sie einmal bestätigst oder den Browser-Helfer laufen lässt (Einstellungen, Sprachen prüfen)"
                 + (f"; bei {need} davon wäre Japan gerade günstiger" if need else ""))
    data["checks"] = {"at": now.isoformat(timespec="seconds"), "warnings": warnings,
                      "units": units, "buyable": buyable}
    for w in warnings:
        _log("Prüfung: " + w)
    if not warnings:
        _log("Prüfung: alles glaubhaft")
    return data["checks"]


def prune_old(data, now=None):
    """Daten von Titeln, die PRUNE_DAYS lang weder auf der Wishlist noch in der Sammlung
    standen, aus items, lows, rel und lchk entfernen; sie lassen sich jederzeit neu holen.
    Die eigene Preisaufzeichnung (history.json) bleibt, sie ist unersetzlich (0.54.1).
    Für Titel, die schon vorher weg waren, beginnt die Frist mit diesem Lauf."""
    now = now or time.time()
    items, owned = data["items"], set(data.get("owned") or [])
    gone = 0
    for slug, it in list(items.items()):
        if it.get("active") or slug in owned:
            it.pop("gone_at", None)
            continue
        it.setdefault("gone_at", now)
        if now - it["gone_at"] > PRUNE_DAYS * 86400:
            del items[slug]
            gone += 1
    links = data.get("links") or {}
    keep = set(items) | owned | set(data.get("extra") or {}) | set(data.get("glangs") or {}) \
        | set(links) | {p for parts in links.values() for p in parts}
    lows = sum(len([s for s in t if s not in keep]) for t in (data.get("lows") or {}).values())
    low_slugs = {s for t in (data.get("lows") or {}).values() for s in t if s not in keep}
    for table in (data.get("lows") or {}).values():
        for slug in [s for s in table if s not in keep]:
            del table[slug]
    pages = 0
    for key in ("rel", "lchk"):
        table = data.get(key) or {}
        for slug in [s for s in table if s not in keep]:
            del table[slug]
            pages += key == "rel"
    # Getrennt benannt (0.56.1): Titel erst nach PRUNE_DAYS, Tiefstpreise und DLC-Seiten sofort, sobald
    # nichts mehr auf sie verweist, etwa ein DLC, den du abgehakt oder ignoriert hast
    parts = ([f"{gone} Titel (seit {PRUNE_DAYS} Tagen weder auf der Wishlist noch in der Sammlung)"] if gone else []) + \
        ([f"{lows} Tiefstpreis-Einträge von {len(low_slugs)} Titeln ohne Bezug ({', '.join(sorted(low_slugs)[:3])}"
          f"{' …' if len(low_slugs) > 3 else ''})"] if lows else []) + ([f"{pages} DLC-Seiten ohne Bezug"] if pages else [])
    _log("Aufräumen: " + ("; ".join(parts) + " entfernt" if parts else "nichts zu entfernen")
         + (". Ohne Bezug heißt: weder Wishlist noch Sammlung noch fehlender DLC, etwa abgehakte oder ignorierte DLC" if lows or pages else ""))


def prune_langs(data, settings):
    """Räumt Sprachangaben auf, die keine Rolle mehr spielen: Titel weder auf der Wishlist
    noch in der Sammlung, Spiele ohne fehlende DLC. Deine Bestätigungen bleiben für alles,
    was auf der Wishlist oder in der Sammlung steht."""
    keep = {s for s, it in data["items"].items() if it.get("active")} | set(data.get("owned") or [])
    for slug, it in data["items"].items():
        if slug not in keep:
            it.pop("langs", None)
            it.pop("langs_checked", None)
            it.pop("langs_tries", None)
            it.pop("langs_src", None)
            it.pop("tdb_checked", None)
    games = {e.get("parent") for e in (data.get("extra") or {}).values()} | set(planner.wish_dlc_parents(data))
    glangs = data.get("glangs") or {}
    for game in [g for g in glangs if g not in games]:
        del glangs[game]
    if "owned" not in data:
        return 0                     # Sammlung nie gelesen: Bestätigungen nicht anfassen
    conf = settings.get("lang_confirm") or {}
    drop = [s for s in conf if s not in keep]
    if drop:
        store.save_settings({"lang_confirm": {s: {f: None for f in conf[s]} for s in drop}})
        for s in drop:
            conf.pop(s, None)
    return len(drop)


def suspect_id(rec, fam, now):
    """Keine Seite oder wiederholt keine Sprache: Vielleicht stimmt die ID nicht. Der nächste
    Abgleich sucht sie bei DekuDeals neu, einmal je ID."""
    nsuid = ((rec.get("ids") or {}).get(fam) or [None])[0]
    if nsuid and (rec.get("ids_verified") or {}).get(fam) != nsuid:
        rec.setdefault("ids_suspect", {})[fam] = now
        return True
    return False


def settle_ids(rec, fam, found, now, title):
    """Ergebnis einer Neusuche: andere ID übernehmen und die Sprache neu fragen, sonst die
    alte als geprüft vermerken, damit es nicht immer wieder sucht. Hat titledb eine ID mit
    derselben Programm-ID wie in Europa gefunden, gilt diese, auch wenn DekuDeals bei der
    alten bleibt (Entscheidung 13.10.2026). Ohne Kandidaten löst titledb seit 0.44.5 keine
    Neusuche mehr aus; ältere Daten können noch einen leeren Hinweis tragen: dann bleibt die
    alte ID, als fraglich markiert."""
    (rec.get("ids_suspect") or {}).pop(fam, None)
    hints = rec.get("ids_hint") or {}
    from_tdb = fam in hints
    hint = hints.pop(fam, None)
    old = (rec.get("ids") or {}).get(fam) or []
    oldest = (old or [None])[0]
    via = ""
    if hint and hint != oldest:
        new, via = [hint], " (laut titledb)"
    elif found and found[0] != oldest:
        new = found
    else:
        new = None
    if new:
        rec.setdefault("ids", {})[fam] = new
        for k in ("langs_checked", "langs_tries", "langs", "langs_src", "ids_doubt"):
            (rec.get(k) or {}).pop(fam, None)
        _log(f"ID korrigiert: {title} ({countries.FAMILIES[fam]}) {oldest or '–'} -> {new[0]}{via}")
    elif from_tdb:
        rec.setdefault("ids_doubt", {})[fam] = oldest
        _log(f"ID fraglich: {title} ({countries.FAMILIES[fam]}) {oldest}, Programm-ID passt laut "
             "titledb nicht zu Europa, DekuDeals bleibt dabei; bitte unter Sprachen prüfen nachsehen")
    rec.setdefault("ids_verified", {})[fam] = (new or old or [None])[0]


def jp_targets(data):
    """Japan-ID -> Einträge, die ihre Sprache tragen: Wishlist-Titel und je Spiel mit
    fehlenden DLC der erste DLC (gilt für alle DLC des Spiels), wie in sync_langs."""
    out = {}
    for it in data["items"].values():
        ids = (it.get("ids") or {}).get("JP")
        if it.get("active") and ids and not it.get("parent"):
            out.setdefault(str(ids[0]), []).append(it)
    glangs = data.setdefault("glangs", {})
    for game, nsuid in game_ids(data, "JP").items():
        out.setdefault(str(nsuid), []).append(glangs.setdefault(game, {}))
    return out


def game_ids(data, fam):
    """Je Spiel mit fehlenden DLC die ID, deren Seite die Sprache trägt: die des Spiels
    selbst, wenn bekannt, sonst die des ersten DLC."""
    glangs, out = data.get("glangs") or {}, {}
    for e in (data.get("extra") or {}).values():
        ids = (e.get("ids") or {}).get(fam)
        game = e.get("parent")
        if game and game not in out and (ids or ((glangs.get(game) or {}).get("ids") or {}).get(fam)):
            own = ((glangs.get(game) or {}).get("ids") or {}).get(fam)
            out[game] = own[0] if own else ids[0]
    # Hauptspiele von DLC auf der Wishlist (0.68): nur mit eigener ID, die DLC-Seite nennt
    # die Sprache oft nicht oder fehlt ganz
    for game in planner.wish_dlc_parents(data):
        own = ((glangs.get(game) or {}).get("ids") or {}).get(fam)
        if game not in out and own:
            out[game] = own[0]
    return out


# Kauftitel in der Sprache des Shops (0.72): titledb-Liste je Konto-Land, englische Namen aus der US-Liste
ESHOP_NAME_FILES = {"JP": "JP.ja", "BR": "BR.pt", "MX": "MX.es", "DE": "DE.de", "AT": "DE.de", "CH": "DE.de",
                    "FR": "FR.fr", "ES": "ES.es", "IT": "IT.it", "NL": "NL.nl", "PT": "PT.pt"}
ESHOP_NAME_RECHECK = 30 * 86400       # ein Kauftitel ohne Treffer: frühestens nach 30 Tagen wieder
ESHOP_NAME_SECONDS = 7 * 24 * 3600    # die Listen höchstens einmal die Woche laden


_KANA_KANJI = re.compile("[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]")


def _name_file(title, region):
    """Welche titledb-Liste den Kauftitel kennt: Kana oder Kanji im Namen heißt Japan, egal in
    welchem Land das Konto beim Lesen stand (Käufe aus früheren Wechseln, 0.76); sonst das Land
    beim Lesen."""
    if _KANA_KANJI.search(str(title or "")):
        return "JP.ja"
    return ESHOP_NAME_FILES.get(str(region or "").upper())


def sync_eshop_names(data, fetch, now=None):
    """Englische Namen für Käufe, die das Tool nicht zuordnen kann (Gruppe unbekannt oder offen):
    Name → Programm-ID in der Liste des Konto-Landes, Programm-ID → Name in der US-Liste. Lädt
    nur, wenn es neue solche Käufe gibt, und höchstens einmal die Woche. Ablage
    data.eshop_names {Kauftitel: [englischer Name oder None, Zeitpunkt, Liste]}."""
    now = now or time.time()
    entries = {e.get("key"): e for e in (data.get("_eshop") or {}).get("entries") or []}
    if not entries:
        return
    names = data.setdefault("eshop_names", {})
    want = {}
    for r in planner.eshop_matches(data)["rows"]:
        e, t = entries.get(r["key"]) or {}, r.get("title")
        f = _name_file(t, e.get("region"))
        old = names.get(t)
        # Ohne Treffer erst nach 30 Tagen wieder, außer die Liste ist eine andere als beim letzten
        # Versuch (bis 0.75 nahm das Tool immer die Liste des Kontolands, auch für japanische Titel)
        if r["group"] not in ("unknown", "ask") or not f or not t or \
                (old and (old[0] or (len(old) > 2 and old[2] == f and now - old[1] < ESHOP_NAME_RECHECK))):
            continue
        want.setdefault(f, set()).add(t)
    if not want:
        return
    if now - data.get("titledb_fail_at", 0) < TITLEDB_FAIL_WAIT or now - data.get("eshop_names_at", 0) < ESHOP_NAME_SECONDS:
        _log("Englische Namen gekaufter Titel: " + str(sum(map(len, want.values()))) + " offen, titledb wieder ab "
             + datetime.fromtimestamp(max(data.get("eshop_names_at", 0) + ESHOP_NAME_SECONDS,
                                          data.get("titledb_fail_at", 0) + TITLEDB_FAIL_WAIT)).strftime("%d.%m."))
        return
    _step("Englische Namen gekaufter Titel aus titledb")
    try:
        apps, used = {}, {}
        for f, titles in sorted(want.items()):
            by_name, _ = sources.fetch_titledb_names(f, names=titles, fetch=fetch)
            apps.update({t: by_name.get(sources.name_key(t)) for t in titles})
            used.update({t: f for t in titles})
        found = {a for a in apps.values() if a}
        eng = sources.fetch_titledb_names("US.en", apps=found, fetch=fetch)[1] if found else {}
    except Exception as e:
        _log(f"titledb nicht abrufbar ({e})")
        data["titledb_fail_at"] = now
        return
    data["eshop_names_at"] = now
    for t, a in apps.items():
        names[t] = [eng.get(a) if a else None, now, used[t]]
    _log(f"Englische Namen gekaufter Titel aus titledb: {sum(1 for t in apps if names[t][0])} von {len(apps)} "
         f"({', '.join(sorted(want))})")


def sync_titledb(data, settings, fetch, now=None):
    """Japan über titledb: Sprachen für Titel ohne Angabe und ein Abgleich der Japan-ID.
    titledb nennt zu jeder ID die Programm-ID, die in allen Regionen gleich ist. Weicht sie
    bei Japan und Europa ab, gehört die Japan-ID vermutlich zu einem anderen Titel: Der
    nächste Abgleich sucht sie einmal neu. Lädt nur, wenn etwas zu tun ist, und höchstens
    einmal die Woche (Japan rund 24 MB, für den ID-Abgleich zusätzlich Deutschland), für
    neue IDs gleich. Jede ID gilt danach als nachgesehen, auch wenn titledb sie nicht kennt.
    Dazu die Japan- und Amerika-IDs fehlender DLC über die Programm-ID ihrer Europa-ID
    (Amerika aus der US-Liste); was titledb nicht kennt, sucht danach DekuDeals, und titledb
    sieht wöchentlich wieder nach."""
    now = now or time.time()
    if data.get("tdb_doubt_reset", 0) < 1:
        # Bis 0.44.4 galt eine abweichende Programm-ID auch ohne Kandidaten als Hinweis auf
        # eine falsche ID. Das traf Spiele mit eigener Programm-ID in Japan: einmal aufheben
        for rec in list(data["items"].values()) + list((data.get("glangs") or {}).values()):
            if "JP" in (rec.get("ids_hint") or {}) and not rec["ids_hint"]["JP"]:
                rec["ids_hint"].pop("JP")
                (rec.get("ids_suspect") or {}).pop("JP", None)
            (rec.get("ids_doubt") or {}).pop("JP", None)
        data["tdb_doubt_reset"] = 1
    fams = needed_families(settings)
    todo, verify = {}, {}
    if "JP" in fams:
        targets = jp_targets(data)
        todo = {n: recs for n, recs in targets.items()
                if any(not (r.get("langs") or {}).get("JP")
                       and now - r.get("tdb_checked", 0) > TITLEDB_RECHECK_SECONDS for r in recs)}
        for n, recs in targets.items():
            for r in recs:
                eu = ((r.get("ids") or {}).get("EU") or [None])[0]
                if eu and (r.get("ids_tdb") or {}).get("JP") != n:
                    verify[n] = (r, str(eu))
    # Fehlende DLC mit Europa-ID, aber ohne Japan- oder Amerika-ID: über die Programm-ID
    # (DLC haben in allen Regionen meist dieselbe). Ohne Treffer wöchentlich neu, titledb
    # wächst laufend und kostet keine DekuDeals-Seite.
    dlc, dlc_new = {}, False
    for e in (data.get("extra") or {}).values():
        eu = ((e.get("ids") or {}).get("EU") or [None])[0]
        for fam in TDB_DLC_REGIONS:
            tried = (e.get("tdb_ids") or {}).get(fam)
            if eu and fam in fams and not (e.get("ids") or {}).get(fam) \
                    and (tried is None or now - tried >= TITLEDB_SECONDS):
                dlc.setdefault(str(eu), []).append((e, fam))
                dlc_new = dlc_new or tried is None
    # DLC mit Japan- oder Amerika-ID: Passt es zum Spiel aus Europa? Ja, wenn titledb in beiden
    # Regionen dieselbe Programm-ID nennt; meist ist das so. Eine eigene Fassung je Region hat eine
    # andere, dann braucht der DLC das Spiel aus dieser Region (ab 0.61, app_same {Region: [ID, gleich]})
    same, same_new = [], False
    recs = list((data.get("extra") or {}).values()) + [it for it in data["items"].values() if it.get("parent")]
    for rec in recs:
        eu = ((rec.get("ids") or {}).get("EU") or [None])[0]
        for fam in TDB_DLC_REGIONS:
            n = ((rec.get("ids") or {}).get(fam) or [None])[0]
            chk = (rec.get("app_chk") or {}).get(fam)
            known = (rec.get("app_same") or {}).get(fam)
            # Kennt titledb sie nicht, monatlich statt wöchentlich (0.64): Sonst lösen dieselben
            # unbekannten DLC jede Woche drei Downloads zu je rund 25 MB aus
            every = TITLEDB_RECHECK_SECONDS if chk is not None and known is None else TITLEDB_SECONDS
            if eu and n and fam in fams and not (isinstance(known, list) and known[0] == str(n)) \
                    and (chk is None or now - chk >= every):
                same.append((rec, fam, str(eu), str(n)))
                same_new = same_new or chk is None
    # Neue IDs, die titledb noch nie gesehen hat: gleich, sonst wöchentlich
    fresh = same_new or dlc_new or any("tdb_checked" not in r for n in todo for r in todo[n]) or any(
        (r.get("ids_tdb") or {}).get("JP") is None for r, _ in verify.values())
    wait = TITLEDB_FRESH_SECONDS if fresh else TITLEDB_SECONDS
    if not (todo or verify or dlc or same):
        _log("titledb: nichts fällig")
        return
    if now - data.get("titledb_fail_at", 0) < TITLEDB_FAIL_WAIT:
        # Nach einem Fehlschlag nicht bei jedem Abgleich wieder bis zu 75 MB anfragen (0.54)
        _log("titledb: zuletzt nicht abrufbar, nächster Versuch ab "
             + datetime.fromtimestamp(data["titledb_fail_at"] + TITLEDB_FAIL_WAIT).strftime("%d.%m., %H:%M"))
        return
    if now - data.get("titledb_at", 0) < wait:
        if dlc_new or same_new:
            # Sonst verschwindet der Schritt still, und die zurückgestellten DLC wirken vergessen
            _log("IDs fehlender DLC aus titledb: zuletzt um "
                 + datetime.fromtimestamp(data["titledb_at"]).strftime("%H:%M")
                 + " geladen, wieder im nächsten Abgleich ab "
                 + datetime.fromtimestamp(data["titledb_at"] + wait).strftime("%H:%M"))
        else:
            _log("titledb: zuletzt am " + datetime.fromtimestamp(data["titledb_at"]).strftime("%d.%m.")
                 + " geladen, wieder ab " + datetime.fromtimestamp(data["titledb_at"] + wait).strftime("%d.%m."))
        return
    need = {fam for recs in dlc.values() for _, fam in recs}
    own = {fam: {n for _, f, _, n in same if f == fam} for fam in TDB_DLC_REGIONS}
    # Nur bei geänderter Datei (0.66): Für reine Wiederholungen bringt dieselbe Datei nichts
    # Neues. Kopfdaten kosten nichts; Neues (fresh) lädt immer, denn behalten wird nur, was gesucht war
    files = (["DE.de"] if verify or dlc or same else []) \
        + (["JP.ja"] if todo or verify or "JP" in need or own["JP"] else []) \
        + ([TDB_DLC_REGIONS["AM"]] if "AM" in need or own["AM"] else [])
    known = data.get("titledb_files") or {}
    stamp = {f: sources.file_stamp(sources.head(sources.TITLEDB_URL.format(f))) for f in files}
    if not fresh and files and all(stamp[f] and known.get(f) == stamp[f] for f in files):
        data["titledb_at"] = now
        _log("titledb: Dateien seit dem letzten Laden unverändert, nichts Neues zu lesen; wieder ab "
             + datetime.fromtimestamp(now + TITLEDB_SECONDS).strftime("%d.%m."))
        store.save_data(data)
        return
    _step("Sprachen Japan aus titledb" if todo or verify else "IDs fehlender DLC aus titledb" if dlc else "DLC-Fassungen aus titledb")
    try:
        eus = {eu for _, eu in verify.values()} | set(dlc) | {eu for _, _, eu, _ in same}
        europe = sources.fetch_titledb(sorted(eus), fetch=fetch, region="DE.de") if eus else {}
        app_of = {eu: (europe.get(eu) or {}).get("app") for eu in dlc}
        apps = {e["app"] for e in europe.values() if e.get("app")}
        # Japan: Sprachen, Programm-IDs der eigenen IDs und die Japan-ID zu jeder
        # Programm-ID aus Europa (Kandidat, falls die eigene nicht passt, und DLC-IDs)
        found, by_app = sources.fetch_titledb(list(set(todo) | set(verify) | own["JP"]), fetch=fetch, apps=apps) \
            if todo or verify or "JP" in need or own["JP"] else ({}, {})
        by_region, found_in = {"JP": by_app}, {"JP": found, "AM": {}}
        if "AM" in need or own["AM"]:
            found_in["AM"], by_region["AM"] = sources.fetch_titledb(
                sorted(own["AM"]), fetch=fetch, region=TDB_DLC_REGIONS["AM"],
                apps={a for a in app_of.values() if a})
    except Exception as e:
        _log(f"titledb nicht abrufbar ({e})")
        data["titledb_fail_at"] = now
        return
    data["titledb_at"] = now
    data["titledb_files"] = {**known, **{f: v for f, v in stamp.items() if v}}
    hits = {fam: [0, 0] for fam in need}
    for eu, recs in dlc.items():
        for e, fam in recs:
            n = (by_region.get(fam) or {}).get(app_of.get(eu)) if app_of.get(eu) else None
            e.setdefault("tdb_ids", {})[fam] = now        # ohne Treffer sucht auch DekuDeals
            hits[fam][1] += 1
            if n:
                e["ids"][fam] = [str(n)]
                e.setdefault("ids_checked", {})[fam] = now
                e.setdefault("app_same", {})[fam] = [str(n), True]     # über die Programm-ID gefunden
                hits[fam][0] += 1
    if dlc:
        _log("IDs fehlender DLC aus titledb: " + ", ".join(
            f"{countries.FAMILIES[f]} {h[0]} von {h[1]}" for f, h in sorted(hits.items()))
            + "; der Rest über DekuDeals")
    if same:
        diff, unknown = [], 0
        for rec, fam, eu, n in same:
            a, b = (europe.get(eu) or {}).get("app"), (found_in.get(fam).get(n) or {}).get("app")
            rec.setdefault("app_chk", {})[fam] = now
            if a and b:
                rec.setdefault("app_same", {})[fam] = [n, a == b]     # gilt nur für diese ID
                if a != b:
                    diff.append(f"{rec.get('title') or eu} ({countries.FAMILIES[fam]})")
            else:
                unknown += 1
        _log(f"DLC-Fassungen: {len(same) - unknown} von {len(same)} geprüft, "
             + (f"eigene Fassung je Region bei {len(diff)}: {', '.join(diff[:8])}{' …' if len(diff) > 8 else ''}"
                if diff else "alle passen zum Spiel aus Europa")
             + (f"; {unknown} kennt titledb nicht, wieder in einer Woche" if unknown else ""))
    got = 0
    for nsuid, recs in todo.items():
        langs = (found.get(nsuid) or {}).get("langs")
        for rec in recs:
            rec["tdb_checked"] = now
            if langs and not (rec.get("langs") or {}).get("JP"):
                rec.setdefault("langs", {})["JP"] = langs
                rec.setdefault("langs_src", {})["JP"] = "titledb"
        got += bool(langs)
    if todo:
        _log(f"Sprachen Japan aus titledb: {got} von {len(todo)} Titeln")
    odd = 0
    for nsuid, (rec, eu) in verify.items():
        a, b = (found.get(nsuid) or {}).get("app"), (europe.get(eu) or {}).get("app")
        rec.setdefault("ids_tdb", {})["JP"] = nsuid       # einmal je ID, auch ohne Ergebnis
        # Manche Spiele haben in Japan eine eigene Programm-ID (etwa Hyrule Warriors). Ein
        # Hinweis ist eine Abweichung nur, wenn titledb in Japan einen Titel mit der
        # Programm-ID aus Europa kennt (Entscheidung 13.10.2026, ab 0.44.5)
        cand = by_app.get(b)
        if a and b and a != b and cand and cand != nsuid and suspect_id(rec, "JP", now):
            rec.setdefault("ids_hint", {})["JP"] = cand
            odd += 1
    if odd:
        _log(f"Japan-IDs: bei {odd} Titeln kennt titledb eine andere Japan-ID mit der Programm-ID aus Europa, "
             "der nächste Abgleich sucht die ID neu")
    store.save_data(data)


def import_jp_langs(text, now=None):
    """Ergebnis des Browser-Helfers einlesen: {"Japan-ID": "日本語, 英語, …"}. Die Angaben
    stammen von Nintendo und ersetzen titledb. Nicht während eines Abgleichs, der würde
    sie beim Speichern überschreiben."""
    try:
        found = json.loads(text or "")
    except ValueError:
        raise ValueError("Das ist nicht der Text des Browser-Helfers (JSON erwartet)")
    if not isinstance(found, dict):
        raise ValueError("Das ist nicht der Text des Browser-Helfers (JSON erwartet)")
    if not _lock.acquire(blocking=False):
        raise RuntimeError("Gerade läuft ein Abgleich, bitte danach noch einmal einfügen")
    try:
        data = store.load_data()
        targets = jp_targets(data)
        now = now or time.time()
        got = empty = unknown = gone = 0
        for nsuid, value in found.items():
            recs = targets.get(str(nsuid).strip())
            if not recs:
                unknown += 1
                continue
            if str(value or "").strip() == "keine Seite":
                gone += sum(1 for rec in recs if suspect_id(rec, "JP", now)) > 0
                continue
            langs = sources.jp_words(str(value or ""))
            if not langs:
                empty += 1
                continue
            for rec in recs:
                rec.setdefault("langs", {})["JP"] = langs
                (rec.get("langs_src") or {}).pop("JP", None)
                rec.setdefault("langs_checked", {})["JP"] = now
            got += 1
        store.save_data(data)
    finally:
        _lock.release()
    return {"read": got, "empty": empty, "unknown": unknown, "gone": gone}


def sync_langs(data, settings, fetch, sleep, now=None, budget=None, report_idle=True):
    """Sprache je Titel und Region, einmal geprüft und dauerhaft gespeichert, unabhängig vom
    Preis: Wishlist-Titel und die fehlenden DLC deiner Spiele (Füllartikel). Europa in einem
    Abruf, Amerika und Japan je Titel. DLC übernimmt die Sprache seines Spiels, deshalb
    reicht für fehlende DLC eine Seite je Spiel und Region. Fehlt eine Angabe, fragt das
    Tool monatlich neu."""
    now = now or time.time()
    items = {s: it for s, it in data["items"].items() if it.get("active")}
    extra = data.get("extra") or {}
    glangs = data.setdefault("glangs", {})
    # Bis 0.35 lieferte der japanische Store oft leere Seiten, Titel mit drei leeren
    # Antworten fragte das Tool nur noch monatlich. Seit der Store die Sprachen wieder
    # zeigt, einmal von vorn (0.36).
    if data.get("langs_jp_reset", 0) < 1:
        for rec in list(items.values()) + list(glangs.values()):
            if not (rec.get("langs") or {}).get("JP"):
                (rec.get("langs_tries") or {}).pop("JP", None)
                (rec.get("langs_checked") or {}).pop("JP", None)
        data["langs_jp_reset"] = 1
    # Bis 0.44.2 fragte das Tool Pakete (IDs ab 7007) unter titles statt bundles ab und
    # fand keine Seite: Pakete ohne Angabe einmal von vorn (0.44.3)
    if data.get("langs_bundle_reset", 0) < 1:
        for rec in items.values():
            for fam in ("AM", "AS"):
                ids = (rec.get("ids") or {}).get(fam)
                if ids and str(ids[0]).startswith("7007") and not (rec.get("langs") or {}).get(fam):
                    (rec.get("langs_tries") or {}).pop(fam, None)
                    (rec.get("langs_checked") or {}).pop(fam, None)
        data["langs_bundle_reset"] = 1
    dropped = prune_langs(data, settings)
    if dropped:
        _log(f"Sprachen: {dropped} Bestätigungen für Titel gelöscht, die weder auf der Wishlist noch in der Sammlung stehen")

    def due(rec, fam):
        """Noch ohne Angabe und wieder an der Reihe. Sperren und Fehler zählen nicht als
        Versuch; eine gelesene Seite ohne Sprachen (auch eine verdeckte Sperre) wird an
        den nächsten Tagen noch zweimal gefragt, danach monatlich. Japan gleich monatlich:
        store-jp zeigt dem Tool fast immer nur den Warteraum; die Sprachen kommen dann aus
        titledb oder vom Browser-Helfer (Entscheidung 13.10.2026)."""
        if (rec.get("langs") or {}).get(fam) and (rec.get("langs_src") or {}).get(fam) != "titledb":
            return False          # Angabe von Nintendo; eine aus titledb fragt store-jp nach
        tries = (rec.get("langs_tries") or {}).get(fam, 0)
        wait = LANG_RECHECK_SECONDS if tries >= (1 if fam == "JP" else LANG_TRIES) else LANG_RETRY_SECONDS
        return now - (rec.get("langs_checked") or {}).get(fam, 0) > wait

    # Europa nennt die Sprachen meist nur beim Spiel, kaum beim DLC: Fehlende DLC fragen
    # deshalb auch die Seite ihres Spiels, und ein DLC, dessen Spiel die Angabe schon hat,
    # braucht keine eigene (0.53)
    eu = {}
    game_eu = {g for g, rec in glangs.items() if (rec.get("langs") or {}).get("EU")}
    for rec in list(items.values()) + [e for e in extra.values() if e.get("parent") not in game_eu] \
            + list(glangs.values()):
        ids = (rec.get("ids") or {}).get("EU")
        if ids and due(rec, "EU"):
            eu.setdefault(ids[0], []).append(rec)
    if eu and budget is not None and budget.get("EU") == 0:
        eu = {}                          # schon im ersten Durchlauf gescheitert: nicht noch einmal (0.64)
    if eu:
        _step("Sprachen abrufen")
        found, done = {}, []
        try:
            found.update(sources.fetch_langs_eu(list(eu), fetch=fetch, pause=lambda: sleep(NINTENDO_PAUSE),
                                                out=found, done=done) or {})
        except Exception as e:
            _log(f"Sprachen Europa nicht abrufbar ({e})" + (f", {len(done)} IDs vorher gelesen" if done else ""))
            eu = {n: r for n, r in eu.items() if n in set(done)}   # nur Gelesenes gilt als geprüft
            if budget is not None:
                budget["EU"] = 0
        if eu:
            for nsuid, recs in eu.items():
                for rec in recs:
                    rec.setdefault("langs_checked", {})["EU"] = now
                    if nsuid in found:
                        rec.setdefault("langs", {})["EU"] = found[nsuid]
                    else:
                        # Ohne Angabe (DLC nennt Europa meist keine): wie bei den anderen
                        # Regionen nach LANG_TRIES Versuchen nur noch monatlich (0.47.2)
                        tries = rec.setdefault("langs_tries", {})
                        tries["EU"] = tries.get("EU", 0) + 1
            missing = len(eu) - len(set(found) & set(eu))
            _log(f"Sprachen Europa: {len(set(found) & set(eu))} von {len(eu)} Titeln"
                 + (f"; {missing} ohne Angabe (meist DLC), nach {LANG_TRIES} Versuchen nur noch monatlich"
                    if missing else ""))
    elif report_idle:
        _log("Sprachen Europa: nichts fällig")

    # Japan und Amerika: eine Seite je Titel, einmal verlässlich, danach nur, wo sie fehlt.
    # DLC übernimmt die Sprache des Hauptspiels, eigene Seiten braucht es dafür nicht;
    # für fehlende DLC deiner Spiele steht die Seite eines DLC für das ganze Spiel.
    per_title = [("JP", "Japan", sources.fetch_langs_jp), ("AM", "Amerika", sources.fetch_langs_am)]
    for fam, name, fetch_one in per_title:
        if not any(settings["countries"][code]["enabled"] for code in countries.ORDER
                   if countries.BY_CODE[code]["family"] == fam):
            continue
        todo = [(it, it["ids"][fam][0]) for it in items.values()
                if it["ids"].get(fam) and due(it, fam) and not it.get("parent")]
        for game, nsuid in game_ids(data, fam).items():
            rec = glangs.setdefault(game, {})
            if due(rec, fam):
                todo.append((rec, nsuid))
        # Nach einem Warteraum ruht store-jp JP_WAIT_SECONDS: Japan kommt aus titledb und vom
        # Browser-Helfer, ein Versuch je Abgleich brachte nur den Warteraum (0.54)
        wait_until = (data.get("lang_wait") or {}).get(fam, 0)
        if todo and now < wait_until:
            if report_idle:
                # Aufgeschlüsselt (0.61): Die Sprachprüfung zeigt nur Wishlist-Titel ohne Angabe; hier zählen
                # auch Spiele der Sammlung (für fehlende DLC) und Angaben aus titledb, die der Store bestätigen soll
                mine = {id(x) for x in items.values()}
                tdb = sum(1 for r, _ in todo if (r.get("langs") or {}).get(fam))
                wish = sum(1 for r, _ in todo if id(r) in mine)
                bare = sum(1 for r, _ in todo if id(r) in mine and not (r.get("langs") or {}).get(fam))
                parts = [f"{wish} Wishlist-Titel, {bare} davon ohne Angabe" if wish else "",
                         f"{len(todo) - wish} Spiele der Sammlung (Sprache für fehlende DLC)" if len(todo) > wish else "",
                         f"davon {tdb} schon aus titledb, nur zur Bestätigung" if tdb else ""]
                _log(f"Sprachen {name}: {len(todo)} Seiten offen ({', '.join(x for x in parts if x)}), der Store zeigte zuletzt den Warteraum; nächster Versuch ab "
                     f"{datetime.fromtimestamp(wait_until).strftime('%d.%m.')}, bis dahin titledb und Browser-Helfer")
            continue
        # Schonend: ungeprüfte zuerst, höchstens LANG_PER_SYNC Seiten, der Rest beim nächsten Abgleich
        todo.sort(key=lambda t: (t[0].get("langs_tries") or {}).get(fam, 0))
        # `budget` teilt die Seiten auf beide Aufrufe eines Abgleichs auf
        n = LANG_PER_SYNC if budget is None else budget.setdefault(fam, LANG_PER_SYNC)
        rest, todo = max(0, len(todo) - n), todo[:n]
        if budget is not None:
            budget[fam] = n - len(todo)
        got = fails = suspects = 0
        queue = False
        blank = []         # gelesene Seiten ohne Sprachen
        if todo:
            _step(f"Sprachen {name} abrufen", len(todo))
        for rec, nsuid in todo:
            gone = False
            try:
                langs = fetch_one(nsuid, fetch=fetch)
            except sources.FetchError as e:
                if e.status == 404:
                    langs, gone = None, True   # keine Seite: als geprüft vermerken
                elif e.status == 503:
                    data.setdefault("lang_wait", {})[fam] = now + JP_WAIT_SECONDS
                    _log(f"Sprachen {name}: Der Store zeigt den Warteraum, nächster Versuch ab "
                         f"{datetime.fromtimestamp(now + JP_WAIT_SECONDS).strftime('%d.%m.')}")
                    queue = True
                    if budget is not None:
                        budget[fam] = 0    # im selben Abgleich nicht noch einmal anklopfen
                    break                  # zählt nicht als Versuch, die anderen Seiten bleiben ungefragt
                else:
                    fails += 1
                    if e.status in (403, 429) or fails >= 5:
                        _log(f"Sprachen {name} unterbrochen ({e})")
                        if budget is not None and e.status in (403, 429):
                            budget[fam] = 0    # nach einer Sperre im selben Abgleich nicht noch einmal (0.64)
                        break
                    status["done"] += 1
                    sleep(DEKU_PAUSE)
                    continue
            if not langs and not gone:
                blank.append((rec, (rec.get("langs_checked") or {}).get(fam), (rec.get("langs_tries") or {}).get(fam),
                              fam in (rec.get("ids_suspect") or {})))
            rec.setdefault("langs_checked", {})[fam] = now
            tries = rec.setdefault("langs_tries", {})
            tries[fam] = tries.get(fam, 0) + 1
            if langs:
                rec.setdefault("langs", {})[fam] = langs
                (rec.get("langs_src") or {}).pop(fam, None)    # jetzt von Nintendo
                got += 1
            elif (gone or tries[fam] >= LANG_TRIES) and suspect_id(rec, fam, now):
                suspects += 1
            status["done"] += 1
            sleep(DEKU_PAUSE)
        if fam == "AM" and not got and len(blank) >= AM_BLANK_ALARM:
            # Amerika nennt die Sprachen sonst auf jeder Seite. Nennt keine einzige sie, hat sich
            # eher die Seite geändert als alle Titel (0.66): melden, nichts als Versuch zählen
            for rec, checked, tried, was_suspect in blank:
                for key, old_v in (("langs_checked", checked), ("langs_tries", tried)):
                    if old_v is None:
                        rec[key].pop(fam, None)
                    else:
                        rec[key][fam] = old_v
                if not was_suspect:
                    (rec.get("ids_suspect") or {}).pop(fam, None)
            _log(f"Sprachen {name}: Warnung: {len(blank)} Seiten gelesen, keine nannte Sprachen. Vermutlich hat "
                 "nintendo.com den Aufbau der Seiten geändert; die Versuche zählen nicht, die Titel kommen beim "
                 "nächsten Abgleich wieder dran")
        elif todo and not (queue and not got):
            _log(f"Sprachen {name}: {got} von {len(todo)} Titeln" + (f", {rest} folgen beim nächsten Abgleich" if rest else "")
                 + (f", bei {suspects} sucht der nächste Abgleich die ID neu" if suspects else ""))
        elif not todo and report_idle:
            _log(f"Sprachen {name}: nichts fällig")
    store.save_data(data)


def sync_lows(data, settings, fetch, sleep, now=None):
    """Lädt fehlende Tiefstpreise von DekuDeals nach, Angebote zuerst."""
    now = now or time.time()
    lows = data.setdefault("lows", {})
    todo, refresh, xtodo = [], [], []
    # Auch die fehlenden DLC der Sammlung, damit sie Bestpreis und Güte zeigen (0.53.3);
    # schonend: höchstens EXTRA_LOWS_PER_SYNC Seiten je Abgleich, Angebote zuerst
    extra = data.get("extra") or {}
    sources_ = [("prices", lambda slug: data["items"].get(slug, {}).get("active")),
                ("xprices", lambda slug: slug in extra and slug not in data["items"])]
    for code, (table, wanted) in ((c, t) for c in countries.ORDER for t in sources_):
        if not settings["countries"][code]["enabled"]:
            continue
        dest = todo if table == "prices" else xtodo
        for slug, p in (data.get(table) or {}).get(code, {}).items():
            if p.get("status") != "onsale" or not wanted(slug):
                continue
            e = lows.get(code, {}).get(slug)
            # Seiten ohne Tiefstpreis aus der Zeit vor dem Verlauf-Ersatz einmal neu lesen
            fresh = "low" in e or e.get("lv", 0) >= LOW_PAGE_V if e else False
            # Ohne Monatstiefstwerte (vor 0.16 gelesen): Seite einmal neu lesen, der
            # Bestpreis rechnet seitdem mit dem Verlauf der letzten 24 Monate
            hist_ok = bool(e) and e.get("hist_v", 0) >= HIST_V
            if e and fresh and hist_ok and ("low" in e or now - e.get("checked", 0) < LOW_RECHECK_SECONDS):
                # Tiefstpreis bekannt: Seite nur für den Angebotsverlauf erneut
                # laden, wenn er fehlt oder alt ist und gerade ein Angebot läuft
                if "discount" in p and now - e.get("sales_at", 0) >= SALES_RECHECK_SECONDS and table == "prices":
                    refresh.append((0 if "sales_at" not in e else 1, code, slug, table))
                continue
            dest.append((0 if "discount" in p else 1, code, slug, table))
    todo.sort()
    refresh.sort()
    xtodo.sort()
    later = max(0, len(todo) - LOWS_PER_SYNC)
    todo = todo[:LOWS_PER_SYNC] + refresh[:SALES_PER_SYNC] + xtodo[:EXTRA_LOWS_PER_SYNC]
    if not todo:
        _log(_lows_summary(data, settings, "nichts fällig"))
        return
    _step("Tiefstpreise nachladen", len(todo))
    fails = read = kept = 0
    for _, code, slug, table in todo:
        try:
            info = sources.fetch_item(slug, code.lower(), fetch=fetch)
        except sources.FetchError as e:
            if e.status in (403, 429) or fails >= 4:
                _log(f"Tiefstpreise unterbrochen ({e}), Rest beim nächsten Abgleich")
                break
            fails += 1
            sleep(LOW_PAUSE)
            continue
        p = data[table][code][slug]
        old_e = ((data.get("lows") or {}).get(code) or {}).get(slug) or {}
        if not info.get("low_found", True) and ("low" in old_e or old_e.get("hist")):
            # Die Seite hat keinen Abschnitt „All time low“ mehr, der Wert war aber bekannt: eher ein
            # geänderter Seitenaufbau als ein verschwundener Tiefstpreis. Alter Wert bleibt (0.64)
            kept += 1
            status["done"] += 1
            sleep(LOW_PAUSE)
            continue
        cur = p.get("discount", p.get("regular"))
        # Spiele für Switch und Switch 2 haben je Plattform einen Tiefstpreis: Es gilt
        # der höchste, den das Angebot jetzt nicht übersteigt, also die eigene Fassung
        cands = info.get("lows") or ([info["low"]] if info.get("low") else [])
        fits = [v for v in cands if cur is None or v <= cur * 1.001 + 0.001]
        low = max(fits) if fits else (min(cands) if cands else None)
        if not low and info.get("history"):
            # DekuDeals nennt manchmal nur einen Händler-Tiefstpreis: dann der
            # niedrigste Preis aus dem digitalen Verlauf
            low = min(v for _, v in info["history"])
        if low and low > p.get("regular", 0) * 1.001:
            low = None                       # unplausibel
        cur = p.get("discount", p.get("regular"))
        if low and cur is not None and cur < low:
            low = cur
        _store_low(data, settings, code, slug, low, now, info.get("history") or [],
                   platforms=len(info.get("lows") or []))
        read += 1
        status["done"] += 1
        if status["done"] % 20 == 0:
            store.save_data(data)
        sleep(LOW_PAUSE)
    store.save_data(data)
    _log(_lows_summary(data, settings, f"{read} von {len(todo)} Seiten gelesen"
                       + (f", {later} folgen beim nächsten Abgleich" if later else "")
                       + (f"; Warnung: {kept} Seiten ohne Abschnitt „All time low“, bekannte Werte behalten "
                          "(hat DekuDeals die Seite umgebaut?)" if kept else "")))


def _lows_summary(data, settings, head):
    """Eine Zeile, die zählt, was heute zählt: Wishlist-Titel in aktiven Ländern. Bis 0.53
    stand hier die Summe aller je gelesenen Seiten, auch alter Titel (0.54)."""
    lows = data.get("lows") or {}
    codes = [c for c in countries.ORDER if settings["countries"][c]["enabled"]]
    active = [s for s, it in data["items"].items() if it.get("active")]
    has = lambda s, k: any(k(lows.get(c, {}).get(s) or {}) for c in codes)
    known = sum(1 for s in active if has(s, lambda e: "low" in e or "own_low" in e))
    runs = sum(1 for s in active if has(s, lambda e: e.get("sales")))
    return (f"Tiefstpreise: {head}; Wishlist {known} von {len(active)} Titeln mit Tiefstpreis, "
            f"{runs} mit Angebotsverlauf")


def update_links(data, slug, related, now):
    """Verbindungen „Paket enthält Teil“ aus einer gelesenen DekuDeals-Seite übernehmen:
    „Contains“ (die Seite ist das Paket) und „Included In“ (die Seite ist ein Teil).
    data["links"] = {Paket: {Teil: {"t": Name, "src": {Seite: Fehlversuche}}}}.
    Neue Verbindungen gelten sofort. Eine Verbindung fällt erst weg, wenn sie auf jeder Seite,
    die sie genannt hat, LINK_MISSES-mal hintereinander fehlt. Fehlt ein Abschnitt ganz,
    ändert die Seite nichts (umgebaute oder kaputte Seite). Gibt Protokollzeilen zurück."""
    links = data.setdefault("links", {})
    lchk = data.setdefault("lchk", {})
    before = lchk.get(slug)                 # Seite schon einmal gelesen: Neues ist eine Änderung
    lchk[slug] = now
    found = set(related.get("found") or [k for k in ("contains", "included_in") if related.get(k)])
    rel = data.get("rel") or {}

    def name(x, fallback=None):
        return (rel.get(x) or {}).get("title") or fallback or x.replace("-", " ")
    seen, notes = set(), []
    edges = []
    if "contains" in found:
        edges += [(slug, p, t) for p, t in related.get("contains") or [] if p != slug]
    if "included_in" in found:
        edges += [(c, slug, name(slug)) for c, _ in related.get("included_in") or [] if c != slug]
    for c, p, t in edges:
        parts = links.setdefault(c, {})
        if p not in parts:
            if before and c == slug:
                notes.append(f"{name(c)} enthält jetzt auch: {t}")
            parts[p] = {"t": t, "src": {}}
        parts[p]["src"][slug] = 0
        seen.add((c, p))
    # Was diese Seite früher genannt hat und jetzt nicht mehr
    for c, parts in list(links.items()):
        for p, e in list(parts.items()):
            if slug not in e["src"] or (c, p) in seen:
                continue
            if not ((c == slug and "contains" in found) or (p == slug and "included_in" in found)):
                continue
            e["src"][slug] += 1
            if e["src"][slug] >= LINK_MISSES:
                del e["src"][slug]
                if not e["src"]:
                    del parts[p]
                    notes.append(f"{name(c)} enthält nicht mehr: {e['t']}")
        if not parts:
            del links[c]
    return notes


def migrate_links(data):
    """Bis 0.49 standen die Pakete nur je Seite in rel: einmal ins Verbindungsnetz (0.50)."""
    if data.get("links_v", 0) >= 1:
        return
    for slug, e in (data.get("rel") or {}).items():
        related = {"contains": e.get("has") or [], "included_in": e.get("in") or []}
        related["found"] = [k for k, v in related.items() if v]
        if related["found"]:
            update_links(data, slug, related, e.get("checked") or 0)
    data["links_v"] = 1


def _log_links(notes):
    for line in notes[:10]:
        _log("Pakete: " + line)
    if len(notes) > 10:
        _log(f"Pakete: {len(notes) - 10} weitere Änderungen")


def sync_related(data, settings, fetch, sleep, now=None):
    """Liest DLC, Pakete ("Included In") und Inhalt ("Contains") der Artikelseiten von
    Sammlung und Wishlist. Schonend: höchstens REL_PER_SYNC Seiten je Abgleich,
    zuerst die noch nie gelesenen und die Sammlung, dann monatlich auffrischen."""
    now = now or time.time()
    rel = data.setdefault("rel", {})
    migrate_links(data)
    owned = list(data.get("owned") or [])
    wished = [s for s, it in data["items"].items() if it.get("active")]
    # Teile von Paketen, die du hast und die kein bekannter DLC sind: vermutlich Spiele (etwa
    # aus einer Deluxe Edition), deren DLC die Sammlung zeigen soll (0.50)
    known_dlc = {d for e in rel.values() for d, _ in e.get("dlc") or []}
    deku = list(owned)
    owned += [s for s in sorted(planner.pack_parts(data, set(owned) | planner.eshop_matches(data)["owned"],
                                                     planner.pack_block(settings)))
              if s not in known_dlc]
    todo = []
    for pos, slug in enumerate(dict.fromkeys(owned + wished)):
        e = rel.get(slug)
        if e and e.get("v", 0) >= REL_V and now - e.get("checked", 0) < REL_RECHECK_SECONDS:
            continue
        todo.append((e is not None, e.get("checked", 0) if e else 0, pos, slug))
    todo.sort()
    todo = todo[:REL_PER_SYNC]
    # Fehlende DLC: ihre Pakete kennt das Tool aus der ID-Suche; wessen Seite länger nicht
    # gelesen wurde, wird mit dem Rest des Budgets nachgesehen (rel bleibt dafür unberührt)
    lchk = data.get("lchk") or {}
    links_todo = sorted((lchk.get(s, 0), s) for s in (data.get("extra") or {})
                        if now - lchk.get(s, 0) >= LINKS_RECHECK_SECONDS)
    links_todo = [s for _, s in links_todo[:REL_PER_SYNC - len(todo)]]
    def summary(head):
        games = [s for s in deku if s in rel and not rel[s].get("parent")]
        _log(f"DLC und Pakete: {head}; bekannt sind {len(games)} Spiele der Sammlung, "
             f"{sum(1 for s in games if rel[s]['dlc'])} davon mit Zusatzinhalten"
             + (f", {sum(1 for s in owned if s not in rel)} folgen" if any(s not in rel for s in owned) else "")
             + (f"; Pakete bekannt: {len(data.get('links') or {})}" if data.get("links") else ""))
    if not todo and not links_todo:
        summary("nichts fällig")
        return
    _step("DLC und Pakete lesen", len(todo) + len(links_todo))
    fails, notes, kept = 0, [], []
    for slug in links_todo:
        try:
            info = sources.fetch_item(slug, "de", fetch=fetch)
        except sources.FetchError as e:
            if e.status in sources.BLOCKED or fails >= 4:
                _log(f"DLC und Pakete unterbrochen ({e}), Rest beim nächsten Abgleich")
                todo = []
                break
            fails += 1
            sleep(LOW_PAUSE)
            continue
        notes += update_links(data, slug, info.get("related") or {}, now)
        status["done"] += 1
        sleep(LOW_PAUSE)
    for *_, slug in todo:
        try:
            info = sources.fetch_item(slug, "de", fetch=fetch)
        except sources.FetchError as e:
            if e.status in sources.BLOCKED or fails >= 4:
                _log(f"DLC und Pakete unterbrochen ({e}), Rest beim nächsten Abgleich")
                break
            fails += 1
            sleep(LOW_PAUSE)
            continue
        r = info.get("related") or {}
        dlc = [list(x) for x in r.get("dlc", []) if x[0] != slug]
        if not dlc and "dlc" not in (r.get("found") or ["dlc"]) and (rel.get(slug) or {}).get("dlc"):
            # Bekannte DLC, aber kein DLC-Abschnitt mehr: eher ein geänderter Seitenaufbau als ein
            # Spiel ohne DLC. Die alte Liste bleibt, sonst fielen fehlende DLC samt IDs weg (0.64)
            dlc = rel[slug]["dlc"]
            kept.append(info.get("title") or slug)
        rel[slug] = {"checked": now, "v": REL_V, "title": info.get("title"),
                     "parent": info.get("parent"),
                     "dlc": dlc,
                     "in": [list(x) for x in r.get("included_in", []) if x[0] != slug],
                     "has": [list(x) for x in r.get("contains", []) if x[0] != slug]}
        notes += update_links(data, slug, r, now)
        status["done"] += 1
        if status["done"] % 10 == 0:
            store.save_data(data)
        sleep(LOW_PAUSE)
    store.save_data(data)
    _log_links(notes)
    if kept:
        _log(f"DLC und Pakete: Warnung, {len(kept)} Seiten ohne DLC-Abschnitt, bekannte DLC behalten "
             f"(hat DekuDeals die Seite umgebaut?): {', '.join(kept[:5])}")
    summary(f"{status['done']} Seiten gelesen")


def sync_extra_ids(data, settings, fetch, sleep, now=None, report=True):
    """Nintendo-IDs der DLC, die deinen Spielen fehlen und nicht auf der Wishlist stehen,
    damit es für sie Preise gibt (Summe in der Sammlung, Vorschläge für den Rest).
    Schonend: höchstens EXTRA_PER_SYNC Artikelseiten je Abgleich, Abbruch bei Sperren."""
    now = now or time.time()
    wanted = planner.extra_dlc(data, settings)
    extra = data.setdefault("extra", {})
    for slug in [s for s in extra if s not in wanted]:
        del extra[slug]                     # gekauft, ignoriert oder jetzt auf der Wishlist
    fams = needed_families(settings)
    if data.get("ids_misses_v", 0) < 1:
        # Bis 0.47 zählte das Tool erfolglose Suchen nicht: eine bisherige gilt als erste
        for rec in list(extra.values()) + list((data.get("glangs") or {}).values()):
            for fam in (rec.get("ids_checked") or {}):
                if not (rec.get("ids") or {}).get(fam):
                    rec.setdefault("ids_misses", {}).setdefault(fam, 1)
        data["ids_misses_v"] = 1
    todo = []
    for slug, (title, parent) in wanted.items():
        e = extra.setdefault(slug, {"title": title, "parent": parent, "ids": {}, "ids_checked": {}})
        e.update(title=title, parent=parent)
        for fam in fams:
            if not e["ids"].get(fam) and now - e["ids_checked"].get(fam, 0) >= _recheck(e, fam):
                todo.append((bool(e["ids_checked"]), slug, fam, e))
    # Auch die IDs der Spiele selbst: Ihre Shopseite nennt die Sprachen, die eines DLC oft
    # nicht (Japan: DLC-Seiten gibt es dort unter dieser Adresse gar nicht). Seit 0.53 auch
    # Europa: Dort fehlte die Angabe bei fast allen DLC.
    glangs = data.setdefault("glangs", {})
    # Dazu die Hauptspiele von DLC auf der Wishlist, die selbst nicht darauf stehen (0.68)
    for game in dict.fromkeys([parent for _, parent in wanted.values()] + list(planner.wish_dlc_parents(data))):
        g = glangs.setdefault(game, {})
        g.setdefault("ids", {})
        g.setdefault("ids_checked", {})
        for fam in fams:
            if ((g.get("ids_suspect") or {}).get(fam) or (
                    not g["ids"].get(fam) and now - g["ids_checked"].get(fam, 0) >= ID_RECHECK_SECONDS)):
                todo.append((bool(g["ids_checked"]), game, fam, g))
    if not todo:
        if report:
            _log_extra_ids(extra, glangs, fams, now)
        return
    # Europa zuerst: Mit der Europa-ID eines DLC findet titledb die Japan- und Amerika-ID
    # über die Programm-ID, ohne eine DekuDeals-Seite (0.46)
    order = {f: i for i, f in enumerate(("EU", "JP", "AM", "AS"))}
    todo.sort(key=lambda t: (t[0], t[1], order.get(t[2], 9)))
    tdb_ok = now - data.get("titledb_fail_at", 0) > 86400
    _step("IDs fehlender DLC suchen", min(len(todo), EXTRA_PER_SYNC))
    pages, fails = 0, 0
    kinds = {"neu": 0, "erneut": 0, "fraglich": 0, "für titledb zurückgestellt": 0}
    for _, slug, fam, e in todo:
        if pages >= EXTRA_PER_SYNC:
            break
        if tdb_ok and slug in extra and fam in TDB_DLC_REGIONS and (e["ids"].get("EU") or [None])[0] \
                and fam not in (e.get("tdb_ids") or {}):
            kinds["für titledb zurückgestellt"] += 1    # titledb sucht gleich nach dem Abgleich der IDs
            continue
        kinds["fraglich" if (e.get("ids_suspect") or {}).get(fam)
              else "erneut" if fam in e["ids_checked"] else "neu"] += 1
        found, reached = [], False
        for lookup in countries.FAMILY_LOOKUP[fam]:
            if pages >= EXTRA_PER_SYNC:
                break
            pages += 1
            try:
                info = sources.fetch_item(slug, lookup, fetch=fetch)
            except sources.FetchError as err:
                fails += 1
                if err.status in sources.BLOCKED or fails >= 4:
                    _log(f"IDs fehlender DLC unterbrochen ({err}), Rest beim nächsten Abgleich")
                    store.save_data(data)
                    if report:
                        _log_extra_ids(extra, glangs, fams, now)
                    return
                sleep(LOW_PAUSE)
                continue
            reached, fails = True, 0
            # Die Seite nennt auch die Pakete des DLC: nebenbei merken, kein eigener Abruf
            _log_links(update_links(data, slug, info.get("related") or {}, now))
            sleep(LOW_PAUSE)
            if info["nsuids"]:
                found = info["nsuids"]
                break
        if reached and (e.get("ids_suspect") or {}).get(fam):
            settle_ids(e, fam, found, now, ((data.get("rel") or {}).get(slug) or {}).get("title") or slug)
            e["ids_checked"][fam] = now
        elif reached:
            e["ids"][fam] = found
            e["ids_checked"][fam] = now
            # Erfolglose Suchen zählen: was DekuDeals zweimal nicht kennt, steht meist nicht
            # (mehr) im eShop, etwa Inhalte, die es nur im Spiel gibt (0.48)
            misses = e.setdefault("ids_misses", {})
            misses[fam] = 0 if found else misses.get(fam, 0) + 1
            if found and slug not in extra:
                # Spiel-ID neu: Sprache dort gleich fragen, die DLC-Seite zählt nicht mehr
                for k in ("langs_checked", "langs_tries"):
                    (e.get(k) or {}).pop(fam, None)
        status["done"] += 1
    store.save_data(data)
    _log("IDs fehlender DLC gesucht: " + ", ".join(f"{n} {k}" for k, n in kinds.items() if n))
    if report:
        _log_extra_ids(extra, glangs, fams, now)


def _recheck(e, fam):
    """Abstand bis zur nächsten DekuDeals-Suche nach einer fehlenden ID. Kennt auch titledb
    den DLC in dieser Region nicht (0.47) oder fand DekuDeals zweimal keine (0.48), gibt es
    ihn dort meist nicht: DekuDeals nur noch selten, titledb sieht weiter wöchentlich nach."""
    if fam in (e.get("tdb_ids") or {}) or (e.get("ids_misses") or {}).get(fam, 0) >= ID_MISSES:
        return ID_RECHECK_LONG
    return ID_RECHECK_SECONDS


def _log_extra_ids(extra, glangs, fams, now):
    """Stand der ID-Suche fürs Protokoll: je Region gefunden, noch nie gesucht, ohne ID
    (Wiederholung nach ID_RECHECK_SECONDS, ID_RECHECK_LONG) und wann die nächste Wiederholung fällig ist."""
    games = [g for g in glangs.values() if "ids_checked" in g]
    parts, nxt = [], None

    def count(mine, fam):
        found = sum(1 for e in mine if (e.get("ids") or {}).get(fam))
        never = sum(1 for e in mine if fam not in (e.get("ids_checked") or {}))
        return f"{found} gefunden" + (f", {never} noch nie gesucht" if never else "") \
            + (f", {len(mine) - found - never} ohne ID" if len(mine) - found - never else "")
    for fam in fams:
        # Spiele zählen getrennt: Ihre ID braucht es für die Sprache (0.51, Europa seit 0.53)
        parts.append(f"{fam} {count(list(extra.values()), fam)}"
                     + (f" (Spiele {count(games, fam)})" if games else ""))
        for e in list(extra.values()) + games:
            if not (e.get("ids") or {}).get(fam) and fam in (e.get("ids_checked") or {}):
                due = e["ids_checked"][fam] + _recheck(e, fam)
                nxt = due if nxt is None else min(nxt, due)
    line = f"Fehlende DLC der Sammlung: {len(extra)} DLC, {len(games)} Spiele; IDs " \
        + "; ".join(parts)
    if nxt:
        line += ". Nächste Wiederholung ohne ID: " + ("jetzt fällig" if nxt <= now else
                                                     datetime.fromtimestamp(nxt).strftime("%d.%m."))
    _log(line)


def _better(new, cur):
    """Bei mehreren Versionen eines Titels gewinnt die günstigste kaufbare."""
    if (new["status"] == "onsale") != (cur["status"] == "onsale"):
        return new["status"] == "onsale"
    return new.get("discount", new.get("regular", 9e18)) < \
        cur.get("discount", cur.get("regular", 9e18))


def clean_ids(data):
    """Bis 0.46.0 konnte eine andere 14-stellige Zahl aus einem Nintendo-Link als ID gelten.
    Solche IDs entfernen; bleibt keine, sucht der Abgleich die Region neu."""
    dropped = 0
    for coll in ("items", "extra", "glangs"):
        for rec in (data.get(coll) or {}).values():
            for fam, ids in list(((rec or {}).get("ids") or {}).items()):
                good = [n for n in ids or [] if sources.NSUID_OK.match(str(n))]
                if len(good) != len(ids or []):
                    dropped += len(ids) - len(good)
                    rec["ids"][fam] = good
                    if not good:
                        (rec.get("ids_checked") or {}).pop(fam, None)
    if dropped:
        _log(f"{dropped} ungültige Nintendo-IDs entfernt")
    return dropped


def remember_eshop(data):
    """Zuordnungen aus dem eShop-Kaufverlauf festhalten, solange Wishlist und fehlende DLC
    sie noch kennen: Ein gekaufter DLC verschwindet danach aus den fehlenden DLC."""
    found = {r["key"]: (r["slug"], r["how"]) for r in planner.eshop_matches(data)["rows"]
             if r["how"] in ("id", "title")}
    if found and store.remember_eshop_matches(found):
        data["_eshop"] = store.load_eshop_history()


def import_eshop_history(text, now=None):
    """Ergebnis des Browser-Helfers „Käufe lesen“ einlesen:
    {"region": "BR", "entries": [{"id", "title", "date"}]} oder nur die Liste."""
    try:
        found = json.loads(text or "")
    except ValueError:
        raise ValueError("Das ist nicht der Text des Browser-Helfers (JSON erwartet)")
    region, newest, complete = "", 0, True
    if isinstance(found, dict):
        complete = found.get("complete") is not False
        region = str(found.get("region") or "")[:4]
        # Nur ein lückenloser Lauf setzt den Stand, ab dem das Lesezeichen künftig liest
        if found.get("complete") is True:
            try:
                newest = int(found.get("newest") or 0)
            except (TypeError, ValueError):
                newest = 0
        found = found.get("entries")
    if not isinstance(found, list):
        raise ValueError("Das ist nicht der Text des Browser-Helfers (Liste erwartet)")
    entries = []
    for e in found[:3000]:
        if not isinstance(e, dict) or not str(e.get("title") or "").strip():
            continue
        nid = str(e.get("id") or "").strip()[:20]
        title = " ".join(str(e["title"]).split())[:200]
        date = str(e.get("date") or "")[:25]
        # Schlüssel: die Vorgangsnummer von Nintendo (gilt fürs ganze Konto, auch nach einem
        # Länderwechsel), sonst ID oder Titel mit Datum
        k = str(e.get("k") or "").strip()[:40]
        entries.append({"key": f"nin:{k}" if k else f"{nid or title}|{date}", "id": nid,
                        "title": title, "date": date, "region": str(e.get("region") or region)[:4],
                        "type": str(e.get("type") or "")[:30], "item": str(e.get("item") or "")[:30],
                        "amount": str(e.get("amount") or "")[:30], "plat": str(e.get("plat") or "")[:10]})
    new, total = store.merge_eshop_history(entries, now or time.time(), newest,
                                           len(store.load_data().get("owned") or []))
    data = store.load_data()
    remember_eshop(data)
    rows = planner.eshop_matches(data)["rows"]
    return {"read": len(entries), "new": new, "total": total, "complete": complete,
            "matched": sum(1 for r in rows if r["slug"]),
            "open": sum(1 for r in rows if r["how"] is None)}


def run_sync(fetch=sources.fetch, sleep=time.sleep):
    if not _lock.acquire(blocking=False):
        return False
    status.update(running=True, ok=None, log=[], finished=None,
                  started=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    sources.item_cache = {}       # eine DekuDeals-Seite je Abgleich nur einmal holen (0.54.1)
    sources.deku_blocked = 0      # eine Sperre von DekuDeals beendet alle DekuDeals-Schritte (0.56.1)
    try:
        settings = store.load_settings()
        data = store.load_data()
        if not settings["wishlist_url"]:
            raise RuntimeError("Kein Wishlist-Link in den Einstellungen")
        if not data.get("last_sync") and not data.get("lows"):
            data["lows_v"] = LOWS_VERSION      # frische Installation, nichts neu zu laden
        # Nach einer Sperre ruht DekuDeals DEKU_REST_SECONDS, auch über Abgleiche hinweg (0.64)
        resting = time.time() < (data.get("deku_wait") or 0)
        if resting:
            sources.deku_blocked = 429
            _log("DekuDeals ruht nach einer Sperre bis " + datetime.fromtimestamp(data["deku_wait"], timezone.utc)
                 .isoformat(timespec="minutes") + "; es gelten die zuletzt gelesenen Listen und Seiten")
        clean_ids(data)
        remember_eshop(data)
        _step("Wishlist lesen")
        sync_wishlist(data, settings, fetch, sleep)
        sync_collection(data, settings, fetch, sleep)
        remember_eshop(data)
        if "owned" in data:            # ohne gelesene Sammlung nichts aufräumen
            prune_old(data)
        store.save_data(data)
        sync_ids(data, settings, fetch, sleep)
        sync_nso(data, settings, fetch, sleep)
        sync_fx(data, fetch)
        history = store.load_history()
        sync_prices(data, settings, fetch, sleep, history)
        store.save_history(history)
        sync_card_prices(data, settings, fetch, sleep)
        sync_offer_prices(data, settings, fetch, sleep)
        record_card_factors(data, settings)
        self_check(data, settings)
        data["last_sync"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        store.save_data(data)      # ab hier ist die Oberfläche aktuell
        langs_budget = {}         # höchstens LANG_PER_SYNC Seiten je Region im ganzen Abgleich
        sync_langs(data, settings, fetch, sleep, budget=langs_budget)
        if data.get("lows_v") != LOWS_VERSION:
            # Frühere Versionen lasen teils den Händler- statt den digitalen
            # Tiefstpreis. Von DekuDeals übernommene Werte neu laden.
            for table in data.get("lows", {}).values():
                for e in table.values():
                    if e.get("src") == "deku":
                        for k in ("low", "src", "checked"):
                            e.pop(k, None)
            data["lows_v"] = LOWS_VERSION
            _log("Tiefstpreise werden neu geladen (Lesefehler bei Spielen für Switch und Switch 2 behoben)")
        sync_lows(data, settings, fetch, sleep)
        sync_related(data, settings, fetch, sleep)
        sync_extra_ids(data, settings, fetch, sleep, report=False)
        sync_titledb(data, settings, fetch)     # nach der ID-Suche, damit neue IDs gleich dabei sind
        sync_eshop_names(data, fetch)           # Kauftitel aus Japan und anderen Ländern zuordnen (0.72)
        # Stand der ID-Suche erst jetzt, mit den IDs aus titledb (0.48.1)
        _log_extra_ids(data.get("extra") or {}, data.get("glangs") or {}, needed_families(settings), time.time())
        sync_langs(data, settings, fetch, sleep, budget=langs_budget, report_idle=False)    # Sprachen der neu gefundenen DLC
        if sources.deku_blocked and not resting:
            data["deku_wait"] = time.time() + DEKU_REST_SECONDS
            _log(f"DekuDeals hat gesperrt (HTTP {sources.deku_blocked}): Die nächsten {DEKU_REST_SECONDS // 3600} Stunden fragt kein Abgleich dort an")
        elif not resting:
            data.pop("deku_wait", None)
        store.save_data(data)
        status["ok"] = True
        _step("Fertig")
    except Exception as e:
        status["ok"] = False
        _log(f"Abbruch: {e}")
        traceback.print_exc()
    finally:
        sources.item_cache = None
        sources.deku_blocked = None
        status.update(running=False,
                      finished=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        _lock.release()
    return True


def diagnose(sleep=time.sleep):
    """Prüft alle Datenquellen einzeln und beschreibt, was zurückkommt."""
    settings = store.load_settings()
    data = store.load_data()
    lines = [f"eShop-Kompass {sources.VERSION}"]

    deku = {"n": 0, "blocked": 0}

    def probe(name, url, ua, extra=None):
        # DekuDeals schonend auch hier (0.64): 1 s Pause zwischen den Proben, nach einer Sperre keine mehr
        if "dekudeals.com" in url:
            if deku["blocked"]:
                lines.append(f"{name}: nicht angefragt, DekuDeals sperrte vorher (HTTP {deku['blocked']})")
                return {"url": url, "status": 0, "text": "", "enc": "", "server": "", "error": "übersprungen"}
            if deku["n"]:
                sleep(DEKU_PAUSE)
            deku["n"] += 1
        r = sources.request(url, ua, timeout=20)
        if "dekudeals.com" in url and r["status"] in sources.BLOCKED:
            deku["blocked"] = r["status"]
        if r["error"]:
            lines.append(f"{name}: keine Verbindung ({r['error']})")
            return r
        try:
            info = extra(r["text"]) if extra else f"{len(r['text'])} Zeichen"
        except Exception as e:        # ein Lesefehler soll nicht den ganzen Test abbrechen
            info = f"{len(r['text'])} Zeichen, nicht auswertbar ({type(e).__name__}: {e})"
        lines.append(f"{name}: HTTP {r['status']}, Server {r['server'] or '?'}, "
                     f"Kodierung {r['enc'] or 'keine'}, {info}")
        return r

    try:
        wid = sources.wishlist_id(settings["wishlist_url"])
        probe("Wishlist", f"https://www.dekudeals.com/wishlist/{wid}?page=1", None, sources.describe)
    except ValueError as e:
        lines.append(f"Wishlist: {e}")
    slug = next((s for s, it in data["items"].items() if it.get("active")), "hades")

    def item_info(text):
        info = sources.parse_item_page(text)
        return (f"Titel „{(info['title'] or '')[:50]}“, IDs {info['nsuids']}, "
                f"Tiefstpreis {info['low']}")
    item = probe(f"Artikelseite {slug}", f"https://www.dekudeals.com/items/{slug}?country=de",
              None, item_info)
    probe("Nintendo-Preise", sources.NINTENDO_PRICE_URL + "?country=DE&lang=de&ids=70010000000126",
          None, lambda t: t[:160])
    probe("Sprachen Europa", sources.SOLR_URL + "?q=*&fq=nsuid_txt:70010000005306"
          "&fl=nsuid_txt,language_availability&wt=json", None, lambda t: t[:200].replace("\n", " "))
    jp = next((it["ids"]["JP"][0] for it in data["items"].values()
               if it.get("active") and (it.get("ids") or {}).get("JP")), "70010000033130")
    # Japan liefert meist nur die JavaScript-Hülle: zeigen, was die Seite stattdessen enthält
    def jp_info(t):
        refs = sorted(set(sources.re.findall(r"""(?:src|href)=["']([^"']{4,90})""", t)))[:8]
        if sources.parse_langs_jp(t) is None and len(t) < sources.JP_WAITING:
            return f"{len(t)} Zeichen, Warteraum (Queue-it), keine Produktseite; Sprachen aus titledb und Browser-Helfer"
        return (f"{len(t)} Zeichen, Sprachen: {sources.parse_langs_jp(t)}, "
                f"Titel „{sources.page_title(t)[:60]}“, Anfang: {sources.visible_text(t)[:160]}, "
                f"Verweise: {' '.join(refs)}")
    probe(f"Sprachen Japan ({jp})", sources.JP_STORE_URL.format(nsuid=jp), None, jp_info)
    # Amerika: Weiterleitung auf nintendo.com, Sprachen aus Seitendaten oder Text
    am = next((it["ids"]["AM"][0] for it in data["items"].values()
               if it.get("active") and (it.get("ids") or {}).get("AM")), "70010000000025")

    def am_info(t):
        spots = [t[max(0, m.start() - 60):m.start() + 200].replace("\n", " ")
                 for m in sources.re.finditer(r"(?i)supported.?languages|\"languages\"", t)][:3]
        return (f"{len(t)} Zeichen, Sprachen: {sources.parse_langs_am(t)}, "
                f"Titel „{sources.page_title(t)[:60]}“, Fundstellen: {' | '.join(spots) or 'keine'}")
    probe(f"Sprachen Amerika ({am})", sources.AM_STORE_URL.format(nsuid=am), None, am_info)

    # Preisverlauf: DekuDeals liefert ihn als JSON in der Artikelseite (für Kurven im Tool)
    text = item["text"]
    for sid in ("price_history_data", "price_history_indices"):
        m = sources.re.search(r"""<script[^>]*id=["']""" + sid + r"""["'][^>]*>(.*?)</script>""",
                              text, sources.re.S)
        lines.append(f"Verlauf, {sid}: " + (f"{len(m.group(1))} Zeichen, Anfang: {m.group(1)[:300]}"
                                            if m else "nicht gefunden"))
    # Wie zeigt DekuDeals Komplettfassungen, DLC und Upgrade-Pakete? Grundlage für später.
    seen = set()
    for m in sources.re.finditer(r"(?i)included in|dlc for|upgrade pack|switch 2 edition", text):
        key = m.group(0).lower().strip()
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"Pakete, Fundstelle „{key}“: "
                     + text[max(0, m.start() - 80):m.start() + 260].replace("\n", " "))
    if not seen:
        lines.append("Pakete: auf dieser Artikelseite keine Fundstelle")
    try:
        cid = sources.wishlist_id(settings.get("collection_url") or settings["wishlist_url"])
        probe("Sammlung", f"https://www.dekudeals.com/collection/{cid}?page=1", None, sources.describe)
    except ValueError as e:
        lines.append(f"Sammlung: {e}")
    # DLC und Pakete: was die Artikelseite eines Spiels aus der Sammlung nennt
    rel = data.get("rel") or {}
    owned = data.get("owned") or []
    game = next((s for s in owned if (rel.get(s) or {}).get("dlc")), owned[0] if owned else "mario-kart-8-deluxe")

    def rel_info(t):
        r = sources.parse_related(t)
        m = sources.re.search(r"(?i)<h[1-6][^>]*>(?:(?!</h).)*?\bDLC\b", t, sources.re.S)
        return ("; ".join(f"{k}: {len(v)} ({', '.join(n for _, n in v[:3])})" for k, v in r.items() if k != "found")
                + f"; Abschnitte: {', '.join(r.get('found') or []) or 'keine'}"
                + (", Ausschnitt: " + sources.re.sub(r"\s+", " ", t[m.start():m.start() + 400]) if m else
                   ", keine Überschrift DLC"))
    probe(f"DLC und Pakete ({game})", f"https://www.dekudeals.com/items/{game}?country=de", None, rel_info)
    # Steht Cashback in der Seite? Dann ließe es sich je Karte prüfen
    def cashback_spots(t):
        spots = [t[max(0, m.start() - 80):m.start() + 120].replace("\n", " ")
                 for m in sources.re.finditer(r"(?i)cash.?back", t)][:3]
        return " | ".join(spots) or "nicht gefunden"

    # Guthabenkarten: liefert die erste eingetragene Shopseite einen lesbaren Preis?
    links = [(code, x["url"]) for code in countries.ORDER
             for x in planner.parse_card_list(settings["countries"][code].get("cards")) if x["url"]]
    if links:
        code, url = links[0]
        probe(f"Guthabenkarte {code} ({urllib.parse.urlsplit(url).netloc})", url, None,
              lambda t: f"{len(t)} Zeichen, Titel „{sources.page_title(t)[:60]}“, "
                        f"Preis in Produktdaten: {sources.parse_ld_price(t)}, alle Angaben: "
                        f"{sorted(sources.ld_prices(t))[:12]}, Anfang: {sources.visible_text(t)[:100]}, "
                        f"Cashback: {cashback_spots(t)}")
    else:
        lines.append("Guthabenkarte: keine Karte mit Link eingetragen, Eneba nicht geprüft")
    probe("Wechselkurse", sources.FX_URL, None, lambda t: t[:80])
    probe("Wechselkurse, Ersatzquelle", sources.FX_FALLBACK_URL, None, lambda t: t[:80])
    # titledb nur mit Kopfdaten: Die Datei hat rund 25 MB (0.54.1)
    url = sources.TITLEDB_URL.format("JP.ja")
    h = sources.head(url)
    lines.append(f"titledb (JP.ja): keine Verbindung ({h['error']})" if h["error"] else
                 f"titledb (JP.ja): HTTP {h['status']}, Größe {int(h['size']) // 1_000_000 if (h['size'] or '').isdigit() else '?'} MB, "
                 f"Stand {h['modified'] or '?'}")
    lines.extend(membership_probe(probe, sleep))
    # Angebote der Mitgliedschaft von Hand (ab 0.60): Ließe sich der Preis lesen? Je Link ein Abruf
    # mit ehrlicher Kennung; eine Prüfseite (Captcha) wird nur gemeldet, nicht umgangen.
    for x in [x for x in (settings.get("nso_extra") or []) + (settings.get("own_offers") or []) if x.get("url")][:4]:
        def shop_info(t, x=x):
            if sources.is_amazon(x["url"]) and sources.amazon_captcha(t):
                return f"{len(t)} Zeichen, Prüfseite (Captcha), nicht lesbar, eingetragen {x['price']}"
            amz = sources.parse_amazon_price(t, sources.amazon_currency(x["url"])) if sources.is_amazon(x["url"]) else None
            found = sources.parse_shop_price(x["url"], t)
            yen = sorted(set(re.findall(r'a-offscreen">\s*([^<]{1,20}?)\s*<', t)))[:8]
            return (f"{len(t)} Zeichen, Titel „{(sources.page_title(t) or '')[:60]}“, "
                    f"gelesen {found[0]:g} {found[1]}{f' ({amz[2]})' if amz else ''}" if found else
                    f"{len(t)} Zeichen, Titel „{(sources.page_title(t) or '')[:60]}“, kein Preis erkannt") + \
                f", Beträge auf der Seite {yen or 'keine'}, eingetragen {x['price']}"
        probe(f"Mitgliedschaft {x['src']} ({x['code']}, {x['key']})" if x.get("key") else
              f"Eigenes Angebot {x['src']} ({x['code']}, {x['slug']})", x["url"], None, shop_info)
        sleep(2)
    return lines


MEMBERSHIP_SLUG = next(v["slug"] for v in planner.NSO_VARIANTS if v["key"] == "m12")


def membership_probe(probe, sleep=time.sleep):
    """Online-Mitgliedschaft (Vorarbeit, Entscheidung 13.10.2026): Woher kommen Preise je Land?
    DekuDeals nennt im Preistabellen-Link die eShop-ID je Land (data-out-analytics-id
    „eshop_de:7008…“, 0.53.5 im echten HTML gesehen); ob die Preis-Schnittstelle sie kennt,
    zeigt die zweite Probe. Nur Probe, nichts wird gespeichert."""
    lines, ids = [], {}

    def deku_info(country):
        def info_of(t):
            info = sources.parse_item_page(t)
            hist = sources.parse_history(t)
            for cc, nsuid in sources.re.findall(r"eshop_([a-z]{2}):(7\d{13})", t):
                ids.setdefault(cc.upper(), [])
                if nsuid not in ids[cc.upper()]:
                    ids[cc.upper()].append(nsuid)
            # Andere Varianten (3 Monate, Familie, Erweiterungspaket): ihre Adressen bei DekuDeals
            variants = sorted(set(sources.re.findall(r"/items/(nintendo-switch-online[a-z0-9-]*)", t)) - {MEMBERSHIP_SLUG})
            return (f"Titel „{(sources.page_title(t) or '')[:60]}“, Tiefstpreis {info['low']}, "
                    f"eShop-IDs {ids.get(country.upper(), [])}, alle Länder {sorted(info.get('eshop_ids') or {})}, Verlauf: {len(hist)} Tage"
                    f"{', zuletzt ' + str(hist[-2:]) if hist else ''}, weitere Varianten: {', '.join(variants) or 'keine verlinkt'}")
        return info_of
    # JP und US seit 0.56.1: In Japan fehlte der Preis, die Probe zeigt, ob DekuDeals dort eine eShop-ID nennt
    for country in ("de", "br", "jp", "us"):
        probe(f"Mitgliedschaft DekuDeals ({country.upper()})",
              f"https://www.dekudeals.com/items/{MEMBERSHIP_SLUG}?country={country}", None, deku_info(country))
        sleep(LOW_PAUSE)
    for code, lang in (("DE", "de"), ("BR", "pt"), ("JP", "ja")):
        if not ids.get(code):
            lines.append(f"Mitgliedschaft Nintendo-Preise ({code}): keine eShop-ID bei DekuDeals, nicht abgefragt")
            continue
        probe(f"Mitgliedschaft Nintendo-Preise ({code})",
              sources.NINTENDO_PRICE_URL + f"?country={code}&lang={lang}&ids={','.join(ids[code][:10])}",
              None, lambda t: t[:500])
        sleep(1)
    # Nintendos eigene Mitgliedschaftsseite (ab 0.58 Quelle der IDs je Region): Zuordnung je Variante
    # und die Preise dazu, so lässt sie sich gegen die Seite im Browser prüfen
    labels = {v["key"]: v["label"] for v in planner.NSO_VARIANTS}
    for fam, (code, lang) in NSO_PAGES.items():
        found = {}

        def ec_page(t, found=found):
            found.update(sources.parse_membership_page(t))
            return (f"{len(t)} Zeichen, Titel „{(sources.page_title(t) or '')[:60]}“, Varianten: "
                    + (", ".join(f"{labels[k]} {n}" for k, n in found.items()) or "keine erkannt"))
        probe(f"Mitgliedschaft Nintendo-Seite ({code})", f"https://ec.nintendo.com/{code}/{lang}/membership", None, ec_page)
        sleep(1)
        if found:
            def amounts(t, found=found):
                by = {str(p.get("title_id")): p for p in json.loads(t).get("prices") or []}
                out = []
                for k, n in found.items():
                    p = by.get(n) or {}
                    rp = p.get("discount_price") or p.get("regular_price") or {}
                    out.append(f"{labels[k]} {rp.get('amount') or p.get('sales_status') or '–'}")
                return ", ".join(out)
            probe(f"Mitgliedschaft Preise der Nintendo-Seite ({code})",
                  sources.NINTENDO_PRICE_URL + f"?country={code}&lang={lang}&ids={','.join(found.values())}", None, amounts)
            sleep(1)
    return lines


def start_sync():
    if status["running"]:
        return False
    threading.Thread(target=run_sync, daemon=True).start()
    return True


BOOT_DELAY = 300          # Abgleich so lange nach jedem Start, etwa nach einem Update
BOOT_MIN_AGE = 1800       # außer der letzte ist jünger, so bleibt es bei Neustarts schonend


def sync_due(last_sync, refresh_hours, now, boot_at=None, failed_at=None):
    """Ist ein Abgleich fällig? Nach Ablauf des Intervalls oder einmal nach dem Start,
    nach einem Fehlschlag frühestens eine Stunde später."""
    if failed_at and (now - datetime.fromisoformat(failed_at)).total_seconds() < 3600:
        return False
    if not last_sync:
        return True
    age = (now - datetime.fromisoformat(last_sync)).total_seconds()
    if boot_at and now >= boot_at and age >= BOOT_MIN_AGE:
        return True
    return age >= max(1.0, refresh_hours) * 3600


def scheduler():
    """Läuft im Hintergrund und gleicht nach Ablauf des Intervalls ab, außerdem
    einmal einige Minuten nach jedem Start."""
    boot_at = datetime.now(timezone.utc) + timedelta(seconds=BOOT_DELAY)
    status["boot_sync"] = boot_at.isoformat(timespec="seconds")
    time.sleep(5)
    while True:
        try:
            settings = store.load_settings()
            data = store.load_data()
            now = datetime.now(timezone.utc)
            if boot_at and data.get("last_sync") and \
                    (now - datetime.fromisoformat(data["last_sync"])).total_seconds() < BOOT_MIN_AGE:
                boot_at = None                 # gerade erst abgeglichen
            failed = status["finished"] if status["ok"] is False else None
            if sync_due(data.get("last_sync"), settings["refresh_hours"], now, boot_at, failed) \
                    and settings["wishlist_url"] and not status["running"]:
                run_sync()
                boot_at = None
            if boot_at is None:
                status["boot_sync"] = None
        except Exception:
            traceback.print_exc()
        time.sleep(min(300, max(5, (boot_at - datetime.now(timezone.utc)).total_seconds() + 1))
                   if boot_at else 300)
