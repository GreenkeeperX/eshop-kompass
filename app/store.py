"""Zwischenspeicher (data.json) und Einstellungen (settings.json)."""
import json
import os
import threading
from datetime import date

from . import countries

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))

DEFAULT_SETTINGS = {
    "wishlist_url": "",
    "collection_url": "",     # leer = Sammlung mit derselben Kennung wie die Wishlist
    "card_fee_pct": 1.75,     # Fremdwährungsgebühr der eigenen Karte
    "gift_markup_pct": 5.0,   # Aufschlag für Guthabenkarten ohne eigenen Preis
    "card_market": True,      # Kartenpreise je Land von gg.deals lesen
    "shop_fee_pct": 10.5,     # Servicegebühr des Kartenshops auf gelesene Preise (Eneba, Okt. 2026)
    # ab dieser Ersparnis lohnt der Länderwechsel, je Stufe (leicht, mittel, schwer)
    "tier_min_saving": {"1": 3.0, "2": 8.0, "3": 20.0},
    "lang_rule": "exclude",   # Regionen ohne deutsche Fassung: exclude, warn, off
    "refresh_hours": 6,
    "current_country": "",    # Land, in dem das Nintendo-Konto gerade steht
    # Urteil im Radar: bis zu diesem Abstand zum Bestpreis in Euro gilt ein
    # Angebot als Kauf bzw. gutes Angebot, auch wenn es prozentual mehr ist
    "deal_eur": {"buy": 0.5, "good": 2.0},
    "countries": countries.default_country_settings(),
}

# Was die Oberfläche sich merkt, für alle Geräte gleich
DEFAULT_UI = {"basket": None, "overrides": {}, "targets": {}, "hidden": [],
              "sort": "saving", "dense": True, "plan_good": False}

EMPTY_DATA = {"items": {}, "prices": {}, "lows": {}, "card_prices": {}, "card_market": {},
              "fx": {"rates": {"EUR": 1.0}, "updated": ""}, "last_sync": None}

lock = threading.RLock()


def _path(name):
    return os.path.join(DATA_DIR, name)


def _load(name, default):
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return json.loads(json.dumps(default))


def _save(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _path(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _path(name))


def load_settings():
    with lock:
        s = _load("settings.json", DEFAULT_SETTINGS)
        for k, v in DEFAULT_SETTINGS.items():
            s.setdefault(k, json.loads(json.dumps(v)))
        for group in ("tier_min_saving", "deal_eur"):
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
        if not s["wishlist_url"]:
            s["wishlist_url"] = os.environ.get("WISHLIST_URL", "")
        return s


def save_settings(new):
    """Übernimmt nur bekannte Felder mit passendem Typ."""
    with lock:
        s = load_settings()
        if isinstance(new.get("wishlist_url"), str):
            s["wishlist_url"] = new["wishlist_url"].strip()
        if isinstance(new.get("collection_url"), str):
            s["collection_url"] = new["collection_url"].strip()
        for k in ("card_fee_pct", "gift_markup_pct", "shop_fee_pct", "refresh_hours"):
            if k in new:
                try:
                    s[k] = max(0.0, float(new[k]))
                except (TypeError, ValueError):
                    pass
        if new.get("current_country") in list(s["countries"]) + [""]:
            s["current_country"] = new["current_country"]
        if isinstance(new.get("card_market"), bool):
            s["card_market"] = new["card_market"]
        if new.get("lang_rule") in ("exclude", "warn", "off"):
            s["lang_rule"] = new["lang_rule"]
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
        for code, c in (new.get("countries") or {}).items():
            if code not in s["countries"] or not isinstance(c, dict):
                continue
            cur = s["countries"][code]
            if "enabled" in c:
                cur["enabled"] = bool(c["enabled"])
            if c.get("pay") in ("card", "giftcard", "auto"):
                cur["pay"] = c["pay"]
            if str(c.get("tier")) in ("1", "2", "3"):
                cur["tier"] = int(c["tier"])
            if "markup_pct" in c:
                try:
                    raw = c["markup_pct"]
                    cur["markup_pct"] = "" if raw in ("", None) else min(100.0, max(-50.0, float(raw)))
                except (TypeError, ValueError):
                    pass
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
        return d


def save_data(d):
    with lock:
        _save("data.json", d)


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
        if new.get("sort") in ("saving", "rest", "end", "tier"):
            ui["sort"] = new["sort"]
        if "dense" in new:
            ui["dense"] = bool(new["dense"])
        if "plan_good" in new:
            ui["plan_good"] = bool(new["plan_good"])
        _save("ui.json", ui)
        return ui


def load_history():
    """Eigene Preisaufzeichnung: {Land: {Titel: [[Zeitpunkt, Preis], ...]}}."""
    with lock:
        return _load("history.json", {})


def save_history(h):
    with lock:
        _save("history.json", h)
