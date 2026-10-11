"""Zwischenspeicher (data.json) und Einstellungen (settings.json)."""
import json
import os
import threading

from . import countries

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))

DEFAULT_SETTINGS = {
    "wishlist_url": "",
    "card_fee_pct": 1.75,     # Fremdwährungsgebühr der eigenen Karte
    "gift_markup_pct": 5.0,   # Aufschlag für Guthabenkarten ohne eigenen Preis
    "min_saving_eur": 5.0,    # ab dieser Ersparnis lohnt der Länderwechsel
    "refresh_hours": 6,
    "current_country": "",    # Land, in dem das Nintendo-Konto gerade steht
    "countries": countries.default_country_settings(),
}

EMPTY_DATA = {"items": {}, "prices": {}, "lows": {},
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
        defaults = countries.default_country_settings()
        for code, d in defaults.items():
            cur = s["countries"].setdefault(code, d)
            for k, v in d.items():
                cur.setdefault(k, v)
        if not s["wishlist_url"]:
            s["wishlist_url"] = os.environ.get("WISHLIST_URL", "")
        return s


def save_settings(new):
    """Übernimmt nur bekannte Felder mit passendem Typ."""
    with lock:
        s = load_settings()
        if isinstance(new.get("wishlist_url"), str):
            s["wishlist_url"] = new["wishlist_url"].strip()
        for k in ("card_fee_pct", "gift_markup_pct", "min_saving_eur", "refresh_hours"):
            if k in new:
                try:
                    s[k] = max(0.0, float(new[k]))
                except (TypeError, ValueError):
                    pass
        if new.get("current_country") in list(s["countries"]) + [""]:
            s["current_country"] = new["current_country"]
        for code, c in (new.get("countries") or {}).items():
            if code not in s["countries"] or not isinstance(c, dict):
                continue
            cur = s["countries"][code]
            if "enabled" in c:
                cur["enabled"] = bool(c["enabled"])
            if c.get("pay") in ("card", "giftcard"):
                cur["pay"] = c["pay"]
            if "rest_blocks" in c:
                cur["rest_blocks"] = bool(c["rest_blocks"])
            if "balance" in c:
                try:
                    cur["balance"] = max(0.0, float(c["balance"] or 0))
                except (TypeError, ValueError):
                    pass
            if isinstance(c.get("cards"), str):
                cur["cards"] = c["cards"].strip()
        s["countries"][countries.REFERENCE]["enabled"] = True
        _save("settings.json", s)
        return s


def load_data():
    with lock:
        d = _load("data.json", EMPTY_DATA)
        for k, v in EMPTY_DATA.items():
            d.setdefault(k, json.loads(json.dumps(v)))
        return d


def save_data(d):
    with lock:
        _save("data.json", d)


def load_history():
    """Eigene Preisaufzeichnung: {Land: {Titel: [[Zeitpunkt, Preis], ...]}}."""
    with lock:
        return _load("history.json", {})


def save_history(h):
    with lock:
        _save("history.json", h)
