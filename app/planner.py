"""Paketrechner: Kartenkombination, Rest, Ersparnis, Bestpreise, Radar.

Beträge in Landeswährung werden intern als ganze Hundertstel gerechnet.
"""
import math
import re
from datetime import datetime, timezone
from itertools import combinations

from . import countries
from .sources import parse_amount

MAX_STATES = 3_000_000
CARD_PRICE_MAX_AGE = 3 * 24 * 3600   # gelesene Kartenpreise gelten so lange
MIN_FILLER_GAIN = 0.5    # Füllartikel erst ab dieser Ersparnis in Euro vorschlagen
BEST_TOLERANCE = 0.02    # bis 2 % über dem Bestpreis gilt ein Angebot als Bestpreis
GOOD_GAP = 15            # bis 15 % über dem Bestpreis gilt ein Angebot als gut


def cents(value):
    return int(round(float(value) * 100))


# ------------------------------------------------------------ Guthabenkarten

_OUT_RE = re.compile(r"^\s*(?:[x#!\-]\s+|\(aus\)\s*)", re.I)


def parse_card_list(text):
    """Kartenliste eines Landes.

    Eine Karte je Zeile: "100 = 16,00 | https://…". Preis und Link sind
    freiwillig, ein vorangestelltes "x " heißt nicht vorrätig. Das alte
    Kurzformat "1000 3000 5000=29,50" wird weiter verstanden.
    """
    cards = {}
    for line in re.split(r"[\n;]+", text or ""):
        line = line.strip()
        if not line:
            continue
        stock = True
        m = _OUT_RE.match(line)
        if m:
            stock, line = False, line[m.end():]
        line = re.sub(r"\s*=\s*", "=", line)
        entries = [line] if ("|" in line or "http" in line.lower()) else line.split()
        for entry in entries:
            url = ""
            mu = re.search(r"https?://\S+", entry)
            if mu:
                url, entry = mu.group(0), entry[:mu.start()]
            head = entry.split("|")[0]
            face_txt, _, cost_txt = head.partition("=")
            if re.match(r"\s*-", face_txt):
                continue
            face = parse_amount(face_txt)
            cost = parse_amount(cost_txt) if cost_txt.strip() else None
            if not face or face <= 0 or (cost is not None and cost <= 0):
                continue
            cards[cents(face)] = {"face": cents(face), "cost": cost, "url": url, "stock": stock}
    return [cards[k] for k in sorted(cards)]


def parse_cards(text):
    """Vorrätige Karten als (Wert in Hundertstel, Preis in Euro oder None)."""
    return [(c["face"], c["cost"]) for c in parse_card_list(text) if c["stock"]]


class CardSolver:
    """Günstigste Kartenkombination, die einen Betrag mindestens deckt."""

    def __init__(self, cards, rate, markup_pct):
        self.cards = [(f, c if c is not None else f / 100 / rate * (1 + markup_pct / 100))
                      for f, c in cards]
        self.g = 0
        for f, _ in self.cards:
            self.g = math.gcd(self.g, f)
        self.n = 0
        self.best, self.pick, self.cover = [0.0], [0], [0]

    def _build(self, limit):
        g = self.g
        maxface = max(f for f, _ in self.cards)
        n = (limit + maxface) // g + 1
        if n > MAX_STATES:
            raise ValueError("Kartenwerte zu kleinteilig für diesen Betrag")
        units = [(f // g, c) for f, c in self.cards]
        inf = float("inf")
        best = [inf] * (n + 1)
        pick = [0] * (n + 1)
        count = [0] * (n + 1)
        best[0] = 0.0
        for s in range(1, n + 1):
            b, p, k = inf, 0, 0
            for u, c in units:
                if s < u:
                    continue
                cost, cards = best[s - u] + c, count[s - u] + 1
                # bei gleichen Kosten (Karten zum Kurs) gewinnen weniger Karten
                if cost < b - 1e-9 or (cost < b + 1e-9 and cards < k):
                    b, p, k = cost, u, cards
            best[s], pick[s], count[s] = b, p, k
        # cover[s]: günstigste erreichbare Summe >= s (bei Gleichstand die kleinere)
        cover = [0] * (n + 2)
        cover[n + 1] = -1
        for s in range(n, -1, -1):
            nxt = cover[s + 1]
            if best[s] < inf and (nxt < 0 or best[s] <= best[nxt] + 1e-9):
                cover[s] = s
            else:
                cover[s] = nxt
        self.n, self.best, self.pick, self.cover = n, best, pick, cover

    def solve(self, need):
        """need in Hundertstel -> Kosten in Euro, Karten, Rest."""
        if need <= 0:
            return {"cost": 0.0, "cards": [], "rest": 0}
        s0 = -(-need // self.g)
        if s0 > self.n - max(f for f, _ in self.cards) // self.g:
            self._build(need * 2)
        s = self.cover[s0]
        counts, cur = {}, s
        while cur > 0:
            u = self.pick[cur]
            counts[u * self.g] = counts.get(u * self.g, 0) + 1
            cur -= u
        return {"cost": self.best[s],
                "cards": sorted(counts.items(), reverse=True),
                "rest": s * self.g - need}


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
    local, sale, end = regular, False, None
    if "discount" in price:
        start, stop = _parse_dt(price.get("start")), _parse_dt(price.get("end"))
        if (start is None or start <= now) and (stop is None or now <= stop):
            local, sale, end = cents(price["discount"]), True, price.get("end")
    return {"local": local, "regular": regular, "sale": sale and local < regular,
            "end": end, "currency": price.get("currency")}


class Context:
    """Alles, was die Rechnungen brauchen: Angebote je Land in Bruttopreisen,
    Europreis je Währungseinheit, Sprachregel und Bestpreise."""

    def __init__(self, data, settings, now=None, include_all=False):
        self.now = now or datetime.now(timezone.utc)
        self.settings = settings
        self.items = {s: it for s, it in data["items"].items() if it.get("active")}
        self.order = sorted(self.items, key=lambda s: self.items[s].get("order", 0))
        self.lows = data.get("lows", {})
        self.owned = set(data.get("owned") or [])
        rates = data["fx"]["rates"]
        self.rates = rates
        self.card_prices = data.get("card_prices") or {}
        self.countries = {}
        for code in countries.ORDER:
            cfg = settings["countries"][code]
            if not (cfg["enabled"] or include_all):
                continue
            meta = countries.BY_CODE[code]
            tax = 0.0 if code == countries.REFERENCE else float(cfg.get("tax_pct") or 0)
            offers, currency = {}, None
            for slug, p in data["prices"].get(code, {}).items():
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
                 "known": set(data["prices"].get(code, {})), "tax": tax,
                 "tier": int(cfg.get("tier") or meta["tier"]), "nolang": set(),
                 "cards": self._live_cards(parse_card_list(cfg.get("cards")))}
            c["unit"] = self._unit(c)
            c["estimated"] = self.estimated(c)
            self.countries[code] = c
        self._apply_language_rule()
        ref = self.countries.get(countries.REFERENCE, {"offers": {}})
        # Vergleichsbasis mit allen Kosten: günstigere Guthabenkarten senken auch sie
        unit = ref.get("unit") or 0.01
        self.ref = {s: o["local"] * unit for s, o in ref["offers"].items()}
        self.ref_regular = {s: o["regular"] * unit for s, o in ref["offers"].items()}
        self._champions()

    def _live_cards(self, cards):
        """Setzt für Karten mit Link den zuletzt gelesenen Shop-Preis ein, solange
        er frisch ist. Sonst bleibt der von Hand eingetragene Preis."""
        now = self.now.timestamp()
        for x in cards:
            e = self.card_prices.get(x["url"]) if x["url"] else None
            if not e or e.get("price") is None or now - e.get("checked", 0) > CARD_PRICE_MAX_AGE:
                continue
            rate = 1.0 if e.get("currency") == "EUR" else self.rates.get(e.get("currency"))
            if not rate:
                continue
            x.update(manual=x["cost"], cost=round(e["price"] / rate, 2), live=e["checked"])
        return cards

    # ---- Europreis je Währungseinheit

    def markup(self, c):
        """Aufschlag in Prozent für Guthabenkarten ohne eigenen Preis."""
        own = c["cfg"].get("markup_pct")
        return float(self.settings["gift_markup_pct"] if own in ("", None) else own)

    def _gift(self, c):
        """Günstigste vorrätige Karte: (Euro je Hundertstel, Karte oder None)."""
        est = 1 / 100 / c["rate"] * (1 + self.markup(c) / 100)
        best, card = est, None
        for x in c["cards"]:
            if not x["stock"]:
                continue
            unit = x["cost"] / x["face"] if x["cost"] is not None else est
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
        if c["code"] == countries.REFERENCE or c["currency"] == "EUR":
            unit = self._euro_card(c)[0] if c["currency"] == "EUR" else mid
            return unit, unit
        return mid * (1 + self.settings["card_fee_pct"] / 100), self._gift(c)[0]

    def _unit(self, c):
        if not c["rate"]:
            return None
        card, gift = self._units(c)
        pay = c["cfg"]["pay"]
        return card if pay == "card" else gift if pay == "giftcard" else min(card, gift)

    def how(self, c):
        """Woraus sich der Europreis eines Landes zusammensetzt, für die Anzeige."""
        if c["unit"] is None:
            return None
        mid = 1 / 100 / c["rate"]
        card_unit, gift_unit = self._units(c)
        pay = c["cfg"]["pay"]
        gift = pay == "giftcard" or (pay == "auto" and gift_unit < card_unit)
        out = {"currency": c["currency"], "rate": c["rate"], "tax": c["tax"],
               "via": "giftcard" if gift else "card", "unit": c["unit"] * 100,
               "vs_mid": round(100 * (c["unit"] / mid - 1), 1),
               "fee": self.settings["card_fee_pct"], "markup": self.markup(c), "card": None,
               # Karten nur mit Wert und ohne Shop-Link: Guthaben zum Kurs, wie bei Amazon Japan.
               # Karten mit Link, aber ohne bekannten Preis, bleiben eine Schätzung.
               "at_rate": any(x["stock"] and x["cost"] is None and not x["url"] for x in c["cards"])}
        if c["currency"] == "EUR":
            card = self._euro_card(c)[1]
            out["via"] = "giftcard" if card else "eur"
            if card:
                out["card"] = {"face": card["face"] / 100, "cost": card["cost"], "url": card["url"],
                               "live": card.get("live")}
        elif gift:
            card = self._gift(c)[1]
            if card and card["cost"] is not None:
                out["card"] = {"face": card["face"] / 100, "cost": card["cost"], "url": card["url"],
                               "live": card.get("live")}
        return out

    def estimated(self, c):
        """True, wenn der Europreis auf dem pauschalen Guthaben-Aufschlag beruht,
        weil für dieses Land gar keine Guthabenkarte eingetragen ist. Karten nur
        mit Wert heißen: Guthaben zum Kurs plus Aufschlag, so wie du es kaufst."""
        how = self.how(c)
        return bool(how and how["via"] == "giftcard" and not how["card"] and not how["at_rate"])

    def est(self, c, local):
        """Europreis eines Bruttobetrags in Landeswährung beim üblichen Zahlweg."""
        return None if c["unit"] is None else local * c["unit"]

    # ---- Sprachen

    def german(self, it, fam):
        """Hat die Fassung dieser Region Deutsch? None, wenn unbekannt.
        Ein DLC ohne eigene Angabe richtet sich nach seinem Hauptspiel."""
        text = (it.get("langs") or {}).get(fam)
        if not text and it.get("parent") in self.items:
            text = (self.items[it["parent"]].get("langs") or {}).get(fam)
        if not text:
            return None
        return "german" in text.lower() or "deutsch" in text.lower() or "ドイツ語" in text

    def _apply_language_rule(self):
        """Gibt es in Deutschland eine deutsche Fassung, kommen nur Regionen
        infrage, die sie ebenfalls haben. Gleiche Region heißt gleiches Produkt."""
        mode = self.settings.get("lang_rule", "exclude")
        if mode == "off":
            return
        for c in self.countries.values():
            fam = c["meta"]["family"]
            if fam == "EU":
                continue
            for slug in list(c["offers"]):
                it = self.items[slug]
                if self.german(it, "EU") is not True:
                    continue
                here = self.german(it, fam)
                if here is False and mode == "exclude":
                    del c["offers"][slug]
                    c["nolang"].add(slug)
                elif here is False:
                    c["offers"][slug]["lang"] = "no"
                elif here is None:
                    c["offers"][slug]["lang"] = "unknown"

    # ---- Tiefst- und Bestpreise

    def low_value(self, code, slug):
        """Tiefstpreis in Landeswährung (ohne Steuer): DekuDeals oder eigene Aufzeichnung."""
        e = self.lows.get(code, {}).get(slug) or {}
        values = [v for v in (e.get("low"), e.get("own_low")) if v is not None]
        return min(values) if values else None

    def low(self, code, slug, o):
        """Tiefstpreis in Landeswährung und ob das aktuelle Angebot ihn erreicht."""
        low = self.low_value(code, slug)
        if low is None:
            return {"low": None, "at_low": False}
        base = o.get("regular_net", o["regular"])
        return {"low": low, "at_low": o.get("net", o["local"]) <= cents(low),
                "low_pct": round(100 * (1 - cents(low) / base)) if base else 0}

    def _champions(self):
        """Bestpreis je Titel: der niedrigste Preis, den es je gab, in Euro zum
        heutigen Kurs. Einmal über alle Länder, einmal nur über die leichten."""
        self.champ_all, self.champ_easy = {}, {}
        for code, c in self.countries.items():
            if c["unit"] is None:
                continue
            for slug, o in c["offers"].items():
                local = o["local"]
                low = self.low_value(code, slug)
                if low is not None:
                    local = min(local, round(cents(low) * (1 + c["tax"] / 100)))
                eur = local * c["unit"]
                for table, ok in ((self.champ_all, True), (self.champ_easy, c["tier"] <= 2)):
                    if ok and (slug not in table or eur < table[slug][0] - 1e-9):
                        table[slug] = (eur, code, c["estimated"])

    def mark(self, c, slug, o):
        """Deal-Güte eines Angebots: Marke und Abstand zum Bestpreis in Prozent."""
        out = {"mark": "", "gap": None, "champ": None, "champ_code": None}
        eur, best = self.est(c, o["local"]), self.champ_all.get(slug)
        if eur is None or not best or not best[0]:
            return out
        out.update(champ=_r(best[0]), champ_code=best[1],
                   gap=max(0, round(100 * (eur / best[0] - 1))))
        if not o["sale"]:
            return out
        easy = self.champ_easy.get(slug)
        if eur <= best[0] * (1 + BEST_TOLERANCE) + 0.005:
            out["mark"] = "best"
        elif c["tier"] <= 2 and easy and eur <= easy[0] * (1 + BEST_TOLERANCE) + 0.005:
            out["mark"] = "best_easy"
        elif self.low(c["code"], slug, o)["at_low"]:
            out["mark"] = "low"
        else:
            out["mark"] = "sale"
        return out

    def cell(self, c, slug, o):
        """Ein Angebot, wie es Tabellen und Karten anzeigen."""
        return {"local": o["local"] / 100, "regular": o["regular"] / 100, "sale": o["sale"],
                "net": o.get("net", o["local"]) / 100,
                "pct": round(100 * (1 - o["local"] / o["regular"])) if o["regular"] else 0,
                "end": o["end"], "eur": _r(self.est(c, o["local"])), "est": c["estimated"],
                "lang": o.get("lang"), "nsuid": o.get("nsuid"),
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
        if parent and title.lower().startswith(parent.lower()):
            rest = title[len(parent):].lstrip(" :–-")
            if len(rest) > 2:
                return rest
        return title


def make_payer(ctx, c):
    """Liefert pay(total) -> Kosten in Euro, Karten, Rest für ein Land.

    Zahlweg "auto" nimmt das Günstigere aus Kartenzahlung und Guthabenkarten.
    """
    balance = cents(c["cfg"].get("balance") or 0)
    mode = c["cfg"]["pay"]
    card_unit, gift_unit = ctx._units(c)
    stocked = [(x["face"], x["cost"]) for x in c["cards"] if x["stock"]]
    solver = None
    if stocked and mode in ("giftcard", "auto"):
        solver = CardSolver(stocked, c["rate"], ctx.markup(c))
    urls = {x["face"]: x["url"] for x in c["cards"]}

    def by_card(need, left):
        return {"cost": need * card_unit, "cards": [], "rest": left, "estimated": False,
                "via": "card"}

    def by_gift(need, left):
        if solver:
            try:
                r = solver.solve(need)
                return {"cost": r["cost"], "cards": r["cards"], "rest": r["rest"] + left,
                        "estimated": False, "via": "giftcard"}
            except ValueError:
                pass
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

    pay.urls = urls
    return pay, bool(solver)


# --------------------------------------------------------------------- Plan

def plan_country(ctx, code, override=None, must=(), basket=None):
    """Plan für ein Land. Mit `basket` gilt derselbe Warenkorb für alle Länder,
    sonst die Angebote des Landes plus eigene Änderungen (`override`)."""
    c = ctx.countries[code]
    override = override or {}
    is_ref = code == countries.REFERENCE
    ref = ctx.ref_regular if is_ref else ctx.ref
    offers = c["offers"]
    out = {"code": code, "name": c["meta"]["name"], "currency": c["currency"],
           "family": countries.FAMILIES[c["meta"]["family"]],
           "pay": c["cfg"]["pay"], "rate": c["rate"], "is_ref": is_ref,
           "tier": c["tier"], "tier_name": countries.TIERS.get(c["tier"], ""),
           "tax": c["tax"], "lang": c["meta"]["lang"],
           "note": c["meta"]["note"], "items": [], "fillers": [], "warnings": [],
           "available": len(offers), "saving": None, "missing": [], "trims": [],
           "current": code == ctx.settings.get("current_country")}
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
            cheaper = slug not in ref or ctx.est(c, o["local"]) < ref[slug] - 0.005
            if o["sale"] and cheaper:
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

    pay, has_cards = make_payer(ctx, c)
    total = sum(offers[s]["local"] for s in chosen)
    base = pay(total)

    no_ref = 0
    for slug in chosen:
        o, it = offers[slug], ctx.items[slug]
        r = ref.get(slug)
        if r is None:
            no_ref += 1
        out["items"].append({
            "slug": slug, "title": it["title"], "short": ctx.short(slug),
            "ref": _r(r), "dlc_of": ctx.parent_title(slug), "forced": slug in must,
            **ctx.owned_flags(slug),
            "over": bool(not is_ref and r is not None and ctx.est(c, o["local"]) > r + 0.005),
            **ctx.cell(c, slug, o),
        })
    ref_total = sum(ref.get(s, 0) for s in chosen)
    out.update({
        "total": total / 100, "cost": _r(base["cost"]), "estimated": base["estimated"],
        "via": base["via"],
        "cards": [{"face": f / 100, "count": n, "url": pay.urls.get(f, "")}
                  for f, n in base["cards"]],
        "rest": None if base["rest"] is None else base["rest"] / 100,
        "rest_eur": None if base["rest"] is None else _r(base["rest"] / 100 / c["rate"]),
        "ref_total": _r(ref_total),
    })
    if chosen:
        # Titel ohne deutschen Vergleichspreis zählen zum geschätzten Europreis
        ref_cmp = ref_total + sum(ctx.est(c, offers[s]["local"])
                                  for s in chosen if s not in ref)
        out["saving"] = _r(ref_cmp - base["cost"])
        out["saving_pct"] = round(100 * (ref_cmp - base["cost"]) / ref_cmp) if ref_cmp else 0
        limit = float((ctx.settings.get("tier_min_saving") or {}).get(str(c["tier"]), 0))
        out["threshold"] = limit
        out["worth"] = is_ref or out["current"] or out["saving"] >= limit

    if no_ref:
        out["warnings"].append(f"{no_ref} Titel ohne deutschen Vergleichspreis")
    if c["cfg"]["pay"] == "giftcard" and not has_cards:
        out["warnings"].append("Keine Guthabenkarten eingetragen: Kosten geschätzt")
    if base["rest"] and chosen and c["cfg"]["rest_blocks"]:
        out["warnings"].append("Rest blockiert den Länderwechsel")
    if any(ctx.items[s].get("parent") and ctx.items[s]["parent"] not in chosen for s in chosen):
        out["warnings"].append(f"DLC braucht in der Regel das Hauptspiel aus {out['family']}")
    unknown = sum(1 for s in chosen if offers[s].get("lang") == "unknown")
    if unknown:
        out["warnings"].append(f"{unknown} Titel mit ungeprüfter Sprache")
    nolang = sum(1 for s in chosen if offers[s].get("lang") == "no")
    if nolang:
        out["warnings"].append(f"{nolang} Titel ohne deutsche Fassung")

    if not is_ref:
        out["fillers"] = _fillers(ctx, c, chosen, total, base, pay, has_cards, ref)
        if not basket:
            out["trims"] = _trims(ctx, c, chosen, total, base, pay, ref, must)
    return out


def _trims(ctx, c, chosen, total, base, pay, ref, must):
    """Titel, die hier unterm Strich mehr kosten als in Deutschland.

    Gerechnet wird mit den Grenzkosten: was das Paket ohne den Titel weniger
    kostet. Löst ein Titel eine zusätzliche Guthabenkarte aus, ist das viel.
    """
    offers, res = c["offers"], []
    if len(chosen) < 2:
        return res
    for s in chosen:
        if s in must or s not in ref:
            continue
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
    cand = [s for s in ctx.order if s in offers and s not in chosen and s in ref]

    def rate_combo(slugs):
        add = sum(offers[s]["local"] for s in slugs)
        p = pay(total + add)
        extra = p["cost"] - base["cost"]
        gain = sum(ref[s] for s in slugs) - extra
        return {"slugs": list(slugs), "titles": [ctx.title(s) for s in slugs],
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
            if o and (best is None or ctx.est(c, o["local"]) < best[0] - 0.005):
                best = (ctx.est(c, o["local"]), c)
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


def plans(data, settings, overrides=None, must=(), basket=None, now=None, with_mix=False):
    ctx = Context(data, settings, now)
    overrides = overrides or {}
    must = [s for s in must if s in ctx.items]
    basket = [s for s in dict.fromkeys(basket or []) if s in ctx.items]
    res = [plan_country(ctx, code, overrides.get(code), must, basket)
           for code in ctx.countries]
    if with_mix:
        ref = [p for p in res if p["is_ref"]]
        rest = sorted((p for p in res if not p["is_ref"]),
                      key=lambda p: (bool(p.get("must_missing")), len(p["missing"]),
                                     p["saving"] is None, -(p["saving"] or 0), -p["available"]))
        return rest + ref, (mix(ctx, basket) if basket else None)
    ref = [p for p in res if p["is_ref"]]
    rest = [p for p in res if not p["is_ref"]]
    # vollständige Körbe zuerst, dann nach Ersparnis
    rest.sort(key=lambda p: (bool(p.get("must_missing")), len(p["missing"]),
                             p["saving"] is None, -(p["saving"] or 0), -p["available"]))
    return rest + ref


def matrix(data, settings, now=None):
    """Alle Wishlist-Titel mal alle aktiven Länder, Preise in Euro."""
    ctx = Context(data, settings, now)
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
            if eur is not None and (best is None or eur < cells[best]["eur"]):
                best = code
        rows.append({"slug": slug, "title": it["title"], "cells": cells, "best": best,
                     "dlc_of": ctx.parent_title(slug), **ctx.owned_flags(slug),
                     "no_ids": not any(it.get("ids", {}).values())})
    return {"cols": cols, "rows": rows}


VERDICTS = ["buy", "good", "hard", "wait", "none"]


def radar(data, settings, targets=None, now=None):
    """Eine Zeile je Titel: bester Preis jetzt, Bestpreis, Urteil.

    "Leicht" fasst die Länder der Stufen 1 und 2 zusammen, "schwer" die
    Stufe 3. Dort lohnt ein Kauf nur bei deutlich besseren Angeboten.
    """
    ctx = Context(data, settings, now)
    targets = targets or {}
    deal_eur = dict({"buy": 0.5, "good": 2.0}, **(settings.get("deal_eur") or {}))
    rows = []
    for slug in ctx.order:
        best = {"easy": None, "hard": None}
        for code, c in ctx.countries.items():
            o = c["offers"].get(slug)
            if not o or c["unit"] is None:
                continue
            raw = ctx.est(c, o["local"])
            group = "easy" if c["tier"] <= 2 else "hard"
            if best[group] is None or raw < best[group]["raw"] - 0.005:
                best[group] = dict(ctx.cell(c, slug, o), code=code, name=c["meta"]["name"],
                                   currency=c["currency"], raw=raw, lang_code=c["meta"]["lang"])
        easy, hard = best["easy"], best["hard"]
        champ_all, champ_easy = ctx.champ_all.get(slug), ctx.champ_easy.get(slug)

        def champ(entry):
            if not entry:
                return None
            return {"eur": _r(entry[0]), "code": entry[1], "est": entry[2],
                    "name": countries.BY_CODE[entry[1]]["name"]}
        try:
            target = float(targets.get(slug))
        except (TypeError, ValueError):
            target = None
        gap_easy = diff_easy = diff_all = None
        if easy and champ_easy and champ_easy[0]:
            gap_easy = max(0, round(100 * (easy["raw"] / champ_easy[0] - 1)))
            diff_easy = max(0.0, _r(easy["raw"] - champ_easy[0]))
        if easy and champ_all:
            diff_all = max(0.0, _r(easy["raw"] - champ_all[0]))
        # Ein Angebot zählt als Kauf oder gutes Angebot, wenn es prozentual
        # oder in Euro nah genug am Bestpreis liegt: 1 € mehr für einen
        # günstigen Titel ist wenig, auch wenn es 30 % sind.
        buy_eur, good_eur = deal_eur["buy"], deal_eur["good"]
        verdict, reason = "none", "kein Angebot"
        if target is not None and easy and easy["raw"] <= target + 0.005:
            verdict, reason = "buy", "Zielpreis erreicht"
        elif easy and easy["mark"] in ("best", "best_easy"):
            verdict, reason = "buy", "Bestpreis"
        elif easy and easy["sale"] and diff_easy is not None and diff_easy <= buy_eur + 0.005:
            verdict, reason = "buy", f"nur {_eur(diff_easy)} über Bestpreis"
        elif easy and easy["sale"] and gap_easy is not None and (
                gap_easy <= GOOD_GAP or diff_easy <= good_eur + 0.005):
            verdict, reason = "good", f"{_eur(diff_easy)} ({gap_easy} %) über Bestpreis"
        elif hard and hard["sale"] and (
                (target is not None and hard["raw"] <= target + 0.005)
                or (hard["mark"] == "best" and (not easy or hard["raw"] < easy["raw"] * 0.85))):
            verdict, reason = "hard", f"stark nur in {hard['name']}"
        elif (easy and easy["sale"]) or (hard and hard["sale"]):
            verdict, reason = "wait", (f"war {_eur(diff_easy)} günstiger" if diff_easy
                                       else "war schon günstiger")
        for b in (easy, hard):
            if b:
                b.pop("raw")
        it = ctx.items[slug]
        rows.append({"slug": slug, "title": it["title"], "dlc_of": ctx.parent_title(slug),
                     **ctx.owned_flags(slug),
                     "easy": easy, "hard": hard, "de": _r(ctx.ref.get(slug)),
                     "champ": champ(champ_all), "champ_easy": champ(champ_easy),
                     "gap_easy": gap_easy, "diff_easy": diff_easy, "diff_all": diff_all,
                     "target": target, "verdict": verdict,
                     "reason": reason, "no_ids": not any(it.get("ids", {}).values())})
    rows.sort(key=lambda r: (VERDICTS.index(r["verdict"]),
                             r["gap_easy"] if r["gap_easy"] is not None else 999))
    return rows


def card_status(data, settings, now=None):
    """Je Land die Karten mit Link: gelesener Preis, Stand oder Fehler."""
    ctx = Context(data, settings, now, include_all=True)
    out = {}
    for code, c in ctx.countries.items():
        rows = []
        for x in c["cards"]:
            if not x["url"]:
                continue
            e = ctx.card_prices.get(x["url"]) or {}
            rows.append({"face": x["face"] / 100, "cost": x["cost"], "live": x.get("live"),
                         "manual": x.get("manual", x["cost"]), "checked": e.get("checked"),
                         "error": e.get("error")})
        if rows:
            out[code] = rows
    return out


def pay_info(data, settings, now=None):
    """Zahlweg und eigener Kurs je Land, auch für abgeschaltete Länder."""
    ctx = Context(data, settings, now, include_all=True)
    return {code: ctx.how(c) for code, c in ctx.countries.items() if c["unit"] is not None}


def price_levels(data, settings, now=None):
    """Preisniveau jedes Landes gegenüber Deutschland, gemessen an der Wishlist.

    Auch für abgeschaltete Länder, damit sich entscheiden lässt, welche lohnen.
    """
    ctx = Context(data, settings, now, include_all=True)
    out = {}
    for code, c in ctx.countries.items():
        if code == countries.REFERENCE or c["unit"] is None:
            continue
        common = [s for s in c["offers"] if s in ctx.ref]
        if len(common) < 3:
            continue
        here = sum(ctx.est(c, c["offers"][s]["local"]) for s in common)
        home = sum(ctx.ref[s] for s in common)
        out[code] = {
            "level": round(100 * (here / home - 1)) if home else 0,
            "titles": len(common),
            "cheaper": sum(1 for s in common
                           if ctx.est(c, c["offers"][s]["local"]) < ctx.ref[s] * 0.95),
            "sale": sum(1 for s in common if c["offers"][s]["sale"]),
        }
    return out
