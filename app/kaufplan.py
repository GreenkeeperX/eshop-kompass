"""Kaufplan: welches Land wann was kauft, mit Wechselgewinn, Paketprüfung und „Passt in den Rest“."""
from itertools import combinations

from . import countries
from .cards import cents
from .membership import membership
from .planner import (_context, _r, _switch2_choice, extra_context, NSO_PREFIX, plan_country, radar,
    with_added)
from .titles import pack_block, pack_parts


def _paid(b):
    """Was ein vermerkter Kauf gekostet hat: die Spiele ohne Rest, sonst die Kartenkosten."""
    return b.get("games") if b.get("games") is not None else b.get("cost")


def purchase_plan(data, settings, targets=None, include_good=False, now=None, bought=None, fill=None):
    """Ein Gesamtvorschlag: welche Titel jetzt in welchem Land, in welcher Reihenfolge.

    Kandidaten sind die Titel mit dem Urteil "kaufen" (wahlweise auch "gutes Angebot").
    Jeder Titel geht in das Land, in dem er am wenigsten kostet. Ein Land, dessen
    Wechselgewinn (gegenüber denselben Titeln ohne diesen Wechsel) die Schwelle seiner
    Stufe nicht schafft, fällt heraus, seine Titel wandern ins nächstbeste Land. Das
    wiederholt sich, bis alle Länder ihre Schwelle erreichen. Ist ein Titel im neuen Land
    kein Kauf mehr (dieselbe Preisgüte wie im Radar), wartet er.

    Rest: Er ist kein Verlust, solange du im Land bleibst. Folgt im Plan noch ein Wechsel,
    verfällt er (Nintendo nimmt Guthaben nicht mit) und zählt als Kosten, ebenso
    Guthaben, das im Kontoland übrig bleibt, wenn der Plan es verlässt. Wo ein Rest den
    Wechsel blockiert (Amerika), ist ein Wechsel danach nicht ausführbar (Entscheidung 12.10.2026):
    So ein Land kommt nur als letzter Schritt, höchstens eins je Plan, und steht das
    Konto dort mit Guthaben, plant der Plan nur dort.

    Füllartikel: Bleibt in einem Schritt ein Rest, nennt der Plan bis zu drei
    Wishlist-Titel, die hineinpassen, möglichst nahe am Rest, egal welches Urteil.
    Was du davon übernimmst (`fill`: {Land: [Titel]}), kommt in diesen Schritt.
    """
    data, settings = with_added(data, settings, [s for slugs in (fill or {}).values() for s in slugs])
    ctx = _context(data, settings, now)
    fill = {code: [s for s in slugs if s in ctx.items] for code, slugs in (fill or {}).items()}
    ok_grades = ("buy", "good") if include_good else ("buy",)
    rows = radar(data, settings, targets, now)
    # Schon gekauft, aber noch auf der Wishlist: nicht noch einmal einplanen. Das gilt auch
    # für alles, was in der Sammlung bei DekuDeals steht (Entscheidung 12.10.2026: keine
    # doppelte Pflege, die Sammlung kommt mit dem nächsten Abgleich).
    done = {s for b in (bought or []) for s in b.get("slugs", [])} | ctx.owned
    wanted = [r["slug"] for r in rows if r["verdict"] in ok_grades and r["slug"] not in done]
    reasons = {r["slug"]: r["reason"] for r in rows}
    target = {r["slug"]: r["target"] for r in rows}
    wanted, s2_skip = _switch2_choice(data, rows, wanted, settings)
    # Stehen ein Pass und seine Teile zum Kauf an, kauft der Plan den Pass: Die Teile
    # kämen sonst doppelt (0.50.1)
    block = pack_block(settings)
    holds = {s: set(pack_parts(data, {s}, block)) for s in wanted}
    in_pack = {}
    for s in sorted(wanted, key=lambda s: -len(holds[s])):    # das größte Paket zuerst
        for p in holds[s]:
            if p in holds and p not in in_pack and s not in in_pack and s not in holds[p]:
                in_pack[p] = s
    packed = [{"slug": s, "title": ctx.title(s), "pack": ctx.title(in_pack[s])}
              for s in wanted if s in in_pack]
    wanted = [s for s in wanted if s not in in_pack]
    current = settings.get("current_country") or ""
    allowed = [code for code, c in ctx.countries.items() if c["unit"] is not None]
    every = list(allowed)
    dropped = []

    def blocks(code):
        return bool(settings["countries"][code].get("rest_blocks"))

    # Das Land, in dem das Konto steht, und was dort an Guthaben liegt, auch wenn das
    # Land gerade keine Preise hat oder abgeschaltet ist
    home = [code for code in countries.ORDER if countries.BY_CODE[code]["shop"] == current]
    cur_code = (current if current in home else home[0]) if home else None
    cur_c = ctx.countries.get(cur_code) if cur_code else None
    cur_balance = cents(settings["countries"][cur_code].get("balance") or 0) if cur_code else 0
    cur_unit = cur_c["unit"] if cur_c else None
    # Guthaben in einem Land, dessen Rest den Wechsel blockiert: Das Konto kommt dort erst
    # weg, wenn es aufgebraucht ist. Bis dahin plant der Plan nur dort.
    locked = bool(cur_code and cur_balance > 0 and blocks(cur_code))

    def fits(slug, eur):
        t = target.get(slug)
        return (t is not None and eur <= t + 0.005) or ctx.grade(eur, slug) in ok_grades

    def cheapest_in(slug, codes):
        best = None
        for code in codes:
            c = ctx.countries[code]
            o = c["offers"].get(slug)
            if not o or not ctx.decides(o):
                continue
            eur = ctx.oeur(c, o)
            if best is None or eur < best[0] - 0.005:
                best = (eur, code)
        return best

    def assign():
        """Jeder Titel ins günstigste noch erlaubte Land. Ist er dort kein Kauf mehr,
        wartet er besser: Das Angebot lohnte nur in einem Land, dessen Wechsel sich nicht rechnet."""
        groups, nowhere, later = {}, [], []
        for slug in wanted:
            best = cheapest_in(slug, [pin[slug]] if pin.get(slug) in allowed else allowed)
            if not best:
                nowhere.append(slug)
            elif fits(slug, best[0]):
                groups.setdefault(best[1], []).append(slug)
            else:
                later.append(slug)
        # Übernommene Füllartikel kommen in ihren Schritt, solange es ihn gibt
        taken = {x for g in groups.values() for x in g}
        for code, slugs in fill.items():
            if code not in groups:
                continue
            offers = ctx.countries[code]["offers"]
            for s in slugs:
                # Die Mitgliedschaft kaufst du immer wieder: ein früherer Kauf hält sie nicht ab (0.69)
                if s not in taken and (s not in done or s.startswith(NSO_PREFIX)) and s in offers and ctx.decides(offers[s]) \
                        and offers[s].get("direct") is None:
                    groups[code].append(s)
                    taken.add(s)
        later = [s for s in later if s not in taken]
        nowhere = [s for s in nowhere if s not in taken]
        return groups, nowhere, later

    def first_end(p):
        ends = [i["end"] for i in p["items"] if i.get("end")]
        return min(ends) if ends else "9999"

    def stuck(p):
        """Bleibt nach diesem Schritt ein Rest, der jeden weiteren Wechsel blockiert?"""
        return blocks(p["code"]) and (p.get("rest") is None or p["rest"] > 0)

    def order(p):
        # Erst das Land, in dem das Konto steht, dann nach Wechselstufe. Ein Land, dessen
        # Rest den Wechsel blockiert, zuletzt. Innerhalb einer Stufe zuerst, wo ein
        # Angebot am frühesten endet.
        # Ohne angegebenes Kontoland gilt Deutschland als Konto ("home") und kommt ebenso zuerst
        return (stuck(p), not (p["current"] or p["home"]), p["tier"] if not p["is_ref"] else 1, first_end(p), p["name"])

    held, everywhere = [], {}
    if locked:
        # Wohin die Titel ohne die Sperre gingen: Was nicht im Kontoland bleibt, wartet
        everywhere = {s: cheapest_in(s, allowed) for s in wanted}
        allowed = [cur_code] if cur_code in allowed else []
        held = [s for s in wanted if everywhere[s] and everywhere[s][1] != cur_code
                and fits(s, everywhere[s][0])]

    pin, tried = {}, set()
    for _round in range(4):
        while True:
            groups, nowhere, later = assign()
            if locked:
                later = [s for s in later if s not in held]
                nowhere = [s for s in nowhere if s not in held]
            plans_by = {code: plan_country(ctx, code, basket=slugs, allowed=allowed)
                        for code, slugs in groups.items()}
            for p in plans_by.values():
                _package_gain(ctx, p, allowed, current)
            steps = sorted(plans_by.values(), key=order)
            for p in steps:
                if p["current"] and steps[0] is not p:
                    # Das Kontoland kommt nach einem anderen Schritt: Dahin geht es zurück,
                    # das ist ein Wechsel wie jeder andere
                    p["current"] = False
                    p["worth"] = p["home"] or p["gain"] >= p.get("threshold", 0)
            for p in steps[:-1]:
                # Danach wechselt das Konto: Der Rest verfällt und zählt als Kosten. Im
                # Kontoland verfällt auch das Guthaben, das der Kauf übrig lässt
                lost = p.get("rest_value") or 0.0
                if p["code"] == cur_code and cur_unit is not None:
                    lost += max(0, cur_balance - round(p["total"] * 100)) * cur_unit
                if lost >= 0.005 and p.get("games_cost") is not None:
                    p["rest_lost"] = _r(lost)
                    p["games_cost"] = _r(p["games_cost"] + lost)
                    p["gain"] = _r(p["gain"] - lost)
                    p["saving"] = _r(p["saving"] - lost)
                    p["worth"] = p["home"] or p["current"] or p["gain"] >= p.get("threshold", 0)
            if steps and cur_balance > 0 and steps[0]["code"] != cur_code and cur_unit is not None:
                # Der Plan verlässt das Kontoland, ohne dort zu kaufen: Das Guthaben verfällt
                p = steps[0]
                lost = cur_balance * cur_unit
                p["balance_lost"] = _r(lost)
                p["games_paid"] = _r(p["games_paid"] + lost)   # verfällt durch diesen Kauf
                p["rest_lost"] = _r((p.get("rest_lost") or 0) + lost)
                p["games_cost"] = _r(p["games_cost"] + lost)
                p["gain"] = _r(p["gain"] - lost)
                p["saving"] = _r(p["saving"] - lost)
                p["worth"] = p["home"] or p["current"] or p["gain"] >= p.get("threshold", 0)
            # Ein Land aus der Paket-Nachprüfung ist günstiger als ein Schritt, der sich schon
            # lohnte: Es fällt nicht an der Schwelle heraus
            moved_to = set(pin.values())
            weak = [(p["gain"] - p.get("threshold", 0), code) for code, p in plans_by.items()
                    if not p["home"] and not p["current"] and not p.get("worth") and code not in moved_to]
            # Zwei Länder mit blockierendem Rest gehen nicht nacheinander: Das schwächere fällt heraus
            stuck_steps = [p for p in steps if stuck(p)]
            if not weak and len(stuck_steps) > 1:
                p = min(stuck_steps, key=lambda p: (p["gain"] - p.get("threshold", 0), p["code"]))
                weak = [(None, p["code"])]
                p["blocked_by"] = [x["name"] for x in stuck_steps if x is not p]
            if not weak:
                break
            _, code = min(weak, key=lambda w: (w[0] is not None, w[0] or 0, w[1]))
            p = plans_by[code]
            dropped.append({"code": code, "name": p["name"], "tier_name": p["tier_name"],
                            "titles": [i["short"] for i in p["items"]],
                            "slugs": [i["slug"] for i in p["items"]],
                            "saving": p["saving"], "gain": p["gain"], "alt_codes": p.get("alt_codes", []),
                            "threshold": p.get("threshold"), "blocked_by": p.get("blocked_by")})
            allowed.remove(code)
        # Paket-Nachprüfung (0.83): Gibt es für alle Titel eines Schritts ein Land gleicher oder
        # leichterer Stufe, in dem sie zusammen günstiger sind, kommen sie dorthin. Sonst konnten
        # sich gleich teure Länder gegenseitig aus dem Plan werfen (jedes schaffte gegen das
        # nächste die Schwelle nicht), bis ein teureres übrig blieb
        moved = _package_moves(ctx, steps, every, current, tried) if _round < 3 else {}
        if not moved:
            break
        for code, slugs in moved.items():
            for s in slugs:
                pin[s] = code
            if code not in allowed:
                allowed.append(code)
            dropped[:] = [d for d in dropped if d["code"] != code]

    # Jeder Titel steht nur einmal unter "Nicht im Plan", mit dem Grund, der zählt: Fiel
    # sein günstigstes Land heraus und kam er nirgends sonst in den Plan, dort; sonst
    # unter "lieber warten" oder "nirgends kaufbar"
    planned = {i["slug"] for p in steps for i in p["items"]}
    shown = set()
    for d in dropped:
        d["open_slugs"] = [s for s in d["slugs"] if s not in planned and s not in shown]
        d["open_titles"] = [ctx.short(s) for s in d["open_slugs"]]
        shown.update(d["open_slugs"])
    later = [s for s in later if s not in shown]
    nowhere = [s for s in nowhere if s not in shown]

    lock = None
    if locked:
        # Was das Guthaben aufbrauchen kann: Wishlist-Titel, die hineinpassen
        step = plans_by.get(cur_code)
        left = step["rest"] if step else cur_balance / 100
        inside = {i["slug"] for i in step["items"]} if step else set()
        offers = cur_c["offers"] if cur_c else {}
        # Was ohnehin wartet, weil es woanders günstiger ist, steht nicht auch hier
        fit = [ctx.short(s) for s in ctx.order if s not in done and s not in inside and s not in held
               and s in offers
               and ctx.decides(offers[s]) and offers[s]["local"] <= round((left or 0) * 100)]
        lock = {"code": cur_code, "name": countries.BY_CODE[cur_code]["name"],
                "currency": (cur_c or {}).get("currency"), "balance": cur_balance / 100,
                "left": left, "fits": fit[:5]}
    skip = done | {x["slug"] for x in s2_skip} | {x["slug"] for x in packed}
    xctx = extra_context(data, settings, now)
    for p in steps:
        c = ctx.countries[p["code"]]
        p["fill_slugs"] = [i["slug"] for i in p["items"] if i["slug"] in fill.get(p["code"], [])]
        p["fill"] = _rest_fill(ctx, c, p, planned, skip, xctx=xctx)
        p["fill_pairs"] = _rest_pairs(p["fill"], p.get("rest") or 0)
        p["reasons"] = {i["slug"]: reasons.get(i["slug"], "") for i in p["items"]}
        # Vergleich mit dem Kauf in Deutschland zum heutigen Preis, auch für den
        # deutschen Schritt (dort ist die Ersparnis dann 0)
        p["de_now"] = _r(sum(ctx.ref[i["slug"]] if i["slug"] in ctx.ref
                             else ctx.oeur(c, c["offers"][i["slug"]]) for i in p["items"]))
    for p in steps:
        p["others"] = [] if locked else _other_countries(ctx, p, every)
    # Online-Mitgliedschaft als Füllartikel (0.57.1, Vorschlag ohne Übernahme): Varianten, die du
    # selbst kaufen kannst und die in den Rest eines Schritts passen, die größte zuerst
    ms = membership(data, settings, now) if any((p.get("rest") or 0) > 0 for p in steps) else {"variants": []}
    for p in steps:
        rest = round((p.get("rest") or 0) * 100)
        fits = []
        for v in ms["variants"]:
            # Nur der eShop zahlt aus dem Guthaben; eigene Angebote (Codes) zahlt die Kreditkarte (0.63)
            r = next((r for r in v["rows"] if r["code"] == p["code"] and r["counts"] and not r.get("src")), None)
            if v.get("family") or not r or rest <= 0 or p.get("is_ref") or round(r["local"] * 100) > rest \
                    or NSO_PREFIX + v["key"] in {i["slug"] for i in p["items"]}:
                continue
            fits.append({"key": v["key"], "label": v["label"], "local": r["local"], "eur": r["eur"],
                         "left": (rest - round(r["local"] * 100)) / 100, "at_best": r.get("at_best", False)})
        p["fill_nso"] = sorted(fits, key=lambda f: f["left"])[:2]
    total = sum(p["cost"] for p in steps if p["cost"] is not None)
    games = sum(p.get("games_cost", p["cost"]) for p in steps if p["cost"] is not None)
    ref_total = sum(p["de_now"] for p in steps)
    return {"steps": steps, "dropped": dropped, "nowhere": [ctx.title(s) for s in nowhere],
            "lock": lock, "held": [{"slug": s, "title": ctx.title(s), "short": ctx.short(s),
                                    "code": everywhere[s][1],
                                    "name": ctx.countries[everywhere[s][1]]["meta"]["name"]}
                                   for s in held],
            "later": [{"slug": s, "title": ctx.title(s), "reason": reasons.get(s, "")} for s in later],
            "s2_skip": [dict(x, title=ctx.title(x["slug"])) for x in s2_skip],
            "packed": packed,
            "count": sum(len(p["items"]) for p in steps), "cost": _r(total),
            "ref_total": _r(ref_total), "saving": _r(ref_total - games),
            "rest_value": _r(total - games),
            "rest_lost": _r(sum(p.get("rest_lost") or 0 for p in steps)),
            "include_good": include_good,
            "bought_waiting": [ctx.title(s) for s in ctx.order if s in done],
            "bought_slugs": [s for s in ctx.order if s in done],
            "bought": [{k: b.get(k) for k in ("at", "code", "titles", "cost", "games", "de", "rest", "currency")}
                       for b in (bought or [])[-5:]][::-1],
            # Ein Rest bleibt als Guthaben und ist kein Verlust: Die Ersparnis rechnet mit
            # dem, was die Spiele kosten. Ältere Einträge kennen nur die Kartenkosten.
            "bought_saving": _r(sum((b.get("de") or 0) - _paid(b) for b in (bought or [])
                                    if b.get("de") is not None and _paid(b) is not None)),
            "good_left": 0 if include_good else sum(1 for r in rows if r["verdict"] == "good")}


def _package_gain(ctx, p, allowed, current):
    """Wechselgewinn gegen das beste Paket (0.83, Entscheidung 19.10.2026): Was dieselben Titel
    zusammen in einem anderen Land kosten, mit Karten, Gebühr und Rest wie „Andere Länder“.
    Die Einzelschätzung je Titel kannte keine Karten; so hielt der Plan einen Wechsel für
    lohnend, der als Paket teurer war als ein anderes Land. Es zählen dieselben Länder wie
    bei der Einzelschätzung (gleiche oder leichtere Stufe oder das Kontoland) und nur, wo
    alle Titel zu haben sind; sonst bleibt die Einzelschätzung."""
    if p.get("current") or p.get("home") or p.get("games_cost") is None or not p["items"]:
        return
    c = ctx.countries[p["code"]]
    slugs = [i["slug"] for i in p["items"]]
    best = None
    for code in allowed:
        o = ctx.countries[code]
        if code == p["code"] or o["unit"] is None or o["meta"]["shop"] == c["meta"]["shop"]:
            continue
        if o["tier"] > c["tier"] and o["meta"]["shop"] != current:
            continue
        q = plan_country(ctx, code, basket=slugs, allowed=allowed, fillers=False)
        if q.get("games_cost") is None or {i["slug"] for i in q["items"]} != set(slugs):
            continue
        if best is None or q["games_cost"] < best[0] - 0.005:
            best = (q["games_cost"], code)
    # Nur, wenn das Paket günstiger ist als die Einzelschätzung: Ein Wechsel muss sich gegen
    # beide Rechnungen lohnen, die Paket-Prüfung macht keinen Wechsel erst lohnend
    if best is None or best[0] >= (p.get("alt_total") or 0) - 0.005:
        return
    p["alt_total"] = _r(best[0])
    p["alt_codes"] = [best[1]]
    p["alt_package"] = True
    p["gain"] = _r(best[0] - p["games_cost"])
    p["worth"] = p["gain"] >= p.get("threshold", 0)


def _package_moves(ctx, steps, codes, current, tried):
    """Schritte, deren Titel zusammen in einem anderen Land gleicher oder leichterer Stufe
    günstiger sind (wie „Andere Länder“ rechnet): {Land: [Titel]}. Nur in ein Land, das noch
    kein Schritt ist, und jeder Schritt höchstens einmal je Land (`tried`), damit nichts kreist."""
    planned = {p["code"] for p in steps}
    out = {}
    for p in steps:
        if p.get("current") or p.get("home") or p.get("games_cost") is None or not p["items"]:
            continue
        c = ctx.countries[p["code"]]
        slugs = [i["slug"] for i in p["items"]]
        own = p["games_cost"] - (p.get("rest_lost") or 0)
        best = None
        for code in codes:
            o = ctx.countries[code]
            if code in planned or code in out or (p["code"], code) in tried or o["unit"] is None \
                    or o["meta"]["shop"] == c["meta"]["shop"]:
                continue
            if o["tier"] > c["tier"] and o["meta"]["shop"] != current:
                continue
            q = plan_country(ctx, code, basket=slugs, allowed=codes, fillers=False)
            if q.get("games_cost") is None or {i["slug"] for i in q["items"]} != set(slugs):
                continue
            if q["games_cost"] < own - 0.005 and (best is None or q["games_cost"] < best[0] - 0.005):
                best = (q["games_cost"], code)
        if best:
            tried.add((p["code"], best[1]))
            out[best[1]] = slugs
    return out


def _other_countries(ctx, step, codes):
    """Andere Länder für einen Schritt des Kaufplans (0.74): Was dieselben Titel dort kosten,
    verglichen mit dem, was die Spiele in diesem Schritt kosten. Ein Rest bleibt auf beiden
    Seiten Guthaben und zählt nicht, auch wenn er im Plan beim nächsten Wechsel verfällt.
    Die Länder stehen nach Mehrkosten, Länder ohne alle Titel am Ende."""
    slugs = [i["slug"] for i in step["items"]]
    own = step.get("games_cost")
    if own is None or not slugs:
        return []
    own -= step.get("rest_lost") or 0     # wie dort: was die Spiele kosten, ein Rest bleibt Guthaben
    out = []
    for code in codes:
        if code == step["code"]:
            continue
        o = plan_country(ctx, code, basket=slugs, allowed=codes, fillers=False)
        if not o["items"] or o.get("games_cost") is None:
            continue
        have = {i["slug"] for i in o["items"]}
        # Fehlen dort Titel, vergleicht die Zeile nur die übrigen: der Schritt ohne deren Preis
        base = own - sum(i["eur"] for i in step["items"] if i["slug"] not in have and i.get("eur") is not None)
        out.append({"code": code, "name": o["name"], "tier": o["tier"],
                    "is_ref": o["is_ref"], "current": o["current"],
                    "games_cost": o["games_cost"], "diff": _r(o["games_cost"] - base),
                    "missing": [ctx.short(s) for s in slugs if s not in have],
                    "estimated": bool(o.get("estimated"))})
    out.sort(key=lambda x: (len(x["missing"]), x["diff"], x["name"]))
    return out


def _rest_fill(ctx, c, p, planned, skip, limit=60, xctx=None):
    """Wishlist-Titel, die in den Rest dieses Schritts passen, der kleinste Abstand zuerst.
    Ein DLC nur, wenn sein Hauptspiel in der Sammlung oder im Plan steht. Dazu fehlende
    DLC deiner Spiele (`xctx`), die nicht auf der Wishlist stehen. Kostenloses füllt
    keinen Rest und fehlt (0.70)."""
    rest = round((p.get("rest") or 0) * 100)
    if rest <= 0 or p.get("is_ref"):
        return []
    out = []
    for s in ctx.order:
        o = c["offers"].get(s)
        if not o or s in planned or s in skip or s in ctx.owned or not ctx.decides(o):
            continue
        parent = ctx.items[s].get("parent")
        if parent and parent not in ctx.owned and parent not in planned:
            continue
        # Ein eigenes Angebot (Code, ab 0.62) zahlt die Kreditkarte, nicht das Guthaben: kein Füller (0.63)
        if o["local"] > rest or o["local"] <= 0 or o.get("direct") is not None:
            continue
        out.append({"slug": s, "title": ctx.title(s), "short": ctx.short(s),
                    "local": o["local"] / 100, "eur": _r(o["local"] / 100 / c["rate"]) if c.get("rate") else None,
                    "left": (rest - o["local"]) / 100, "sale": bool(o.get("sale")), "dlc": bool(parent)})
    xc = xctx.countries.get(c["code"]) if xctx else None
    for s, o in (xc or {}).get("offers", {}).items():
        if o["local"] > rest or o["local"] <= 0 or s in planned or not xctx.decides(o):
            continue
        it = xctx.items[s]
        game = ((ctx.items.get(it["dlc_of"]) or {}).get("title")
                or ((ctx.rel or {}).get(it["dlc_of"]) or {}).get("title") or it["dlc_of"])
        out.append({"slug": s, "title": f"{it['title']} ({game})", "short": it["title"],
                    "local": o["local"] / 100, "eur": _r(o["local"] / 100 / c["rate"]) if c.get("rate") else None,
                    "left": (rest - o["local"]) / 100, "sale": bool(o.get("sale")), "dlc": True,
                    "extra": True, "game": game})
    return sorted(out, key=lambda f: (f["left"], f["title"]))[:limit]


def _rest_pairs(fill, rest, limit=3):
    """Zwei Titel, die zusammen in den Rest passen und weniger übrig lassen als jeder einzelne
    (0.70). Nur übernehmbare Titel (Wishlist), kleinster Rest zuerst."""
    cand = [f for f in fill if not f.get("extra")]
    best = min((f["left"] for f in cand), default=rest)
    out = []
    for a, b in combinations(cand, 2):
        left = round(rest - a["local"] - b["local"], 2)
        if -0.005 < left < best - 0.005:
            out.append({"slugs": [a["slug"], b["slug"]], "shorts": [a["short"], b["short"]],
                        "titles": [a["title"], b["title"]], "local": _r(a["local"] + b["local"]),
                        "left": max(left, 0.0)})
    return sorted(out, key=lambda f: (f["left"], f["shorts"]))[:limit]
