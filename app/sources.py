"""Datenquellen: DekuDeals (Wishlist, Titel-IDs), Nintendo (Preise), Wechselkurse.

Alle Netzabrufe laufen über `fetch(url)`, damit Tests eine Attrappe
einsetzen können.
"""
import codecs
import gzip
import html
import http.cookiejar
import ipaddress
import json
import re
import socket
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zlib

VERSION = "1.1.9"

# Das Tool gibt sich immer als es selbst zu erkennen. Antwortet eine Quelle mit
# einer Sperre (403, 429) oder einer Prüfseite, hört es auf, statt sich zu tarnen.
USER_AGENT = f"eshop-kompass/{VERSION} (privates Wishlist-Tool)"
BLOCKED = (403, 429)

NINTENDO_PRICE_URL = "https://api.ec.nintendo.com/v1/price"
FX_URL = "https://open.er-api.com/v6/latest/EUR"
FX_FALLBACK_URL = "https://api.frankfurter.dev/v1/latest?from=EUR"

def blocked_target(url):
    """Grund, warum das Tool eine Adresse nicht abruft, sonst "" (0.82). Abgerufen wird nur das
    öffentliche Internet: Eigene Links (Karten, Angebote) könnten sonst Geräte im Heimnetz oder
    den Server selbst ansprechen. Geprüft wird jede Adresse, die der Name ergibt; lässt er sich
    hier nicht auflösen (etwa hinter einem Proxy), entscheidet der Abruf selbst."""
    p = urllib.parse.urlsplit(str(url or ""))
    if p.scheme not in ("http", "https"):
        return "nur http und https"
    if p.username or p.password:
        return "Adresse mit Zugangsdaten"
    try:
        port = p.port or (443 if p.scheme == "https" else 80)
        infos = socket.getaddrinfo(p.hostname or "", port, proto=socket.IPPROTO_TCP)
    except (OSError, ValueError, UnicodeError):
        return ""
    for info in infos:
        try:
            ip = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        except ValueError:
            continue
        if not ip.is_global:
            return "Adresse nicht öffentlich"
    return ""


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Weiterleitungen nur ins öffentliche Internet (0.82)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        why = blocked_target(newurl)
        if why:
            raise urllib.error.URLError(f"Weiterleitung abgelehnt: {why}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), _SafeRedirect)


class FetchError(Exception):
    def __init__(self, url, status, detail=""):
        super().__init__(f"{status} bei {url} {detail}".strip())
        self.url, self.status = url, status


MAX_BODY = 20 << 20      # größte Antwort, gepackt und entpackt (0.99.1): Shopseiten haben unter 2 MB


def _inflate(raw, wbits):
    d = zlib.decompressobj(wbits)
    out = d.decompress(raw, MAX_BODY + 1)
    if len(out) > MAX_BODY:
        raise ValueError("Antwort zu groß")
    return out


def _decode(raw, enc):
    if enc == "gzip":
        return _inflate(raw, 16 + zlib.MAX_WBITS)
    if enc == "deflate":
        try:
            return _inflate(raw, zlib.MAX_WBITS)
        except zlib.error:
            return _inflate(raw, -zlib.MAX_WBITS)
    return raw


def request(url, ua=None, timeout=25, encoding="gzip, deflate"):
    """HTTP GET ohne Ausnahme: liefert Status, Text und Kopfdaten für die Diagnose."""
    headers = {
        "User-Agent": ua or USER_AGENT,
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
        "Accept-Encoding": encoding,
    }
    cur = amazon_currency(url)
    if cur:
        # Amazon rechnet für Besucher aus Deutschland in Euro um (bis 0.62 als Yen gelesen).
        # Die Währungswahl der Seite selbst ist ein Cookie; er stellt die Landeswährung ein.
        headers["Cookie"] = f"i18n-prefs={cur}"
    req = urllib.request.Request(url, headers=headers)
    out = {"url": url, "status": 0, "text": "", "enc": "", "server": "", "error": ""}
    out["error"] = blocked_target(url)
    if out["error"]:
        return out
    try:
        try:
            resp = _opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            resp = e                      # Fehlerseiten haben auch einen Inhalt
        with resp:
            raw = resp.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                raise ValueError("Antwort zu groß")
            out["status"] = getattr(resp, "status", None) or resp.getcode()
            out["enc"] = (resp.headers.get("Content-Encoding") or "").lower()
            out["server"] = resp.headers.get("Server") or ""
            if out["enc"] not in ("", "identity", "gzip", "deflate") and encoding != "identity":
                return request(url, ua, timeout, "identity")   # z. B. Brotli
            charset = resp.headers.get_content_charset() or "utf-8"
            out["text"] = _decode(raw, out["enc"]).decode(charset, errors="replace")
    except Exception as e:                # Zeitüberschreitung, DNS, TLS
        out["error"] = str(e)[:160]
    return out


def head(url, timeout=20):
    """Nur die Kopfdaten (HEAD), für Proben großer Dateien: Status, Größe, Stand."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    why = blocked_target(url)
    if why:
        return {"status": 0, "error": why, "size": None, "modified": None, "etag": None}
    try:
        try:
            resp = _opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            resp = e
        with resp:
            return {"status": getattr(resp, "status", None) or resp.getcode(), "error": "",
                    "size": resp.headers.get("Content-Length"), "modified": resp.headers.get("Last-Modified"),
                    "etag": resp.headers.get("ETag")}
    except Exception as e:
        return {"status": 0, "error": str(e)[:160], "size": None, "modified": None, "etag": None}


def file_stamp(h):
    """Kennzeichen eines Dateistands aus den Kopfdaten (ETag, sonst Datum und Größe), None ohne."""
    if not h or h.get("status") != 200:
        return None
    if h.get("etag"):
        return h["etag"]
    return f"{h['modified']}|{h['size']}" if h.get("modified") and h.get("size") else None


def fetch(url, timeout=25, ua=None):
    """HTTP GET, gibt Text zurück. Wirft FetchError mit Statuscode."""
    r = request(url, ua, timeout)
    if r["error"]:
        raise FetchError(url, 0, r["error"])
    if r["status"] >= 400:
        raise FetchError(url, r["status"])
    return r["text"]


_plain_fetch = fetch      # echter Abruf; Tests setzen eigene Funktionen ein


# ---------------------------------------------------------------- DekuDeals

_WISHLIST_RE = re.compile(r"dekudeals\.com/(?:wishlist|collection)/([A-Za-z0-9]+)")
# Titel-Links: nur echte Verweise (<a href>), deren Pfad nach dem Kürzel endet.
# So zählen Unterpfade wie /items/123/add nicht als eigener Titel.
_ITEM_LINK_RE = re.compile(
    r"""<a\b[^>]*?\bhref\s*=\s*["']?(?:https?://(?:www\.)?dekudeals\.com)?"""
    r"""/items/([A-Za-z0-9][A-Za-z0-9_\-]*)(?=["'?#\s>])""", re.I)
# Ersatz, falls die Seite ihre Verweise anders schreibt
_ITEM_LOOSE_RE = re.compile(
    r"""(?:(?<=["'=(\s>])|(?<=dekudeals\.com))/items/([A-Za-z0-9][A-Za-z0-9_\-]*)(?=["'?#\s>)]|$)""")
_URL_RE = re.compile(r"""https?://[^\s"'<>]+""")
# Nintendo-IDs beginnen mit 700 (7001 Spiel, 7005 DLC, 7007 Paket); andere 14-stellige
# Zahlen in Links (Kennungen, Zeitstempel) sind keine
_NSUID_RE = re.compile(r"(?<!\d)(700\d{11})(?!\d)")
NSUID_OK = re.compile(r"^700\d{11}$")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_PARENT_RE = re.compile(
    r"""DLC for[^<]*(?:<(?!a\b)[^>]*>[^<]*)*<a\b[^>]*href=["']?[^"'>\s]*?/items/([A-Za-z0-9_\-]+)"""
    r"""[^>]*>([^<]*)""", re.S | re.I)
_SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)

attempts = []       # Protokoll des letzten DekuDeals-Abrufs, für die Diagnose


def _norm(page_html):
    return (page_html or "").replace("\\/", "/")


def page_title(page_html):
    m = _TITLE_RE.search(page_html or "")
    return html.unescape(m.group(1)).strip() if m else ""


def describe(page_html):
    """Kurzbeschreibung einer Seite: Länge, Titel, Treffer, sichtbarer Anfang."""
    return (f"{len(page_html or '')} Zeichen, Titel „{page_title(page_html)[:60]}“, "
            f"{len(parse_wishlist_page(page_html))} Titel-Links, Anfang: {visible_text(page_html)[:140]}")


def visible_text(page_html):
    text = _TAG_RE.sub(" ", _SCRIPT_RE.sub(" ", page_html or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# Während eines Abgleichs 0, nach der ersten Sperre (403/429) von DekuDeals deren Status:
# Danach fragt kein Schritt DekuDeals mehr an, bis zum nächsten Abgleich (0.56.1).
# Außerhalb eines Abgleichs (Verbindungstest) None.
deku_blocked = None


def deku_get(url, ok, fetch=fetch):
    """Holt eine DekuDeals-Seite und prüft mit `ok`, ob sie brauchbar ist."""
    global deku_blocked
    del attempts[:]
    if deku_blocked:
        raise FetchError(url, deku_blocked, "(DekuDeals hat gesperrt, nicht angefragt)")
    try:
        text = fetch(url)
    except FetchError as e:
        attempts.append(f"Fehler {e.status or ''} {str(e)[-120:] if not e.status else ''}".strip())
        if e.status in BLOCKED and deku_blocked is not None:
            deku_blocked = e.status
        raise
    if not ok(text):
        attempts.append(describe(text))
        raise FetchError(url, 200, "Seite ohne erwarteten Inhalt")
    return text


_LOW_RE = re.compile(r"All[\s\-]*time low(.{0,1500})", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_AMOUNT_RE = re.compile(
    r"(?<![\d.,])(?:\d{1,3}(?:[.,\u00a0\u202f ]\d{3})+|\d+)(?:[.,]\d{1,2})?(?!\d)")


def parse_amount(text):
    """Erste Preisangabe im Text als Zahl: "62,00 kr", "$1.49", "¥1,400", "1.299,00"."""
    m = _AMOUNT_RE.search(text or "")
    if not m:
        return None
    raw = re.sub(r"[\s\u00a0\u202f]", "", m.group(0))
    dec = re.search(r"[.,](\d{1,2})$", raw)
    if dec:
        whole = re.sub(r"[.,]", "", raw[:dec.start()]) or "0"
        return float(f"{whole}.{dec.group(1)}")
    return float(re.sub(r"[.,]", "", raw))


_LOW_TOKEN_RE = re.compile(
    r"digital|physical|"
    r"(?:(?P<pre>[€$¥£₩₪]|(?<![A-Za-z])(?:R\$?|kr|zł|Kč|CHF|Ft|S/))\s?)?"
    r"(?P<num>" + _AMOUNT_RE.pattern + r")"
    r"(?:\s?(?P<suf>[€¥円]|(?:kr|zł|Kč|CHF|Ft|lei)(?![A-Za-z])))?", re.I)


def parse_lows(page_html):
    """Digitale Tiefstpreise einer Artikelseite, einer je Plattform.

    DekuDeals schreibt sie in drei Formen: "Digital: $6.24 Physical: $17.49",
    eine Tabelle "Digital | Physical" mit einer Zeile Werte, oder bei Spielen für
    Switch und Switch 2 eine Zeile je Plattform unter "Physical | Digital". Für den
    eShop-Vergleich zählt nur digital. Plattformnamen wie "Switch 2" sind keine Preise.
    """
    m = _LOW_RE.search(page_html or "")
    if not m:
        return []
    text = html.unescape(_TAG_RE.sub(" ", m.group(1)))
    text = re.split(r"Time range|Historical data", text, maxsplit=1, flags=re.I)[0]
    text = re.sub(r"\(\s*[-−+]?\s*\d+\s*%\s*\)", " ", text)            # (-60%)
    text = re.sub(r"(?:Nintendo\s+)?Switch(?:\s*2)?|\b\d+\s*[my]\b", " ", text, flags=re.I)
    seq = []
    for t in _LOW_TOKEN_RE.finditer(text.replace("\u00a0", " ")):
        w = t.group(0).lower()
        if w in ("digital", "physical"):
            seq.append(w)
        elif t.group("pre") or t.group("suf"):
            # Nur Beträge mit Währung (1.0.5): Zahlen ohne Währung in der Nähe des Abschnitts
            # (Breiten, Prozente, Zähler) lieferten sonst Tiefstpreise wie 768 oder 100
            seq.append(parse_amount(t.group("num")))
    if "digital" not in seq:
        if "physical" in seq:
            return []                         # nur ein Händler-Tiefstpreis bekannt
        return [v for v in seq if isinstance(v, float)][:1]
    head = []
    for v in seq:
        if not isinstance(v, str):
            break
        head.append(v)
    if len(head) > 1:                         # Tabelle: Kopf, dann Werte je Zeile
        values = [v for v in seq[len(head):] if isinstance(v, float)]
        d = head.index("digital")
        return values[d::len(head)]
    out = []                                  # Wort, dann Wert
    for i, v in enumerate(seq):
        if v == "digital" and i + 1 < len(seq) and isinstance(seq[i + 1], float):
            out.append(seq[i + 1])
    return out


def low_snippet(page_html, n=160):
    """Text des Abschnitts „All time low“ für den Verbindungstest (1.0.5): zeigt, was der Leser sieht."""
    m = _LOW_RE.search(page_html or "")
    if not m:
        return "kein Abschnitt „All time low“"
    text = html.unescape(_TAG_RE.sub(" ", m.group(1)))
    return re.sub(r"\s+", " ", text).strip()[:n]


def parse_low(page_html):
    """Digitaler Tiefstpreis einer Artikelseite; bei mehreren Plattformen der höchste,
    damit ein günstigerer Tiefstpreis der anderen Fassung keinen falschen Bestpreis macht."""
    lows = parse_lows(page_html)
    return max(lows) if lows else None


_HIST_RE = r"""<script[^>]*id=["']{}["'][^>]*>(.*?)</script>"""


def parse_history(page_html):
    """Digitaler Tagesverlauf einer Artikelseite: [(Datum, Preis), ...].

    DekuDeals bettet ihn als JSON ein. Die Spalten nennt price_history_indices;
    zählt nur, was digital und nicht physisch ist (der eShop).
    """
    page_html = page_html or ""

    def block(sid):
        m = re.search(_HIST_RE.format(sid), page_html, re.S)
        if not m:
            return None
        try:
            return json.loads(html.unescape(m.group(1)))
        except ValueError:
            return None
    data, idx = block("price_history_data"), block("price_history_indices") or {}
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return []
    cols = [i for i in idx.get("digital") or [] if i and i not in (idx.get("physical") or [])]
    out = []
    for row in data["data"]:
        if not isinstance(row, list) or len(row) < 2 or not isinstance(row[0], str):
            continue
        col = cols[0] if cols else len(row) - 1
        v = row[col] if col < len(row) else None
        if isinstance(v, (int, float)) and v > 0:
            out.append((row[0][:10], float(v)))
    return out


def sale_runs(series, since=None):
    """Angebotsphasen eines Tagesverlaufs: [[Beginn, Tiefstwert, letzter Tag], ...].

    Normalpreis ist der häufigste Preis im Zeitraum, ein Angebot jede Strecke
    mindestens 3 % darunter. Steigt der Normalpreis, zählt der häufigere.
    """
    series = [(d, v) for d, v in series if not since or d >= since]
    if not series:
        return []
    counts = {}
    for _, v in series:
        counts[v] = counts.get(v, 0) + 1
    regular = max(counts, key=lambda v: (counts[v], v))
    runs, run = [], None
    for d, v in series:
        if v < regular * 0.97:
            if run is None:
                run = [d, v, d]
            run[1] = min(run[1], v)
            run[2] = d
        elif run is not None:
            runs.append(run)
            run = None
    if run is not None:
        runs.append(run)
    return runs


def month_lows(series):
    """Tiefster Preis je Monat eines Tagesverlaufs: [[JJJJ-MM, Tiefstwert], ...]. Klein genug
    zum Speichern; der Bestpreis wählt daraus seinen Zeitraum."""
    out = {}
    for d, v in series:
        m = d[:7]
        if v and v > 0 and (m not in out or v < out[m]):
            out[m] = v
    return [[m, out[m]] for m in sorted(out)]


def wishlist_id(url_or_id):
    m = _WISHLIST_RE.search(url_or_id or "")
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9]+", (url_or_id or "").strip()):
        return url_or_id.strip()
    raise ValueError("Kein gültiger DekuDeals-Wishlist-Link")


def parse_wishlist_page(page_html):
    """Slugs der Titel auf einer Wishlist-Seite, in Reihenfolge, ohne Dubletten."""
    seen, out = set(), []
    text = _norm(page_html)
    for slug in _ITEM_LINK_RE.findall(text) or _ITEM_LOOSE_RE.findall(text):
        if slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


def fetch_wishlist(url_or_id, fetch=fetch, max_pages=30, pause=None, kind="wishlist"):
    """Alle Slugs einer DekuDeals-Liste (Wishlist oder Sammlung) über alle Seiten."""
    wid = wishlist_id(url_or_id)
    slugs, seen = [], set()
    for page in range(1, max_pages + 1):
        url = f"https://www.dekudeals.com/{kind}/{wid}?page={page}"
        # Seite 1 muss Titel enthalten, Folgeseiten dürfen leer sein
        ok = (lambda t: bool(parse_wishlist_page(t))) if page == 1 else (lambda t: True)
        try:
            page_html = deku_get(url, ok, fetch)
        except FetchError as e:
            # DekuDeals verlinkt eine Folgeseite, auch wenn es keine gibt: Die meldet „nicht
            # gefunden“ (4xx). Eine Sperre, ein Serverfehler oder eine Zeitüberschreitung heißt
            # dagegen „nicht lesbar“, sonst gälte eine gekürzte Liste als vollständig (0.64)
            if page > 1 and 400 <= e.status < 500 and e.status not in BLOCKED:
                break
            raise
        new = [s for s in parse_wishlist_page(page_html) if s not in seen]
        if not new:
            break
        slugs.extend(new)
        seen.update(new)
        if pause:
            pause()
    return slugs


_HEADING_RE = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1\s*>", re.S | re.I)
_ANCHOR_RE = re.compile(r"<a\b([^>]*)>(.*?)</a\s*>", re.S | re.I)
_ALT_RE = re.compile(r"""\b(?:alt|title)\s*=\s*["']([^"']+)["']""", re.I)
# Preisangaben und Rabatte, die in einer Kachel neben dem Namen stehen
_PRICE_BITS_RE = re.compile(
    r"(?:[$€£¥]|R\$|MX\$|CA\$|A\$|NZ\$|kr|zł|CHF)\s?\d[\d.,]*|\d[\d.,]*\s?(?:€|zł|kr|CHF)|-?\d+\s?%")
# Abschnitte einer Artikelseite, die auf verwandte Artikel zeigen
RELATED = {"dlc": ("dlc", "add-on", "add-ons"), "included_in": ("included in",), "contains": ("contains",)}


def _link_title(attrs, inner):
    text = re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", _SCRIPT_RE.sub(" ", inner)))).strip()
    text = re.sub(r"\s+", " ", _PRICE_BITS_RE.sub(" ", text)).strip(" ·|-")
    if not text:
        m = _ALT_RE.search(inner) or _ALT_RE.search(attrs)
        text = html.unescape(m.group(1)).strip() if m else ""
    return text


def parse_related(page_html):
    """Verwandte Artikel einer Artikelseite: DLC, enthalten in (Pakete), enthält.

    DekuDeals setzt über jeden Abschnitt eine Überschrift ("DLC", "Included In",
    "Contains"). Ein Abschnitt reicht bis zur nächsten Überschrift gleicher oder
    höherer Ebene, kleinere Überschriften in den Kacheln gehören dazu. Liefert
    {"dlc": [(Kürzel, Name)], "included_in": [...], "contains": [...], "found": [Abschnitte]},
    in der Reihenfolge der Seite, jedes Kürzel einmal."""
    page_html = _norm(page_html)
    heads = list(_HEADING_RE.finditer(page_html))
    out = {k: [] for k in RELATED}
    found = set()
    for n, h in enumerate(heads):
        name = re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", h.group(2)))).strip().lower()
        name = re.sub(r"\s*\(?\d+\)?$", "", name)          # "DLC (12)"
        key = next((k for k, names in RELATED.items() if name in names), None)
        if not key:
            continue
        found.add(key)
        level = int(h.group(1))
        end = len(page_html)
        for later in heads[n + 1:]:
            if int(later.group(1)) <= level:
                end = later.start()
                break
        seen = {}
        for a in _ANCHOR_RE.finditer(page_html, h.end(), end):
            m = _ITEM_LINK_RE.match("<a " + a.group(1) + ">")
            if not m:
                continue
            slug = m.group(1)
            title = _link_title(a.group(1), a.group(2))
            if slug not in seen or (not seen[slug] and title):
                seen[slug] = title
        out[key] += [(s, t or s.replace("-", " ")) for s, t in seen.items()
                     if s not in {x for x, _ in out[key]}]
    out["found"] = sorted(found)          # welche Abschnitte die Seite überhaupt hat
    return out


def parse_item_page(page_html):
    """Titel, Hauptspiel (bei DLC) und Nintendo-IDs aus einer Artikelseite."""
    page_html = _norm(page_html)
    title = re.sub(r"\s*\|\s*Deku Deals\s*$", "", page_title(page_html)) or None
    parent = parent_title = None
    m = _PARENT_RE.search(page_html)
    if m:
        parent = m.group(1)
        parent_title = html.unescape(m.group(2)).strip() or None
    nsuids = []
    for href in _URL_RE.findall(html.unescape(page_html)):
        if "nintendo" not in href.lower():
            continue
        for n in _NSUID_RE.findall(href):
            if n not in nsuids:
                nsuids.append(n)
    low = parse_low(page_html)
    # eShop-ID je Land aus den Links der Preistabelle („eshop_de:7008…“), auch dort, wo die
    # Shop-Adresse keine ID trägt (Online-Mitgliedschaft, 0.53.6)
    eshop_ids, eshop_urls = {}, {}
    for cc, n in re.findall(r"eshop_([a-z]{2}):(70\d{12})", page_html):
        eshop_ids.setdefault(cc.upper(), [])
        if n not in eshop_ids[cc.upper()]:
            eshop_ids[cc.upper()].append(n)
    # Shop-Link dieser Zeile, nur Nintendo-Adressen (für die Mitgliedschaft, 0.56.1)
    for tag in re.findall(r"<a\b[^>]*eshop_[a-z]{2}:70\d{12}[^>]*>", page_html):
        cc = re.search(r"eshop_([a-z]{2}):", tag).group(1).upper()
        m = re.search(r"href=['\"](https://[a-z.-]*nintendo\.[a-z.]+/[^'\"]*)['\"]", tag)
        if m and cc not in eshop_urls:
            eshop_urls[cc] = html.unescape(m.group(1))
    return {"title": title, "parent": parent, "parent_title": parent_title,
            "nsuids": nsuids, "eshop_ids": eshop_ids, "eshop_urls": eshop_urls, "low": low, "lows": parse_lows(page_html),
            "history": parse_history(page_html), "related": parse_related(page_html),
            # Hat die Seite den Abschnitt der Tiefstpreise überhaupt? Ohne ihn bleibt der alte
            # Wert stehen, statt still zu verschwinden (0.64: ein geänderter Seitenaufbau löscht nichts)
            "low_found": bool(_LOW_RE.search(page_html))}


# Während eines Abgleichs ein Dict: Jede Artikelseite kommt höchstens einmal, auch wenn
# mehrere Schritte sie brauchen (IDs, Tiefstpreis, DLC und Pakete). Sonst None (0.54.1)
item_cache = None


def fetch_item(slug, country, fetch=fetch):
    key = (slug, country)
    if item_cache is not None and key in item_cache:
        return item_cache[key]
    url = f"https://www.dekudeals.com/items/{slug}?country={country}"
    info = parse_item_page(deku_get(url, lambda t: "deku deals" in page_title(t).lower(), fetch))
    if item_cache is not None:
        item_cache[key] = info
    return info


# ----------------------------------------------------------------- Nintendo

_LANG_FALLBACK = ["en", "es", "pt", "ja", "de", "fr"]


def parse_prices(payload):
    """Antwort der Preisabfrage -> {nsuid: {...}}."""
    out = {}
    for p in payload.get("prices", []):
        nsuid = str(p.get("title_id"))
        entry = {"status": p.get("sales_status") or "unknown"}
        reg = p.get("regular_price")
        if reg:
            entry["currency"] = reg.get("currency")
            entry["regular"] = float(reg.get("raw_value"))
        disc = p.get("discount_price")
        if disc:
            entry["discount"] = float(disc.get("raw_value"))
            entry["start"] = disc.get("start_datetime")
            entry["end"] = disc.get("end_datetime")
        out[nsuid] = entry
    return out


def fetch_prices(country, nsuids, lang="en", fetch=fetch, pause=None):
    """Preise eines Landes für beliebig viele IDs (50 je Abruf)."""
    nsuids = list(dict.fromkeys(nsuids))
    out = {}
    langs = [lang] + [l for l in _LANG_FALLBACK if l != lang]
    good_lang = None
    for i in range(0, len(nsuids), 50):
        chunk = nsuids[i:i + 50]
        last_err = None
        for l in ([good_lang] if good_lang else langs):
            q = urllib.parse.urlencode(
                {"country": country, "lang": l, "ids": ",".join(chunk)})
            try:
                payload = json.loads(fetch(f"{NINTENDO_PRICE_URL}?{q}"))
            except FetchError as e:
                last_err = e
                if e.status == 400 and not good_lang:
                    continue  # andere Sprache versuchen
                raise
            good_lang = l
            out.update(parse_prices(payload))
            last_err = None
            break
        if last_err:
            raise last_err
        if pause:
            pause()
    return out


# Nintendos Mitgliedschaftsseite ec.nintendo.com/{Land}/{Sprache}/membership (ab 0.58): Sie nennt
# die eShop-IDs aller Varianten, gruppiert nach Tarif, im eingebetteten Seitenzustand (Next.js,
# Anführungszeichen dort als \\"). Je Tarif eine Liste ticketItemsV2; ein Eintrag hat seine
# nsUid, darin eine Abo-Fassung (subscriptionTicketItem, eigene ID, hier nicht gebraucht) und am
# Ende die Laufzeit in Minuten (grantMinutes, 43200 = 30 Tage). isOp2LimitedRight true ist eine
# Probe-Mitgliedschaft. Aufbau am 14.10.2026 im echten HTML für JP, DE und US gesehen.
NSO_GROUPS = {"individual": None, "family": "fam", "exIndividual": "ep", "exFamily": "epfam"}
NSO_MONTHS = {1: "m1", 3: "m3", 12: "m12"}
_NSO_GROUP_RE = re.compile(r'"(individual|family|exIndividual|exFamily)":\{"ticketItemsV2":\[')
_NSO_ITEM_RE = re.compile(r'\{"nsUid":"?(7008\d{10})')
_NSO_GRANT_RE = re.compile(r'"isOp2LimitedRight":(true|false),"grantMinutes":(\d+)')


def parse_membership_page(page_html):
    """{Variante: eShop-ID} aus Nintendos Mitgliedschaftsseite, Varianten wie planner.NSO_VARIANTS."""
    t = (page_html or "").replace('\\"', '"')
    starts = [(m.start(), m.end(), m.group(1)) for m in _NSO_GROUP_RE.finditer(t)]
    out = {}
    for i, (_, pos, group) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else pos + 20000
        seg = t[pos:end]
        for m in _NSO_ITEM_RE.finditer(seg):
            if "subscriptionTicketItem" in seg[max(0, m.start() - 30):m.start()]:
                continue                  # Abo-Fassung desselben Eintrags
            key = NSO_GROUPS[group]
            if key is None:               # einzeln: Laufzeit entscheidet
                g = _NSO_GRANT_RE.search(t, pos + m.end())
                if not g or g.group(1) == "true":
                    continue
                key = NSO_MONTHS.get(round(int(g.group(2)) / 43200))
            if key and key not in out:
                out[key] = m.group(1)
            if NSO_GROUPS[group]:         # Familie und Erweiterungspaket: je Tarif eine Laufzeit
                break
    return out


# ------------------------------------------------------------------ Sprachen

SOLR_URL = "https://search.nintendo-europe.com/en/select"
JP_STORE_URL = "https://store-jp.nintendo.com/item/software/D{nsuid}"
_JP_LANG_RE = re.compile(r"対応言語(.{0,600})", re.S)
_JP_WORD_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]+語")


def parse_langs_eu(payload):
    """Antwort der Nintendo-Europa-Suche -> {nsuid: "english, german, …"}."""
    out = {}
    for doc in (payload.get("response") or {}).get("docs", []):
        lang = doc.get("language_availability")
        if isinstance(lang, list):
            lang = ", ".join(lang)
        if not lang:
            continue
        for n in doc.get("nsuid_txt") or []:
            out[str(n)] = lang
    return out


def fetch_langs_eu(nsuids, fetch=fetch, pause=None, out=None, done=None):
    """Sprachen der europäischen Fassungen, 40 Titel je Abruf. `out` und `done` (Liste der
    abgefragten IDs) behalten, was vor einem Fehler schon gelesen war (0.64)."""
    out = {} if out is None else out
    nsuids = list(dict.fromkeys(nsuids))
    for i in range(0, len(nsuids), 40):
        if i and pause:
            pause()
        q = urllib.parse.urlencode({
            "q": "*", "fq": "nsuid_txt:(" + " OR ".join(nsuids[i:i + 40]) + ")",
            "fl": "nsuid_txt,language_availability", "rows": 200, "wt": "json"})
        out.update(parse_langs_eu(json.loads(fetch(f"{SOLR_URL}?{q}"))))
        if done is not None:
            done.extend(nsuids[i:i + 40])
    return out


def parse_langs_jp(page_html):
    """Sprachen von einer Produktseite des japanischen Stores (対応言語)."""
    m = _JP_LANG_RE.search(page_html or "")
    if not m:
        return None
    text = html.unescape(_TAG_RE.sub(" ", m.group(1)))
    words = [w for w in _JP_WORD_RE.findall(text) if w != "対応言語"]
    return ", ".join(dict.fromkeys(words)) or None


JP_WAITING = 20000   # kürzere Seiten ohne 対応言語 sind der Warteraum, keine Produktseite


def fetch_langs_jp(nsuid, fetch=fetch):
    """store-jp steht hinter einem Warteraum (Queue-it) mit Bot-Schutz. Durch kommt nur ein
    Browser mit JavaScript; das Tool bekommt dann eine kurze Seite ohne Produkt. Die meldet
    es als 503, damit der Abgleich Japan für diesmal sein lässt, statt jede Seite zu fragen."""
    url = JP_STORE_URL.format(nsuid=nsuid)
    page = fetch(url)
    langs = parse_langs_jp(page)
    if langs is None and len(page or "") < JP_WAITING:
        raise FetchError(url, 503, "Warteraum")
    return langs


def jp_words(text):
    """Sprachwörter aus einem Text des japanischen Stores, z. B. vom Browser-Helfer."""
    return ", ".join(dict.fromkeys(w for w in _JP_WORD_RE.findall(text or "") if w != "対応言語")) or None


# titledb: eine offene Titelliste auf GitHub, aus der Homebrew-Szene, mit den Sprachen
# vieler japanischer Fassungen. Keine Angabe von Nintendo, deshalb in der Oberfläche
# benannt; store-jp und der Browser-Helfer gehen vor. Die Datei ist groß (rund 24 MB
# gepackt), das Tool liest sie deshalb Stück für Stück und behält nur die eigenen IDs.
TITLEDB_URL = "https://raw.githubusercontent.com/blawar/titledb/master/{}.json"
_TDB_LANGS = {"ja": "japanese", "en": "english", "es": "spanish", "fr": "french", "de": "german",
              "it": "italian", "nl": "dutch", "pt": "portuguese", "ru": "russian", "ko": "korean",
              "zh": "chinese", "pl": "polish", "th": "thai"}


def parse_titledb(chunks, wanted):
    """{nsuid: "japanese, english, …"} für die gesuchten IDs mit Sprachangabe."""
    return {n: e["langs"] for n, e in titledb_entries(chunks, wanted).items() if e["langs"]}


def titledb_entries(chunks, wanted):
    """Liest titledb ({nsuid: {..., "id": Programm-ID, "languages": [...]}}) aus Textstücken.
    Liefert für die gesuchten IDs {nsuid: {"langs": "japanese, …" oder None, "app": Programm-ID}}.
    Die Programm-ID ist in allen Regionen gleich, solange es dasselbe Spiel ist."""
    return titledb_scan(chunks, wanted)[0]


def titledb_scan(chunks, wanted, apps=()):
    """Wie titledb_entries, dazu {Programm-ID: nsuid} für die gesuchten Programm-IDs
    (ohne Demos): so findet sich die ID eines Spiels in einer anderen Region."""
    apps = {str(a).upper() for a in apps}
    by_app = {}
    dec, buf, pos, out = json.JSONDecoder(), "", 0, {}
    chunks = iter(chunks)

    def more():
        nonlocal buf, pos
        c = next(chunks, None)
        if c is None:
            return False
        buf, pos = buf[pos:] + c, 0
        return True
    while "{" not in buf[pos:]:
        if not more():
            return out, by_app
    pos = buf.index("{", pos) + 1
    while True:
        while pos < len(buf) and buf[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(buf):
            if not more():
                return out, by_app
            continue
        if buf[pos] == "}":
            return out, by_app
        try:
            key, end = dec.raw_decode(buf, pos)
            colon = buf.index(":", end)
            start = colon + 1
            while start < len(buf) and buf[start] in " \t\r\n":
                start += 1
            val, end = dec.raw_decode(buf, start)
        except ValueError:
            if len(buf) - pos > 5_000_000:
                raise ValueError("titledb: Eintrag nicht lesbar")
            if not more():
                raise ValueError("titledb: Datei endet mitten in einem Eintrag")
            continue
        pos = end
        app = str(val.get("id") or "").upper() if isinstance(val, dict) else ""
        if app in apps and not val.get("isDemo") and app not in by_app:
            by_app[app] = key
        if key in wanted and isinstance(val, dict):
            langs = val.get("languages") if isinstance(val.get("languages"), list) else []
            out[key] = {"langs": ", ".join(dict.fromkeys(_TDB_LANGS.get(str(l), str(l)) for l in langs)) or None,
                        "app": str(val.get("id") or "").upper() or None}


def _stream(url, timeout=60):
    """Großen Text in Stücken laden, gzip unterwegs entpacken."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    if blocked_target(url):
        raise FetchError(url, 0, blocked_target(url))
    try:
        resp = _opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise FetchError(url, e.code)
    except Exception as e:
        raise FetchError(url, 0, str(e)[:160])
    with resp:
        unzip = (zlib.decompressobj(16 + zlib.MAX_WBITS)
                 if (resp.headers.get("Content-Encoding") or "").lower() == "gzip" else None)
        text = codecs.getincrementaldecoder("utf-8")(errors="replace")
        while True:
            raw = resp.read(1 << 16)
            if not raw:
                break
            yield text.decode(unzip.decompress(raw) if unzip else raw)
        yield text.decode(unzip.flush() if unzip else b"", final=True)


def name_key(title):
    """Name zum Vergleichen (Kauftitel und titledb): ohne ™ ®, Satzzeichen, Groß-/Kleinschreibung."""
    t = re.sub(r"[\u0300-\u036f]", "", unicodedata.normalize("NFKD", re.sub(r"[™®©]", "", str(title or ""))))
    t = unicodedata.normalize("NFKC", t).casefold()     # ohne Akzente lateinischer Buchstaben (0.76)
    return " ".join(re.sub(r"[^\w]+", " ", t).split())


def titledb_names(chunks, names=(), apps=()):
    """Namen in einer titledb-Liste (0.72): {Name: Programm-ID} für die gesuchten Namen (ohne Demos)
    und {Programm-ID: Name} für die gesuchten Programm-IDs. Liest die Datei Stück für Stück wie
    titledb_scan; behalten wird nur, was gesucht war."""
    names = {name_key(n) for n in names} - {""}
    apps = {str(a).upper() for a in apps}
    by_name, by_app = {}, {}
    for key, val in _titledb_items(chunks):
        if not isinstance(val, dict) or val.get("isDemo"):
            continue
        app = str(val.get("id") or "").upper()
        n = name_key(val.get("name"))
        if n in names and app and n not in by_name:
            by_name[n] = app
        if app in apps and app not in by_app and val.get("name"):
            by_app[app] = str(val["name"])
    return by_name, by_app


def titledb_lookup(chunks, names):
    """Kauftitel in einer titledb-Liste nachschlagen (0.79): {Name: {"app", "ns", "pre"}}.
    app ist die Programm-ID, ns die Shop-ID dieser Region (auch bei Pässen und Paketen, die
    titledb ohne Programm-ID führt). Ohne Programm-ID sucht pre das längste bekannte Spiel, mit
    dessen Namen der Kauf beginnt: [Programm-ID, Rest des Namens], etwa „… アップグレードパス“."""
    want = {name_key(n) for n in names} - {""}
    found, games = {}, {}
    for key, val in _titledb_items(chunks):
        if not isinstance(val, dict) or val.get("isDemo"):
            continue
        n, app = name_key(val.get("name")), str(val.get("id") or "").upper()
        if app and n and len(n) >= 3:
            games.setdefault(n, app)
        if n in want:
            hit = found.setdefault(n, {"app": None, "ns": None})
            hit["app"] = hit["app"] or app or None
            hit["ns"] = hit["ns"] or str(val.get("nsuId") or key or "") or None
    for n in want:
        hit = found.setdefault(n, {"app": None, "ns": None})
        if hit["app"]:
            continue
        words = n.split(" ")
        for i in range(len(words) - 1, 0, -1):
            head = " ".join(words[:i])
            if head in games:
                hit["pre"] = [games[head], " ".join(words[i:])]
                break
    return {n: h for n, h in found.items() if h["app"] or h["ns"] or h.get("pre")}


def fetch_titledb_lookup(region, names, fetch=fetch):
    url = TITLEDB_URL.format(region)
    chunks = _stream(url) if fetch is _plain_fetch else [fetch(url)]
    return titledb_lookup(chunks, names)


def _titledb_items(chunks):
    """(Schlüssel, Eintrag) einer titledb-Liste, Stück für Stück gelesen."""
    dec, buf, pos = json.JSONDecoder(), "", 0
    chunks = iter(chunks)

    def more():
        nonlocal buf, pos
        c = next(chunks, None)
        if c is None:
            return False
        buf, pos = buf[pos:] + c, 0
        return True
    while "{" not in buf[pos:]:
        if not more():
            return
    pos = buf.index("{", pos) + 1
    while True:
        while pos < len(buf) and buf[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(buf):
            if not more():
                return
            continue
        if buf[pos] == "}":
            return
        try:
            key, end = dec.raw_decode(buf, pos)
            colon = buf.index(":", end)
            start = colon + 1
            while start < len(buf) and buf[start] in " \t\r\n":
                start += 1
            val, end = dec.raw_decode(buf, start)
        except ValueError:
            if len(buf) - pos > 5_000_000:
                raise ValueError("titledb: Eintrag nicht lesbar")
            if not more():
                raise ValueError("titledb: Datei endet mitten in einem Eintrag")
            continue
        pos = end
        yield key, val


def fetch_titledb_names(region, names=(), apps=(), fetch=fetch):
    url = TITLEDB_URL.format(region)
    chunks = _stream(url) if fetch is _plain_fetch else [fetch(url)]
    return titledb_names(chunks, names, apps)


def fetch_titledb(nsuids, fetch=fetch, region="JP.ja", apps=None):
    """Einträge einer titledb-Region (JP.ja, DE.de, …) für diese IDs, siehe titledb_entries.
    Mit `apps` zusätzlich {Programm-ID: nsuid} dieser Region, siehe titledb_scan."""
    url = TITLEDB_URL.format(region)
    chunks = _stream(url) if fetch is _plain_fetch else [fetch(url)]
    found, by_app = titledb_scan(chunks, {str(n) for n in nsuids}, apps or ())
    return found if apps is None else (found, by_app)


# Amerika: Die Titelseite des eShops leitet auf die Produktseite von nintendo.com
# weiter. Dort stehen die Sprachen als "Supported languages" und in den
# eingebetteten Seitendaten. Erlaubt laut robots.txt (User-agent *).
AM_STORE_URL = "https://ec.nintendo.com/US/en/titles/{nsuid}"


def ec_url(url, nsuid):
    """Pakete (IDs ab 7007) liegen im eShop unter bundles, nicht unter titles."""
    return url.replace("/titles/", "/bundles/" if str(nsuid).startswith("7007") else "/titles/") \
        .format(nsuid=nsuid)
_LANG_NAMES = ["english", "french", "german", "italian", "spanish", "dutch", "portuguese",
               "russian", "japanese", "korean", "chinese", "polish", "swedish", "danish",
               "norwegian", "finnish", "czech", "hungarian", "greek", "turkish", "ukrainian",
               "arabic", "thai"]
_LANG_NAME_RE = re.compile(r"\b(" + "|".join(_LANG_NAMES) + r")\b", re.I)
_AM_JSON_RE = re.compile(
    r'"(?:supportedLanguages|supported_languages|languages)"\s*:\s*(\[[^\]]{0,1500}\]|"[^"]{0,600}")')
_AM_TEXT_RE = re.compile(r"Supported languages?\s*:?\s*(.{0,250})", re.I)


def _lang_words(text):
    """Bekannte Sprachnamen in Reihenfolge, klein geschrieben. None, wenn keine."""
    words = [w.lower() for w in _LANG_NAME_RE.findall(text or "")]
    return ", ".join(dict.fromkeys(words)) or None


def parse_langs_am(page_html):
    """Sprachen von einer Produktseite von nintendo.com (Amerika)."""
    page_html = _norm(html.unescape(page_html or ""))
    for m in _AM_JSON_RE.finditer(page_html):
        found = _lang_words(m.group(1))
        if found:
            return found
    m = _AM_TEXT_RE.search(visible_text(page_html))
    return _lang_words(m.group(1)) if m else None


def fetch_langs_am(nsuid, fetch=fetch):
    return parse_langs_am(fetch(ec_url(AM_STORE_URL, nsuid)))


# ------------------------------------------------------------ Wechselkurse

def fetch_fx(fetch=fetch):
    """Kurse je 1 EUR. Liefert (rates, stand, quelle)."""
    try:
        data = json.loads(fetch(FX_URL))
        if data.get("result") == "success" and data.get("rates"):
            rates = {k: float(v) for k, v in data["rates"].items()}
            rates["EUR"] = 1.0
            return rates, data.get("time_last_update_utc", ""), "open.er-api"
    except (FetchError, ValueError):
        pass
    data = json.loads(fetch(FX_FALLBACK_URL))
    rates = {k: float(v) for k, v in data["rates"].items()}
    rates["EUR"] = 1.0
    return rates, data.get("date", ""), "frankfurter (EZB)"


# ----------------------------------------------------------- Guthabenkarten

_LD_RE = re.compile(r"""<script[^>]*type=["']application/ld\+json["'][^>]*>(.*?)</script>""", re.S | re.I)


def ld_prices(page_html):
    """Alle Preise aus den strukturierten Produktdaten einer Shopseite (schema.org):
    [(Preis, Währung, Feld)]. Eine Seite kann viele Angebote nennen."""
    out = []
    for block in _LD_RE.findall(page_html or ""):
        try:
            stack = [json.loads(block)]
        except ValueError:
            continue
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
                continue
            if not isinstance(x, dict):
                continue
            cur = x.get("priceCurrency")
            for key in ("lowPrice", "price", "highPrice"):
                if x.get(key) not in (None, "") and cur:
                    try:
                        out.append((float(x[key]), cur, key))
                    except (TypeError, ValueError):
                        pass
            stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
    return out


def parse_ld_price(page_html):
    """Günstigster Preis aus den Produktdaten einer Shopseite: (Preis, Währung) oder
    None, wenn die Seite keine mitliefert, etwa weil sie ihre Preise erst im Browser
    lädt. Nennt die Seite mehrere Angebote, zählt das günstigste (nie ein Höchstpreis)."""
    found = [(p, cur) for p, cur, key in ld_prices(page_html) if key != "highPrice" and p > 0]
    if not found:
        return None
    # Mehrere Währungen: die häufigste nehmen, darin den kleinsten Preis
    cur = max({c for _, c in found}, key=lambda c: sum(1 for _, x in found if x == c))
    return min(p for p, c in found if c == cur), cur


# Amazon (ab 0.61): Die Produktseite nennt den Preis des Hauptangebots als Daten der
# Kaufoptionen ("priceAmount" mit "currencySymbol") und sichtbar im Kasten corePrice. Andere
# Beträge auf der Seite (Referenzpreis, Zubehör, Werbung) zählen nicht. Die Währung steht
# daneben: Amazon zeigt Besuchern aus Deutschland umgerechnete Europreise (ab 0.62.1 erkannt).
_AMZ_AMOUNT_RE = re.compile(r'"desktop_buybox_group_1"\s*:\s*\[\s*\{([^\]]{0,3000}?)"priceAmount"\s*:\s*([\d.]+)([^}\]]{0,800})')
_AMZ_SYMBOL_RE = re.compile(r'"(?:currencySymbol|displayPrice)"\s*:\s*"([^"]{1,40})"')
_AMZ_CORE_RE = re.compile(r'id="(?:corePrice(?:Display)?_(?:desktop_)?feature_div|apex_desktop)"(.{0,6000})', re.S)
_AMZ_OFF_RE = re.compile(r'class="a-offscreen">\s*([^<]{1,40}?)\s*<')
_AMZ_PRICE_RE = re.compile(r'(?:class="a-price-symbol">\s*([^<]{1,6}?)\s*</span>\s*)?<span class="a-price-whole">\s*([\d.,]+)')
_AMZ_SHOPS = {"amazon.co.jp": "JPY", "amazon.de": "EUR", "amazon.fr": "EUR", "amazon.it": "EUR",
              "amazon.es": "EUR", "amazon.nl": "EUR", "amazon.com": "USD", "amazon.ca": "CAD",
              "amazon.co.uk": "GBP", "amazon.com.au": "AUD", "amazon.com.mx": "MXN", "amazon.com.br": "BRL"}
_SYMBOLS = (("JP¥", "JPY"), ("CA$", "CAD"), ("A$", "AUD"), ("R$", "BRL"), ("MX$", "MXN"), ("US$", "USD"),
            ("￥", "JPY"), ("¥", "JPY"), ("円", "JPY"), ("€", "EUR"), ("£", "GBP"), ("$", "USD"),
            ("\\u20ac", "EUR"), ("\\uffe5", "JPY"), ("\\u00a5", "JPY"), ("\\u00a3", "GBP"),
            ("EUR", "EUR"), ("JPY", "JPY"), ("USD", "USD"), ("GBP", "GBP"))


def is_amazon(url):
    return bool(re.match(r"https?://(?:www\.)?amazon\.[a-z.]+/", url or "", re.I))


def amazon_currency(url):
    """Landeswährung eines Amazon-Shops nach seiner Adresse, sonst None."""
    m = re.match(r"https?://(?:www\.)?(amazon\.[a-z.]+)/", url or "", re.I)
    return _AMZ_SHOPS.get(m.group(1).lower()) if m else None


def amazon_captcha(page_html):
    """Prüfseite statt Produktseite. Das Wort „robot“ allein genügt nicht: Es steht auch
    auf normalen Produktseiten (bis 0.60 ein Fehlalarm)."""
    t = page_html or ""
    return "validateCaptcha" in t or ("captcha" in t.lower() and len(t) < 30000)


def _symbol(text):
    """Währung aus einem Zeichen oder Kürzel wie €, ￥, JP¥, EUR; sonst None."""
    for sym, cur in _SYMBOLS:
        if sym in (text or ""):
            return cur
    return None


def _amount(text, cur):
    """Betrag aus einem Preistext. Yen ohne Nachkommastellen, Euro auch mit Komma."""
    t = re.sub(r"[^\d.,]", "", text or "")
    if not t:
        return None
    if cur == "JPY":
        t = t.replace(",", "").split(".")[0]
    elif re.search(r",\d{2}$", t):
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", "")
    try:
        v = float(t.rstrip("."))
    except ValueError:
        return None
    return v if 0 < v < 1_000_000 else None


def parse_amazon_price(page_html, default=None):
    """(Preis, Währung, Fundstelle) des Hauptangebots einer Amazon-Produktseite, sonst None.
    Die Währung kommt von der Seite; nennt sie keine, gilt `default` (die des Shops)."""
    t = page_html or ""
    m = _AMZ_AMOUNT_RE.search(t.replace("&quot;", '"'))
    if m:
        around = m.group(1) + m.group(3)
        cur = next((_symbol(x) for x in _AMZ_SYMBOL_RE.findall(around) if _symbol(x)), None) or default
        v = _amount(m.group(2), None)
        if v and cur:
            return v, cur, "Kaufoptionen"
    core = _AMZ_CORE_RE.search(t)
    if core:
        for text in _AMZ_OFF_RE.findall(core.group(1)):
            cur = _symbol(text) or default
            v = _amount(text, cur)
            if v and cur:
                return v, cur, "Preiskasten"
        m = _AMZ_PRICE_RE.search(core.group(1))
        if m:
            cur = _symbol(m.group(1) or "") or default
            v = _amount(m.group(2), cur)
            if v and cur:
                return v, cur, "Preiskasten"
    return None


def parse_shop_price(url, page_html):
    """Preis einer Shopseite: Produktdaten (schema.org), bei Amazon das Hauptangebot.
    (Preis, Währung) oder None."""
    if is_amazon(url):
        if amazon_captcha(page_html):
            return None
        found = parse_amazon_price(page_html, amazon_currency(url))
        return found[:2] if found else None
    return parse_ld_price(page_html)


def fetch_card_price(url, fetch=fetch):
    """Preis einer Guthabenkarte von ihrer Shopseite: (Preis, Währung) oder None."""
    return parse_ld_price(fetch(url))
