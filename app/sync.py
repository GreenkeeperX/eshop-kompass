"""Abgleich: Wishlist -> Titel-IDs je Region -> Preise je Land -> Wechselkurse."""
import re
import threading
import time
import traceback
import urllib.parse
from datetime import datetime, timezone

from . import countries, planner, sources, store

ID_RECHECK_SECONDS = 14 * 24 * 3600   # fehlende IDs alle zwei Wochen neu suchen
DEKU_PAUSE = 1.0                      # Sekunden zwischen DekuDeals-Abrufen
NINTENDO_PAUSE = 0.3
LOW_PAUSE = 2.5                       # Tiefstpreise gemächlich nachladen
LOW_RECHECK_SECONDS = 30 * 24 * 3600  # Seiten ohne Tiefstpreis monatlich neu prüfen
LOWS_VERSION = 2                      # erhöht sich, wenn Tiefstpreise neu zu laden sind
LANG_RECHECK_SECONDS = 30 * 24 * 3600 # fehlende Sprachangaben monatlich neu prüfen
PRICE_FAIL_PAUSE = 7 * 24 * 3600      # abgeschaltete Länder ohne Preisantwort ruhen lassen
CARD_RECHECK_SECONDS = 20 * 3600      # Kartenpreise höchstens einmal am Tag lesen
CARD_PAUSE = 3.0

status = {"running": False, "step": "", "done": 0, "total": 0,
          "log": [], "started": None, "finished": None, "ok": None}
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
    except sources.FetchError:
        for line in sources.attempts:      # was DekuDeals je Kennung geantwortet hat
            _log("  " + line)
        raise RuntimeError("Wishlist nicht lesbar, Einzelheiten stehen darüber")
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
            if it["ids"].get(fam):
                continue
            if now - it["ids_checked"].get(fam, 0) < ID_RECHECK_SECONDS:
                continue
            todo.append((slug, fam))
    _step("Titel-IDs suchen", len(todo))
    misses = 0
    for slug, fam in todo:
        it = data["items"][slug]
        found, reached = [], False
        for lookup in countries.FAMILY_LOOKUP[fam]:
            try:
                info = sources.fetch_item(slug, lookup, fetch=fetch)
            except sources.FetchError as e:
                _log(f"{slug} ({lookup}): {e}")
                misses += 1
                if e.status in sources.BLOCKED:
                    store.save_data(data)
                    raise RuntimeError(f"DekuDeals lehnt Abrufe ab (HTTP {e.status}), "
                                       "nächster Versuch beim nächsten Abgleich")
                if misses >= 6:            # nicht hundertfach gegen eine Sperre anrennen
                    for line in sources.attempts:
                        _log("  " + line)
                    store.save_data(data)
                    raise RuntimeError("Artikelseiten bei DekuDeals nicht lesbar")
                sleep(DEKU_PAUSE)
                continue
            reached, misses = True, 0
            if info["title"]:
                it["title"] = info["title"]
            if info["parent"]:
                it["parent"] = info["parent"]
                if info["parent_title"]:
                    it["parent_title"] = info["parent_title"]
            _store_low(data, settings, lookup.upper(), slug, info["low"], now)
            sleep(DEKU_PAUSE)
            if info["nsuids"]:
                found = info["nsuids"]
                break
        it["ids"][fam] = found
        if reached:  # bei Netzfehlern beim nächsten Abgleich erneut versuchen
            it["ids_checked"][fam] = now
        status["done"] += 1
        if status["done"] % 10 == 0:
            store.save_data(data)
    merge_aliases(data)
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


def _store_low(data, settings, code, slug, low, now):
    """Merkt sich den Tiefstpreis von DekuDeals für ein aktives Land."""
    cfg = settings["countries"].get(code)
    if not cfg or not cfg["enabled"]:
        return
    e = data.setdefault("lows", {}).setdefault(code, {}).setdefault(slug, {})
    e["checked"] = now
    if low and low > 0:
        e.update(low=low, src="deku")
    else:
        e.pop("low", None)
        e.pop("src", None)


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


def sync_prices(data, settings, fetch, sleep, history=None):
    # Abgeschaltete Länder laufen mit, solange die IDs ihrer Region bekannt sind:
    # ein Abruf je Land, dafür zeigt die Länderliste ihr Preisniveau.
    enabled = list(countries.ORDER)
    _step("Preise abrufen", len(enabled))
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    history = {} if history is None else history
    quiet = []
    for code in enabled:
        fam = countries.BY_CODE[code]["family"]
        by_nsuid = {}
        for slug, it in data["items"].items():
            if it.get("active"):
                for n in it["ids"].get(fam, []):
                    by_nsuid[n] = slug
        active = settings["countries"][code]["enabled"]
        failed = data.setdefault("price_fail", {})
        if not by_nsuid or (not active and time.time() - failed.get(code, 0) < PRICE_FAIL_PAUSE):
            status["done"] += 1
            continue
        try:
            res = sources.fetch_prices(code, list(by_nsuid), fetch=fetch,
                                       lang=countries.BY_CODE[code]["lang"],
                                       pause=lambda: sleep(NINTENDO_PAUSE))
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
        table = {}
        for nsuid, p in res.items():
            slug = by_nsuid.get(nsuid)
            if not slug:
                continue
            p = dict(p, nsuid=nsuid, fetched=stamp)
            cur = table.get(slug)
            if cur is None or _better(p, cur):
                table[slug] = p
        data["prices"][code] = table
        _track(data, history, code, table, stamp)
        buyable = sum(1 for p in table.values() if p["status"] == "onsale")
        if settings["countries"][code]["enabled"]:
            _log(f"{code}: {buyable} von {len(table)} Titeln kaufbar")
        status["done"] += 1
    if quiet:
        _log("Ohne Preise (abgeschaltete Länder): " + ", ".join(quiet))


def sync_card_prices(data, settings, fetch, sleep, now=None):
    """Liest die Preise der Guthabenkarten, die einen Link haben, von der Shopseite.

    Nur aktive Länder, höchstens einmal am Tag je Link. Liefert eine Seite
    keinen Preis, bleibt der von Hand eingetragene Wert.
    """
    now = now or time.time()
    prices = data.setdefault("card_prices", {})
    urls = []
    for code in countries.ORDER:
        cfg = settings["countries"][code]
        if not cfg["enabled"]:
            continue
        for x in planner.parse_card_list(cfg.get("cards")):
            if x["url"] and x["stock"] and x["url"] not in urls:
                urls.append(x["url"])
    for url in list(prices):                  # Links, die nicht mehr eingetragen sind
        if url not in urls:
            del prices[url]
    todo = [u for u in urls if now - (prices.get(u) or {}).get("checked", 0) >= CARD_RECHECK_SECONDS]
    if not todo:
        return
    _step("Kartenpreise lesen", len(todo))
    got = 0
    for url in todo:
        try:
            found = sources.fetch_card_price(url, fetch=fetch)
        except sources.FetchError as e:
            if e.status in sources.BLOCKED:
                _log(f"Kartenpreise: Shop lehnt Abrufe ab ({e}), Werte von Hand gelten weiter")
                break
            prices[url] = {"checked": now, "error": f"HTTP {e.status or 'Fehler'}"}
        else:
            if found:
                prices[url] = {"checked": now, "price": found[0], "currency": found[1]}
                got += 1
            else:
                prices[url] = {"checked": now, "error": "Seite nennt keinen Preis"}
        status["done"] += 1
        sleep(CARD_PAUSE)
    _log(f"Kartenpreise: {got} von {len(todo)} gelesen" +
         ("" if got == len(todo) else ", für die übrigen gilt der Wert von Hand"))


def sync_card_market(data, settings, fetch, sleep, now=None):
    """Kartenpreise je Land von gg.deals: eine Seite je Land, höchstens einmal am Tag.

    Die Seite nennt je Kartenwert den günstigsten Preis über alle Shops in Euro.
    Bei 403 oder 429 endet das Lesen, die bisherigen Werte gelten weiter.
    """
    now = now or time.time()
    market = data.setdefault("card_market", {})
    if not settings.get("card_market", True):
        return
    todo = []
    for code in countries.ORDER:
        cfg = settings["countries"][code]
        slug = countries.GGDEALS.get(code)
        if not slug or not cfg["enabled"] or (cfg["pay"] == "card" and code != countries.REFERENCE):
            continue
        if now - (market.get(code) or {}).get("checked", 0) >= CARD_RECHECK_SECONDS:
            todo.append((code, slug))
    if not todo:
        return
    _step("Kartenpreise bei gg.deals", len(todo))
    got = 0
    for code, slug in todo:
        url = sources.GGDEALS_URL.format(slug)
        currency = slug.split("-")[0].upper()
        old = market.get(code) or {}
        try:
            cards = sources.parse_ggdeals_group(fetch(url), currency)
        except sources.FetchError as e:
            if e.status in sources.BLOCKED:
                _log(f"Kartenpreise: gg.deals lehnt Abrufe ab ({e}), bisherige Werte gelten weiter")
                break
            market[code] = dict(old, checked=now, error=f"HTTP {e.status or 'Fehler'}")
        else:
            if cards:
                market[code] = {"checked": now, "url": url,
                                "cards": {str(f): {"price": p, "url": u} for f, (p, u) in cards.items()}}
                got += 1
            else:
                market[code] = dict(old, checked=now, error="Seite nennt keine Kartenpreise")
        status["done"] += 1
        sleep(CARD_PAUSE)
    _log(f"Kartenpreise gg.deals: {got} von {len(todo)} Ländern gelesen")


def log_implausible(data, settings):
    """Meldet gelesene Kartenpreise, die außerhalb des glaubhaften Bereichs liegen
    und deshalb nicht zählen (planner.CARD_PLAUSIBLE)."""
    try:
        ctx = planner.Context(data, settings)
    except Exception:
        return
    for code, c in ctx.countries.items():
        if c["implausible"]:
            _log(f"Kartenpreise {code}: unglaubhaft und ignoriert: " + ", ".join(
                f"{planner.num_txt(i['face'])} {c['currency'] or ''} für {planner._eur(i['price'])} ({i['src']})"
                for i in c["implausible"]))


def sync_langs(data, settings, fetch, sleep, now=None):
    """Sprachen je Region von Nintendo: Europa in einem Abruf, Japan je Titel."""
    now = now or time.time()
    items = {s: it for s, it in data["items"].items() if it.get("active")}

    def due(it, fam):
        if (it.get("langs") or {}).get(fam):
            return False
        return now - (it.get("langs_checked") or {}).get(fam, 0) > LANG_RECHECK_SECONDS

    eu = {it["ids"]["EU"][0]: s for s, it in items.items()
          if it["ids"].get("EU") and due(it, "EU")}
    if eu:
        _step("Sprachen abrufen")
        try:
            found = sources.fetch_langs_eu(list(eu), fetch=fetch)
        except Exception as e:
            _log(f"Sprachen Europa nicht abrufbar ({e})")
            found = None
        if found is not None:
            for nsuid, slug in eu.items():
                it = items[slug]
                it.setdefault("langs_checked", {})["EU"] = now
                if nsuid in found:
                    it.setdefault("langs", {})["EU"] = found[nsuid]
            _log(f"Sprachen Europa: {len(found)} von {len(eu)} Titeln")

    if settings["countries"]["JP"]["enabled"]:
        # DLC übernimmt die Sprache des Hauptspiels, eigene Seiten braucht es dafür nicht
        todo = [(s, it["ids"]["JP"][0]) for s, it in items.items()
                if it["ids"].get("JP") and due(it, "JP") and not it.get("parent")]
        got = fails = 0
        if todo:
            _step("Sprachen Japan abrufen", len(todo))
        for slug, nsuid in todo:
            it = items[slug]
            try:
                langs = sources.fetch_langs_jp(nsuid, fetch=fetch)
            except sources.FetchError as e:
                if e.status == 404:
                    langs = None           # keine Seite: als geprüft vermerken
                else:
                    fails += 1
                    if e.status in (403, 429) or fails >= 5:
                        _log(f"Sprachen Japan unterbrochen ({e})")
                        break
                    status["done"] += 1
                    sleep(DEKU_PAUSE)
                    continue
            it.setdefault("langs_checked", {})["JP"] = now
            if langs:
                it.setdefault("langs", {})["JP"] = langs
                got += 1
            status["done"] += 1
            sleep(DEKU_PAUSE)
        if todo:
            _log(f"Sprachen Japan: {got} von {len(todo)} Titeln")
    store.save_data(data)


def sync_lows(data, settings, fetch, sleep, now=None):
    """Lädt fehlende Tiefstpreise von DekuDeals nach, Angebote zuerst."""
    now = now or time.time()
    lows = data.setdefault("lows", {})
    todo = []
    for code in countries.ORDER:
        if not settings["countries"][code]["enabled"]:
            continue
        for slug, p in data["prices"].get(code, {}).items():
            if p.get("status") != "onsale" or not data["items"].get(slug, {}).get("active"):
                continue
            e = lows.get(code, {}).get(slug)
            if e and ("low" in e or now - e.get("checked", 0) < LOW_RECHECK_SECONDS):
                continue
            todo.append((0 if "discount" in p else 1, code, slug))
    todo.sort()
    if not todo:
        return
    _step("Tiefstpreise nachladen", len(todo))
    fails = 0
    for _, code, slug in todo:
        try:
            info = sources.fetch_item(slug, code.lower(), fetch=fetch)
        except sources.FetchError as e:
            if e.status in (403, 429) or fails >= 4:
                _log(f"Tiefstpreise unterbrochen ({e}), Rest beim nächsten Abgleich")
                break
            fails += 1
            sleep(LOW_PAUSE)
            continue
        low = info["low"]
        p = data["prices"][code][slug]
        if low and low > p.get("regular", 0) * 1.001:
            low = None                       # unplausibel
        cur = p.get("discount", p.get("regular"))
        if low and cur is not None and cur < low:
            low = cur
        _store_low(data, settings, code, slug, low, now)
        status["done"] += 1
        if status["done"] % 20 == 0:
            store.save_data(data)
        sleep(LOW_PAUSE)
    store.save_data(data)
    known = sum(1 for c in lows.values() for e in c.values() if "low" in e)
    _log(f"Tiefstpreise bekannt: {known}")


def _better(new, cur):
    """Bei mehreren Versionen eines Titels gewinnt die günstigste kaufbare."""
    if (new["status"] == "onsale") != (cur["status"] == "onsale"):
        return new["status"] == "onsale"
    return new.get("discount", new.get("regular", 9e18)) < \
        cur.get("discount", cur.get("regular", 9e18))


def run_sync(fetch=sources.fetch, sleep=time.sleep):
    if not _lock.acquire(blocking=False):
        return False
    status.update(running=True, ok=None, log=[], finished=None,
                  started=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    try:
        settings = store.load_settings()
        data = store.load_data()
        if not settings["wishlist_url"]:
            raise RuntimeError("Kein Wishlist-Link in den Einstellungen")
        if not data.get("last_sync") and not data.get("lows"):
            data["lows_v"] = LOWS_VERSION      # frische Installation, nichts neu zu laden
        _step("Wishlist lesen")
        sync_wishlist(data, settings, fetch, sleep)
        sync_collection(data, settings, fetch, sleep)
        store.save_data(data)
        sync_ids(data, settings, fetch, sleep)
        _step("Wechselkurse abrufen")
        try:
            rates, updated = sources.fetch_fx(fetch=fetch)
            data["fx"] = {"rates": rates, "updated": updated}
        except Exception as e:
            _log(f"Wechselkurse nicht aktualisiert ({e})")
        history = store.load_history()
        sync_prices(data, settings, fetch, sleep, history)
        store.save_history(history)
        sync_card_prices(data, settings, fetch, sleep)
        sync_card_market(data, settings, fetch, sleep)
        log_implausible(data, settings)
        data["last_sync"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        store.save_data(data)      # ab hier ist die Oberfläche aktuell
        sync_langs(data, settings, fetch, sleep)
        if data.get("lows_v") != LOWS_VERSION:
            # Frühere Versionen lasen teils den Händler- statt den digitalen
            # Tiefstpreis. Von DekuDeals übernommene Werte neu laden.
            for table in data.get("lows", {}).values():
                for e in table.values():
                    if e.get("src") == "deku":
                        for k in ("low", "src", "checked"):
                            e.pop(k, None)
            data["lows_v"] = LOWS_VERSION
            _log("Tiefstpreise werden neu geladen (nur digitale Preise)")
        sync_lows(data, settings, fetch, sleep)
        status["ok"] = True
        _step("Fertig")
    except Exception as e:
        status["ok"] = False
        _log(f"Abbruch: {e}")
        traceback.print_exc()
    finally:
        status.update(running=False,
                      finished=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        _lock.release()
    return True


def gg_excerpt(page_html):
    """HTML rund um die erste Kartenkachel, gekürzt: zeigt, wie Link und Preis stehen."""
    i = page_html.find("/gift-card/")
    if i < 0:
        return sources.visible_text(page_html)[:200]
    return re.sub(r"\s+", " ", page_html[max(0, i - 200):i + 900])


def diagnose():
    """Prüft alle Datenquellen einzeln und beschreibt, was zurückkommt."""
    settings = store.load_settings()
    data = store.load_data()
    lines = [f"eShop-Kompass {sources.VERSION}"]

    def probe(name, url, ua, extra=None):
        r = sources.request(url, ua, timeout=20)
        if r["error"]:
            lines.append(f"{name}: keine Verbindung ({r['error']})")
            return r
        info = extra(r["text"]) if extra else f"{len(r['text'])} Zeichen"
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
    r = probe(f"Artikelseite {slug}", f"https://www.dekudeals.com/items/{slug}?country=de",
              None, item_info)
    probe("Nintendo-Preise", sources.NINTENDO_PRICE_URL + "?country=DE&lang=de&ids=70010000000126",
          None, lambda t: t[:160])
    probe("Sprachen Europa", sources.SOLR_URL + "?q=*&fq=nsuid_txt:70010000005306"
          "&fl=nsuid_txt,language_availability&wt=json", None, lambda t: t[:200].replace("\n", " "))
    jp = next((it["ids"]["JP"][0] for it in data["items"].values()
               if it.get("active") and (it.get("ids") or {}).get("JP")), "70010000033130")
    # Japan meldete zuletzt keine Sprachen: zeigen, was die Seite stattdessen enthält
    def jp_info(t):
        refs = sorted(set(sources.re.findall(r"""(?:src|href)=["']([^"']{4,90})""", t)))[:8]
        return (f"{len(t)} Zeichen, Sprachen: {sources.parse_langs_jp(t)}, "
                f"Titel „{sources.page_title(t)[:60]}“, Anfang: {sources.visible_text(t)[:160]}, "
                f"Verweise: {' '.join(refs)}")
    probe(f"Sprachen Japan ({jp})", sources.JP_STORE_URL.format(nsuid=jp), None, jp_info)

    # Preisverlauf: DekuDeals liefert ihn als JSON in der Artikelseite (für Kurven im Tool)
    text = r["text"]
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
    # Guthabenkarten: liefert die erste eingetragene Shopseite einen lesbaren Preis?
    links = [(code, x["url"]) for code in countries.ORDER
             for x in planner.parse_card_list(settings["countries"][code].get("cards")) if x["url"]]
    if links:
        code, url = links[0]
        probe(f"Guthabenkarte {code} ({urllib.parse.urlsplit(url).netloc})", url, None,
              lambda t: f"{len(t)} Zeichen, Titel „{sources.page_title(t)[:60]}“, "
                        f"Preis in Produktdaten: {sources.parse_ld_price(t)}, Anfang: {sources.visible_text(t)[:140]}")
    else:
        lines.append("Guthabenkarte: keine Karte mit Link eingetragen, Eneba nicht geprüft")
    # gg.deals: Kartenwerte und Preise einer Gruppenseite, dazu ein Ausschnitt zum Nachbessern
    probe("Kartenpreise gg.deals (BR)", sources.GGDEALS_URL.format("brl-brazil"), None,
          lambda t: f"{len(t)} Zeichen, Titel „{sources.page_title(t)[:60]}“, gelesen: "
                    f"{ {f: p for f, (p, _) in sorted(sources.parse_ggdeals_group(t, 'BRL').items())} }, "
                    f"Ausschnitt: {gg_excerpt(t)}")
    probe("Wechselkurse", sources.FX_URL, None, lambda t: t[:80])
    return lines


def start_sync():
    if status["running"]:
        return False
    threading.Thread(target=run_sync, daemon=True).start()
    return True


def scheduler():
    """Läuft im Hintergrund und gleicht nach Ablauf des Intervalls ab."""
    time.sleep(5)
    while True:
        try:
            settings = store.load_settings()
            data = store.load_data()
            due = True
            if data.get("last_sync"):
                last = datetime.fromisoformat(data["last_sync"])
                age = (datetime.now(timezone.utc) - last).total_seconds()
                due = age >= max(1.0, settings["refresh_hours"]) * 3600
            if status["ok"] is False and status["finished"]:
                # nach einem Fehlschlag frühestens nach einer Stunde erneut
                last_try = datetime.fromisoformat(status["finished"])
                if (datetime.now(timezone.utc) - last_try).total_seconds() < 3600:
                    due = False
            if due and settings["wishlist_url"] and not status["running"]:
                run_sync()
        except Exception:
            traceback.print_exc()
        time.sleep(300)
