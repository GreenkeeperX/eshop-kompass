"""Paketrechner: Angebote, Bewertung (Context), Pläne je Land, Urteile, Sammlung, Sprachen.

Beträge in Landeswährung werden intern als ganze Hundertstel gerechnet.

Seit 0.86 liegen Teile in eigenen Dateien: cards (Guthabenkarten), titles (Namen, Käufe, Besitz),
kaufplan und membership. planner reicht alle ihre Namen weiter, planner.X gilt also überall wie bisher.
"""
import functools
import importlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from itertools import combinations

from . import countries
from .sources import ec_url
from .cards import (MAX_STATES, CARD_HIST_DAYS, CARD_HIST_MIN_DAYS, CARD_STEPS, _fac, card_hist_window,
    CARD_PLAUSIBLE, cents, _OUT_RE, plausible_card, parse_card_list, parse_cards, CardSolver)
from .titles import (_shared, shared_contexts, _tnorm, _ESHOP_VOID, slug_names, known_titles, pretty_slug,
    _MATCH_KEYS, eshop_matches, _S2, _s2base, _PASSES, _pass_kind, _pass_label, _eshop_matches, pack_parts,
    pack_block, owned_set, owned_games)

CARD_PRICE_MAX_AGE = 14 * 24 * 3600  # zuletzt gelesene Kartenpreise gelten so lange, auch wenn ein Abruf scheitert
OFFER_DEVIATION = 0.4                # ein vom Link gelesener Preis, der so weit vom eingetragenen abweicht, gilt nicht
MIN_FILLER_GAIN = 0.5    # Füllartikel erst ab dieser Ersparnis in Euro vorschlagen
BEST_TOLERANCE = 0.02    # bis 2 % über dem Bestpreis gilt ein Angebot als Bestpreis
PRICE_STALE_SECONDS = 6 * 3600   # Preise eines Lands so weit hinter dem jüngsten Abruf: veraltet (0.95)
GOOD_GAP = 15            # bis 15 % über dem Bestpreis gilt ein Angebot als gut
# Typischer Angebotspreis: Median der Tiefstwerte aller Angebotsphasen im
# DekuDeals-Tagesverlauf dieses Zeitraums, erst ab so vielen Phasen
TYPICAL_DAYS = 730
HIGH_REST_EUR = 5.0      # ab diesem Rest in Euro warnt ein Paket
TYPICAL_MIN_RUNS = 2
# Bestpreis und Landestief: tiefster Preis dieses Zeitraums aus dem DekuDeals-Verlauf. Ältere
# Tiefstwerte, zum heutigen Kurs gerechnet, zeigen Preise, die es so nie gab (Entscheidung 12.10.2026)
BEST_MONTHS = 24






# ------------------------------------------------------------------ Angebote

def _parse_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def offer(price, now):
    """Aktueller Preis eines Titels in einem Land oder None, wenn nicht kaufbar."""
    if not price or price.get("status") != "onsale" or "regular" not in price:
        return None
    regular = cents(price["regular"])
    local, sale, end, since = regular, False, None, None
    if "discount" in price:
        start, stop = _parse_dt(price.get("start")), _parse_dt(price.get("end"))
        if (start is None or start <= now) and (stop is None or now <= stop):
            local, sale, end, since = cents(price["discount"]), True, price.get("end"), price.get("start")
    # start (1.3.0): seit wann das Angebot läuft, für „Neu im Angebot“ in Jetzt
    return {"local": local, "regular": regular, "sale": sale and local < regular,
            "end": end, "start": since if sale and local < regular else None, "currency": price.get("currency")}


def read_offer(x, offer_prices, currency, now_ts):
    """Welcher Preis gilt für ein eigenes Angebot (ab 0.62.1 mit Plausibilität)?

    Der vom Link gelesene Preis gilt bis CARD_PRICE_MAX_AGE nach dem letzten Erfolg, aber nur
    in der Währung des Landes und höchstens OFFER_DEVIATION vom eingetragenen Preis entfernt.
    Sonst gilt der eingetragene, und `check` sagt warum: "cur" (Seite zeigt eine andere
    Währung, etwa Amazon in Euro), "off" (weicht stark ab: falscher Link oder Tippfehler),
    "err" (letzter Abruf gescheitert), "old" (zu lange nicht gelesen), "wait" (noch nie gelesen)."""
    out = {"price": x["price"], "read": None, "check": None, "seen": None, "seen_cur": None, "error": None}
    if not x.get("url"):
        return out
    got = (offer_prices or {}).get(x["url"]) or {}
    out["error"] = got.get("error")
    if got.get("price") is None:
        out["check"] = "err" if got.get("error") else "wait"
        return out
    out["seen"], out["seen_cur"] = got["price"], got.get("currency")
    if got.get("currency") != currency:
        out["check"] = "cur"
    elif x["price"] and abs(got["price"] / x["price"] - 1) > OFFER_DEVIATION:
        out["check"] = "off"
    elif now_ts - got.get("ok", 0) > CARD_PRICE_MAX_AGE:
        out["check"] = "old"
    else:
        out["price"], out["read"] = got["price"], got.get("ok")
    return out


def offer_checks(data, settings, pay, now=None):
    """Prüfstand aller eigenen Angebote mit Link für die Oberfläche: {url: read_offer}.
    `pay` ist pay_info (Währung je Land)."""
    now_ts = (now or datetime.now(timezone.utc)).timestamp()
    out = {}
    for x in (settings.get("nso_extra") or []) + (settings.get("own_offers") or []):
        cur = (pay.get(x.get("code")) or {}).get("currency")
        if x.get("url") and cur:
            out[x["url"]] = read_offer(x, data.get("offer_prices"), cur, now_ts)
    return out


def _context(data, settings, now=None, include_all=False):
    cache = getattr(_shared, "cache", None)
    if cache is None:
        return Context(data, settings, now, include_all)
    key = (id(data), id(settings), now, include_all)
    hit = cache.get(key)
    if hit is None or hit[0] is not data or hit[1] is not settings:
        hit = cache[key] = (data, settings, Context(data, settings, now, include_all))
    return hit[2]


class Context:
    """Alles, was die Rechnungen brauchen: Angebote je Land in Bruttopreisen,
    Europreis je Währungseinheit, Sprachregel und Bestpreise."""

    def __init__(self, data, settings, now=None, include_all=False):
        self.now = now or datetime.now(timezone.utc)
        y, m = self.now.year, self.now.month - BEST_MONTHS
        while m < 1:
            y, m = y - 1, m + 12
        self.best_since = f"{y:04d}-{m:02d}"
        self.settings = settings
        self.items = {s: it for s, it in data["items"].items() if it.get("active")}
        self.order = sorted(self.items, key=lambda s: self.items[s].get("order", 0))
        self.lows = data.get("lows", {})
        self.owned = owned_set(data, settings)
        self.rel = data.get("rel") or {}
        self.glangs = data.get("glangs") or {}
        rates = data["fx"]["rates"]
        self.rates = rates
        self.card_prices = data.get("card_prices") or {}
        self.offer_prices = data.get("offer_prices") or {}
        self.card_hist = data.get("card_hist") or {}
        self._payers, self._shares = {}, {}
        # Preisstand je Shop (0.95): der jüngste Abruf. Liegt er deutlich hinter dem jüngsten
        # aller Shops, scheiterte der letzte Abruf dort, und die alten Preise gelten still weiter
        self.price_at = {shop: max((p.get("fetched") or "" for p in t.values()), default="") or None
                         for shop, t in data["prices"].items()}
        newest = max((v for v in self.price_at.values() if v), default=None)
        self.price_stale = set()
        if newest:
            top = datetime.fromisoformat(newest)
            for shop, at in self.price_at.items():
                try:
                    if at and (top - datetime.fromisoformat(at)).total_seconds() > PRICE_STALE_SECONDS:
                        self.price_stale.add(shop)
                except (TypeError, ValueError):
                    pass
        self.countries = {}
        for code in countries.ORDER:
            cfg = settings["countries"][code]
            if not (cfg["enabled"] or include_all):
                continue
            meta = countries.BY_CODE[code]
            tax = 0.0 if code == countries.REFERENCE else float(cfg.get("tax_pct") or 0)
            offers, currency = {}, None
            for slug, p in data["prices"].get(meta["shop"], {}).items():
                if slug not in self.items:
                    continue
                currency = currency or p.get("currency")
                o = offer(p, self.now)
                if not o:
                    continue
                o["net"], o["regular_net"] = o["local"], o["regular"]
                o["nsuid"] = p.get("nsuid")
                if tax:       # Shop zeigt Preise ohne Steuer, gerechnet wird brutto
                    o["local"] = round(o["local"] * (1 + tax / 100))
                    o["regular"] = round(o["regular"] * (1 + tax / 100))
                offers[slug] = o
            c = {"code": code, "cfg": cfg, "meta": meta, "offers": offers,
                 "currency": currency, "rate": rates.get(currency) if currency else None,
                 "known": set(data["prices"].get(meta["shop"], {})), "tax": tax,
                 "tier": int(cfg.get("tier") or meta["tier"]), "nolang": set(),
                 "cards": parse_card_list(cfg.get("cards")), "implausible": []}
            if c["rate"]:
                c["cards"] = self._live_cards(c["cards"], c["rate"], c["implausible"])
            c["unit"] = self._unit(c)
            c["estimated"] = self.estimated(c)
            # Guthabenland ohne Karte mit Preis: Dort kommst du nicht an Guthaben, der
            # Europreis wäre geraten. Gezeigt wird das Angebot, entschieden wird damit nicht.
            c["nocard"] = c["estimated"] and cfg["pay"] == "giftcard"
            # Mit Karten aus einem Shop gekauft: Dort gibt es manchmal Cashback
            c["shop_cards"] = any(x.get("live") for x in c["cards"])
            if c["nocard"]:
                for o in c["offers"].values():
                    o["nocard"] = True
            self._own_offers(c)
            self.countries[code] = c
        self._apply_language_rule()
        ref = self.countries.get(countries.REFERENCE, {"offers": {}})
        # Vergleichsbasis mit allen Kosten: günstigere Guthabenkarten senken auch sie
        unit = ref.get("unit") or 0.01
        self.ref = {s: o["local"] * unit for s, o in ref["offers"].items()}
        self._champions()

    def offer_price(self, x, currency):
        """Preis eines eigenen Angebots in Landeswährung: vom Link gelesen oder wie
        eingetragen. (Preis, gelesen um oder None), Prüfung siehe read_offer."""
        r = read_offer(x, self.offer_prices, currency, self.now.timestamp())
        return r["price"], r["read"]

    def _own_offers(self, c):
        """Eigene Angebote für Titel (ab 0.62), etwa Codes bei Amazon Japan: bezahlt mit
        Kreditkarte zum Mittelkurs plus Gebühr, eingelöst im Konto dieses Landes. Ist der
        Code günstiger als der eShop, tritt er an dessen Stelle; er zählt dann wie jedes
        Angebot für Bestpreis, Urteil und Kaufplan. `direct` ist sein Europreis: Er läuft
        nicht über Guthaben, also auch nicht über Karten und Rest."""
        if not c["rate"]:
            return
        for j, x in enumerate(self.settings.get("own_offers") or []):
            if x.get("code") != c["code"] or x.get("slug") not in self.items:
                continue
            price, read = self.offer_price(x, c["currency"])
            local = cents(price)
            direct = local * self.code_unit(c)
            o = c["offers"].get(x["slug"])
            if o and not o.get("nocard") and self.oeur(c, o) <= direct + 0.005:
                continue               # der eShop ist gleich günstig oder günstiger
            c["offers"][x["slug"]] = {
                "local": local, "regular": local, "sale": False, "end": None, "currency": c["currency"],
                "net": local, "regular_net": local, "nsuid": (o or {}).get("nsuid"), "direct": direct,
                "own": {"src": x.get("src") or "Händler", "url": x.get("url") or "", "read": read,
                        "manual": x["price"], "idx": j, "eshop": _r(self.oeur(c, o)) if o else None}}

    def oeur(self, c, o):
        """Europreis eines Angebots: eigenes Angebot direkt, sonst über den Zahlweg des Landes."""
        return o["direct"] if o.get("direct") is not None else self.est(c, o["local"])

    def low_or_now(self, c, slug, o, low):
        """Europreis des Tiefstpreises der letzten 24 Monate, das Angebot jetzt eingeschlossen."""
        if o.get("direct") is not None:
            # Ohne Kartenpreis zählt der eShop-Tiefstpreis dort nicht (er wäre nur geschätzt, 0.63)
            if low is None or c.get("nocard"):
                return o["direct"]
            return min(o["direct"], self.est(c, round(cents(low) * (1 + c["tax"] / 100))))
        local = o["local"] if low is None else min(o["local"], round(cents(low) * (1 + c["tax"] / 100)))
        return self.est(c, local)

    def _live_cards(self, cards, country_rate, implausible):
        """Setzt für Karten mit Link den zuletzt gelesenen Shop-Preis ein, solange
        er glaubhaft und höchstens CARD_PRICE_MAX_AGE alt ist, auch wenn der letzte Abruf
        scheiterte. Sonst bleibt der von Hand eingetragene Preis."""
        now = self.now.timestamp()
        for x in cards:
            e = self.card_prices.get(x["url"]) if x["url"] else None
            if not e or e.get("price") is None or now - e.get("ok", e.get("checked", 0)) > CARD_PRICE_MAX_AGE:
                continue
            rate = 1.0 if e.get("currency") == "EUR" else self.rates.get(e.get("currency"))
            if not rate:
                continue
            # Der Shop zeigt den Preis ohne seine Servicegebühr, die kommt an der Kasse dazu.
            # Der feste Teil steckt hier in jeder Karte; ein Paket aus mehreren Karten
            # (eine Bestellung) rechnet ihn in make_payer nur einmal
            fee = float(self.settings.get("shop_fee_pct") or 0)
            fee_eur = float(self.settings.get("shop_fee_eur") or 0)
            cost = round(e["price"] / rate * (1 + fee / 100) + fee_eur, 2)
            if not plausible_card(cost, x["face"], country_rate):
                implausible.append({"face": x["face"] / 100, "price": cost, "src": "shop"})
                continue
            x.update(manual=x["cost"], cost=cost, live=e.get("ok", e["checked"]), fee=fee, fee_eur=fee_eur)
        return cards

    # ---- Europreis je Währungseinheit

    def markup(self, c):
        """Aufschlag in Prozent, wenn für Guthaben kein Kartenpreis lesbar ist (Schätzung).
        Seit 0.52.1 ein Wert für alle Länder (Entscheidung 13.10.2026)."""
        return float(self.settings["gift_markup_pct"])

    def face_cost(self, c, x):
        """Preis einer Karte in Euro: gelesen oder eingetragen; nur ein Wert ohne Link heißt
        Guthaben zum Kurs, mit deiner Karte bezahlt wie im eShop (etwa Amazon Japan; bei einer
        Karte ohne Fremdwährungsgebühr genau zum Kurs); None = unbekannt."""
        if x["cost"] is not None:
            return x["cost"]
        if not x["url"]:
            return x["face"] / 100 / c["rate"] * (1 + self.settings["card_fee_pct"] / 100)
        return None

    def _gift(self, c):
        """Günstigste vorrätige Karte: (Euro je Hundertstel, Karte oder None)."""
        est = 1 / 100 / c["rate"] * (1 + self.markup(c) / 100)
        best, card = est, None
        for x in c["cards"]:
            if not x["stock"]:
                continue
            cost = self.face_cost(c, x)
            if cost is None:               # ohne Preis keine Grundlage (0.63)
                continue
            unit = cost / x["face"]
            if card is None or unit < best - 1e-12:
                best, card = unit, x
        return best, card

    def _euro_card(self, c):
        """Euro-Land: günstigste vorrätige Karte mit bekanntem Preis unter Nennwert.
        Ein Rest bleibt auf dem eigenen Konto, deshalb zählt nur der Preis je Euro."""
        best, card = 0.01, None
        for x in c["cards"]:
            if x["stock"] and x["cost"] is not None and x["cost"] / x["face"] < best - 1e-12:
                best, card = x["cost"] / x["face"], x
        return best, card

    def _units(self, c):
        """(Kartenzahlung, Guthabenkarte) in Euro je Hundertstel Landeswährung."""
        mid = 1 / 100 / c["rate"]
        if c["code"] == countries.REFERENCE:
            return mid, mid           # Vergleichsbasis: der Preis im deutschen eShop
        if c["currency"] == "EUR":
            unit = self._euro_card(c)[0]
            return unit, unit
        return mid * (1 + self.settings["card_fee_pct"] / 100), self._gift(c)[0]

    def code_unit(self, c):
        """Euro je Hundertstel für einen Code beim Händler (eigene Angebote, 0.63): immer mit
        Kreditkarte zum Mittelkurs plus Gebühr, in Euro genau der Betrag. Nie über Guthabenkarten,
        auch nicht im Euro-Land, wo _units den Faktor der Guthabenkarten liefert."""
        mid = 1 / 100 / c["rate"]
        return mid if c["currency"] == "EUR" else mid * (1 + self.settings["card_fee_pct"] / 100)

    def _unit(self, c):
        if not c["rate"]:
            return None
        card, gift = self._units(c)
        pay = c["cfg"]["pay"]
        if pay == "auto" and c["currency"] != "EUR" and c["code"] != countries.REFERENCE \
                and not any(x["stock"] and self.face_cost(c, x) is not None for x in c["cards"]):
            return card           # „das Günstigere“ wählt nie eine Schätzung (0.52.1)
        return card if pay == "card" else gift if pay == "giftcard" else min(card, gift)

    def factor(self, c, x):
        """Faktor einer Karte: was sie kostet ÷ was sie zum Mittelkurs wert ist; None = Preis
        unbekannt. Euro-Guthaben ist zum Nennwert wert."""
        cost = self.face_cost(c, x) if c["currency"] != "EUR" else x["cost"]
        if cost is None or not c["rate"]:
            return None
        return cost / (x["face"] / 100 / (1.0 if c["currency"] == "EUR" else c["rate"]))

    def rate_card(self, c, factor, url=None):
        """Bewertung eines Faktors, je nach Land (Entscheidung 13.10.2026):
        Kreditkarte möglich: gegen deren Faktor. Nur Guthaben: gegen den besten Faktor dieser
        Karte in CARD_HIST_DAYS Tagen. Euro-Guthaben: feste Stufen (einstellbar).
        Ergebnis: {"level": top|good|ok|bad|cheaper|dearer|None, "text", "best"}."""
        if factor is None:
            return {"level": None, "text": "Preis unbekannt", "best": None}
        if c["currency"] == "EUR":
            steps = self.settings["eur_card_steps"]
            for key, level, text in (("top", "top", "Top"), ("good", "good", "gut"), ("ok", "ok", "okay")):
                if factor <= steps[key] + 1e-9:
                    return {"level": level, "text": text, "best": None}
            return {"level": "bad", "text": "teuer", "best": None}
        if c["cfg"]["pay"] in ("auto", "card"):
            ref = 1 + self.settings["card_fee_pct"] / 100
            if abs(factor - ref) < 0.0005:
                return {"level": "same", "text": "wie Kreditkarte", "best": ref}
            if factor < ref:
                return {"level": "cheaper", "text": "günstiger als Kreditkarte", "best": ref}
            return {"level": "dearer", "text": f"teurer als Kreditkarte ({_fac(factor)} zu {_fac(ref)})"
                    + (", nicht genutzt" if c["cfg"]["pay"] == "auto" else ""), "best": ref}
        if not url:
            return {"level": None, "text": "zum Kurs" if factor and abs(factor - 1 - self.settings["card_fee_pct"] / 100) < 1e-6
                    else "dein eingetragener Preis", "best": None}
        hist = card_hist_window(self.card_hist.get(url) or {}, self.now)
        if not hist or (self.now - datetime.fromisoformat(min(hist)).replace(tzinfo=timezone.utc)).days < CARD_HIST_MIN_DAYS:
            # Wann der Vergleich beginnt, damit die graue Zeile nicht wie ein Fehler wirkt
            start = datetime.fromisoformat(min(hist)).replace(tzinfo=timezone.utc) + timedelta(days=CARD_HIST_MIN_DAYS) if hist else None
            return {"level": None, "text": f"Bewertung ab {start:%d.%m.}" if start else "noch kein Vergleich",
                    "best": min(hist.values()) if hist else None}
        best = min(min(hist.values()), factor)
        for limit, level, text in CARD_STEPS:
            if factor <= best * limit + 1e-9:
                return {"level": level, "text": text, "best": best}
        return {"level": "bad", "text": f"teuer, {round(100 * (factor / best - 1))} % über Bestwert", "best": best}

    def how(self, c):
        """Woraus sich der Europreis eines Landes zusammensetzt, für die Anzeige."""
        if c["unit"] is None:
            return None
        mid = 1 / 100 / c["rate"]
        card_unit, gift_unit = self._units(c)
        pay = c["cfg"]["pay"]
        gift = pay == "giftcard" or (pay == "auto" and gift_unit < card_unit and c["unit"] < card_unit - 1e-12)
        out = {"currency": c["currency"], "rate": c["rate"], "tax": c["tax"],
               "via": "giftcard" if gift else "card", "unit": c["unit"] * 100,
               "vs_mid": round(100 * (c["unit"] / mid - 1), 1),
               "fee": self.settings["card_fee_pct"], "markup": self.markup(c), "card": None,
               # Karten nur mit Wert und ohne Shop-Link: Guthaben zum Kurs, wie bei Amazon Japan.
               # Karten mit Link, aber ohne bekannten Preis, bleiben eine Schätzung.
               "at_rate": any(x["stock"] and x["cost"] is None and not x["url"] for x in c["cards"])}
        out["factor"] = round(c["unit"] / mid, 4)
        card = None
        if c["currency"] == "EUR":
            card = self._euro_card(c)[1]
            out["via"] = "giftcard" if card else "eur"
            out["factor"] = round(c["unit"] / 0.01, 4)
        elif gift:
            card = self._gift(c)[1]
            if card and card["cost"] is None:
                card = None
        if card:
            f = self.factor(c, card)
            out["card"] = {"face": card["face"] / 100, "cost": card["cost"], "url": card["url"],
                           "live": card.get("live"), "fee": card.get("fee"), "fee_eur": card.get("fee_eur"),
                           "value": round(card["face"] / 100 / (1.0 if c["currency"] == "EUR" else c["rate"]), 2),
                           "factor": round(f, 4)}
            out["rating"] = self.rate_card(c, f, card["url"])
        return out

    def estimated(self, c):
        """True, wenn der Europreis auf dem pauschalen Guthaben-Aufschlag beruht,
        weil für dieses Land gar keine Guthabenkarte eingetragen ist. Karten nur
        mit Wert heißen: Guthaben zum Kurs plus Aufschlag, so wie du es kaufst."""
        how = self.how(c)
        return bool(how and how["via"] == "giftcard" and not how["card"] and not how["at_rate"])

    def est(self, c, local):
        """Europreis eines Bruttobetrags in Landeswährung beim üblichen Zahlweg.
        Mit Guthabenkarten: mit den Karten, die zu diesem Betrag passen, anteilig."""
        if c["unit"] is None:
            return None
        if c["code"] == countries.REFERENCE or local <= 0:
            return local * c["unit"]
        key = (c["code"], local)
        if key not in self._shares:
            v = self._payer(c).share(local)
            self._shares[key] = local * c["unit"] if v is None else v
        return self._shares[key]

    def _payer(self, c):
        if c["code"] not in self._payers:
            self._payers[c["code"]] = make_payer(self, c)[0]
        return self._payers[c["code"]]

    # ---- Sprachen

    def german(self, it, fam, slug=None, by_hand=True):
        """Hat die Fassung dieser Region Deutsch? None, wenn unbekannt.
        Deine Bestätigung von Hand geht vor, dann die Angabe von Nintendo.
        Ein DLC ohne eigene Angabe richtet sich nach seinem Hauptspiel."""
        conf = (self.settings.get("lang_confirm") or {}) if by_hand else {}

        def own(s, item):
            v = (conf.get(s) or {}).get(fam) if s else None
            if isinstance(v, bool):
                return v
            text = (item.get("langs") or {}).get(fam)
            if not text or (item.get("ids_doubt") or {}).get(fam):
                return None          # ID fraglich: gelesene Sprache gehört vielleicht zu einem anderen Titel
            return "german" in text.lower() or "deutsch" in text.lower() or "ドイツ語" in text
        if it.get("dlc_of"):
            # fehlendes DLC deines Spiels: deine Angabe zum Spiel gilt auch für sein DLC
            v = (conf.get(it["dlc_of"]) or {}).get(fam)
            if isinstance(v, bool):
                return v
        found = own(slug, it)
        if found is None and it.get("parent") in self.items:
            found = own(it["parent"], self.items[it["parent"]])
        elif found is None and it.get("parent") in getattr(self, "glangs", {}):
            # Hauptspiel nicht auf der Wishlist: seine eigene Seite je Region (0.68), wie bei
            # den fehlenden DLC der Sammlung
            found = own(it["parent"], self.glangs[it["parent"]])
        return found

    def _apply_language_rule(self):
        """Gibt es in Deutschland eine deutsche Fassung, kommen nur Regionen
        infrage, die sie ebenfalls haben. Gleiche Region heißt gleiches Produkt."""
        mode = self.settings.get("lang_rule", "exclude")
        if mode == "off":
            return
        for c in self.countries.values():
            fam = c["meta"]["family"]
            for slug in list(c["offers"]):
                it = self.items[slug]
                if it.get("nso") or self.german(it, "EU", slug) is not True:
                    continue            # Mitgliedschaft: keine Sprachfassung (0.69)
                if fam == "EU":
                    # dasselbe Produkt wie im deutschen eShop
                    c["offers"][slug]["lang"] = "same"
                    continue
                here = self.german(it, fam, slug)
                if here is True:
                    c["offers"][slug]["lang"] = "de"
                elif here is False and mode == "exclude":
                    del c["offers"][slug]
                    c["nolang"].add(slug)
                elif here is False:
                    c["offers"][slug]["lang"] = "no"
                elif here is None:
                    c["offers"][slug]["lang"] = "unknown"

    def decides(self, o):
        """Darf dieses Angebot Bestpreis, Urteil und Kaufplan bestimmen? Nicht, wenn
        die Sprachregel gilt und für die Region unbekannt ist, ob es Deutsch gibt:
        Gezeigt wird es weiter, entschieden wird damit nicht."""
        if o.get("nocard"):
            return False
        return not (self.settings.get("lang_rule", "exclude") == "exclude"
                    and o.get("lang") == "unknown")

    # ---- Tiefst- und Bestpreise

    def low_value(self, code, slug):
        """Tiefstpreis in Landeswährung (ohne Steuer) der letzten 24 Monate: aus dem
        DekuDeals-Tagesverlauf und der eigenen Aufzeichnung. Ohne Verlauf (noch nicht
        gelesen, oder die Seite gilt für Switch und Switch 2) der Allzeit-Tiefstpreis."""
        e = self.lows.get(countries.BY_CODE[code]["shop"], {}).get(slug) or {}
        own = e.get("own_low")
        # Das Fenster gilt für alle Werte (0.63): ein eigener Tiefstwert nur, wenn er darin liegt
        if own is not None and str(e.get("own_since") or "9999")[:7] < self.best_since:
            own = None
        if e.get("hist") and not e.get("hist_multi"):
            vals = [v for m, v in e["hist"] if m >= self.best_since and v and v > 0]
            if vals:
                return min(vals + ([own] if own is not None else []))
        values = [v for v in (e.get("low"), own) if v is not None]
        return min(values) if values else None

    def has_history(self, slug):
        """Ob DekuDeals für den Titel in irgendeinem Shop einen Tiefstpreis oder Verlauf geliefert
        hat. Ohne beruht der Bestpreis nur auf heutigen Preisen und der eigenen Aufzeichnung (0.95)."""
        return any("low" in (shop.get(slug) or {}) or (shop.get(slug) or {}).get("hist")
                   for shop in self.lows.values())

    def low(self, code, slug, o):
        """Tiefstpreis in Landeswährung und ob das aktuelle Angebot ihn erreicht."""
        low = self.low_value(code, slug)
        if low is None:
            return {"low": None, "at_low": False}
        base = o.get("regular_net", o["regular"])
        return {"low": low, "at_low": o.get("net", o["local"]) <= cents(low),
                "low_pct": round(100 * (1 - cents(low) / base)) if base else 0}

    def typical_value(self, code, slug):
        """Typischer Angebotspreis in Landeswährung (ohne Steuer) und Zahl der
        Angebotsphasen, aus dem DekuDeals-Verlauf. None, wenn zu wenige bekannt."""
        e = self.lows.get(countries.BY_CODE[code]["shop"], {}).get(slug) or {}
        since = (self.now.timestamp() - TYPICAL_DAYS * 86400)
        since = datetime.fromtimestamp(since, timezone.utc).strftime("%Y-%m-%d")
        runs = [(r[0], r[1]) for r in e.get("sales") or [] if r[0] >= since and r[1] and r[1] > 0]
        if len(runs) < TYPICAL_MIN_RUNS:
            return None
        lows, n = sorted(v for _, v in runs), len(runs)
        median = lows[n // 2] if n % 2 else (lows[n // 2 - 1] + lows[n // 2]) / 2
        # War das letzte Angebot tiefer, gilt es: Nintendo senkt Angebotspreise
        # oft dauerhaft, der Median hinkt dann hinterher
        return min(median, max(runs)[1]), n

    def _champions(self):
        """Bestpreis je Titel: der niedrigste Preis der letzten 24 Monate über alle
        zählenden Länder, in Euro mit dem heutigen Einkaufsweg. Normalpreise zählen mit:
        Ist ein Spiel irgendwo dauerhaft am billigsten, ist das sein Bestpreis."""
        self.champ_all = {}
        # Typischer Angebotspreis: nur zur Information, das günstigste Land
        self.typ_all = {}
        for code, c in self.countries.items():
            if c["unit"] is None:
                continue
            for slug, o in c["offers"].items():
                if not self.decides(o):
                    continue
                typ = self.typical_value(code, slug)
                if typ:
                    eur = self.est(c, round(cents(typ[0]) * (1 + c["tax"] / 100)))
                    if slug not in self.typ_all or eur < self.typ_all[slug][0] - 1e-9:
                        self.typ_all[slug] = (eur, code, c["estimated"], typ[1])
                eur = self.low_or_now(c, slug, o, self.low_value(code, slug))
                if slug not in self.champ_all or eur < self.champ_all[slug][0] - 1e-9:
                    self.champ_all[slug] = (eur, code, c["estimated"])

    def deal(self):
        return dict({"buy": 0.5, "good": 2.0, "mini": 2.0}, **(self.settings.get("deal_eur") or {}))

    def mini(self, slug, eur=None):
        """Kleinkram (0.92): Bestpreis unter deal_eur.mini, wie beim Urteil (ab 0.99.5, Entscheidung
        20.10.2026; vorher nahm der Kaufplan den heutigen Preis). Ohne Bestpreis der Preis `eur`.
        Er macht im Kaufplan keine Guthabenkarte größer (Entscheidung 19.10.2026)."""
        best = self.champ_all.get(slug)
        val = best[0] if best and best[0] else eur
        return val is not None and val < self.deal()["mini"] - 1e-9

    def grade(self, eur, slug):
        """Preisgüte eines Europreises gegenüber dem Bestpreis, für jedes Land gleich:
        buy (am Bestpreis, bis 2 % oder deal_eur.buy darüber), good (bis 15 % oder
        deal_eur.good darüber), wait. None ohne Bestpreis. Kleinkram (Bestpreis unter
        deal_eur.mini) ist nur bis 2 % "buy": 0,50 € wären bei 1 € schon 50 % (Entscheidung 19.10.2026)."""
        best = self.champ_all.get(slug)
        if eur is None or not best or not best[0]:
            return None
        deal = self.deal()
        diff = eur - best[0]
        small = best[0] < deal["mini"] - 1e-9
        if eur <= best[0] * (1 + BEST_TOLERANCE) + 0.005 or (not small and diff <= deal["buy"] + 0.005):
            return "buy"
        if 100 * (eur / best[0] - 1) <= GOOD_GAP + 1e-9 or diff <= deal["good"] + 0.005:
            return "good"
        return "wait"

    def alt_price(self, slug, tier, shop, allowed=None):
        """Was ein Titel ohne den Wechsel in ein Land der Stufe `tier` kostet: der günstigste
        zählende Preis jetzt in einem anderen Land gleicher oder leichterer Stufe oder in dem
        Land, in dem das Konto steht. (Euro, Land) oder None."""
        # Gemerkt (0.96): Der Kaufplan fragt dieselbe Kombination tausendfach
        key = (slug, tier, shop, None if allowed is None else tuple(allowed))
        memo = self.__dict__.setdefault("_alt_memo", {})
        if key in memo:
            return memo[key]
        memo[key] = best = self._alt_price(slug, tier, shop, allowed)
        return best

    def _alt_price(self, slug, tier, shop, allowed):
        current = self.settings.get("current_country") or ""
        best = None
        for code, c in self.countries.items():
            if allowed is not None and code not in allowed:
                continue
            if c["unit"] is None or c["meta"]["shop"] == shop:
                continue
            if c["tier"] > tier and c["meta"]["shop"] != current:
                continue
            o = c["offers"].get(slug)
            if not o or not self.decides(o):
                continue
            eur = self.oeur(c, o)
            if best is None or eur < best[0] - 1e-9:
                best = (eur, code)
        return best

    def mark(self, c, slug, o):
        """Deal-Güte eines Angebots: Marke und Abstand zum Bestpreis in Prozent."""
        out = {"mark": "", "gap": None, "champ": None, "champ_code": None}
        eur, best = self.oeur(c, o), self.champ_all.get(slug)
        if eur is None or not best or not best[0]:
            return out
        out.update(champ=_r(best[0]), champ_code=best[1],
                   gap=max(0, round(100 * (eur / best[0] - 1))))
        if not o["sale"]:
            # Ein Normalpreis am Bestpreis trägt die Bestpreis-Marke, sonst keine
            if self.decides(o) and eur <= best[0] * (1 + BEST_TOLERANCE) + 0.005:
                out["mark"] = "best"
            return out
        if not self.decides(o):
            # Ungeprüfte Sprache bestimmt keinen Bestpreis, also auch keine Bestpreis-Marke
            out["mark"] = "low" if self.low(c["code"], slug, o)["at_low"] else "sale"
        elif eur <= best[0] * (1 + BEST_TOLERANCE) + 0.005:
            out["mark"] = "best"
        elif self.low(c["code"], slug, o)["at_low"]:
            out["mark"] = "low"
        else:
            out["mark"] = "sale"
        return out

    def alone(self, c, local):
        """Was der Titel kostet, wenn er allein gekauft wird: mit den Karten,
        die dafür nötig sind, und ihrem Rest. None, wenn das dem Anteilspreis gleicht."""
        if c["unit"] is None:
            return None
        r = self._payer(c)(local)
        if r["estimated"] or abs(r["cost"] - self.est(c, local)) < 0.005:
            return None
        return {"eur": _r(r["cost"]), "rest": None if r["rest"] is None else r["rest"] / 100,
                "cards": [{"face": f / 100, "count": n} for f, n in r["cards"]]}

    def low_eur(self, c, slug, o):
        """Landestief in Euro zum heutigen Kurs, mit Steuer; das Angebot jetzt zählt mit."""
        low = self.low_value(c["code"], slug)
        return None if low is None else _r(self.low_or_now(c, slug, o, low))

    def cell(self, c, slug, o):
        """Ein Angebot, wie es Tabellen und Karten anzeigen."""
        return {"low_eur": self.low_eur(c, slug, o),"local": o["local"] / 100, "regular": o["regular"] / 100, "sale": o["sale"],
                "net": o.get("net", o["local"]) / 100,
                "pct": round(100 * (1 - o["local"] / o["regular"])) if o["regular"] else 0,
                "end": o["end"], "start": o.get("start"), "eur": _r(self.oeur(c, o)), "est": c["estimated"],
                "lang": o.get("lang"), "nocard": bool(o.get("nocard")), "nsuid": o.get("nsuid"),
                "alone": None if o.get("direct") is not None else self.alone(c, o["local"]), "own": o.get("own"),
                **self.low(c["code"], slug, o), **self.mark(c, slug, o)}

    # ---- Titel

    def owned_flags(self, slug):
        """Steht der Titel schon in der Sammlung? Bei DLC: das Hauptspiel?"""
        parent = (self.items.get(slug) or {}).get("parent")
        return {"owned": slug in self.owned,
                "parent_owned": (parent in self.owned) if parent and self.owned else None}

    def title(self, slug):
        it = self.items.get(slug)
        return it["title"] if it else slug.replace("-", " ").title()

    def parent_title(self, slug):
        """Name des Hauptspiels, wenn der Titel ein DLC ist."""
        it = self.items.get(slug) or {}
        if not it.get("parent"):
            return None
        return it.get("parent_title") or self.title(it["parent"])

    def short(self, slug):
        """Titel ohne vorangestellten Spielnamen, damit DLCs unterscheidbar bleiben."""
        title, parent = self.title(slug), self.parent_title(slug)
        # Typografische und gerade Apostrophe gelten gleich („Luigi’s“ und „Luigi's“, 1.1.5)
        same = lambda t: t.lower().translate(_APOS)
        if parent and same(title).startswith(same(parent)):
            rest = title[len(parent):].lstrip(" :–-")
            if len(rest) > 2:
                return rest
        return title


_APOS = str.maketrans("’‘`´", "'" * 4)


def cfg_balance(c):
    return cents(c["cfg"].get("balance") or 0)


def _rest_value(base, total, balance):
    """Anteil der Kartenkosten, der als Rest auf dem Konto bleibt."""
    need = max(0, total - balance)
    rest = (base["rest"] or 0) - max(0, balance - total)
    if base["estimated"] or not base["cost"] or rest <= 0 or need <= 0:
        return 0.0
    return base["cost"] * rest / (need + rest)


def no_cards_warning(c):
    """Warum ein Land mit Guthabenkarten geschätzt rechnet, nach Ursache (0.95). Beginnt immer
    mit „Keine Guthabenkarte“, daran erkennt die Oberfläche die Warnung."""
    cards = c["cards"]
    if not cards:
        return "Keine Guthabenkarten eingetragen: Kosten geschätzt"
    if not any(x["stock"] for x in cards):
        return "Keine Guthabenkarte vorrätig: alle eingetragenen sind als nicht vorrätig markiert, Kosten geschätzt"
    return "Keine Guthabenkarte mit Preis: kein Preis gelesen oder eingetragen, Kosten geschätzt"


def make_payer(ctx, c):
    """Liefert pay(total) -> Kosten in Euro, Karten, Rest für ein Land.

    Zahlweg "auto" nimmt das Günstigere aus Kartenzahlung und Guthabenkarten.
    """
    balance = cents(c["cfg"].get("balance") or 0)
    mode = c["cfg"]["pay"]
    card_unit, gift_unit = ctx._units(c)
    # Nur Karten mit Preis (0.63): Eine Karte mit Link, deren Preis (noch) nicht gelesen ist, ginge
    # sonst still als Schätzung in die Rechnung. Hat keine Karte einen Preis, schätzt by_gift mit „ca.“
    stocked = [(x["face"], ctx.face_cost(c, x)) for x in c["cards"]
               if x["stock"] and ctx.face_cost(c, x) is not None]
    solver = None
    if stocked and mode in ("giftcard", "auto"):
        solver = CardSolver(stocked, c["rate"], ctx.markup(c))
    urls = {x["face"]: x["url"] for x in c["cards"]}
    # Der feste Teil der Servicegebühr fällt je Bestellung an, nicht je Karte: Jede
    # gelesene Karte trägt ihn im Preis, bei mehreren Karten zählt er nur einmal
    fixed = {x["face"]: x["fee_eur"] for x in c["cards"] if x.get("fee_eur")}

    def by_card(need, left):
        return {"cost": need * card_unit, "cards": [], "rest": left, "estimated": False,
                "via": "card"}

    def by_gift(need, left):
        if solver:
            try:
                r = solver.solve(need)
                fees = [fixed[f] for f, n in r["cards"] if f in fixed for _ in range(n)]
                if len(fees) > 1:
                    r["cost"] -= sum(fees) - max(fees)
                return {"cost": r["cost"], "cards": r["cards"], "rest": r["rest"] + left,
                        "estimated": False, "via": "giftcard"}
            except ValueError:
                pass
        if c["currency"] == "EUR":
            # Euro-Guthaben ohne Kartenpreis (0.99.3): zum Nennwert, wie Bewertung und Bestpreis rechnen
            # (_euro_card); keine Schätzung, ein Rest bliebe ohnehin auf dem eigenen Konto
            return {"cost": need / 100, "cards": [], "rest": left, "estimated": False, "via": "giftcard"}
        mid = 1 / 100 / c["rate"] * (1 + ctx.markup(c) / 100)
        return {"cost": need * mid, "cards": [], "rest": None, "estimated": True,
                "via": "giftcard"}

    def pay(total):
        need, left = max(0, total - balance), max(0, balance - total)
        if mode == "card":
            return by_card(need, left)
        if mode == "giftcard":
            return by_gift(need, left)
        a, b = by_card(need, left), by_gift(need, left)
        return b if not b["estimated"] and b["cost"] < a["cost"] - 0.005 else a

    def share(local):
        """Europreis eines Titels, wenn du nur für ihn Guthaben kaufst: die Karten,
        die ihn decken, anteilig. Ein Rest ist kein Verlust, zählt aber zu dem Kurs,
        zu dem diese Karten ihn liefern, nicht zum Kurs einer großen Karte (Entscheidung
        12.10.2026: keine 1000 MXN für ein Spiel zu 3 €). None: kein Kartenpreis
        bekannt, dann gilt der pauschale Kurs."""
        if local <= 0 or mode == "card":
            return None
        g = by_gift(local, 0)
        if g["estimated"] or not g["cost"]:
            return None
        gv = g["cost"] * local / (local + (g["rest"] or 0))
        return gv if mode == "giftcard" or gv < local * card_unit - 1e-9 else local * card_unit

    pay.urls = urls
    pay.share = share
    return pay, bool(solver)


# --------------------------------------------------------------------- Plan

def plan_country(ctx, code, override=None, must=(), basket=None, allowed=None, fillers=True):
    """Plan für ein Land. Mit `basket` gilt derselbe Warenkorb für alle Länder,
    sonst die Angebote des Landes plus eigene Änderungen (`override`).

    Ob sich der Wechsel lohnt, misst der Wechselgewinn: was dieselben Titel ohne diesen
    Wechsel kosten (günstigstes zählendes Land gleicher oder leichterer Stufe oder das
    Land, in dem das Konto steht, siehe Context.alt_price), minus was sie hier kosten.
    `allowed` begrenzt die Länder, die als Alternative zählen (Kaufplan). Ohne `fillers` fehlen
    die Vorschläge „Passt dazu“; sie kosten die meiste Rechenzeit („Andere Länder“, 0.77)."""
    c = ctx.countries[code]
    override = override or {}
    is_ref = code == countries.REFERENCE
    ref = ctx.ref
    offers = c["offers"]
    out = {"code": code, "name": c["meta"]["name"], "currency": c["currency"],
           "family": countries.FAMILIES[c["meta"]["family"]],
           "pay": c["cfg"]["pay"], "rate": c["rate"], "is_ref": is_ref,
           "tier": c["tier"], "tier_name": countries.TIERS.get(c["tier"], ""),
           "tax": c["tax"], "lang": c["meta"]["lang"],
           "note": c["meta"]["note"], "items": [], "fillers": [], "warnings": [],
           "price_at": ctx.price_at.get(c["meta"]["shop"]), "price_stale": c["meta"]["shop"] in ctx.price_stale,
           "available": len(offers), "saving": None, "missing": [], "trims": [],
           "current": bool(ctx.settings.get("current_country"))
                      and c["meta"]["shop"] == ctx.settings.get("current_country"),
           # Ohne eingetragenes Kontoland gilt Deutschland als Konto: kein Wechsel
           "home": is_ref and not ctx.settings.get("current_country")}
    if not c["rate"]:
        if not c["known"]:
            out["warnings"].append("Noch keine Preise abgerufen")
        else:
            out["warnings"].append("Kein Wechselkurs für " + str(c["currency"]))
        return out

    chosen = []
    if basket:
        must = ()
        chosen = [s for s in basket if s in offers]
        out["missing"] = [{"slug": s, "title": ctx.title(s), "short": ctx.short(s),
                           "dlc": bool(ctx.parent_title(s)), "nolang": s in c["nolang"]}
                          for s in basket if s not in offers]
    else:
        for slug in ctx.order:
            o = offers.get(slug)
            if not o:
                continue
            # Deutschland misst sich nicht an sich selbst: Dort zählt jedes Angebot
            cheaper = is_ref or slug not in ref or ctx.oeur(c, o) < ref[slug] - 0.005
            # Angebote, und dauerhaft günstige Normalpreise, die das Urteil "kaufen" tragen:
            # Sie zählen im Kaufplan, also auch hier (Entscheidung 12.10.2026)
            lasting = not o["sale"] and ctx.decides(o) and \
                ctx.grade(ctx.oeur(c, o), slug) == "buy"
            if (o["sale"] or lasting) and cheaper:
                chosen.append(slug)
        chosen = [s for s in chosen if s not in set(override.get("remove", []))]
        for slug in list(override.get("add", [])) + list(must):
            if slug in offers and slug not in chosen:
                chosen.append(slug)
    missing_must = [s for s in must if s not in offers]
    if missing_must:
        out["warnings"].append("Pflichttitel hier nicht kaufbar: " +
                               ", ".join(ctx.title(s) for s in missing_must))
        out["must_missing"] = True

    # Was jeder Titel ohne diesen Wechsel kostet; ohne Alternative der deutsche Preis,
    # ohne beides der Preis hier (dann bringt der Titel keinen Wechselgewinn)
    alt, alt_code = {}, {}
    for slug in offers:
        a = ctx.alt_price(slug, c["tier"], c["meta"]["shop"], allowed)
        if a:
            alt[slug], alt_code[slug] = a
        elif slug in ctx.ref and not is_ref:
            alt[slug], alt_code[slug] = ctx.ref[slug], countries.REFERENCE

    pay, has_cards = make_payer(ctx, c)
    # Eigene Angebote (ab 0.62) laufen nicht über das Guthaben: direkt in Euro, ohne Karten und Rest
    direct = {s: offers[s]["direct"] for s in chosen if offers[s].get("direct") is not None}
    total = sum(offers[s]["local"] for s in chosen if s not in direct)
    base = pay(total)
    extra_cost = sum(direct.values())

    no_ref = 0
    for slug in chosen:
        o, it = offers[slug], ctx.items[slug]
        r = ref.get(slug)
        if r is None:
            no_ref += 1
        out["items"].append({
            "slug": slug, "title": it["title"], "short": ctx.short(slug),
            "ref": _r(r), "dlc_of": ctx.parent_title(slug), "forced": slug in must,
            # DLC ohne Hauptspiel im selben Korb: braucht es meist aus dieser Region
            "needs_parent": bool(it.get("parent") and it["parent"] not in chosen),
            "alt": _r(alt.get(slug)), "alt_code": alt_code.get(slug),
            **ctx.owned_flags(slug),
            "over": bool(slug in alt and ctx.oeur(c, o) > alt[slug] + 0.005),
            **ctx.cell(c, slug, o),
        })
    ref_total = sum(ref.get(s, 0) for s in chosen)
    out.update({
        "total": total / 100, "cost": _r(base["cost"] + extra_cost), "estimated": base["estimated"],
        "direct": _r(extra_cost), "direct_n": len(direct),
        "via": base["via"],
        "cards": [{"face": f / 100, "count": n, "url": pay.urls.get(f, "")}
                  for f, n in base["cards"]],
        "rest": None if base["rest"] is None else base["rest"] / 100,
        "rest_eur": None if base["rest"] is None else _r(base["rest"] / 100 / c["rate"]),
        # Was der Rest gekostet hat: anteilig an den Karten, die du dafür kaufst
        "rest_value": _r(_rest_value(base, total, cfg_balance(c))),
        "ref_total": _r(ref_total),
    })
    if chosen:
        # Titel ohne deutschen Vergleichspreis zählen zum geschätzten Europreis
        ref_cmp = ref_total + sum(ctx.oeur(c, offers[s])
                                  for s in chosen if s not in ref)
        # Ein Rest bleibt auf dem Konto und ist kein Verlust: Ersparnis und
        # Schwelle rechnen mit dem, was die Spiele selbst kosten (Entscheidung 12.10.2026).
        # Ein hoher Rest wird gewarnt.
        games = base["cost"] - out["rest_value"] + extra_cost
        # Vorhandenes Guthaben ist schon bezahlt, aber nicht umsonst: Es zählt mit
        # dem Kurs, zu dem du es bekommst, sonst stünde ein Paket aus Guthaben bei 0 €
        used = min(cfg_balance(c), total)
        if used and c["unit"] is not None:
            games += used * c["unit"]
            out["balance_value"] = _r(used * c["unit"])
        out["games_cost"] = _r(games)
        # Was dieser Kauf kostet, wenn er stattfindet: Spiele ohne den Rest, der als
        # Guthaben bleibt (fürs Kaufprotokoll; ein späterer Wechsel zählt dort nicht)
        out["games_paid"] = _r(games)
        # Im Paket teilen sich die Titel die Karten: Europreis je Titel anteilig. Ab 0.99.3 auch, wenn
        # „das Günstigere“ den Korb mit Kreditkarte zahlt (vorher standen dann Kartenpreise da), und
        # auf den Cent so verteilt, dass die Zeilen zusammen die Spiele des Schritts ergeben
        if total and not base["estimated"] and games >= extra_cost:
            rows = [i for i in out["items"] if i["slug"] not in direct]
            whole = round((games - extra_cost) * 100)
            exact = [whole * offers[i["slug"]]["local"] / total for i in rows]
            cents_ = [int(x) for x in exact]
            for k in sorted(range(len(rows)), key=lambda k: cents_[k] - exact[k])[:whole - sum(cents_)]:
                cents_[k] += 1
            for i, ct in zip(rows, cents_):
                i["eur"] = ct / 100
                # Teurer als ohne den Wechsel: mit dem Preis, der in der Zeile steht (0.99.3)
                i["over"] = bool(i["slug"] in alt and i["eur"] > alt[i["slug"]] + 0.005)
        out["saving"] = _r(ref_cmp - games)
        out["saving_pct"] = round(100 * (ref_cmp - games) / ref_cmp) if ref_cmp else 0
        # Wechselgewinn gegenüber der Alternative ohne diesen Wechsel (Entscheidung 12.10.2026)
        alt_total = sum(alt.get(s, ctx.oeur(c, offers[s])) for s in chosen)
        out["alt_total"] = _r(alt_total)
        out["gain"] = _r(alt_total - games)
        codes = [alt_code[s] for s in chosen if s in alt_code]
        out["alt_codes"] = sorted(dict.fromkeys(codes), key=lambda k: -codes.count(k))
        limit = float((ctx.settings.get("tier_min_saving") or {}).get(str(c["tier"]), 0))
        out["threshold"] = limit
        # Auch der Weg zurück nach Deutschland ist ein Wechsel der Stufe leicht und muss
        # die Schwelle schaffen, außer das Konto steht dort (Entscheidung 12.10.2026)
        out["worth"] = out["current"] or out["home"] or out["gain"] >= limit

    # Abstand zum Optimum: je Titel, wie weit der Preis hier über dem Bestpreis
    # liegt, den es je irgendwo gab (Entscheidung 12.10.2026: wichtiger als Deutschland)
    # Paket: Optimum ist die Summe der Bestpreise aller Länder je Titel, also was
    # die Spiele gekostet hätten, wenn jedes zu seinem besten Zeitpunkt im besten Land
    # gekauft worden wäre. Abstand: was das Paket hier wirklich kostet (ohne Rest) minus Optimum.
    known = [i for i in out["items"] if i.get("champ") is not None and i.get("eur") is not None]
    out["opt_known"] = len(known)
    out["opt_at"] = sum(1 for i in known if i["eur"] <= i["champ"] * (1 + BEST_TOLERANCE) + 0.005)
    out["optimum"] = out["opt_gap"] = out["opt_pct"] = None
    # Paket-Güte mit denselben Grenzen wie das Urteil: buy, wenn jeder Titel "kaufen" ist,
    # good, wenn jeder mindestens "gut" ist
    grades = [ctx.grade(i["eur"], i["slug"]) for i in out["items"]]
    for i, g in zip(out["items"], grades):
        i["grade"] = g
    out["grade"] = None if not grades or None in grades else \
        "buy" if all(g == "buy" for g in grades) else "good" if "wait" not in grades else "wait"
    if known and chosen and out.get("games_cost") is not None:
        optimum = sum(i["champ"] for i in known) + sum(i["eur"] or 0 for i in out["items"] if i not in known)
        out["optimum"] = _r(optimum)
        out["opt_gap"] = _r(max(0.0, out["games_cost"] - optimum))
        out["opt_pct"] = round(100 * out["opt_gap"] / optimum) if optimum else 0
    if no_ref:
        out["warnings"].append(f"{no_ref} Titel ohne deutschen Vergleichspreis")
    if c["cfg"]["pay"] == "giftcard" and not has_cards:
        out["warnings"].append(no_cards_warning(c))
    if base["rest"] and chosen and c["cfg"]["rest_blocks"]:
        out["warnings"].append("Rest blockiert den Länderwechsel")
    elif chosen and out["rest_value"] >= HIGH_REST_EUR:
        out["warnings"].append(f"hoher Rest: {_eur(out['rest_value'])} bleiben auf dem Konto")
    need = sum(1 for i in out["items"] if i["needs_parent"])
    if need:
        out["warnings"].append(f"DLC braucht in der Regel das Hauptspiel aus {out['family']}"
                               f" ({need} DLC)")
    unknown = sum(1 for s in chosen if offers[s].get("lang") == "unknown")
    if unknown:
        out["warnings"].append(f"{unknown} Titel mit ungeprüfter Sprache")
    nolang = sum(1 for s in chosen if offers[s].get("lang") == "no")
    if nolang:
        out["warnings"].append(f"{nolang} Titel ohne deutsche Fassung")

    if not is_ref and fillers:
        out["fillers"] = _fillers(ctx, c, chosen, total, base, pay, has_cards, alt)
        if not basket:
            out["trims"] = _trims(ctx, c, chosen, total, base, pay, alt, must)
    return out


def _trims(ctx, c, chosen, total, base, pay, ref, must):
    """Titel, die hier unterm Strich mehr kosten als ohne diesen Wechsel (`ref`: Alternative).

    Gerechnet wird mit den Grenzkosten: was das Paket ohne den Titel weniger
    kostet. Löst ein Titel eine zusätzliche Guthabenkarte aus, ist das viel.
    """
    offers, res = c["offers"], []
    if len(chosen) < 2:
        return res
    for s in chosen:
        if s in must or s not in ref:
            continue
        if offers[s].get("direct") is not None:
            p, marginal = dict(base), offers[s]["direct"]     # eigenes Angebot: kostet genau sich selbst
        else:
            p = pay(total - offers[s]["local"])
            if p["cost"] is None or base["cost"] is None:
                continue
            marginal = base["cost"] - p["cost"]
        gain = marginal - ref[s]
        if gain >= MIN_FILLER_GAIN:
            res.append({"slug": s, "title": ctx.title(s), "short": ctx.short(s),
                        "marginal": _r(marginal),
                        "ref": _r(ref[s]), "gain": _r(gain),
                        "rest": None if p["rest"] is None else p["rest"] / 100})
    return sorted(res, key=lambda t: -t["gain"])[:2]


def _fillers(ctx, c, chosen, total, base, pay, has_cards, ref):
    offers = c["offers"]
    # Nur Titel, die hier höchstens „gut“ über ihrem Bestpreis liegen (0.77, Entscheidung 19.10.2026):
    # Was heute spart, aber weit über dem Bestpreis liegt, wäre im nächsten Angebot günstiger
    cand = [s for s in ctx.order if s in offers and s not in chosen and s in ref
            and ctx.grade(ctx.oeur(c, offers[s]), s) in ("buy", "good", None)]

    def rate_combo(slugs):
        add = sum(offers[s]["local"] for s in slugs if offers[s].get("direct") is None)
        p = pay(total + add)
        extra = p["cost"] - base["cost"] + sum(offers[s]["direct"] for s in slugs if offers[s].get("direct") is not None)
        gain = sum(ref[s] for s in slugs) - extra
        # Zum Vergleich mit dem Bestpreis (0.77): Preis der Titel hier in Euro und ihr Bestpreis
        champs = [ctx.champ_all.get(s) for s in slugs]
        return {"slugs": list(slugs), "titles": [ctx.title(s) for s in slugs],
                "eur": _r(sum(ctx.oeur(c, offers[s]) for s in slugs)),
                "champ": _r(sum(x[0] for x in champs)) if all(x and x[0] for x in champs) else None,
                "shorts": [ctx.short(s) for s in slugs],
                "local": add / 100, "extra": _r(extra), "ref": _r(sum(ref[s] for s in slugs)),
                "gain": _r(gain), "rest": None if p["rest"] is None else p["rest"] / 100,
                "sale": all(offers[s]["sale"] for s in slugs)}

    singles = sorted((rate_combo([s]) for s in cand), key=lambda f: -f["gain"])
    singles = [f for f in singles if f["gain"] >= MIN_FILLER_GAIN][:4]
    result = list(singles)
    if has_cards and chosen:
        best_single = singles[0]["gain"] if singles else 0.0
        small = sorted(cand, key=lambda s: offers[s]["local"])[:40]
        pairs = sorted((rate_combo(p) for p in combinations(small, 2)),
                       key=lambda f: -f["gain"])
        result += [f for f in pairs if f["gain"] > best_single + 0.5][:2]
    return result


def _eur(x):
    return f"{x:.2f}".replace(".", ",") + " €"


def num_txt(x):
    return (f"{x:.2f}".rstrip("0").rstrip(".")).replace(".", ",")


def _r(x):
    return None if x is None else round(x + 0.0, 2)


def mix(ctx, basket):
    """Korb auf mehrere Länder mit Kartenzahlung verteilen.

    Nur dort kostet der Wechsel nichts und es bleibt kein Rest: Stufe leicht,
    bezahlt per Karte. Jeder Titel geht in das Land, in dem er am wenigsten kostet.
    """
    eligible = [c for c in ctx.countries.values()
                if c["unit"] is not None and c["tier"] == 1
                and (c["cfg"]["pay"] == "card" or c["code"] == countries.REFERENCE)]
    parts, total = {}, 0.0
    for slug in basket:
        best = None
        for c in eligible:
            o = c["offers"].get(slug)
            if o and (best is None or ctx.oeur(c, o) < best[0] - 0.005):
                best = (ctx.oeur(c, o), c)
        if best is None:
            return None                      # ein Titel fehlt überall: kein Mix
        eur, c = best
        part = parts.setdefault(c["code"], {"code": c["code"], "name": c["meta"]["name"],
                                            "titles": [], "cost": 0.0})
        part["titles"].append(ctx.short(slug))
        part["cost"] += eur
        total += eur
    for p in parts.values():
        p["cost"] = _r(p["cost"])
    return {"cost": _r(total), "parts": sorted(parts.values(), key=lambda p: -p["cost"])}


def plans(data, settings, overrides=None, must=(), basket=None, now=None, with_mix=False, only=None):
    data, settings = with_added(data, settings, list(basket or []) + list(must or []) +
                              [s for o in (overrides or {}).values() for s in (o or {}).get("add") or []])
    ctx = _context(data, settings, now)
    overrides = overrides or {}
    must = [s for s in must if s in ctx.items]
    basket = [s for s in dict.fromkeys(basket or []) if s in ctx.items]
    # only: nur diese Länder (und das Vergleichsland), etwa für „Andere Länder“ am Schritt (1.0.3)
    res = [plan_country(ctx, code, overrides.get(code), must, basket)
           for code in ctx.countries if not only or code in only or code == countries.REFERENCE]
    if with_mix:
        # Länderkarten und Korb zeigen „Passt in den Rest“ wie der Kaufplan (0.94)
        from .kaufplan import rest_suggestions
        rest_suggestions(data, settings, ctx, res, None, set(), now)
        ref = [p for p in res if p["is_ref"]]
        rest = sorted((p for p in res if not p["is_ref"]),
                      key=lambda p: (bool(p.get("must_missing")), len(p["missing"]),
                                     p["saving"] is None, -(p["saving"] or 0), -p["available"]))
        return rest + ref, (mix(ctx, basket) if basket and not only else None)
    ref = [p for p in res if p["is_ref"]]
    rest = [p for p in res if not p["is_ref"]]
    # vollständige Körbe zuerst, dann nach Ersparnis
    rest.sort(key=lambda p: (bool(p.get("must_missing")), len(p["missing"]),
                             p["saving"] is None, -(p["saving"] or 0), -p["available"]))
    return rest + ref


def matrix(data, settings, now=None):
    """Alle Wishlist-Titel mal alle aktiven Länder, Preise in Euro."""
    ctx = _context(data, settings, now)
    cols = [{"code": c["code"], "name": c["meta"]["name"], "currency": c["currency"],
             "tier": c["tier"], "lang": c["meta"]["lang"]}
            for c in ctx.countries.values()]
    rows = []
    for slug in ctx.order:
        it = ctx.items[slug]
        cells, best = {}, None
        for code, c in ctx.countries.items():
            o = c["offers"].get(slug)
            if not o:
                if slug in c["nolang"]:
                    cells[code] = {"na": True, "nolang": True}
                elif slug in c["known"]:
                    cells[code] = {"na": True}
                continue
            cells[code] = ctx.cell(c, slug, o)
            eur = cells[code]["eur"]
            # Preisgüte wie im Urteil, nur für Angebote, die zählen (Zellfarbe im Preisvergleich)
            cells[code]["grade"] = ctx.grade(eur, slug) if ctx.decides(o) else None
            # Hervorgehoben wird das günstigste Angebot, nicht der günstigste Normalpreis
            if eur is not None and o["sale"] and ctx.decides(o) and (
                    best is None or eur < cells[best]["eur"]):
                best = code
        champ, typ = ctx.champ_all.get(slug), ctx.typ_all.get(slug)
        rows.append({"slug": slug, "title": it["title"], "cells": cells, "best": best,
                     "champ": None if not champ else {"eur": _r(champ[0]), "code": champ[1],
                                                      "est": champ[2]},
                     "typical": None if not typ else {"eur": _r(typ[0]), "code": typ[1],
                                                      "est": typ[2], "runs": typ[3]},
                     "dlc_of": ctx.parent_title(slug), **ctx.owned_flags(slug),
                     "no_ids": not any(it.get("ids", {}).values())})
    return {"cols": cols, "rows": rows}


VERDICTS = ["buy", "good", "wait", "none"]


def _not_buyable(data, settings, slug, it):
    """Warum ein Titel in keinem aktiven Land zu kaufen ist, nach der Antwort von Nintendo."""
    if not any((it.get("ids") or {}).values()):
        return "nicht im eShop gefunden"
    states = {((data.get("prices") or {}).get(code) or {}).get(slug, {}).get("status")
              for code, cfg in settings["countries"].items() if cfg.get("enabled")}
    states.discard(None)
    if "unreleased" in states or "pre_order" in states or "preorder" in states:
        return "noch nicht erschienen"
    if states and states <= {"not_found", "sales_termination", "unknown"}:
        return ("nicht mehr im Verkauf" if "sales_termination" in states else
                "im eShop nicht einzeln kaufbar (etwa nur im Abo oder in einem Paket)")
    return "nirgends kaufbar"


def radar(data, settings, targets=None, now=None):
    """Eine Zeile je Titel: bester Preis jetzt, Bestpreis, Urteil.

    Das Urteil misst nur die Preisgüte: wie nah das günstigste zählende Angebot am
    Bestpreis liegt, mit denselben Grenzen für jedes Land. Ob sich der Weg in ein
    schweres Land lohnt, entscheiden Kaufplan und Pakete über den Wechselgewinn.
    "Jetzt, leicht" (Stufen 1 und 2) und "Jetzt, schwer" (Stufe 3) zeigen beide Seiten.
    """
    ctx = _context(data, settings, now)
    targets = targets or {}
    rows = []
    for slug in ctx.order:
        if ctx.items[slug].get("nso") or ctx.items[slug].get("extra"):
            continue                 # Mitgliedschaft und DLC außerhalb der Wishlist nur, wenn du sie dazunimmst
        best = {"easy": None, "hard": None}
        unsure, nocard = [], []
        for code, c in ctx.countries.items():
            o = c["offers"].get(slug)
            if not o or c["unit"] is None:
                continue
            if not ctx.decides(o):
                (nocard if o.get("nocard") else unsure).append(code)
                continue
            raw = ctx.oeur(c, o)
            group = "easy" if c["tier"] <= 2 else "hard"
            if best[group] is None or raw < best[group]["raw"] - 0.005:
                best[group] = dict(ctx.cell(c, slug, o), code=code, name=c["meta"]["name"],
                                   currency=c["currency"], raw=raw, lang_code=c["meta"]["lang"],
                                   tier=c["tier"],
                                   shop_cards=c["shop_cards"] and c["unit"] != ctx._units(c)[0])
        easy, hard = best["easy"], best["hard"]
        champ_all = ctx.champ_all.get(slug)

        def champ(entry):
            if not entry:
                return None
            return {"eur": _r(entry[0]), "code": entry[1], "est": entry[2],
                    "name": countries.BY_CODE[entry[1]]["name"]}
        try:
            target = float(targets.get(slug))
        except (TypeError, ValueError):
            target = None
        both = [b for b in (easy, hard) if b]
        cheapest = min(both, key=lambda b: b["raw"]) if both else None
        # Das Urteil gilt dem günstigsten zählenden Preis jetzt, egal in welcher Stufe und
        # ob mit Rabatt: Ein dauerhaft günstiger Normalpreis am Bestpreis ist ein Kauf
        # wie ein Angebot, ein teureres Angebot anderswo ändert daran nichts (Entscheidung 12.10.2026)
        top = cheapest
        shown = cheapest                  # das Angebot, dessen Abstand die Zeile zeigt
        diff = gap = None
        if shown and champ_all and champ_all[0]:
            diff = max(0.0, _r(shown["raw"] - champ_all[0]))
            gap = max(0, round(100 * (shown["raw"] / champ_all[0] - 1)))
        typ = ctx.typ_all.get(slug)
        typ_diff = typ_gap = None
        if shown and typ:
            typ_diff = _r(shown["raw"] - typ[0])
            typ_gap = round(100 * (shown["raw"] / typ[0] - 1)) if typ[0] else 0

        def where(b):
            return f" in {b['name']}" + (" (schwer)" if b["tier"] >= 3 else "")
        verdict, reason, at = "none", _not_buyable(data, settings, slug, ctx.items[slug]), None
        if (unsure or nocard) and not both:
            why = ([", ".join(unsure) + ": Sprache ungeprüft"] if unsure else []) + \
                  ([", ".join(nocard) + ": keine Guthabenkarte mit Preis"] if nocard else [])
            reason = "nur dort kaufbar, wo es nicht zählt (" + "; ".join(why) + ")"
        if target is not None and cheapest and cheapest["raw"] <= target + 0.005:
            verdict, reason, at = "buy", "Zielpreis erreicht" + where(cheapest), cheapest
        elif top:
            g = ctx.grade(top["raw"], slug)
            at = top
            lasting = "" if top["sale"] else ", Normalpreis"
            if g == "buy":
                verdict = "buy"
                reason = ("Bestpreis" if top["mark"] == "best" else f"nur {_eur(diff)} über Bestpreis") + where(top) + lasting
            elif g == "good":
                verdict, reason = "good", f"{_eur(diff)} ({gap} %) über Bestpreis" + where(top) + lasting
            elif top["raw"] < 0.005:
                reason = "kostenlos"
            elif g is None:
                reason = "Bestpreis noch nicht bekannt"
            else:
                verdict = "wait"
                reason = f"war {_eur(diff)} günstiger" if diff else "war schon günstiger"
        # Cashback gibt es nicht immer: nur ein Hinweis, wenn es das Angebot unter den
        # Bestpreis drücken könnte (bezahlt mit Guthaben aus einem Kartenshop)
        cb = float(settings.get("cashback_pct") or 0)
        cashback = None
        if cb > 0 and champ_all and verdict not in ("buy",):
            for b in (easy, hard):
                if b and b["sale"] and b.get("shop_cards"):
                    with_cb = b["raw"] * (1 - cb / 100)
                    if with_cb <= champ_all[0] * (1 + BEST_TOLERANCE) + 0.005 and (
                            cashback is None or with_cb < cashback["eur"]):
                        cashback = {"eur": _r(with_cb), "code": b["code"], "pct": cb}
        # Urteil ohne Verlauf (0.95): sichtbar machen, statt es still wie jedes andere zu zeigen
        nohist = verdict in ("buy", "good") and not reason.startswith("Zielpreis") and not ctx.has_history(slug)
        at_info = None if not at else {"code": at["code"], "name": at["name"], "tier": at["tier"]}
        shown_info = None if not shown else {"code": shown["code"], "name": shown["name"],
                                              "tier": shown["tier"], "sale": shown["sale"]}
        for b in (easy, hard):
            if b:
                b.pop("raw")
        it = ctx.items[slug]
        rows.append({"slug": slug, "title": it["title"], "dlc_of": ctx.parent_title(slug),
                     **ctx.owned_flags(slug),
                     "easy": easy, "hard": hard, "de": _r(ctx.ref.get(slug)),
                     "champ": champ(champ_all),
                     "gap": gap, "diff": diff, "shown": shown_info,
                     "typical": None if not typ else {
                         "eur": _r(typ[0]), "code": typ[1], "est": typ[2], "runs": typ[3],
                         "name": countries.BY_CODE[typ[1]]["name"]},
                     "typ_diff": typ_diff, "typ_gap": typ_gap, "cashback": cashback,
                     "target": target, "verdict": verdict, "at": at_info,
                     "lang_unsure": [] if both else unsure + nocard,
                     "reason": reason, "nohist": nohist, "no_ids": not any(it.get("ids", {}).values()),
                     "rhythm": sale_rhythm(ctx, slug)})
    rows.sort(key=lambda r: (VERDICTS.index(r["verdict"]), r["gap"] if r["gap"] is not None else 999))
    return rows


def sale_rhythm(ctx, slug, limit=4):
    """Angebotsrhythmus je Land aus den DekuDeals-Angebotsphasen der letzten 24 Monate:
    Zahl, übliche Abstände, das letzte Angebot und die Monate, in die sie meist fielen.
    Eine Vorhersage gibt es nicht. Nur bei recht gleichmäßigen Abständen nennt der
    Rhythmus, wann das nächste nach diesem Muster üblich wäre (Schätzung)."""
    since = datetime.fromtimestamp(ctx.now.timestamp() - TYPICAL_DAYS * 86400,
                                   timezone.utc).strftime("%Y-%m-%d")
    today = ctx.now.strftime("%Y-%m-%d")
    out = []
    for code, c in ctx.countries.items():
        e = ctx.lows.get(c["meta"]["shop"], {}).get(slug) or {}
        runs = sorted(r for r in e.get("sales") or [] if r[0] >= since)
        if not runs:
            continue
        starts = [datetime.strptime(r[0], "%Y-%m-%d") for r in runs]
        gaps = [(b - a).days / 7 for a, b in zip(starts, starts[1:])]
        last = runs[-1]
        row = {"code": code, "name": c["meta"]["name"], "count": len(runs),
               "since": max(e.get("sales_from") or since, since),
               "last_start": last[0], "last_end": last[2] if len(last) > 2 else None,
               "weeks_ago": round((ctx.now.replace(tzinfo=None) - starts[-1]).days / 7),
               "gap": None, "gap_min": None, "gap_max": None, "months": [], "next": None}
        if row["last_end"] and row["last_end"] >= (ctx.now - timedelta(days=2)).strftime("%Y-%m-%d"):
            row["last_end"] = None          # läuft noch oder endete gerade: kein Ende bekannt
            row["running"] = last[0] <= today
        if gaps:
            mean = sum(gaps) / len(gaps)
            row.update(gap=round(mean), gap_min=round(min(gaps)), gap_max=round(max(gaps)))
            # gleichmäßig: mindestens 4 Angebote, alle Abstände höchstens 30 % vom Schnitt
            if len(runs) >= 4 and all(abs(g - mean) <= 0.3 * mean for g in gaps):
                row["next"] = (starts[-1] + timedelta(weeks=mean)).strftime("%Y-%m-%d")
        if len(runs) >= 3:
            months = {}
            for d in starts:
                months[d.month] = months.get(d.month, 0) + 1
            row["months"] = sorted(m for m, n in sorted(months.items(), key=lambda x: -x[1])[:3] if n >= 2)
        out.append(row)
    return sorted(out, key=lambda r: (-r["count"], r["name"]))[:limit]


def is_upgrade(slug, title=""):
    """Upgrade-Paket für die Switch 2: DekuDeals führt es als DLC des Switch-1-Spiels."""
    t = f"{slug} {title}".lower().replace("-", " ")
    return "upgrade pack" in t and "switch 2" in t


_S2_SUFFIX = re.compile(r"-(?:nintendo-)?switch-2-edition(?:-.*)?$")


def _now_eur(r):
    """Einkaufspreis des Angebots, das das Urteil eines Radar-Titels trägt."""
    shown = (r or {}).get("shown") or {}
    best = next((b for b in ((r or {}).get("easy"), (r or {}).get("hard"))
                 if b and b.get("code") == shown.get("code")), None)
    return (best.get("eur"), shown.get("name"), bool(best.get("est"))) if best else (None, None, False)


def switch2_paths(data, rows, settings=None):
    """Switch-2-Edition auf der Wishlist: Reicht das Upgrade-Paket?

    Die Edition heißt bei DekuDeals wie das Switch-1-Spiel plus "Nintendo Switch 2
    Edition", das Upgrade-Paket ist ein DLC des Switch-1-Spiels. Hast du das Spiel,
    genügt das Paket; sonst steht der Weg Spiel plus Paket gegen die Edition, soweit
    die Preise bekannt sind (beides auf der Wishlist). {Kürzel der Edition: Angaben}"""
    rel = data.get("rel") or {}
    owned = owned_set(data, settings)
    by = {r["slug"]: r for r in rows}
    items = data.get("items") or {}
    out = {}
    for r in rows:
        slug = r["slug"]
        if is_upgrade(slug, r["title"]) or "switch 2 edition" not in f"{slug} {r['title']}".lower().replace("-", " "):
            continue
        base = _S2_SUFFIX.sub("", slug)
        if base == slug or not (base in owned or base in rel or base in items):
            continue
        cand = [(s, t) for s, t in (rel.get(base) or {}).get("dlc") or [] if is_upgrade(s, t)]
        cand += [(s, it.get("title") or s) for s, it in items.items()
                 if it.get("active") and is_upgrade(s, it.get("title") or "") and
                 (it.get("parent") == base or s.startswith(base + "-"))]
        up = cand[0] if cand else None
        title = (rel.get(base) or {}).get("title") or (items.get(base) or {}).get("title") or base
        info = {"base": base, "base_title": title, "base_owned": base in owned,
                "upgrade": up[0] if up else None, "upgrade_title": up[1] if up else None,
                "upgrade_owned": bool(up and up[0] in owned)}
        ed_eur = _now_eur(r)[0]
        up_eur, up_name, up_est = _now_eur(by.get(up[0])) if up else (None, None, False)
        base_eur, base_name, base_est = _now_eur(by.get(base))
        info.update(edition_eur=ed_eur, upgrade_eur=up_eur, upgrade_name=up_name,
                    upgrade_verdict=(by.get(up[0]) or {}).get("verdict") if up else None,
                    base_eur=base_eur, base_name=base_name, est=up_est or base_est)
        # Was der Weg über das Upgrade kostet: nur das Paket, oder Spiel plus Paket
        path = up_eur if info["base_owned"] else (
            up_eur + base_eur if up_eur is not None and base_eur is not None else None)
        info["path_eur"] = _r(path)
        info["path_saving"] = _r(ed_eur - path) if path is not None and ed_eur is not None else None
        out[slug] = info
    return out


def _switch2_choice(data, rows, wanted, settings=None):
    """Switch 2 im Kaufplan: Du kaufst die Edition oder das Switch-1-Spiel plus
    Upgrade-Paket, nie beides; das Paket auch später (Entscheidung 12.10.2026).

    Hast du das Spiel, fällt die Edition weg, das Paket plant der Plan wie jeden
    Wishlist-Titel. Stehen Edition und Spiel zum Kauf an, bleibt der günstigere Weg.
    Ist der Preis des Pakets unbekannt, bleibt die Edition. Liefert die übrigen
    Kandidaten und die weggelassenen Titel mit Grund."""
    wanted = list(wanted)
    listed = {r["slug"] for r in rows}
    skip = []

    def drop(slug, reason):
        if slug in wanted:
            wanted.remove(slug)
            skip.append({"slug": slug, "reason": reason})

    for ed, p in switch2_paths(data, rows, settings).items():
        base, up = p["base"], p["upgrade"]
        if p["base_owned"]:
            why = "Switch-1-Fassung in der Sammlung, das Upgrade-Paket genügt"
            if p["upgrade_owned"]:
                why = "Switch-1-Fassung und Upgrade-Paket in der Sammlung"
            elif up not in listed:
                why += " (steht nicht auf der Wishlist)"
            drop(ed, why)
        elif ed in wanted and base in wanted:
            if p["path_saving"] is not None and p["path_saving"] > 0.005:
                drop(ed, f"Switch-1-Fassung plus Upgrade-Paket ist {_eur(p['path_saving'])} günstiger")
            else:
                why = ("die Switch-2-Edition ist nicht teurer als Spiel plus Upgrade-Paket"
                       if p["path_eur"] is not None else
                       "die Switch-2-Edition kommt in den Plan, der Preis des Upgrade-Pakets ist unbekannt")
                drop(base, why)
                drop(up, why)
        elif ed in wanted and up in wanted:
            drop(up, "ohne die Switch-1-Fassung nutzlos, die Switch-2-Edition kommt in den Plan")
    return wanted, skip


def bundles(data, rows, settings=None):
    """Komplett-Editionen und Pakete gegen Einzelkauf.

    Was ein Paket enthält, nennt DekuDeals lückenhaft: der Abschnitt "Contains" der
    Paketseite (oft nur das Hauptspiel) und "Included In" auf den Seiten der Teile.
    Beides zusammen ergibt die bekannten Teile. Verglichen wird mit dem, was die
    fehlenden Teile einzeln jetzt kosten, sofern jedes einen Preis hat (Wishlist).
    Teile in der Sammlung zählen nicht, du hättest sie doppelt.
    {"packs": {Paket: Angaben}, "in": {Titel: [{slug, title, wish}]}}"""
    rel = data.get("rel") or {}
    owned = owned_set(data, settings)
    by = {r["slug"]: r for r in rows}
    items = data.get("items") or {}
    parts, names = {}, {}
    for slug, e in rel.items():
        for b_slug, b_title in e.get("in") or []:
            parts.setdefault(b_slug, {})[slug] = e.get("title") or slug
            names.setdefault(b_slug, b_title)
        for p_slug, p_title in e.get("has") or []:
            parts.setdefault(slug, {}).setdefault(p_slug, p_title)
    title = lambda s: (by.get(s) or {}).get("title") or (rel.get(s) or {}).get("title") or names.get(s) or s
    packs, inside = {}, {}
    for b_slug, ps in parts.items():
        known = [{"slug": p, "title": title(p) if p in by or p in rel else t, "owned": p in owned,
                  "eur": _now_eur(by.get(p))[0], "wish": p in by} for p, t in ps.items()]
        for k in known:
            if k["wish"] and b_slug != k["slug"]:
                inside.setdefault(k["slug"], []).append(
                    {"slug": b_slug, "title": title(b_slug), "wish": b_slug in by})
        if b_slug not in by:
            continue
        missing = [k for k in known if not k["owned"]]
        priced = all(k["eur"] is not None for k in missing)
        alone = _r(sum(k["eur"] for k in missing)) if missing and priced else None
        pack_eur, pack_name, est = _now_eur(by[b_slug])
        # Ein Paket hat mindestens zwei Teile: Ist nur eines bekannt, fehlt der Rest
        # in den Daten, und ein Vergleich wäre schief
        if len(known) < 2:
            alone = None
        packs[b_slug] = {"parts": known, "have": [k["title"] for k in known if k["owned"]],
                         "partial": len(known) < 2,
                         "alone": alone, "eur": pack_eur, "name": pack_name, "est": est,
                         "unpriced": [k["title"] for k in missing if k["eur"] is None],
                         "saving": _r(alone - pack_eur) if alone is not None and pack_eur is not None else None}
    return {"packs": packs, "in": inside}


def _nso(slug, title):
    return "nintendo switch online" in f"{slug} {title}".lower().replace("-", " ")


def wish_dlc_parents(data):
    """Hauptspiele der DLC auf der Wishlist, die selbst nicht darauf stehen: {Spiel: [DLC]}.
    Ihre Seite je Region nennt die Sprachen, die eines DLC oft nicht (0.68)."""
    items = data.get("items") or {}
    out = {}
    for slug, it in items.items():
        p = it.get("parent")
        if it.get("active") and p and not (items.get(p) or {}).get("active"):
            out.setdefault(p, []).append(slug)
    return out


def extra_dlc(data, settings):
    """DLC deiner Spiele, die fehlen und nicht auf der Wishlist stehen: {DLC: (Titel, Spiel)}.
    Ohne Abo-Inhalte, ohne abgehakte und ignorierte."""
    rel, owned = data.get("rel") or {}, owned_set(data, settings)
    marks = settings.get("dlc_marks") or {}
    wished = {s for s, it in (data.get("items") or {}).items() if it.get("active")}
    out = {}
    for game in owned_games(data, settings):
        e = rel.get(game)
        if not e or e.get("parent") or marks.get(game) == "ignore_all":
            continue
        for d_slug, d_title in e.get("dlc") or []:
            if d_slug in owned or d_slug in wished or marks.get(d_slug) in ("have", "ignore") \
                    or _nso(d_slug, d_title):
                continue
            out.setdefault(d_slug, (d_title, game))
    return out


def extra_context(data, settings, now=None):
    """Rechnet die fehlenden DLC der Sammlung wie Wishlist-Titel: eigene Angebote je Land
    aus ihren Preisen (xprices), dieselben Karten und Kurse. None ohne solche DLC."""
    cache = getattr(_shared, "cache", None)
    key = ("extra", id(data), id(settings), now)
    if cache is not None and key in cache and cache[key][0] is data and cache[key][1] is settings:
        return cache[key][2]
    x = _extra_context(data, settings, now)
    if cache is not None:
        cache[key] = (data, settings, x)
    return x


def _extra_context(data, settings, now=None):
    wanted = extra_dlc(data, settings)
    extra = {s: e for s, e in (data.get("extra") or {}).items() if s in wanted}
    if not extra:
        return None
    glangs = data.get("glangs") or {}
    # Sprache: eigene Angabe des DLC (Europa), sonst die seines Spiels (eine Seite je Spiel)
    items = {s: {"title": e["title"], "parent": None, "dlc_of": e["parent"], "active": True,
                 "order": i, "ids": e.get("ids") or {},
                 "langs": dict((glangs.get(e["parent"]) or {}).get("langs") or {}, **(e.get("langs") or {})),
                 "langs_src": (glangs.get(e["parent"]) or {}).get("langs_src") or {}}
             for i, (s, e) in enumerate(extra.items())}
    # Tiefstpreise liest der Abgleich seit 0.53.3 auch für fehlende DLC: Bestpreis wie bei Titeln
    return _context(dict(data, items=items, prices=data.get("xprices") or {}), settings, now)


def extra_offers(data, settings, now=None):
    """Fehlende DLC deiner Spiele für „Titel dazunehmen …“ (0.72): [{slug, title, game, local:
    {Land: Preis in Landeswährung}, eur: günstigster zählender Preis}]. Kostenloses fehlt."""
    xctx = extra_context(data, settings, now)
    if not xctx:
        return []
    want, rel = extra_dlc(data, settings), data.get("rel") or {}
    out = []
    for slug, it in xctx.items.items():
        local = {code: c["offers"][slug]["local"] / 100 for code, c in xctx.countries.items()
                 if slug in c["offers"] and c["offers"][slug]["local"] > 0 and xctx.decides(c["offers"][slug])}
        if not local:
            continue
        best = _extra_best(xctx, slug)
        game = want.get(slug, (None, None))[1]
        out.append({"slug": slug, "title": it["title"], "game": (rel.get(game) or {}).get("title") or it.get("dlc_of"),
                    "local": local, "eur": best["eur"] if best else None})
    return sorted(out, key=lambda x: ((x["game"] or "").casefold(), x["title"].casefold()))


def _extra_best(xctx, slug):
    """Günstigstes zählendes Angebot eines fehlenden DLC in Euro."""
    best = None
    for code, c in xctx.countries.items():
        o = c["offers"].get(slug)
        if not o or c["unit"] is None or not xctx.decides(o):
            continue
        eur = xctx.oeur(c, o)
        if best is None or eur < best["eur"] - 0.005:
            best = {"eur": _r(eur), "code": code, "name": c["meta"]["name"], "est": c["estimated"],
                    "sale": o["sale"], "end": o.get("end") if o["sale"] else None,
                    "pct": round(100 * (1 - o["local"] / o["regular"])) if o["sale"] and o["regular"] else None}
    if best:
        # Güte wie bei Titeln: am Bestpreis (Stern), kaufen, gut (0.53.3)
        # Ohne Tiefstpreis oder Verlauf von DekuDeals wäre jedes günstigste Land „am Bestpreis“:
        # dann keine Güte (bis der Abgleich die Seiten gelesen hat)
        known = any(slug in t and ("low" in t[slug] or t[slug].get("hist")) for t in xctx.lows.values())
        champ = xctx.champ_all.get(slug) if known else None
        best["grade"] = xctx.grade(best["eur"], slug) if champ and best["eur"] >= 0.005 else None
        best["at_best"] = bool(champ and best["eur"] >= 0.005
                               and best["eur"] <= champ[0] * (1 + BEST_TOLERANCE) + 0.005)
        best["champ"] = _r(champ[0]) if champ else None
    return best


GONE_MISSES = 2       # wie sync.ID_MISSES: so oft ohne eShop-Eintrag, dann nicht mehr erhältlich


def _gone(data, slug):
    """Fehlender DLC, den es nicht mehr zu kaufen gibt: Die ID-Suche (sync_extra_ids) fand
    ihn in keiner gesuchten Region, jeweils mindestens GONE_MISSES Mal. Meist Inhalte, die
    es nur im Spiel gibt oder die aus dem eShop verschwunden sind."""
    e = (data.get("extra") or {}).get(slug)
    if not e or any((e.get("ids") or {}).values()):
        return False
    checked = e.get("ids_checked") or {}
    misses = e.get("ids_misses") or {}
    return bool(checked) and all(misses.get(f, 0) >= GONE_MISSES for f in checked)


def _group_packs(data, dlc, links):
    """Fehlende Pässe mit ihren Teilen zusammenfassen: Der Pass bekommt „pack“ (Teile,
    schon da, einzeln, als Pass, günstiger), die Teile „in_pack“ und stehen direkt
    darunter. Ein Teil gehört zum größten Paket, das ihn enthält. Liefert die neu
    geordnete Liste und die Gruppen."""
    rows = {d["slug"]: d for d in dlc}
    heads = []
    for d in dlc:
        if d["slug"] in links and not d["have"] and not d["ignored"]:
            parts = [p for p in pack_parts(data, {d["slug"]}) if p in rows]
            if parts:
                heads.append((d, parts))
    heads.sort(key=lambda h: -len(h[1]))
    taken, groups = set(), []
    for head, parts in heads:
        if head["slug"] in taken:
            continue                       # steckt selbst in einem größeren Paket
        mine = [rows[p] for p in parts if p not in taken and rows[p] is not head]
        if not mine:
            continue
        taken.update(p["slug"] for p in mine)
        mine.sort(key=lambda p: [x["slug"] for x in dlc].index(p["slug"]))
        todo = [p for p in mine if not p["have"] and not p["ignored"] and not p["gone"]]
        single = _r(sum(p["eur"] for p in todo)) if todo and all(
            p.get("eur") is not None for p in todo) else None
        cheaper = None
        if todo and head.get("eur") is not None and (single is None or head["eur"] < single - 0.005):
            cheaper = "pass"
        elif single is not None:
            cheaper = "single"
        head["pack"] = {"n": len(mine), "have": sum(1 for p in mine if p["have"]),
                        "open": len(todo), "single": single, "cheaper": cheaper}
        for p in mine:
            p["in_pack"] = head["title"]
        groups.append({"row": head, "parts": mine, "pack": head["pack"]})
    out = []
    for d in dlc:
        if d["slug"] in taken:
            continue
        out.append(d)
        g = next((g for g in groups if g["row"] is d), None)
        if g:
            out.extend(g["parts"])
    return out, groups


# Genres auf Deutsch (1.6.1): DekuDeals nennt sie wie der amerikanische eShop, die Europa-Suche wie der
# britische. Gleich heißt gleich nach dieser Liste; was fehlt, bleibt englisch
GENRE_DE = {"action": "Action", "adventure": "Abenteuer", "role-playing": "Rollenspiel", "rpg": "Rollenspiel",
            "role playing": "Rollenspiel", "simulation": "Simulation", "platformer": "Plattformer",
            "platform": "Plattformer", "puzzle": "Puzzle", "party": "Party", "sports": "Sport", "sport": "Sport",
            "racing": "Rennspiel", "fighting": "Kampfspiel", "strategy": "Strategie", "shooter": "Shooter",
            "music": "Musik", "education": "Lernen", "educational": "Lernen", "arcade": "Arcade", "other": "Sonstiges",
            "lifestyle": "Alltag", "practical": "Alltag", "board game": "Brettspiel", "communication": "Kommunikation",
            "first-person": "Ego-Perspektive", "fitness": "Fitness", "training": "Training", "utility": "Werkzeug",
            "video": "Video", "multiplayer": "Mehrspieler", "study": "Lernen", "application": "Anwendung",
            "first-person shooter": "Shooter", "survival": "Survival", "horror": "Horror", "roguelike": "Roguelike",
            "metroidvania": "Metroidvania", "visual novel": "Visual Novel", "card game": "Kartenspiel",
            "trivia": "Quiz", "quiz": "Quiz", "tower defense": "Tower Defense", "rhythm": "Rhythmus",
            "animal life": "Tiere", "football": "Fußball", "golf": "Golf"}


def _genre(name):
    return GENRE_DE.get(re.sub(r"\s+", " ", str(name).strip().lower()), str(name).strip())


def _pub(name):
    return re.sub(r"[^a-z0-9]+", "", re.sub(r"(?i)\b(inc|ltd|llc|co|corp|gmbh|s\.?a|games|entertainment)\b\.?", "",
                                              str(name or "").lower()))


_S2_CUT = re.compile(r"\s+[–—-]\s+Nintendo Switch 2 Edition", re.I)
CLARIFY_FILE = os.path.join(os.path.dirname(__file__), "klarstellungen.json")


@functools.lru_cache(maxsize=1)
def clarifications():
    """Geklärte Widersprüche zwischen DekuDeals und Nintendo (1.7.2), im Repository mit Quelle:
    {Spiel: {"players.offline" | "players.online" | "year" | "publisher": {"v": Wert, "src": Adresse,
    "note": Text, "date": JJJJ-MM-TT}}}. Öffentliche Angaben zu Spielen, nichts aus einem Konto."""
    try:
        with open(CLARIFY_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return {k: v for k, v in d.items() if isinstance(v, dict) and not k.startswith("_")}
    except (OSError, ValueError):
        return {}


def _clarify(g, fix):
    """Eine Klarstellung gilt vor beiden Quellen, der Widerspruch verschwindet."""
    for key, c in fix.items():
        if not isinstance(c, dict) or "v" not in c:
            continue
        if key.startswith("players.") and key[8:] in g["players"]:
            g["players"][key[8:]] = {"v": c["v"], "ok": True, "src": "geklärt", "fix": c.get("src")}
        elif key == "year" and g.get("year"):
            g.update(year=str(c["v"]), year_ok=True, year_alt=None, year_fix=c.get("src"))
        elif key == "publisher" and g.get("publisher"):
            g.update(publisher=c["v"], pub_ok=True, pub_alt=None, pub_fix=c.get("src"))


def contradictions(games):
    """Liste „Widersprüche“ (1.7.2): wo Nintendo etwas anderes nennt als DekuDeals und noch keine
    Klarstellung gilt. [{slug, title, what, deku, nin}]"""
    out = []
    lab = {"offline": "Spieler an einer Konsole", "local": "Spieler lokal drahtlos", "online": "Spieler online"}
    rng = lambda v: "ja" if not v else str(v[1]) if v[0] == v[1] else f"{v[0]}–{v[1]}"
    for g in games:
        for k, p in g["players"].items():
            if p.get("alt"):
                out.append({"slug": g["slug"], "title": g["title"], "what": lab[k], "key": "players." + k,
                            "deku": rng(p["v"]), "nin": rng(p["alt"])})
        if g.get("year_alt"):
            out.append({"slug": g["slug"], "title": g["title"], "what": "Jahr", "key": "year", "deku": g["year"], "nin": g["year_alt"]})
        if g.get("pub_alt"):
            out.append({"slug": g["slug"], "title": g["title"], "what": "Verlag", "key": "publisher",
                        "deku": g["publisher"], "nin": g["pub_alt"]})
    return out


def game_infos(data, settings):
    """Ansicht „Spiele“ der Sammlung (1.6.1): je Spiel die Spielinfos von DekuDeals (rel.info), geprüft
    gegen die Nintendo-Europa-Suche (rel.nin). DekuDeals gilt; nennt Nintendo etwas anderes, steht der
    andere Wert daneben (alt). Genre kommt von Nintendo, ohne Nintendo-Angabe von DekuDeals (1.7.0).
    Pakete (1.7.0, Entscheidung 27.10.2026): Ein Paket, dessen Teile Spiele der Sammlung sind, steht nicht
    als eigene Zeile da; seine Spiele tragen „aus“ und nehmen fehlende Angaben von der Seite des Pakets."""
    rel = data.get("rel") or {}
    links = data.get("links") or {}
    owned_list = list(dict.fromkeys(data.get("owned") or []))
    direct = set(owned_list) | eshop_matches(data)["owned"]
    via = pack_parts(data, direct, pack_block(settings))
    owned = owned_set(data, settings)
    bought = {}
    for r in eshop_matches(data).get("rows") or []:
        if r.get("slug") and r.get("date"):
            bought[r["slug"]] = max(bought.get(r["slug"], ""), str(r["date"])[:10])
    slugs = [s for s in owned_games(data, settings) if not (rel.get(s) or {}).get("parent")]
    games = set(slugs)
    packs = {s for s in slugs if any(p in games for p in links.get(s) or {})}
    marks = settings.get("game_marks") or {}
    # GameShare (1.7.2): Nintendos Liste, je Seitenkennung und je Name (auch ohne „– Nintendo Switch 2 Edition …“)
    gs_id, gs_name = {}, {}
    for r in (data.get("gameshare") or {}).get("rows") or []:
        if r.get("id"):
            gs_id[str(r["id"])] = r
        t0 = r.get("t") or ""
        for t in {t0, t0.split(" + ")[0], _S2_CUT.split(t0)[0]}:
            if _tnorm(t):
                gs_name.setdefault(_tnorm(t), r)
    fixes = clarifications()

    def pack_of(slug):
        """Das Paket der Sammlung, aus dem ein Spiel kommt (auch über Zwischenstufen), sonst None."""
        seen, c = set(), via.get(slug)
        while c and c not in packs and c not in seen:
            seen.add(c)
            c = via.get(c)
        return c if c in packs else next((p for p in packs if slug in (links.get(p) or {})), None)
    out, genres = [], {}
    for slug in slugs:
        if slug in packs:
            continue
        e = rel.get(slug) or {}
        title = e.get("title") or ((data.get("items") or {}).get(slug) or {}).get("title") or slug.replace("-", " ").title()
        pk = pack_of(slug)
        pe = rel.get(pk) or {} if pk else {}
        di, ni = dict(e.get("info") or {}), dict(e.get("nin") or {})
        filled = [k for k, v in (pe.get("info") or {}).items() if k not in di and v not in (None, "", [], {})]
        for k in filled:
            di[k] = pe["info"][k]
        if pk and not (ni.get("at") and not ni.get("none")) and (pe.get("nin") or {}).get("at"):
            ni = dict(pe["nin"])
        nin = bool(ni.get("at")) and not ni.get("none")
        g = {"slug": slug, "title": title, "read": e.get("iv", 0) > 0 or bool(filled), "nin": nin,
             "via": (rel.get(pk) or {}).get("title") or pk if pk and slug not in direct else None}
        if pk:
            g["pack"] = {"slug": pk, "title": (rel.get(pk) or {}).get("title") or pk, "filled": filled}
        # System: Switch 2 Edition im Namen, ein vorhandenes Upgrade-Paket oder eine Quelle nennt Switch 2
        ups = [d for d, t in e.get("dlc") or [] if is_upgrade(d, t)]
        sysn = " ".join([str(di.get("platform") or "")] + [str(x) for x in ni.get("sys") or []]).lower()
        g["s2"] = ("edition" if _S2.search(" " + _tnorm(title)) else "upgrade" if any(d in owned for d in ups)
                   else "switch2" if "switch 2" in sysn else None)
        # Genre (1.7.0): Nintendo Europa trennt feiner (23 statt 12 Genres), ohne Nintendo-Angabe DekuDeals
        dg = list(dict.fromkeys(_genre(x) for x in di.get("genre") or []))
        ng = list(dict.fromkeys(_genre(x) for x in ni.get("genre") or []))
        g["genre"] = [{"n": x, "ok": x in dg and x in ng, "src": "Nintendo" if ng else "DekuDeals"} for x in (ng or dg)]
        for x in g["genre"]:
            genres[x["n"]] = genres.get(x["n"], 0) + 1
        # Spieler (1.6.2): an einer Konsole gegen Nintendos players_to_system, online gegen players_to_online;
        # Nintendos players_to allein ist die Höchstzahl über alle Spielweisen und taugt nicht zum Vergleich
        pl = di.get("players") or {}
        npl = {"offline": ni.get("sys_pl"), "online": ni.get("on_pl")}
        players = {}
        for k in ("offline", "local", "online"):
            if pl.get(k):
                players[k] = {"v": pl[k], "ok": bool(npl.get(k) and npl[k][1] == pl[k][1])}
                if npl.get(k) and npl[k][1] != pl[k][1]:
                    players[k]["alt"] = npl[k]
            elif npl.get(k):
                players[k] = {"v": npl[k], "ok": False, "src": "Nintendo"}
        if "offline" not in players and ni.get("players") and not ni.get("on_pl"):
            players["offline"] = {"v": ni["players"], "ok": False, "src": "Nintendo"}
        if "online" not in players and ni.get("online") is True:
            players["online"] = {"v": None, "ok": False, "src": "Nintendo"}
        g["players"] = players
        g["max"] = max([v["v"][1] for v in players.values() if v["v"]] or [0]) or None
        g["paid_online"] = ni.get("online") is True       # Nintendo: Online-Spiel braucht die Mitgliedschaft
        dm, nm = di.get("modes") or [], ni.get("modes") or []
        g["modes"] = [{"n": m, "ok": m in dm and m in nm} for m in ("tv", "tabletop", "handheld") if m in dm or m in nm]
        # Koop (1.7.2): genau von IGDB, sonst nur der Hinweis, dass HowLongToBeat eine Koop-Spielzeit kennt
        ig = e.get("igdb") or (pe.get("igdb") if pk else None) or {}
        if ig.get("coop"):
            g["coop"] = dict(ig["coop"], src="IGDB")
        elif (di.get("hltb") or {}).get("coop"):
            g["coop"] = {"any": True, "src": "HowLongToBeat"}
        else:
            g["coop"] = False
        gsr = gs_id.get(str(ni.get("page") or "")) or gs_name.get(_tnorm(title)) or gs_name.get(_tnorm(_S2_CUT.split(title)[0]))
        if gsr:
            g["gs"] = {"local": bool(gsr.get("local")), "online": bool(gsr.get("online"))}
        for k in ("mc", "mcu", "oc", "hltb", "developer", "size_gb"):
            if di.get(k) not in (None, "", {}):
                g[k] = di[k]
        dr, nr = di.get("released"), ni.get("released")
        if dr or nr:
            g["year"] = (dr or nr)[:4]
            g["year_ok"] = bool(dr and nr and dr[:4] == nr[:4])
            g["year_alt"] = nr[:4] if dr and nr and dr[:4] != nr[:4] else None
            g["released"] = dr if dr and (len(dr) > 4 or not nr) else nr
        dp, np_ = di.get("publisher"), ni.get("publisher")
        if dp or np_:
            g["publisher"] = dp or np_
            g["pub_ok"] = bool(dp and np_ and (_pub(dp) in _pub(np_) or _pub(np_) in _pub(dp)))
            g["pub_alt"] = np_ if dp and np_ and not g["pub_ok"] else None
        ages = [a for a in (di.get("age"), ni.get("age")) if a]
        if ages:
            g["age"] = " · ".join(dict.fromkeys(ages))
            for a in ages:                          # USK für die Zeile, PEGI für den Tooltip (1.7.0)
                m = re.match(r"(USK|PEGI)\s+(\S+)", a)
                if m:
                    g.setdefault(m.group(1).lower(), m.group(2))
        _clarify(g, fixes.get(slug) or {})
        if slug in bought:
            g["bought"] = bought[slug]
        g["score"] = di.get("mc") or di.get("oc")
        h = di.get("hltb") or {}
        g["hours"] = h.get("main") or h.get("solo") or h.get("extra") or h.get("coop")
        g["mm"] = ni.get("mm")
        if ni.get("langs"):
            g["langs"] = ni["langs"]                   # Nintendo Europa, englische Namen klein (1.7.1)
        g["mine"] = marks.get(slug) or {}              # Mein Stand von Hand (1.7.1)
        out.append(g)
    out.sort(key=lambda g: g["title"].lower())
    # Feste Reihenfolge der Genres in jeder Zeile (1.7.0): das seltenere, also genauere zuerst, gleich
    # häufige nach dem Alphabet, „Sonstiges“ zuletzt. So steht ein Genre überall an derselben Stelle
    # zu den anderen, und die zwei sichtbaren sagen am meisten
    rank = {n: (n == "Sonstiges", c, n) for n, c in genres.items()}
    for g in out:
        g["genre"].sort(key=lambda x: rank[x["n"]])
    return {"games": out, "genres": sorted(genres.items(), key=lambda x: (-x[1], x[0])),
            "contra": contradictions(out), "fixed": sum(1 for s in fixes if s in games),
            "entries": len(owned_list), "dlc_entries": sum(1 for s in owned_list if (rel.get(s) or {}).get("parent")),
            "via_packs": sum(1 for g in out if g["via"]), "packs": len(packs),
            "read": sum(1 for g in out if g["read"]), "with_info": sum(1 for g in out if g["genre"] or g["players"]),
            "confirmed": sum(1 for g in out if g["nin"])}


def collection(data, settings, targets=None, now=None, rows=None):
    """Spiele der Sammlung mit ihren Zusatzinhalten: welche du hast, welche fehlen.

    Grundlage sind die Abschnitte "DLC" der DekuDeals-Artikelseiten (sync_related).
    Ob du einen DLC hast, sagt die Sammlung, die du bei DekuDeals pflegst; was sie nicht
    kennt, hakst du hier ab („habe ich“), Unwichtiges blendest du aus („ignorieren“, je DLC
    oder für alle DLC eines Spiels). Die DekuDeals-Sammlung geht vor. Steht ein
    fehlender DLC auf der Wishlist, gibt es Urteil und Einkaufspreis wie im Radar;
    sonst kennt das Tool keinen Preis (keine Nintendo-ID)."""
    rel = data.get("rel") or {}
    owned_list = list(dict.fromkeys(data.get("owned") or []))
    owned = owned_set(data, settings)
    direct = set(owned_list) | eshop_matches(data)["owned"]
    via = pack_parts(data, direct, pack_block(settings))   # nur über ein Paket vorhanden: {Teil: Paket}
    links = data.get("links") or {}
    by = {r["slug"]: r for r in (rows if rows is not None else radar(data, settings, targets, now))}
    items = data.get("items") or {}
    marks = settings.get("dlc_marks") or {}
    xctx = extra_context(data, settings, now)
    games, unread, no_dlc, plain, waiting, hints = [], 0, 0, [], [], []

    def name(slug, e=None):
        return (e or {}).get("title") or (items.get(slug) or {}).get("title") or \
            slug.replace("-", " ").title()
    def pack_name(slug):
        c = via.get(slug)
        return name(c, rel.get(c)) if c else None
    for slug in owned_games(data, settings):
        e = rel.get(slug)
        if not e:
            unread += 1
            waiting.append({"slug": slug, "title": name(slug)})
            continue
        if e.get("parent"):
            continue                         # selbst ein DLC, steht beim Hauptspiel
        dlc = []
        for d_slug, d_title in e.get("dlc") or []:
            if _nso(d_slug, d_title):
                continue                     # Abo-Inhalte gibt es nicht zu kaufen
            r = by.get(d_slug)
            mark = marks.get(d_slug)
            row = {"slug": d_slug, "title": d_title, "owned": d_slug in owned,
                   "wish": r is not None, "upgrade": is_upgrade(d_slug, d_title)}
            if row["owned"] and d_slug in via and d_slug not in direct:
                row["via"] = pack_name(d_slug)       # „im Paket …“
            # „stimmt nicht“: DekuDeals nennt ihn in einem Paket, das du hast, er fehlt aber
            row["not_in_pack"] = mark == "missing" and d_slug not in direct
            row["have"] = row["owned"] or mark == "have"
            row["by_hand"] = not row["owned"] and mark == "have"
            row["ignored"] = not row["have"] and (mark == "ignore" or marks.get(slug) == "ignore_all")
            row["gone"] = not row["have"] and not row["ignored"] and r is None and _gone(data, d_slug)
            row["mark"] = mark
            if r:
                shown = r.get("shown") or {}
                best = next((b for b in (r.get("easy"), r.get("hard"))
                             if b and b.get("code") == shown.get("code")), None)
                row.update(verdict=r["verdict"], reason=r.get("reason"),
                           eur=best.get("eur") if best else None, est=bool(best and best.get("est")),
                           code=shown.get("code"), name=shown.get("name"),
                           end=best.get("end") if best and best.get("sale") else None)
            elif xctx and not row["have"] and not row["ignored"] and not row["gone"]:
                best = _extra_best(xctx, d_slug)
                if best:
                    row.update(eur=best["eur"], est=best["est"], code=best["code"],
                               name=best["name"], end=best["end"], sale=best["sale"], pct=best.get("pct"),
                               grade=best.get("grade"), at_best=best.get("at_best"), champ=best.get("champ"))
            dlc.append(row)
        if not dlc:
            no_dlc += 1
            plain.append({"slug": slug, "title": name(slug, e),
                          "via": pack_name(slug) if slug not in direct else None})
            continue
        dlc, groups = _group_packs(data, dlc, links)
        have = sum(1 for d in dlc if d["have"])
        ignored = sum(1 for d in dlc if d["ignored"])
        gone = sum(1 for d in dlc if d["gone"])
        # „fehlen“ zählt Inhalte, nicht Kaufwege: Ein Pass mit bekannten Teilen zählt nicht
        # zusätzlich, für die Summe zählt der günstigere Weg (einzeln oder als Pass)
        open_ = [d for d in dlc if not d["have"] and not d["ignored"] and not d["gone"]
                 and not d.get("pack")]
        priced = [d for d in open_ if d.get("eur") is not None and not d.get("in_pack")]
        cost = sum(d["eur"] for d in priced)
        n_priced, n_sale = len(priced), sum(1 for d in priced if d.get("sale") or d.get("end"))
        for g in groups:
            info, head = g["pack"], g["row"]
            todo = [d for d in g["parts"] if not d["have"] and not d["ignored"] and not d["gone"]]
            if not todo:
                continue
            wished = [d for d in todo if d["wish"]]
            if wished and not head["wish"] and info["cheaper"] == "pass":
                # Teile stehen auf der Wishlist, der Pass nicht, ist aber günstiger als alle
                # fehlenden Teile einzeln: Hinweis, ihn auf die Wishlist zu setzen (0.52)
                hints.append({"game": e.get("title") or slug, "slug": head["slug"], "title": head["title"],
                              "eur": head["eur"], "est": head.get("est"), "single": info["single"],
                              "open": len(todo), "saving": _r(info["single"] - head["eur"]),
                              "wished": [{"slug": d["slug"], "title": d["title"], "eur": d.get("eur")} for d in wished]})
            if info["cheaper"] == "pass":
                cost += head["eur"]
                n_priced += len(todo)
                n_sale += len(todo) if head.get("sale") or head.get("end") else 0
            else:
                part_p = [d for d in todo if d.get("eur") is not None]
                cost += sum(d["eur"] for d in part_p)
                n_priced += len(part_p)
                n_sale += sum(1 for d in part_p if d.get("sale") or d.get("end"))
        games.append({"slug": slug, "title": e.get("title") or slug, "dlc": dlc,
                      "via": pack_name(slug) if slug not in direct else None,
                      "have": have, "ignored": ignored, "gone": gone,
                      "ignore_all": marks.get(slug) == "ignore_all",
                      "missing": len(open_),
                      "missing_eur": _r(cost) if n_priced else None,
                      "missing_priced": n_priced,
                      "missing_sale": n_sale})
    games.sort(key=lambda g: (g["missing"] == 0, g["title"].lower()))
    plain.sort(key=lambda g: g["title"].lower())
    waiting.sort(key=lambda g: g["title"].lower())
    priced = [g for g in games if g["missing_priced"]]
    free = [{"slug": d["slug"], "title": d["title"], "game": g["title"], "end": d.get("end")}
            for g in games for d in g["dlc"]
            if d.get("eur") is not None and d["eur"] < 0.005 and not d["have"] and not d["ignored"]
            and not d["gone"] and not d.get("pack")]
    return {"games": games, "owned": len(owned_list), "unread": unread, "no_dlc": no_dlc,
            "plain": plain, "waiting": waiting, "pass_hints": hints, "free": free,
            "missing_eur": _r(sum(g["missing_eur"] for g in priced)) if priced else None,
            "missing_priced": sum(g["missing_priced"] for g in priced),
            "missing_sale": sum(g["missing_sale"] for g in priced)}


LANG_CHECK_URL = {
    "JP": "https://store-jp.nintendo.com/item/software/D{nsuid}",
    "AM": "https://ec.nintendo.com/US/en/titles/{nsuid}",
    "AS": "https://ec.nintendo.com/SG/en/titles/{nsuid}",
}


def lang_todo(data, settings, now=None):
    """Sprache je Titel und Region mit aktivem Land, für Titel mit deutscher Fassung in
    Deutschland: Wishlist-Titel und die Spiele, denen DLC fehlt (Füllartikel). Jeder Titel
    steht einmal je Region in der Liste, unabhängig vom Preis: von Nintendo gelesen, von
    dir bestätigt oder offen. Von Hand gilt vor Nintendo."""
    ctx = _context(data, settings, now, include_all=True)
    live = _context(data, settings, now)       # Bestpreis nur über die aktiven Länder
    xctx = extra_context(data, settings, now)

    def cheapest(slug, codes, c_=live):
        """Günstigster Preis jetzt oder je in diesen Ländern, in Euro."""
        best = None
        for code in codes:
            c = c_.countries.get(code)
            o = c and c["offers"].get(slug)
            if not o or c["unit"] is None:
                continue
            eur = c_.low_or_now(c, slug, o, c_.low_value(code, slug))
            if best is None or eur < best[0]:
                best = (eur, code)
        return best
    fams = {}
    for c in ctx.countries.values():
        fam = c["meta"]["family"]
        if fam != "EU" and settings["countries"][c["code"]]["enabled"]:
            fams.setdefault(fam, []).append(c["code"])
    out, conf = [], settings.get("lang_confirm") or {}

    def row(slug, title, fam, codes, nsuid, state, nintendo, text, here, champ, src=None, doubt=None, **more):
        return dict({"slug": slug, "title": title, "family": fam,
                     "here": None if not here else {"eur": _r(here[0]), "code": here[1]},
                     "champ": None if not champ else {"eur": _r(champ[0]), "code": champ[1]},
                     # dort gerade günstiger als der Bestpreis: die Antwort ändert jetzt etwas
                     "matters": bool(here and (not champ or here[0] < champ[0] - 0.005)),
                     "family_name": countries.FAMILIES[fam], "codes": codes,
                     "url": ec_url(LANG_CHECK_URL.get(fam, ""), nsuid),
                     "state": state, "manual": isinstance((conf.get(slug) or {}).get(fam), bool),
                     "text": text, "nintendo": nintendo, "nsuid": nsuid,
                     # Programm-ID passt laut titledb nicht zu Europa, DekuDeals bleibt bei der ID
                     "doubt": bool(doubt),
                     # Herkunft der gelesenen Angabe: None = Nintendo, "titledb" = Titelliste
                     "src": src if text else None}, **more)
    for slug in ctx.order:
        it = ctx.items[slug]
        # DLC mit Hauptspiel auf der Wishlist richtet sich nach dem Spiel
        if it.get("parent") in ctx.items or ctx.german(it, "EU", slug) is not True:
            continue
        game = ctx.glangs.get(it.get("parent")) or {} if it.get("parent") else {}
        for fam, codes in fams.items():
            ids = (it.get("ids") or {}).get(fam) or []
            if ids:
                # DLC ohne eigene Angabe: Seite und Angabe seines Spiels (0.68)
                src = it if (it.get("langs") or {}).get(fam) or not ((game.get("ids") or {}).get(fam)) else game
                out.append(row(slug, it["title"], fam, codes, (src.get("ids") or {})[fam][0] if src is game else ids[0],
                               ctx.german(it, fam, slug), ctx.german(it, fam, slug, by_hand=False),
                               (src.get("langs") or {}).get(fam), cheapest(slug, codes),
                               live.champ_all.get(slug), (src.get("langs_src") or {}).get(fam),
                               (src.get("ids_doubt") or {}).get(fam)))
    if xctx:
        rel, games = data.get("rel") or {}, {}
        for s in xctx.order:
            games.setdefault(xctx.items[s]["dlc_of"], []).append(s)
        for game, dlc in games.items():
            if not any(xctx.german(xctx.items[s], "EU", s) is True for s in dlc):
                continue
            for fam, codes in fams.items():
                with_id = [s for s in dlc if (xctx.items[s].get("ids") or {}).get(fam)]
                if not with_id:
                    continue
                first = xctx.items[with_id[0]]
                prices, matters = [], False
                for s in with_id:
                    p = cheapest(s, codes, xctx)
                    # Kostenlose DLC gibt es überall gratis: kein „ab 0,00 €“, kein „günstiger“ (0.53.3)
                    if p and p[0] >= 0.005:
                        prices.append(p)
                        best = _extra_best(xctx, s)
                        matters = matters or not best or p[0] < best["eur"] - 0.005
                out.append(row(game, (rel.get(game) or {}).get("title") or game, fam, codes,
                               # Seite des Spiels, wenn seine ID bekannt ist (nennt die Sprachen)
                               ((((data.get("glangs") or {}).get(game) or {}).get("ids") or {}).get(fam)
                                or first["ids"][fam])[0], xctx.german(first, fam, with_id[0]),
                               xctx.german(first, fam, with_id[0], by_hand=False),
                               (first.get("langs") or {}).get(fam), min(prices) if prices else None,
                               None, (first.get("langs_src") or {}).get(fam), dlc=len(dlc), matters=matters))
    return out


def card_status(data, settings, now=None):
    """Je Land die Karten mit Link: gelesener Preis, Stand oder Fehler."""
    ctx = _context(data, settings, now, include_all=True)
    out = {}
    for code, c in ctx.countries.items():
        rows = []
        odd_shop = {round(i["face"] * 100): i["price"] for i in c["implausible"] if i["src"] == "shop"}
        how = ctx.how(c) if c["rate"] else None
        used = (how or {}).get("card") or {}
        for x in c["cards"]:
            e = ctx.card_prices.get(x["url"]) or {} if x["url"] else {}
            error = e.get("error")
            if x["face"] in odd_shop:
                error = f"gelesen {_eur(odd_shop[x['face']])}, unglaubhaft, ignoriert"
            f = ctx.factor(c, x) if c["rate"] else None
            rows.append({"face": x["face"] / 100, "cost": x["cost"], "live": x.get("live"),
                         "fee": x.get("fee"), "fee_eur": x.get("fee_eur"),
                         "manual": x.get("manual", x["cost"]), "checked": e.get("checked"),
                         "error": error, "url": bool(x["url"]), "stock": x["stock"],
                         "value": round(x["face"] / 100 / (1.0 if c["currency"] == "EUR" else c["rate"]), 2)
                         if c["rate"] else None,
                         "factor": round(f, 4) if f is not None else None,
                         "rating": ctx.rate_card(c, f, x["url"]) if c["rate"] else None,
                         "used": bool(used) and used.get("face") == x["face"] / 100 and x["stock"]})
        if rows:
            out[code] = rows
    return out


def card_factors(data, settings, now=None):
    """Faktor jeder Karte mit gelesenem Shop-Preis, für den Verlauf: {Link: (Datum, Faktor)}."""
    ctx = _context(data, settings, now, include_all=True)
    out = {}
    for c in ctx.countries.values():
        if not c["rate"]:
            continue
        for x in c["cards"]:
            if x["url"] and x.get("live"):
                day = datetime.fromtimestamp(x["live"], timezone.utc).date().isoformat()
                out[x["url"]] = (day, round(ctx.factor(c, x), 4))
    return out


def pay_info(data, settings, now=None):
    """Zahlweg und eigener Kurs je Land, auch für abgeschaltete Länder."""
    ctx = _context(data, settings, now, include_all=True)
    return {code: ctx.how(c) for code, c in ctx.countries.items() if c["unit"] is not None}


def price_levels(data, settings, now=None):
    """Preisniveau jedes Landes gegenüber Deutschland, gemessen an der Wishlist.

    Auch für abgeschaltete Länder, damit sich entscheiden lässt, welche lohnen.
    """
    ctx = _context(data, settings, now, include_all=True)
    out = {}
    for code, c in ctx.countries.items():
        if code == countries.REFERENCE or c["unit"] is None:
            continue
        common = [s for s in c["offers"] if s in ctx.ref]
        if len(common) < 3:
            continue
        here = sum(ctx.oeur(c, c["offers"][s]) for s in common)
        home = sum(ctx.ref[s] for s in common)
        out[code] = {
            "level": round(100 * (here / home - 1)) if home else 0,
            "titles": len(common),
            "cheaper": sum(1 for s in common
                           if ctx.oeur(c, c["offers"][s]) < ctx.ref[s] * 0.95),
            "sale": sum(1 for s in common if c["offers"][s]["sale"]),
        }
    return out




def price_history(data, settings, history, slug, now=None):
    """Preisverlauf eines Titels aus der eigenen Aufzeichnung, je Land.

    Die Aufzeichnung hält nur Preiswechsel fest (Zeitpunkt, Preis ohne Steuer).
    Europreise rechnen mit dem heutigen Kurs und Zahlweg, damit Länder und
    Zeitpunkte vergleichbar bleiben. Ein Angebot ist jede Strecke unter dem
    heutigen Normalpreis; Lücken, in denen das Tool nicht lief, sieht die
    Aufzeichnung nicht.
    """
    ctx = _context(data, settings, now)
    now = ctx.now
    out = {"slug": slug, "title": ctx.title(slug), "now": now.isoformat(timespec="seconds"),
           "since": None, "countries": []}
    champ = ctx.champ_all.get(slug)
    out["champ"] = None if not champ else {"eur": _r(champ[0]), "code": champ[1], "est": champ[2]}
    typ = ctx.typ_all.get(slug)
    out["typical"] = None if not typ else {"eur": _r(typ[0]), "code": typ[1], "est": typ[2], "runs": typ[3]}
    for code, c in ctx.countries.items():
        series = (history.get(c["meta"]["shop"]) or {}).get(slug) or []
        points = [(t, _parse_dt(t), v) for t, v in series if _parse_dt(t) and v is not None]
        if not points or c["unit"] is None:
            continue
        points.sort(key=lambda p: p[1])
        o = c["offers"].get(slug)
        # Normalpreis ohne Steuer: heute bekannt oder der höchste aufgezeichnete
        regular = o["regular_net"] / 100 if o else max(v for _, _, v in points)
        gross = 1 + c["tax"] / 100

        def eur(v):
            return _r(ctx.est(c, round(v * 100 * gross)))
        sales, run = [], None
        for i, (t, dt, v) in enumerate(points):
            if v < regular - 1e-9:
                if run is None:
                    run = {"start": t, "end": None, "low": v}
                run["low"] = min(run["low"], v)
            elif run is not None:
                run["end"] = t
                sales.append(run)
                run = None
        if run is not None:
            sales.append(run)
        first = points[0][1]
        span = max((now - first).total_seconds(), 1)
        on_sale = 0.0
        for s in sales:
            end = _parse_dt(s["end"]) if s["end"] else now
            on_sale += max((end - _parse_dt(s["start"])).total_seconds(), 0)
        done = [(_parse_dt(s["end"]) - _parse_dt(s["start"])).total_seconds() / 86400
                for s in sales if s["end"]]
        low_t, _, low_v = min(points, key=lambda p: (p[2], p[1]))
        for s in sales:
            s.update(low_eur=eur(s["low"]), pct=round(100 * (1 - s["low"] / regular)) if regular else 0)
        out["countries"].append({
            "code": code, "name": c["meta"]["name"], "currency": c["currency"],
            "tier": c["tier"], "est": c["estimated"], "regular": _r(regular * gross),
            "regular_eur": eur(regular),
            "points": [[t, _r(v * gross), eur(v)] for t, _, v in points],
            "now_eur": _r(ctx.oeur(c, o)) if o else None,
            "low": _r(low_v * gross), "low_eur": eur(low_v), "low_at": low_t,
            "deku_low_eur": (lambda lv: None if lv is None else eur(lv))(
                (ctx.lows.get(c["meta"]["shop"], {}).get(slug) or {}).get("low")),
            "sales": sales, "sale_count": len(sales),
            # Angebote laut DekuDeals in den letzten 24 Monaten: Die eigene Aufzeichnung
            # kennt nur die Zeit, seit das Tool läuft
            "deku_sales": (lambda e: len(e["sales"]) if "sales" in e else None)(
                ctx.lows.get(c["meta"]["shop"], {}).get(slug) or {}),
            "on_sale_pct": round(100 * on_sale / span),
            "typical_days": round(sorted(done)[len(done) // 2], 1) if done else None,
            "days": round(span / 86400, 1),
        })
        if out["since"] is None or points[0][0] < out["since"]:
            out["since"] = points[0][0]
    out["countries"].sort(key=lambda x: (x["code"] != countries.REFERENCE, x["low_eur"]))
    return out


def case_export(data, settings, history, slug, now=None):
    """Alles, was die Rechnung für einen Titel braucht, zum Nachbauen eines Falls.
    Wishlist- und Sammlungslink bleiben draußen."""
    shops = {countries.BY_CODE[c]["shop"] for c in countries.ORDER}
    it = (data.get("items") or {}).get(slug)
    keep = dict(settings, wishlist_url="", collection_url="")
    row = next((r for r in radar(data, settings, now=now) if r["slug"] == slug), None)
    parent = (it or {}).get("parent")
    return {
        "slug": slug, "item": it,
        "parent": {parent: data["items"].get(parent)} if parent and parent in data.get("items", {}) else {},
        "prices": {s: (data.get("prices") or {}).get(s, {}).get(slug) for s in shops
                   if (data.get("prices") or {}).get(s, {}).get(slug)},
        "lows": {s: (data.get("lows") or {}).get(s, {}).get(slug) for s in shops
                 if (data.get("lows") or {}).get(s, {}).get(slug)},
        "history": {s: (history.get(s) or {}).get(slug) for s in shops if (history.get(s) or {}).get(slug)},
        "fx": data.get("fx"), "card_prices": data.get("card_prices"), "settings": keep, "radar": row,
    }


NSO_TITLE = "Online-Mitgliedschaft"
# Varianten der Online-Mitgliedschaft. IDs je Region von Nintendos Mitgliedschaftsseite (ab 0.58),
# je Land von DekuDeals, wo es sie führt (slug); 1 Monat und Erweiterungspaket Familie führt DekuDeals
# nicht (Verbindungstest 14.10.2026). accounts: Konten, auf die sich der Preis verteilt.
NSO_VARIANTS = [
    {"key": "m1", "slug": None, "label": "1 Monat", "months": 1, "accounts": 1},
    {"key": "m3", "slug": "nintendo-switch-online-3-month-membership", "label": "3 Monate", "months": 3, "accounts": 1},
    {"key": "m12", "slug": "nintendo-switch-online-12-month-membership", "label": "12 Monate", "months": 12, "accounts": 1},
    {"key": "ep", "slug": "nintendo-switch-online-expansion-pack-12-month-individual-membership",
     "label": "Erweiterungspaket (12 Monate)", "months": 12, "accounts": 1},
    {"key": "fam", "slug": "nintendo-switch-online-12-month-family-membership", "label": "Familie (12 Monate)",
     "months": 12, "accounts": 8, "family": True},
    {"key": "epfam", "slug": None, "label": "Erweiterungspaket Familie (12 Monate)", "months": 12, "accounts": 8,
     "family": True},
]
NSO_KEYS = [v["key"] for v in NSO_VARIANTS]


def nso_variants(data):
    """Je Variante {ids, checked, lows, urls}. Bis 0.56 lag nur „12 Monate“ flach in data.nso;
    so gelesen laden alte Dateien weiter."""
    nso = data.get("nso") or {}
    v = dict(nso.get("v") or {})
    if "ids" in nso and "m12" not in v:
        v["m12"] = {k: nso.get(k) or {} for k in ("ids", "checked", "lows", "urls")}
    return v


NSO_PREFIX = "nso-"


def nso_items(data):
    """Die Varianten als wählbare Einträge für Korb und Kaufplan (ab 0.69): [{slug, title, key}]."""
    have = {k for t in (data.get("nso_prices") or {}).values() for k in NSO_KEYS if nso_price(t, k)}
    return [{"slug": NSO_PREFIX + v["key"], "title": f"{NSO_TITLE} {v['label']}", "key": v["key"],
             "family": bool(v.get("family"))} for v in NSO_VARIANTS if v["key"] in have]


def with_added(data, settings, wanted):
    """Daten und Einstellungen mit dem, was du ausdrücklich dazunimmst: fehlende DLC deiner Spiele
    (ab 0.72) und Varianten der Mitgliedschaft als Titel (ab 0.69):
    Preise je Land aus nso_prices, Deutsch in jeder Region (die Sprachregel gilt nicht), eigene
    Angebote der Variante (etwa Amazon-Codes) wie eigene Angebote eines Titels. Nur für Korb und
    Kaufplan, wenn du sie ausdrücklich dazunimmst; Urteil und Wishlist kennen sie nicht."""
    keys = [s[len(NSO_PREFIX):] for s in dict.fromkeys(wanted or []) if str(s).startswith(NSO_PREFIX)
            and s[len(NSO_PREFIX):] in NSO_KEYS]
    # Fehlende DLC deiner Spiele, die nicht auf der Wishlist stehen (0.72): wie in extra_context,
    # Preise aus xprices, Sprache vom DLC oder seinem Spiel
    extra, items0 = data.get("extra") or {}, data.get("items") or {}
    xs = [s for s in dict.fromkeys(wanted or []) if s in extra and not (items0.get(s) or {}).get("active")]
    if not keys and not xs:
        return data, settings
    items = dict(items0)
    prices = {shop: dict(t) for shop, t in (data.get("prices") or {}).items()}
    own = list(settings.get("own_offers") or [])
    glangs = data.get("glangs") or {}
    for i, s in enumerate(xs):
        e, g = extra[s], glangs.get(extra[s].get("parent")) or {}
        items[s] = {"title": e["title"], "parent": e.get("parent"), "active": True, "order": 10 ** 6 + 1 + i,
                    "ids": e.get("ids") or {}, "langs": dict(g.get("langs") or {}, **(e.get("langs") or {})),
                    "langs_src": g.get("langs_src") or {}, "extra": True}
        for shop, t in (data.get("xprices") or {}).items():
            if s in t:
                prices.setdefault(shop, {})[s] = t[s]
    for key in keys:
        v = next(x for x in NSO_VARIANTS if x["key"] == key)
        slug = NSO_PREFIX + key
        items[slug] = {"title": f"{NSO_TITLE} {v['label']}", "active": True, "order": 10 ** 6, "ids": {},
                       "langs": {f: "german" for f in countries.FAMILIES}, "nso": key}
        for shop, t in (data.get("nso_prices") or {}).items():
            p = nso_price(t, key)
            if p:
                prices.setdefault(shop, {})[slug] = p
        own += [dict({k: x[k] for k in x if k != "key"}, slug=slug)
                for x in settings.get("nso_extra") or [] if x.get("key") == key]
    return dict(data, items=items, prices=prices), dict(settings, own_offers=own)


def nso_price(table, key):
    """Preis einer Variante aus nso_prices[Land]; bis 0.56 hieß „12 Monate“ dort „nso“."""
    return (table or {}).get(key) or ((table or {}).get("nso") if key == "m12" else None)


def dlc_fit(data):
    """Passt ein DLC aus Japan oder Amerika zum Spiel aus Europa? {slug: {Region: True/False}}
    aus dem Vergleich der Programm-IDs in titledb (ab 0.61). Fehlt eine Region, ist es ungeprüft."""
    out = {}
    recs = list((data.get("extra") or {}).items()) + [(s, it) for s, it in data["items"].items() if it.get("parent")]
    for slug, rec in recs:
        for fam, v in (rec.get("app_same") or {}).items():
            cur = ((rec.get("ids") or {}).get(fam) or [None])[0]
            if isinstance(v, list) and len(v) == 2 and cur and v[0] == str(cur):
                out.setdefault(slug, {})[fam] = bool(v[1])
    return out



# Kaufplan und Mitgliedschaft bauen auf diesem Modul auf und laden es selbst. Damit planner.purchase_plan,
# planner.membership usw. weiter gelten, reicht planner ihre Namen beim ersten Zugriff weiter (0.86)
_LATER = {
    "kaufplan": ("_paid", "purchase_plan", "_package_gain", "_package_moves", "_other_countries", "_rest_fill",
                 "_rest_pairs"),
    "membership": ("NSO_REMIND_DAYS", "NSO_DAYS", "until_suggest", "membership", "_membership_rows"),
}


def __getattr__(name):
    for mod, names in _LATER.items():
        if name in names:
            return getattr(importlib.import_module(f"{__package__}.{mod}"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
