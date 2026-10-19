"""Titel und Besitz: Namen vergleichen, eShop-Käufe den Titeln zuordnen, Pakete und was du hast.

Dazu der gemeinsame Zwischenspeicher einer Anfrage (shared_contexts).
"""
import contextlib
import re
import threading
import unicodedata




# Eine Anfrage an den Server rechnet viele Teile aus denselben Daten; jedes Teil baute bis 0.76
# seinen eigenen Context (bis zu 16 je Startseite). Innerhalb von shared_contexts() teilen sie
# sich einen je Datenstand, Einstellungen und Variante (0.77). Nur für Lesezugriffe: Der
# Abgleich ändert die Daten unterwegs und rechnet ohne.
_shared = threading.local()


@contextlib.contextmanager
def shared_contexts():
    _shared.cache = {}
    try:
        yield
    finally:
        _shared.cache = None


def _tnorm(title):
    """Titel zum Vergleichen: ohne ™ ®, Satzzeichen und Groß-/Kleinschreibung."""
    t = re.sub(r"[™®©]", "", str(title or ""))           # vorher: NFKC macht aus ™ „TM“
    # Akzente lateinischer Buchstaben fallen weg (0.76): „Pokemon“ im Kaufverlauf ist „Pokémon“.
    # Japanische Zeichen bleiben, wie sie sind (ズ ist nicht ス)
    t = re.sub(r"[\u0300-\u036f]", "", unicodedata.normalize("NFKD", t))
    t = unicodedata.normalize("NFKC", t).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", t).split())


# Arten im Kaufverlauf, die keinen Besitz bedeuten (Rückerstattung, Storno)
_ESHOP_VOID = re.compile(r"REFUND|CANCEL|REVOK|VOID|CHARGEBACK", re.I)


def slug_names(data):
    """Name und Spiel zu jeder Kennung, die das Tool kennt, auch zu längst gekauften DLC, die
    nicht mehr unter den fehlenden stehen: {slug: (Titel, Spiel oder None)}. Quellen sind die
    Titel, die fehlenden DLC und die Verbindungen der DekuDeals-Seiten (DLC, Pakete)."""
    out = {}
    for s, r in (data.get("rel") or {}).items():
        if r.get("title"):
            out.setdefault(s, (r["title"], None))
        for k in ("dlc", "in", "has"):
            for pair in r.get(k) or []:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2 and pair[1]:
                    out.setdefault(pair[0], (pair[1], r.get("title") if k == "dlc" else None))
    for s, e in (data.get("extra") or {}).items():
        if e.get("title"):
            game = e.get("parent_title") or (out.get(e.get("parent")) or (None,))[0]
            out[s] = (e["title"], game)
    for s, it in (data.get("items") or {}).items():
        if it.get("title"):
            out[s] = (it["title"], (out.get(s) or (None, None))[1])
    return out


def known_titles(data):
    """Alle bekannten Titel und DLC für die Suche „anderer …“ bei den Käufen (0.71):
    [{slug, title, game}], nach Spiel und Titel."""
    return sorted(({"slug": s, "title": t, "game": g} for s, (t, g) in slug_names(data).items()),
                  key=lambda x: ((x["game"] or x["title"]).casefold(), x["game"] is not None, x["title"].casefold()))


def pretty_slug(slug):
    """Lesbarer Ersatz, wenn zu einer Kennung kein Name bekannt ist."""
    words = [w for w in str(slug or "").split("-") if w and not re.fullmatch(r"\d{8,}", w)]
    return " ".join(w[:1].upper() + w[1:] for w in words)


_MATCH_KEYS = ("_eshop", "eshop_names", "extra", "items", "links", "owned", "rel")


def eshop_matches(data):
    """Wie _eshop_matches; innerhalb von shared_contexts() einmal je Datenstand (0.77: die
    Startseite fragte bis zu 19-mal)."""
    cache = getattr(_shared, "cache", None)
    if cache is None:
        return _eshop_matches(data)
    parts = tuple(data.get(k) for k in _MATCH_KEYS)
    key = ("matches",) + tuple(map(id, parts))
    hit = cache.get(key)
    if hit is None or any(a is not b for a, b in zip(hit[0], parts)):
        hit = cache[key] = (parts, _eshop_matches(data))
    return hit[1]


# Switch 2 Edition (0.79): DekuDeals führt Spiel und Upgrade als einen Eintrag „Spiel – Nintendo
# Switch 2 Edition (+ Zusatz)“; der eShop verkauft Spiel und Upgrade-Pass getrennt
_S2 = re.compile(r" nintendo switch 2 edition\b.*$")


def _s2base(title):
    return _S2.sub("", _tnorm(title))


# Pässe ohne Programm-ID in titledb (0.79): Rest des japanischen Kauftitels hinter dem Spielnamen →
# Name des DLC bei DekuDeals. upgrade gilt für jedes Upgrade Pack des Spiels
_PASSES = [(re.compile(r"アップグレードパス"), "upgrade"),
           (re.compile(r"ファイターパス vol 2"), "fighters pass vol 2"),
           (re.compile(r"ファイターパス"), "fighters pass"),
           (re.compile(r"エキスパンション ?パス"), "expansion pass")]


def _pass_kind(rest):
    for rx, kind in _PASSES:
        if rx.search(rest or ""):
            return kind
    return None


def _pass_label(m):
    """Lesbarer Name eines Passes ohne englischen Namen: „Spiel: Upgrade Pack“."""
    kind = _pass_kind((m or {}).get("rest"))
    if not kind or not m.get("game"):
        return None
    return f"{m['game']}: " + {"upgrade": "Upgrade Pack", "fighters pass": "Fighters Pass",
                               "fighters pass vol 2": "Fighters Pass Vol. 2", "expansion pass": "Expansion Pass"}[kind]


def _eshop_matches(data):
    """Kaufverlauf aus dem eShop mit Wishlist und fehlenden DLC abgleichen. Zuerst über die
    Nintendo-ID, sonst über den Titel, wenn genau ein Titel passt (bei DLC auch mit dem Namen
    des Spiels davor); von Hand Zugeordnetes gilt immer. Passt nichts genau, schlägt das Tool
    ähnliche Titel vor, die zählen erst nach deiner Bestätigung.
    {"rows": [{key, title, date, type, slug, how, name, suggest}], "owned": {Titel}}.
    how: "id", "title", "eng" (englischer Name aus titledb), "pick", "none" (kein Wunschtitel), "void" (erstattet) oder None (offen)."""
    h = data.get("_eshop") or {}
    entries, picks = h.get("entries") or [], h.get("picks") or {}
    items = data.get("items") or {}
    cands = {s: it for s, it in items.items() if it.get("active")}
    for s, e in (data.get("extra") or {}).items():
        cands.setdefault(s, e)
    by_id, by_title, toks, games = {}, {}, {}, {}
    for s, it in cands.items():
        for ids in (it.get("ids") or {}).values():
            for i in ids or []:
                by_id.setdefault(str(i), s)
        names = {_tnorm(it.get("title"))}
        parent = it.get("parent")
        if parent:
            p_title = it.get("parent_title") or (items.get(parent) or {}).get("title") or \
                ((data.get("rel") or {}).get(parent) or {}).get("title") or parent.replace("-", " ")
            names.add(_tnorm(f"{p_title} {it.get('title')}"))
            games[s] = p_title          # zum Prüfen: „Upgrade Pack“ allein sagt nicht, welches Spiel (0.68)
        for n in names:
            if n:
                by_title.setdefault(n, set()).add(s)
        toks[s] = set(" ".join(names).split())
    # DLC je Spiel (0.79): {Spiel ohne „Switch 2 Edition“: [(DLC-Name, Slug)]}
    dlc_of = {}
    for s, g in games.items():
        dlc_of.setdefault(_s2base(g), []).append((_tnorm(cands[s].get("title")), s))
    rows, owned = [], set()
    known = slug_names(data)
    # Auch DLC, die nicht mehr unter den fehlenden stehen (0.82.2): Ein gekaufter Pass zählt als
    # Besitz und fällt deshalb aus extra; ohne sie wäre er beim nächsten Abgleich wieder unbekannt
    for s, (t, g) in known.items():
        if g and s not in games:
            dlc_of.setdefault(_s2base(g), []).append((_tnorm(t), s))
    # Alle bekannten Titel und DLC als Rückfall für genaue Namen (0.81.3): Ein gekaufter DLC fällt
    # aus den fehlenden DLC (extra), sobald er als Besitz zählt; ohne diesen Rückfall wäre er beim
    # nächsten Abgleich wieder unbekannt gewesen und hätte zwischen beiden Zuständen gewechselt
    by_known = {}
    coll = set(data.get("owned") or [])
    for s, (t, game) in known.items():
        if s in cands or s in coll:      # die Sammlung ordnet in_coll ein
            continue
        for n in {_tnorm(t), _tnorm(f"{game} {t}") if game else ""} - {""}:
            by_known.setdefault(n, set()).add(s)
    # DekuDeals-Sammlung (0.71): Was dort steht, ordnet das Tool selbst ein und fragt nicht
    coll = set(data.get("owned") or [])
    coll_title, coll_toks = {}, {}
    for s in coll:
        t, game = known.get(s, (None, None))
        # Ohne bekannten Namen (etwa DLC, die keine DekuDeals-Seite des Abgleichs nennt) aus der
        # Kennung (0.81; vorher blieb so ein Titel der Sammlung beim Zuordnen unsichtbar)
        t = t or pretty_slug(s)
        names = {_tnorm(t)} | ({_tnorm(f"{game} {t}")} if game else set())
        names.discard("")
        for n in names:
            coll_title.setdefault(n, s)
        if names:
            coll_toks[s] = set(" ".join(names).split())
    # Spiel als Switch 2 Edition in der Sammlung (0.79): der Name ohne Zusatz zählt auch, wenn das
    # Spiel nicht auch allein dort steht
    coll_s2 = {}
    for s in coll:
        n = _tnorm(known.get(s, (None,))[0])
        if " nintendo switch 2 edition" in f" {n}":
            coll_s2.setdefault(_s2base(n), s)
            coll_title.setdefault(_s2base(n), s)
    # Kauftitel → englischer Name aus titledb (0.72), {Titel: [Name oder None, Zeitpunkt]}
    eng = {t: v[0] for t, v in (data.get("eshop_names") or {}).items() if isinstance(v, list) and v and v[0]}
    # Shop-ID und Spiel zu Pässen ohne Programm-ID (0.79)
    more = {t: v[3] for t, v in (data.get("eshop_names") or {}).items()
            if isinstance(v, list) and len(v) > 3 and isinstance(v[3], dict)}

    def pass_dlc(m):
        """Gekaufter Pass → DLC des Spiels, wenn genau einer passt."""
        kind = _pass_kind(m.get("rest"))
        if not kind or not m.get("game"):
            return None
        dl = dlc_of.get(_s2base(m["game"]), [])
        hit = sorted({s for n, s in dl if ("upgrade pack" in n if kind == "upgrade" else n == kind)})
        return hit[0] if len(hit) == 1 else None

    def in_coll(title):
        e = eng.get(title) or ""
        # DLC heißen in titledb „Spiel: DLC“, in der Sammlung oft nur „DLC“ (0.81): auch den Teil
        # hinter dem Spielnamen versuchen
        for t in (title, e):
            n = _tnorm(t)
            if n and n in coll_title:
                return coll_title[n]
        part = re.split(r":\s|\s[-–]\s", e, maxsplit=1)
        if len(part) == 2:
            s = coll_title.get(_tnorm(part[1]))
            # nur, wenn die Sammlung den DLC demselben Spiel zuordnet oder (Spiel unbekannt) der Name
            # lang genug und kein Pass ist, sonst träfe „Upgrade Pack“ jedes Spiel
            g = known.get(s, (None, None))[1]
            if s and (_tnorm(g) == _tnorm(part[0]) if g else len(_tnorm(part[1]).split()) >= 3 and not _pass_kind(part[1])):
                return s
        for t in (title, e):
            w = set(_tnorm(t).split())
            if not w:
                continue
            best = sorted((-len(w & k) / len(w | k), s) for s, k in coll_toks.items() if w & k)
            if best and -best[0][0] >= 0.75 and (len(best) == 1 or best[1][0] > best[0][0]):
                return best[0][1]
        return None
    for e in entries:
        key, slug, how, suggest = e.get("key"), None, None, []
        pick = picks.get(key)
        norm = _tnorm(e.get("title"))
        enorm = _tnorm(eng.get(e.get("title")))
        if pick == "-":
            how = "none"
        elif pick:
            slug, how = pick, "pick"
        elif _ESHOP_VOID.search(str(e.get("type") or "")):
            how = "void"
        elif e.get("slug"):
            # Beim Einlesen gemerkt: Ein gekaufter DLC fällt danach aus den fehlenden DLC
            slug, how = e["slug"], e.get("how") or "id"
        elif str(e.get("id") or "") in by_id:
            slug, how = by_id[str(e["id"])], "id"
        elif len(by_title.get(norm, ())) == 1:
            slug, how = next(iter(by_title[norm])), "title"
        elif len(by_title.get(enorm, ())) == 1:
            slug, how = next(iter(by_title[enorm])), "eng"         # über den englischen Namen (0.72)
        elif len(by_known.get(norm, ())) == 1:
            slug, how = next(iter(by_known[norm])), "title"
        elif len(by_known.get(enorm, ())) == 1:
            slug, how = next(iter(by_known[enorm])), "eng"
        elif str((more.get(e.get("title")) or {}).get("ns") or "") in by_id:
            slug, how = by_id[str(more[e["title"]]["ns"])], "id"   # Shop-ID aus titledb (0.79)
        elif pass_dlc(more.get(e.get("title")) or {}):
            slug, how = pass_dlc(more[e["title"]]), "eng"          # Spiel + Pass (0.79)
        else:
            words = set((enorm or norm).split())
            scored = []
            for s, t in toks.items():
                common = len(words & t)
                if common and common / len(words | t) >= 0.5:
                    scored.append((-common / len(words | t), cands[s].get("title") or s, s))
            suggest = [{"slug": s, "title": t, "game": games.get(s)} for _, t, s in sorted(scored)[:3]]
        # Gruppe (0.71): void erstattet, ticket Mitgliedschaft oder Gutschein, plan zählt als Besitz
        # (fehlt in der DekuDeals-Sammlung: nachtragen), coll steht schon in der Sammlung, ask
        # Vorschläge, die den Plan ändern, unknown kennt das Tool nicht
        in_c = None
        if how == "void":
            group = "void"
        elif slug:
            group = "plan" if slug not in coll else "coll"
        elif (e.get("item") or "") in ("TICKET", "CATALOG_TICKET"):
            group, suggest = "ticket", []
        else:
            in_c = in_coll(e.get("title"))
            m = more.get(e.get("title")) or {}
            if not in_c and _pass_kind(m.get("rest")) == "upgrade":
                # Upgrade-Pass zu einem Spiel, das als Switch 2 Edition in der Sammlung steht (0.79)
                in_c = coll_s2.get(_s2base(m.get("game")))
            if in_c:
                group, suggest = "coll", []
            elif suggest and how is None:
                group = "ask"
            else:
                group = "unknown"
        if slug:
            owned.add(slug)
        rows.append({"key": key, "title": e.get("title"), "date": e.get("date"), "group": group,
                     "coll": in_c, "coll_name": known.get(in_c, (pretty_slug(in_c),))[0] if in_c else None,
                     "eng": eng.get(e.get("title")) or _pass_label(more.get(e.get("title"))),
                     "type": e.get("type"), "slug": slug, "how": how, "suggest": suggest,
                     "item": e.get("item") or "", "plat": e.get("plat") or "", "amount": e.get("amount") or "",
                     "game": (games.get(slug) or known.get(slug, (None, None))[1]) if slug else None,
                     "name": ((cands.get(slug) or items.get(slug) or {}).get("title")
                              or known.get(slug, (None,))[0] or pretty_slug(slug)) if slug else None})
    return {"rows": rows, "owned": owned}


def pack_parts(data, base, block=()):
    """Alles, was in base steckt, auch über mehrere Stufen (Edition → Pass → DLC):
    {Teil: Paket, über das er kommt}. Die Verbindungen stammen aus den Abschnitten
    „Contains“ und „Included In“ bei DekuDeals (sync.update_links). Nur in eine Richtung:
    Wer das Paket hat, hat die Teile, nicht umgekehrt. Was in block steht („stimmt
    nicht“), zählt nicht als enthalten, auch nicht, was darin steckt."""
    links = data.get("links") or {}
    via, stack = {}, [s for s in base if s in links]
    seen = set(base) | set(block)
    while stack:
        c = stack.pop()
        for p in links.get(c) or {}:
            if p not in seen:
                seen.add(p)
                via[p] = c
                stack.append(p)
    return via


def pack_block(settings):
    """Teile, bei denen du „stimmt nicht“ gewählt hast: DekuDeals nennt sie in einem
    Paket, du hast sie aber nicht (dlc_marks "missing")."""
    return {s for s, m in ((settings or {}).get("dlc_marks") or {}).items() if m == "missing"}


def owned_set(data, settings=None):
    """Was du hast: deine DekuDeals-Sammlung plus Käufe aus dem eShop-Kaufverlauf, dazu
    alles, was in diesen Paketen steckt. Abgeleitet bei jedem Aufruf, nie gespeichert:
    Ändert sich eine Verbindung, stimmt das Ergebnis von selbst."""
    base = set(data.get("owned") or []) | eshop_matches(data)["owned"]
    return base | set(pack_parts(data, base, pack_block(settings)))


def owned_games(data, settings=None):
    """Spiele, deren DLC die Sammlung zeigt: die der DekuDeals-Sammlung und Spiele, die du
    nur über ein Paket hast (etwa eine Deluxe Edition), sobald ihre Seite gelesen ist."""
    rel = data.get("rel") or {}
    games = list(dict.fromkeys(data.get("owned") or []))
    known = set(games)
    for slug in sorted(pack_parts(data, set(games) | eshop_matches(data)["owned"], pack_block(settings))):
        e = rel.get(slug)
        if slug not in known and e and not e.get("parent"):
            games.append(slug)
    return games
