"""Paketrechner: Kartenkombination, Rest, Ersparnis, Füllartikel, Rangliste.

Beträge in Landeswährung werden intern als ganze Hundertstel gerechnet.
"""
import math
import re
from datetime import datetime, timezone
from itertools import combinations

from . import countries

MAX_STATES = 3_000_000
MIN_FILLER_GAIN = 0.5   # Füllartikel erst ab dieser Ersparnis in Euro vorschlagen


def cents(value):
    return int(round(float(value) * 100))


# ------------------------------------------------------------ Guthabenkarten

def parse_cards(text):
    """"1000 3000 5000=29,50" -> [(100000, None), (300000, None), (500000, 29.5)].

    Einträge durch Leerzeichen, Zeilenumbruch oder Semikolon getrennt.
    Ohne "=Preis" wird der Kartenpreis aus Kurs plus Aufschlag geschätzt.
    """
    cards = {}
    for tok in re.split(r"[\s;]+", text or ""):
        tok = tok.strip().rstrip(",")
        if not tok:
            continue
        face, _, cost = tok.partition("=")
        try:
            f = cents(face.replace(",", "."))
            c = float(cost.replace(",", ".")) if cost else None
        except ValueError:
            continue
        if f > 0 and (c is None or c > 0):
            cards[f] = c
    return sorted(cards.items())


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
        best[0] = 0.0
        for s in range(1, n + 1):
            b, p = inf, 0
            for u, c in units:
                if s >= u and best[s - u] + c < b:
                    b, p = best[s - u] + c, u
            best[s], pick[s] = b, p
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
    def __init__(self, data, settings, now=None):
        self.now = now or datetime.now(timezone.utc)
        self.settings = settings
        self.items = {s: it for s, it in data["items"].items() if it.get("active")}
        self.order = sorted(self.items, key=lambda s: self.items[s].get("order", 0))
        rates = data["fx"]["rates"]
        self.countries = {}
        for code in countries.ORDER:
            cfg = settings["countries"][code]
            if not cfg["enabled"]:
                continue
            offers, currency = {}, None
            for slug, p in data["prices"].get(code, {}).items():
                if slug not in self.items:
                    continue
                currency = currency or p.get("currency")
                o = offer(p, self.now)
                if o:
                    offers[slug] = o
            rate = rates.get(currency) if currency else None
            self.countries[code] = {
                "code": code, "cfg": cfg, "meta": countries.BY_CODE[code],
                "offers": offers, "currency": currency, "rate": rate,
                "known": set(data["prices"].get(code, {})),
            }
        self.lows = data.get("lows", {})
        ref = self.countries.get(countries.REFERENCE, {"offers": {}})
        self.ref = {s: o["local"] / 100 for s, o in ref["offers"].items()}
        self.ref_regular = {s: o["regular"] / 100 for s, o in ref["offers"].items()}

    def pct(self, c):
        """Aufschlag in Prozent auf den Mittelkurs, je nach Zahlweg."""
        if c["code"] == countries.REFERENCE or c["currency"] == "EUR":
            return 0.0
        if c["cfg"]["pay"] == "card":
            return self.settings["card_fee_pct"]
        return self.settings["gift_markup_pct"]

    def est(self, c, local):
        """Geschätzter Europreis eines Betrags in Landeswährung."""
        if not c["rate"]:
            return None
        return local / 100 / c["rate"] * (1 + self.pct(c) / 100)

    def low(self, code, slug, o):
        """Tiefstpreis in Landeswährung und ob das aktuelle Angebot ihn erreicht."""
        e = self.lows.get(code, {}).get(slug) or {}
        low = e.get("low")
        if low is None:
            return {"low": None, "at_low": False}
        return {"low": low, "at_low": o["local"] <= cents(low),
                "low_pct": round(100 * (1 - cents(low) / o["regular"])) if o["regular"] else 0}

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
    """Liefert pay(total) -> Kosten in Euro, Karten, Rest für ein Land."""
    balance = cents(c["cfg"].get("balance") or 0)
    cards = parse_cards(c["cfg"].get("cards")) if c["cfg"]["pay"] == "giftcard" else []
    solver = CardSolver(cards, c["rate"], ctx.settings["gift_markup_pct"]) if cards else None

    def pay(total):
        need = max(0, total - balance)
        left = max(0, balance - total)
        if c["cfg"]["pay"] == "giftcard" and solver:
            try:
                r = solver.solve(need)
                return {"cost": r["cost"], "cards": r["cards"], "rest": r["rest"] + left,
                        "estimated": False}
            except ValueError:
                pass
        est = c["cfg"]["pay"] == "giftcard"
        return {"cost": ctx.est(c, need), "cards": [], "rest": left if not est else None,
                "estimated": est}

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
                           "dlc": bool(ctx.parent_title(s))}
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
            "local": o["local"] / 100,
            "regular": o["regular"] / 100, "sale": o["sale"],
            "pct": round(100 * (1 - o["local"] / o["regular"])) if o["regular"] else 0,
            "end": o["end"], "eur": _r(ctx.est(c, o["local"])), "ref": _r(r),
            "dlc_of": ctx.parent_title(slug),
            "forced": slug in must,
            "over": bool(not is_ref and r is not None and ctx.est(c, o["local"]) > r + 0.005),
            **ctx.low(code, slug, o),
        })
    ref_total = sum(ref.get(s, 0) for s in chosen)
    out.update({
        "total": total / 100, "cost": _r(base["cost"]), "estimated": base["estimated"],
        "cards": [{"face": f / 100, "count": n} for f, n in base["cards"]],
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
        out["worth"] = (is_ref or out["current"]
                        or out["saving"] >= ctx.settings["min_saving_eur"])

    if no_ref:
        out["warnings"].append(f"{no_ref} Titel ohne deutschen Vergleichspreis")
    if c["cfg"]["pay"] == "giftcard" and not has_cards:
        out["warnings"].append("Keine Guthabenkarten eingetragen: Kosten geschätzt")
    if base["rest"] and chosen and c["cfg"]["rest_blocks"]:
        out["warnings"].append("Rest blockiert den Länderwechsel")
    if any(ctx.items[s].get("parent") and ctx.items[s]["parent"] not in chosen for s in chosen):
        out["warnings"].append(f"DLC braucht in der Regel das Hauptspiel aus {out['family']}")

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


def _r(x):
    return None if x is None else round(x + 0.0, 2)


def plans(data, settings, overrides=None, must=(), basket=None, now=None):
    ctx = Context(data, settings, now)
    overrides = overrides or {}
    must = [s for s in must if s in ctx.items]
    basket = [s for s in dict.fromkeys(basket or []) if s in ctx.items]
    res = [plan_country(ctx, code, overrides.get(code), must, basket)
           for code in ctx.countries]
    ref = [p for p in res if p["is_ref"]]
    rest = [p for p in res if not p["is_ref"]]
    # vollständige Körbe zuerst, dann nach Ersparnis
    rest.sort(key=lambda p: (bool(p.get("must_missing")), len(p["missing"]),
                             p["saving"] is None, -(p["saving"] or 0), -p["available"]))
    return rest + ref


def matrix(data, settings, now=None):
    """Alle Wishlist-Titel mal alle aktiven Länder, Preise in Euro."""
    ctx = Context(data, settings, now)
    cols = [{"code": c["code"], "name": c["meta"]["name"], "currency": c["currency"]}
            for c in ctx.countries.values()]
    rows = []
    for slug in ctx.order:
        it = ctx.items[slug]
        cells, best = {}, None
        for code, c in ctx.countries.items():
            o = c["offers"].get(slug)
            if not o:
                if slug in c["known"]:
                    cells[code] = {"na": True}
                continue
            eur = ctx.est(c, o["local"])
            cells[code] = {"eur": _r(eur), "local": o["local"] / 100, "sale": o["sale"],
                           "pct": round(100 * (1 - o["local"] / o["regular"])) if o["regular"] else 0,
                           "end": o["end"], **ctx.low(code, slug, o)}
            if eur is not None and (best is None or eur < cells[best]["eur"]):
                best = code
        rows.append({"slug": slug, "title": it["title"], "cells": cells, "best": best,
                     "dlc_of": ctx.parent_title(slug),
                     "no_ids": not any(it.get("ids", {}).values())})
    return {"cols": cols, "rows": rows}
