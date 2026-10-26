"""Zwischenspeicher (data.json) und Einstellungen (settings.json)."""
import json
import re
import os
import sys
import threading
from datetime import date, datetime, timezone

from . import countries

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))

DEFAULT_SETTINGS = {
    "wishlist_url": "",
    "collection_url": "",     # leer = Sammlung mit derselben Kennung wie die Wishlist
    "card_fee_pct": 1.75,     # Fremdwährungsgebühr der eigenen Karte
    "gift_markup_pct": 5.0,   # Schätzung: Aufschlag auf den Kurs, wenn kein Kartenpreis lesbar ist
    # Servicegebühr des Kartenshops auf gelesene Preise: fester Betrag plus Anteil.
    # Eneba, Okt. 2026: nachgerechnete Bestellungen passen auf den Cent zu 0,40 € + 7,75 %
    "shop_fee_pct": 7.75,
    "shop_fee_eur": 0.40,
    # ab dieser Ersparnis lohnt der Länderwechsel, je Stufe (leicht, mittel, schwer)
    "tier_min_saving": {"1": 3.0, "2": 8.0, "3": 20.0},
    "lang_rule": "exclude",   # Regionen ohne deutsche Fassung: exclude, warn, off
    # Sprachen von Hand bestätigt: {slug: {"JP": true, "AM": false}}
    "lang_confirm": {},
    # DLC in der Sammlung von Hand: {DLC: "have" | "ignore", Spiel: "ignore_all"}
    "dlc_marks": {},
    # Cashback des Kartenshops in Prozent, wenn es eins gibt. Nur für einen Hinweis,
    # nicht in den Preisen: Es gibt es nicht immer
    "cashback_pct": 0.0,
    "refresh_hours": 6,
    "current_country": "",    # Land, in dem das Nintendo-Konto gerade steht
    "nso_until": "",          # Online-Mitgliedschaft läuft bis (JJJJ-MM-TT), leer = unbekannt
    # Wann du das Ablaufdatum zuletzt gesetzt oder bestätigt hast (ab 0.88); nur Käufe danach
    # verlängern es. Ohne Angabe gilt das Erscheinen von 0.88: ältere Käufe sind schon eingetragen
    "nso_until_set": "2026-10-19T22:00:00+00:00",
    "nso_variant": "m12",     # deine Mitgliedschaft: m1, m3, m12, ep, fam, epfam (planner.NSO_VARIANTS)
    # Weitere Angebote der Mitgliedschaft von Hand, etwa Codes bei Amazon Japan (ab 0.60):
    # [{"key": "m12", "code": "JP", "price": 2970, "src": "Amazon", "url": "…", "date": "JJJJ-MM-TT"}]
    "nso_extra": [],
    "own_offers": [],         # eigene Angebote für Titel, etwa Codes bei Amazon Japan (ab 0.62)
    # Urteil im Radar: bis zu diesem Abstand zum Bestpreis in Euro gilt ein
    # Angebot als Kauf bzw. gutes Angebot, auch wenn es prozentual mehr ist
    # mini (0.92): Titel mit Bestpreis unter diesem Betrag sind Kleinkram, siehe planner.Context.mini
    "deal_eur": {"buy": 0.5, "good": 2.0, "mini": 2.0},
    # Auf Null (1.1.0): „Fast Null“ lässt höchstens left € Rest und kostet höchstens near € mehr;
    # „Genau Null“ hat keine Grenze (Entscheidung 20.10.2026)
    "zero": {"near": 10.0, "left": 0.5},
    # Euro-Guthaben (Deutschland mit Guthaben): Faktor bis zu diesem Wert gilt als Top, gut,
    # okay; darüber teuer. Stufen wie bei Kenixa (Entscheidung 13.10.2026)
    "eur_card_steps": {"top": 0.81, "good": 0.83, "ok": 0.86},
    "countries": countries.default_country_settings(),
}

# Was die Oberfläche sich merkt, für alle Geräte gleich
DEFAULT_UI = {"basket": None, "overrides": {}, "targets": {}, "hidden": [],
              "sort": "optimum", "dense": True, "plan_good": False, "plan_fill": {},
              "plan_skip": {}, "plan_assume": {}}

EMPTY_DATA = {"items": {}, "prices": {}, "lows": {}, "card_prices": {},
              "fx": {"rates": {"EUR": 1.0}, "updated": ""}, "last_sync": None}

lock = threading.RLock()


def _path(name):
    return os.path.join(DATA_DIR, name)


def _load(name, default):
    try:
        with open(_path(name), encoding="utf-8") as f:
            got = json.load(f)
        if type(got) is type(default):
            return got
        why = "falsche Form"
    except FileNotFoundError:
        return json.loads(json.dumps(default))
    except ValueError as e:
        why = str(e)[:80]
    # Kaputte Datei (0.99.2): nicht still durch die Vorgabe ersetzen, sonst überschriebe das nächste
    # Speichern sie endgültig. Sie bleibt daneben liegen, das Protokoll des Containers nennt sie
    keep = f"{_path(name)}.kaputt-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    try:
        os.replace(_path(name), keep)
        print(f"{name} nicht lesbar ({why}), aufgehoben als {os.path.basename(keep)}", file=sys.stderr)
    except OSError:
        pass
    return json.loads(json.dumps(default))


def _save(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _path(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())      # erst auf der Platte, dann umbenennen: kein leeres File nach Stromausfall
    os.replace(tmp, _path(name))


def load_settings():
    with lock:
        s = _load("settings.json", DEFAULT_SETTINGS)
        for k, v in DEFAULT_SETTINGS.items():
            s.setdefault(k, json.loads(json.dumps(v)))
        s.pop("card_market", None)    # gg.deals ist seit 0.20 ausgebaut
        if s.get("current_country") in countries.BY_CODE:   # bis 0.62 war DG als Konto wählbar
            s["current_country"] = countries.BY_CODE[s["current_country"]]["shop"]
        for group in ("tier_min_saving", "deal_eur", "eur_card_steps", "zero"):
            for k, value in DEFAULT_SETTINGS[group].items():
                s[group].setdefault(k, value)
        defaults = countries.default_country_settings()
        for code, d in defaults.items():
            cur = s["countries"].setdefault(code, d)
            for k, v in d.items():
                cur.setdefault(k, v)
        if s.get("settings_v", 0) < 1:
            # Bis 0.6 blockierte ein Rest in Japan den Wechsel. Dort verfällt er nur.
            s["countries"]["JP"]["rest_blocks"] = False
            s["settings_v"] = 1
        if s.get("settings_v", 0) < 2:
            # 0.8.1 schätzte die Eneba-Gebühr pauschal auf 10,5 %, gemessen sind 0,40 € + 7,75 %
            if s.get("shop_fee_pct") == 10.5:
                s["shop_fee_pct"] = DEFAULT_SETTINGS["shop_fee_pct"]
            s["settings_v"] = 2
        if s.get("settings_v", 0) < 3:
            # Bis 0.9.2 senkten deutsche Guthabenkarten die Vergleichsbasis selbst. Jetzt
            # bleibt Deutschland beim Shop-Preis, die Karten gehören zu „Deutschland mit Guthaben“.
            de, dg = s["countries"][countries.REFERENCE], s["countries"]["DG"]
            if de.get("cards"):
                dg["cards"] = de["cards"] if not dg.get("cards") else dg["cards"] + "\n" + de["cards"]
                dg["cards_checked"] = de.get("cards_checked", "")
                dg["enabled"] = True
                de["cards"], de["cards_checked"] = "", ""
            s["settings_v"] = 3
        if s.get("settings_v", 0) < 4:
            # Ab 0.36 blockiert ein Rest nirgends mehr den Wechsel: Er geht auch mit Guthaben,
            # über den Support. Der Rest verfällt oder wartet auf den nächsten Wechsel dorthin
            # (Entscheidung 12.10.2026). Wer es anders will, setzt den Haken wieder.
            for c in s["countries"].values():
                c["rest_blocks"] = False
            s["settings_v"] = 4
        if s.get("settings_v", 0) < 5:
            # Ab 0.52.1 kein Aufschlag je Land mehr: Werte ohne Link rechnen zum Kurs wie
            # Kartenzahlung, die Schätzung ohne Kartenpreis nimmt den allgemeinen Wert
            for c in s["countries"].values():
                c.pop("markup_pct", None)
            s["settings_v"] = 5
        if not s["wishlist_url"]:
            s["wishlist_url"] = os.environ.get("WISHLIST_URL", "")
        return s


NSO_KEYS = ("m1", "m3", "m12", "ep", "fam", "epfam")


def _nso_extra(e, known):
    """Ein Angebot der Mitgliedschaft von Hand prüfen; None, wenn es nicht passt."""
    if not isinstance(e, dict) or e.get("key") not in NSO_KEYS or e.get("code") not in known:
        return None
    try:
        price = float(e.get("price"))
    except (TypeError, ValueError):
        return None
    url = str(e.get("url") or "").strip()
    if price <= 0 or len(url) > 2000 or (url and not re.fullmatch(r"https?://[^\s\"'<>]+", url)):
        return None
    date = str(e.get("date") or "")
    return {"key": e["key"], "code": e["code"], "price": round(price, 2),
            "src": (str(e.get("src") or "").strip() or "Händler")[:30], "url": url,
            "date": date if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) else ""}


def _own_offer(e, known):
    """Ein eigenes Angebot für einen Titel prüfen (ab 0.62); None, wenn es nicht passt."""
    if not isinstance(e, dict) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,150}", str(e.get("slug") or "")):
        return None
    x = _nso_extra(dict(e, key=NSO_KEYS[0]), known)
    return x and {"slug": e["slug"], **{k: v for k, v in x.items() if k != "key"}}


def save_settings(new):
    """Übernimmt nur bekannte Felder mit passendem Typ."""
    with lock:
        s = load_settings()
        if isinstance(new.get("wishlist_url"), str):
            s["wishlist_url"] = new["wishlist_url"].strip()
        if isinstance(new.get("collection_url"), str):
            s["collection_url"] = new["collection_url"].strip()
        for k in ("card_fee_pct", "gift_markup_pct", "shop_fee_pct", "shop_fee_eur", "refresh_hours",
                  "cashback_pct"):
            if k in new:
                try:
                    s[k] = max(0.0, float(new[k]))
                except (TypeError, ValueError):
                    pass
        s["cashback_pct"] = min(50.0, s["cashback_pct"])
        if new.get("current_country") in list(s["countries"]) + [""]:
            # Ein Konto steht in einem Land mit eigenem Shop: „Deutschland (Guthaben)“ ist das deutsche (0.63)
            s["current_country"] = countries.BY_CODE[new["current_country"]]["shop"] if new["current_country"] else ""
        if isinstance(new.get("nso_until"), str) and re.fullmatch(r"(\d{4}-\d{2}-\d{2})?", new["nso_until"]):
            s["nso_until"] = new["nso_until"]
            # Käufe danach verlängern es (Vorschlag in planner.membership)
            s["nso_until_set"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if new.get("nso_variant") in NSO_KEYS:
            s["nso_variant"] = new["nso_variant"]
        if isinstance(new.get("nso_extra"), list):
            s["nso_extra"] = [x for x in (_nso_extra(e, s["countries"]) for e in new["nso_extra"][:30]) if x]
        if isinstance(new.get("own_offers"), list):
            s["own_offers"] = [x for x in (_own_offer(e, s["countries"]) for e in new["own_offers"][:60]) if x]
        if new.get("lang_rule") in ("exclude", "warn", "off"):
            s["lang_rule"] = new["lang_rule"]
        for slug, fams in (new.get("lang_confirm") or {}).items() if isinstance(
                new.get("lang_confirm"), dict) else []:
            if not isinstance(fams, dict) or not isinstance(slug, str) or len(slug) > 200:
                continue
            cur = s["lang_confirm"].setdefault(slug, {})
            for fam, value in fams.items():
                if fam not in ("JP", "AM", "AS"):
                    continue
                if isinstance(value, bool):
                    cur[fam] = value
                elif value is None:
                    cur.pop(fam, None)
            if not cur:
                del s["lang_confirm"][slug]
        marks = new.get("dlc_marks")
        for slug, value in marks.items() if isinstance(marks, dict) else []:
            if not isinstance(slug, str) or len(slug) > 200:
                continue
            if value in ("have", "ignore", "ignore_all", "missing"):
                s["dlc_marks"][slug] = value
            elif value is None:
                s["dlc_marks"].pop(slug, None)
        for tier, value in (new.get("tier_min_saving") or {}).items():
            if str(tier) in s["tier_min_saving"]:
                try:
                    s["tier_min_saving"][str(tier)] = max(0.0, float(value))
                except (TypeError, ValueError):
                    pass
        for k, value in (new.get("deal_eur") or {}).items():
            if k in s["deal_eur"]:
                try:
                    s["deal_eur"][k] = min(100.0, max(0.0, float(value)))
                except (TypeError, ValueError):
                    pass
        for k, value in (new.get("zero") or {}).items():
            if k in s["zero"]:
                try:
                    s["zero"][k] = min(1000.0, max(0.0, float(value)))
                except (TypeError, ValueError):
                    pass
        for k, value in (new.get("eur_card_steps") or {}).items():
            if k in s["eur_card_steps"]:
                try:
                    s["eur_card_steps"][k] = min(1.0, max(0.5, float(value)))
                except (TypeError, ValueError):
                    pass
        incoming = dict(new.get("countries") or {})
        de = incoming.get(countries.REFERENCE)
        if isinstance(de, dict) and ("cards" in de or "cards_add" in de):
            # Karten für Deutschland (etwa aus einer älteren Einlese-Datei) gehören jetzt
            # zu „Deutschland mit Guthaben“. Nur, wenn dort wirklich welche stehen (0.99.2): Jede
            # Sicherung hat für Deutschland leere Karten, und die leerten die von DG
            if str(de.get("cards") or "").strip() or de.get("cards_add"):
                dg = dict(incoming.get("DG") or {}, enabled=True)
                for k in ("cards", "cards_add"):
                    if de.get(k) and not dg.get(k):
                        dg[k] = de[k]
                incoming["DG"] = dg
            incoming[countries.REFERENCE] = {k: v for k, v in de.items() if k not in ("cards", "cards_add")}
        for code, c in incoming.items():
            if code not in s["countries"] or not isinstance(c, dict):
                continue
            cur = s["countries"][code]
            if "enabled" in c:
                cur["enabled"] = bool(c["enabled"])
            if c.get("pay") in ("card", "giftcard", "auto"):
                cur["pay"] = c["pay"]
            if str(c.get("tier")) in ("1", "2", "3"):
                cur["tier"] = int(c["tier"])
            if "tax_pct" in c:
                try:
                    cur["tax_pct"] = min(50.0, max(0.0, float(c["tax_pct"] or 0)))
                except (TypeError, ValueError):
                    pass
            if "rest_blocks" in c:
                cur["rest_blocks"] = bool(c["rest_blocks"])
            if "balance" in c:
                try:
                    cur["balance"] = max(0.0, float(c["balance"] or 0))
                except (TypeError, ValueError):
                    pass
            if isinstance(c.get("cards_add"), str):     # aus einer Datei: ergänzen statt ersetzen
                c = dict(c, cards=merge_cards(c.get("cards", cur["cards"]), c["cards_add"]))
            if isinstance(c.get("cards"), str) and c["cards"].strip() != cur["cards"]:
                cur["cards"] = c["cards"].strip()
                cur["cards_checked"] = date.today().isoformat() if cur["cards"] else ""
        s["countries"][countries.REFERENCE]["enabled"] = True
        _save("settings.json", s)
        return s


def merge_cards(text, add):
    """Ergänzt eine Kartenliste um Zeilen, ohne Vorhandenes zu verlieren.

    Gibt es den Kartenwert schon, bekommt die Zeile nur den Link, falls sie
    noch keinen hat. Der eingetragene Preis bleibt.
    """
    from . import planner
    lines = [l for l in (text or "").splitlines() if l.strip()]
    for new in (add or "").splitlines():
        card = planner.parse_card_list(new)
        if not new.strip() or not card:
            continue
        card = card[0]
        for i, line in enumerate(lines):
            old = planner.parse_card_list(line)
            if any(o["face"] == card["face"] for o in old):
                if len(old) == 1 and card["url"] and not old[0]["url"]:
                    lines[i] = line.rstrip() + " | " + card["url"]
                break
        else:
            lines.append(new.strip())
    return "\n".join(lines)


def load_data():
    with lock:
        d = _load("data.json", EMPTY_DATA)
        for k, v in EMPTY_DATA.items():
            d.setdefault(k, json.loads(json.dumps(v)))
        d.pop("card_market", None)    # gg.deals ist seit 0.20 ausgebaut
        d["_eshop"] = load_eshop_history()
        return d


def save_data(d):
    with lock:
        # Mit "_" beginnende Felder kommen aus anderen Dateien und werden dort gespeichert
        _save("data.json", {k: v for k, v in d.items() if not k.startswith("_")})


def load_eshop_history():
    """Kaufverlauf aus dem eShop, vom Browser-Helfer gelesen:
    {"entries": [{key, id, title, date, region}], "picks": {key: Titel oder "-"}, "at": Zeit}."""
    with lock:
        h = _load("eshop_history.json", {})
        h.setdefault("entries", [])
        h.setdefault("picks", {})
        # 0.49.0 bis 0.49.2 hatten das Land im Schlüssel ("nin:BR:123"): Nach einem
        # Länderwechsel wäre derselbe Kauf doppelt gekommen
        if any(e.get("key", "").count(":") == 2 and e["key"].startswith("nin:") for e in h["entries"]):
            fix = lambda k: re.sub(r"^nin:[A-Z]*:", "nin:", k)
            seen, entries = set(), []
            for e in h["entries"]:
                e["key"] = fix(e.get("key", ""))
                if e["key"] not in seen:
                    seen.add(e["key"])
                    entries.append(e)
            h["entries"] = entries
            h["picks"] = {fix(k): v for k, v in h["picks"].items()}
        return h


def merge_eshop_history(entries, now, newest=0, owned_n=None):
    """Neue Einträge anhängen, bekannte (gleicher Schlüssel) überspringen. newest: neuester
    Vorgang eines lückenlosen Laufs, ab dem das Lesezeichen künftig liest. Gibt (neu, gesamt)."""
    with lock:
        h = load_eshop_history()
        known = {e["key"]: e for e in h["entries"]}
        new = 0
        for e in entries:
            if e["key"] not in known:
                known[e["key"]] = e
                h["entries"].append(e)
                new += 1
            else:
                # Ein erneuter Lauf ergänzt Angaben, die ältere Einträge noch nicht hatten
                # (Plattform ab 0.68); Zuordnungen bleiben
                old = known[e["key"]]
                for k, v in e.items():
                    if v and not old.get(k):
                        old[k] = v
        h["entries"] = h["entries"][-3000:]
        h["at"] = now
        if newest and newest > (h.get("seit") or 0):
            h["seit"] = newest
        if owned_n is not None:
            h["owned_n"] = owned_n        # Größe der DekuDeals-Sammlung beim Lesen (Erinnerung, 0.52)
        _save("eshop_history.json", h)
        return new, len(h["entries"])


def remember_eshop_matches(found):
    """Gefundene Zuordnungen {Schlüssel: (Titel, Weg)} in die Einträge schreiben."""
    with lock:
        h = load_eshop_history()
        changed = False
        for e in h["entries"]:
            hit = found.get(e["key"])
            if hit and not e.get("slug"):
                e["slug"], e["how"] = hit
                changed = True
        if changed:
            _save("eshop_history.json", h)
        return changed


def pick_eshop_history(key, slug):
    """Eintrag von Hand zuordnen (Titel), als „kein Wunschtitel“ markieren ("-") oder
    die Zuordnung zurücknehmen (leer)."""
    slug = str(slug or "").strip()
    if slug and slug != "-" and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,199}", slug):
        raise ValueError("Bitte einen DekuDeals-Link oder dessen letzten Teil angeben")
    with lock:
        h = load_eshop_history()
        if slug:
            h["picks"][key] = slug
        else:
            h["picks"].pop(key, None)
        _save("eshop_history.json", h)
        return h


def load_ui():
    with lock:
        ui = _load("ui.json", DEFAULT_UI)
        for k, v in DEFAULT_UI.items():
            ui.setdefault(k, json.loads(json.dumps(v)))
        return ui


def save_ui(new):
    """Übernimmt nur bekannte Felder mit passendem Typ."""
    with lock:
        ui = load_ui()
        if "basket" in new:
            b = new["basket"]
            ui["basket"] = [str(x) for x in b][:200] if isinstance(b, list) and b else None
        if isinstance(new.get("overrides"), dict):
            ui["overrides"] = {
                str(code): {k: [str(x) for x in (o.get(k) or [])][:200] for k in ("add", "remove")}
                for code, o in new["overrides"].items() if isinstance(o, dict)}
        if isinstance(new.get("targets"), dict):
            targets = {}
            for slug, value in new["targets"].items():
                try:
                    if value not in (None, "") and float(value) > 0:
                        targets[str(slug)] = round(float(value), 2)
                except (TypeError, ValueError):
                    pass
            ui["targets"] = targets
        if isinstance(new.get("hidden"), list):
            ui["hidden"] = [str(x) for x in new["hidden"]][:60]
        if new.get("sort") in ("optimum", "saving", "rest", "end", "tier"):
            ui["sort"] = new["sort"]
        if "dense" in new:
            ui["dense"] = bool(new["dense"])
        if "plan_good" in new:
            ui["plan_good"] = bool(new["plan_good"])
        # Aus einem Schritt des Kaufplans herausgenommen (0.94): {Land: [Titel]}
        if isinstance(new.get("plan_skip"), dict):
            ui["plan_skip"] = {str(code): [str(x) for x in slugs][:50]
                               for code, slugs in new["plan_skip"].items()
                               if isinstance(slugs, list) and slugs}
        if isinstance(new.get("plan_fill"), dict):
            # ab 1.3.0 bis 100 je Land: „In Jetzt übernehmen“ bringt einen ganzen Korb
            ui["plan_fill"] = {str(code): [str(x) for x in slugs][:100]
                               for code, slugs in new["plan_fill"].items()
                               if isinstance(slugs, list) and slugs}
        # Angenommene Preise (1.3.0): {Land: {Titel: Preis im Shop}}
        if isinstance(new.get("plan_assume"), dict):
            ui["plan_assume"] = {}
            for code, m in list(new["plan_assume"].items())[:60]:
                if not isinstance(m, dict):
                    continue
                keep = {}
                for slug, v in list(m.items())[:50]:
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= v < 1e9:
                        keep[str(slug)] = v
                if keep:
                    ui["plan_assume"][str(code)] = keep
        _save("ui.json", ui)
        return ui


def load_history():
    """Eigene Preisaufzeichnung: {Land: {Titel: [[Zeitpunkt, Preis], ...]}}."""
    with lock:
        return _load("history.json", {})


def save_history(h):
    with lock:
        _save("history.json", h)


def merge_history(extra):
    """Preisaufzeichnung aus einer Sicherung dazunehmen: Punkte beider Stände, jeder
    Zeitpunkt einmal. Die Aufzeichnung lässt sich nicht neu laden, deshalb ergänzen statt
    ersetzen."""
    with lock:
        h = _load("history.json", {})
        for code, titles in extra.items():
            if not isinstance(titles, dict):
                continue
            for slug, points in titles.items():
                if not isinstance(points, list):
                    continue
                cur = {p[0]: p for p in h.get(code, {}).get(slug, [])}
                for p in points:
                    if isinstance(p, list) and len(p) == 2 and isinstance(p[0], str) and \
                            isinstance(p[1], (int, float)):
                        cur.setdefault(p[0], p)
                if cur:
                    h.setdefault(code, {})[slug] = sorted(cur.values())
        _save("history.json", h)


def load_purchases():
    """Kaufprotokoll: [{at, code, slugs, titles, cost, de, rest, before}, ...]."""
    with lock:
        return _load("purchases.json", [])


def save_purchases(p):
    with lock:
        _save("purchases.json", p)


def record_purchase(entry):
    """Vermerkt einen Kauf: Das Konto steht danach im Land des Kaufs, dort bleibt der
    Rest als Guthaben. Guthaben anderer Länder gibt es nach einem Wechsel nicht mehr
    (Nintendo nimmt es nicht mit). Der Zustand davor wird für „Rückgängig“ gemerkt."""
    with lock:
        s = load_settings()
        code = entry["code"]
        if code not in s["countries"]:
            raise ValueError("unbekanntes Land")
        before = {"current_country": s.get("current_country", ""),
                  "balance": {c: v["balance"] for c, v in s["countries"].items() if v.get("balance")}}
        for c, v in s["countries"].items():
            v["balance"] = 0.0
        rest = entry.get("rest")
        try:
            s["countries"][code]["balance"] = max(0.0, round(float(rest or 0), 2))
        except (TypeError, ValueError):
            pass
        s["current_country"] = countries.BY_CODE[code]["shop"]   # DG ist das deutsche Konto
        _save("settings.json", s)
        log = load_purchases()
        log.append(dict(entry, before=before))
        save_purchases(log[-500:])
        return log


def undo_purchase():
    """Nimmt den letzten Kauf zurück und stellt Land und Guthaben wieder her."""
    with lock:
        log = load_purchases()
        if not log:
            return log
        last = log.pop()
        s = load_settings()
        before = last.get("before") or {}
        s["current_country"] = before.get("current_country", "")
        for c, v in s["countries"].items():
            v["balance"] = float((before.get("balance") or {}).get(c, 0.0))
        _save("settings.json", s)
        save_purchases(log)
        return log

