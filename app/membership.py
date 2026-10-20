"""Online-Mitgliedschaft: Preis je Variante und Land, günstigstes Land, Erinnerung vor Ablauf."""
from datetime import datetime, timedelta, timezone

from . import countries
from .cards import cents
from .planner import (_context, _r, BEST_TOLERANCE, NSO_KEYS, NSO_PREFIX, nso_price, NSO_TITLE, NSO_VARIANTS,
    nso_variants, read_offer)


NSO_REMIND_DAYS = 30      # so lange vor Ablauf erscheint die Verlängerung unter „Zu erledigen“
NSO_DAYS = {1: 30, 3: 90, 12: 365}   # Laufzeit in Tagen je Monate, wie Nintendo sie rechnet


def until_suggest(settings, bought):
    """Ablaufdatum nach einem vermerkten Kauf (0.88): Steht in einem Kauf, den du nach dem letzten
    Setzen des Datums als „gekauft“ vermerkt hast, eine Variante der Mitgliedschaft, verlängert sie
    das Datum ab Ablauf, oder ab dem Kauftag, wenn sie schon abgelaufen war. Nur ein Vorschlag:
    Übernehmen oder Verwerfen setzt das Datum und damit den Stand neu. None ohne solchen Kauf."""
    set_at = settings.get("nso_until_set") or ""
    try:
        cur = datetime.strptime(settings.get("nso_until") or "", "%Y-%m-%d").date()
    except ValueError:
        cur = None
    start, used = cur, []
    for b in bought or []:
        if not b.get("at") or b["at"] <= set_at:
            continue
        day = datetime.fromisoformat(b["at"]).date()
        for slug in b.get("slugs") or []:
            v = next((x for x in NSO_VARIANTS if NSO_PREFIX + x["key"] == slug), None)
            if v:
                cur = max(cur, day) if cur else day
                cur += timedelta(days=NSO_DAYS[v["months"]])
                used.append({"label": v["label"], "date": day.isoformat(), "code": b.get("code")})
    if not used or cur == start:
        return None
    return {"until": cur.isoformat(), "from": used}


def membership(data, settings, now=None, bought=None):
    """Online-Mitgliedschaft in allen Varianten (ab 0.57): je Variante der Einkaufspreis je aktivem
    Land mit demselben Zahlweg wie bei Spielen (Kreditkarte oder Guthabenkarten), Bestpreis, Güte
    und ★ wie bei Titeln. Die Sprachregel gilt hier nicht. Dazu deine Variante und Ablaufdatum aus
    den Einstellungen und ob die Verlängerung ansteht. rows und champ oben gelten deiner Variante."""
    now = now or datetime.now(timezone.utc)
    until = settings.get("nso_until") or ""
    mine = settings.get("nso_variant") if settings.get("nso_variant") in NSO_KEYS else "m12"
    days = None
    if until:
        try:
            days = (datetime.strptime(until, "%Y-%m-%d").date() - now.date()).days
        except ValueError:
            days = None
    var_data = nso_variants(data)
    out = {"title": NSO_TITLE, "until": until, "days_left": days, "rows": [], "mine": mine, "variants": [],
           "suggest": until_suggest(settings, bought),
           "due": days is not None and days <= NSO_REMIND_DAYS,
           "ids_known": any((e or {}).get("ids") for e in var_data.values())}
    prices = data.get("nso_prices") or {}
    if not any(prices.values()):
        return out
    current = settings.get("current_country") or ""
    for v in NSO_VARIANTS:
        e = var_data.get(v["key"]) or {}
        vp = {code: {"nso": p} for code, t in prices.items() if (p := nso_price(t, v["key"]))}
        extra = [dict(x, idx=j) for j, x in enumerate(settings.get("nso_extra") or []) if x.get("key") == v["key"]]
        rows, champ = _membership_rows(data, settings, now, vp, e.get("lows") or {}, e.get("urls") or {}, current, v, extra)
        if not v["slug"]:      # Tiefstpreis aus der eigenen Aufzeichnung (0.87): seit wann
            for r in rows:
                r["low_since"] = (e.get("own_since") or {}).get(countries.BY_CODE[r["code"]]["shop"]) if not r.get("src") else None
        out["variants"].append(dict({k: v[k] for k in ("key", "slug", "label", "months", "accounts")},
                                    family=bool(v.get("family")), rows=rows, champ=champ,
                                    best=next((r for r in rows if r["counts"]), None)))
        if v["key"] == mine:
            out["rows"], out["champ"] = rows, champ
    return out


def _membership_rows(data, settings, now, prices, lows, urls, current, v, extra=()):
    if not prices and not extra:
        return [], None
    # Ein Kunstgriff: Die Mitgliedschaft ist ein Titel mit Deutsch in jeder Region, damit die
    # Sprachregel sie nicht ausschließt
    items = {"nso": {"title": NSO_TITLE, "active": True, "order": 0, "ids": {},
                     "langs": {f: "german" for f in countries.FAMILIES}}}
    # Ohne Kaufverlauf (0.96): Besitz spielt für die Mitgliedschaft keine Rolle, und der Abgleich der
    # Käufe kostete je Variante so viel wie der ganze Rest der Rechnung
    ctx = _context(dict(data, items=items, prices=prices, lows={}, _eshop=None), settings, now)
    rows = []
    for code, c in ctx.countries.items():
        o = c["offers"].get("nso")
        if not o or c["unit"] is None:
            continue
        eur = ctx.oeur(c, o)
        if eur is None:
            continue
        rows.append({
            "code": code, "name": c["meta"]["name"], "tier": c["tier"], "eur": _r(eur),
            "month": _r(eur / v["months"]), "per_account": _r(eur / v["months"] / v["accounts"]),
            "local": o["local"] / 100, "currency": o.get("currency") or c["currency"],
            "sale": o["sale"], "pct": round(100 * (1 - o["local"] / o["regular"])) if o["sale"] and o["regular"] else None,
            "end": o.get("end") if o["sale"] else None, "est": c["estimated"], "counts": ctx.decides(o),
            "current": code == current or (not current and code == countries.REFERENCE),
            # Kauflink von DekuDeals, sonst Nintendos Mitgliedschaftsseite des Landes (ab 0.58, etwa Japan)
            "url": urls.get(c["meta"]["shop"]) or f"https://ec.nintendo.com/{code}/{c['meta']['lang']}/membership",
            "low_eur": None})
        # Tiefstpreis dieses Landes (24 Monate, DekuDeals) mit deinem heutigen Zahlweg, wie bei Titeln
        low = lows.get(c["meta"]["shop"])
        if low:
            le = ctx.est(c, cents(low * (1 + c["tax"] / 100)))
            rows[-1]["low_eur"] = _r(min(le, eur)) if le is not None else None
    # Angebote von Hand (ab 0.60), etwa Codes bei Amazon Japan: bezahlt mit Kreditkarte zum Mittelkurs
    # plus Fremdwährungsgebühr, eingelöst auf dem Konto des Landes
    for x in extra:
        c = ctx.countries.get(x["code"])
        if not c or not c["rate"]:
            continue
        # Mit Link liest der Abgleich den Preis von der Shopseite (ab 0.61); der zuletzt
        # gelesene gilt wie bei Karten bis CARD_PRICE_MAX_AGE, sonst der eingetragene
        got = read_offer(x, data.get("offer_prices"), c["currency"], now.timestamp())
        price = got["price"]
        eur = cents(price) * ctx.code_unit(c)
        rows.append({
            "code": x["code"], "name": c["meta"]["name"], "tier": c["tier"], "eur": _r(eur),
            "month": _r(eur / v["months"]), "per_account": _r(eur / v["months"] / v["accounts"]),
            "local": price, "currency": c["currency"], "sale": False, "pct": None, "end": None,
            "est": False, "counts": True, "src": x["src"], "date": x.get("date") or "", "extra": x.get("idx", 0),
            "read": got["read"], "manual": x["price"], "read_err": got["error"],
            "current": x["code"] == current or (not current and x["code"] == countries.REFERENCE),
            "url": x.get("url") or None, "low_eur": None})
    # Bestpreis über alle zählenden Länder, Güte und ★ wie bei Titeln (0.56.1)
    # Bestpreis und sein Land: Ist er gerade nicht zu haben, sagt das Land, wo er war (0.57.1)
    champ_row = min((r for r in rows if r["counts"]), key=lambda r: r["low_eur"] if r["low_eur"] is not None else r["eur"], default=None)
    champ = (champ_row["low_eur"] if champ_row["low_eur"] is not None else champ_row["eur"]) if champ_row else None
    if champ:
        for r in rows:
            r["champ_name"] = champ_row["name"]
        ctx.champ_all["nso"] = (champ, None)
        for r in rows:
            r["grade"] = ctx.grade(r["eur"], "nso") if r["counts"] else None
            r["at_best"] = r["counts"] and r["eur"] <= champ * (1 + BEST_TOLERANCE) + 0.005
            r["over"] = _r(r["eur"] - champ)
    rows.sort(key=lambda r: (not r["counts"], r["eur"]))
    return rows, champ
