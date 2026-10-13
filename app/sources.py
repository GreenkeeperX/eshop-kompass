"""Datenquellen: DekuDeals (Wishlist, Titel-IDs), Nintendo (Preise), Wechselkurse.

Alle Netzabrufe laufen über `fetch(url)`, damit Tests eine Attrappe
einsetzen können.
"""
import codecs
import gzip
import html
import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zlib

VERSION = "0.53.4"

# Das Tool gibt sich immer als es selbst zu erkennen. Antwortet eine Quelle mit
# einer Sperre (403, 429) oder einer Prüfseite, hört es auf, statt sich zu tarnen.
USER_AGENT = f"eshop-kompass/{VERSION} (privates Wishlist-Tool)"
BLOCKED = (403, 429)

NINTENDO_PRICE_URL = "https://api.ec.nintendo.com/v1/price"
FX_URL = "https://open.er-api.com/v6/latest/EUR"
FX_FALLBACK_URL = "https://api.frankfurter.dev/v1/latest?from=EUR"

_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


class FetchError(Exception):
    def __init__(self, url, status, detail=""):
        super().__init__(f"{status} bei {url} {detail}".strip())
        self.url, self.status = url, status


def _decode(raw, enc):
    if enc == "gzip":
        return gzip.decompress(raw)
    if enc == "deflate":
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw


def request(url, ua=None, timeout=25, encoding="gzip, deflate"):
    """HTTP GET ohne Ausnahme: liefert Status, Text und Kopfdaten für die Diagnose."""
    req = urllib.request.Request(url, headers={
        "User-Agent": ua or USER_AGENT,
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
        "Accept-Encoding": encoding,
    })
    out = {"url": url, "status": 0, "text": "", "enc": "", "server": "", "error": ""}
    try:
        try:
            resp = _opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            resp = e                      # Fehlerseiten haben auch einen Inhalt
        with resp:
            raw = resp.read()
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


def deku_get(url, ok, fetch=fetch):
    """Holt eine DekuDeals-Seite und prüft mit `ok`, ob sie brauchbar ist."""
    del attempts[:]
    try:
        text = fetch(url)
    except FetchError as e:
        attempts.append(f"Fehler {e.status or ''} {str(e)[-120:] if not e.status else ''}".strip())
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
    for t in re.finditer(r"digital|physical|" + _AMOUNT_RE.pattern, text, re.I):
        w = t.group(0).lower()
        seq.append(w if w in ("digital", "physical") else parse_amount(t.group(0)))
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
            # DekuDeals verlinkt eine Folgeseite, auch wenn es keine gibt
            if page > 1 and e.status >= 400:
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
    return {"title": title, "parent": parent, "parent_title": parent_title,
            "nsuids": nsuids, "low": low, "lows": parse_lows(page_html),
            "history": parse_history(page_html), "related": parse_related(page_html)}


def fetch_item(slug, country, fetch=fetch):
    url = f"https://www.dekudeals.com/items/{slug}?country={country}"
    return parse_item_page(deku_get(url, lambda t: "deku deals" in page_title(t).lower(), fetch))


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


def fetch_langs_eu(nsuids, fetch=fetch, pause=None):
    """Sprachen der europäischen Fassungen, 40 Titel je Abruf."""
    out = {}
    nsuids = list(dict.fromkeys(nsuids))
    for i in range(0, len(nsuids), 40):
        q = urllib.parse.urlencode({
            "q": "*", "fq": "nsuid_txt:(" + " OR ".join(nsuids[i:i + 40]) + ")",
            "fl": "nsuid_txt,language_availability", "rows": 200, "wt": "json"})
        out.update(parse_langs_eu(json.loads(fetch(f"{SOLR_URL}?{q}"))))
        if pause:
            pause()
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
    """Kurse je 1 EUR. Liefert (rates, stand)."""
    try:
        data = json.loads(fetch(FX_URL))
        if data.get("result") == "success" and data.get("rates"):
            rates = {k: float(v) for k, v in data["rates"].items()}
            rates["EUR"] = 1.0
            return rates, data.get("time_last_update_utc", "")
    except (FetchError, ValueError):
        pass
    data = json.loads(fetch(FX_FALLBACK_URL))
    rates = {k: float(v) for k, v in data["rates"].items()}
    rates["EUR"] = 1.0
    return rates, data.get("date", "")


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


def fetch_card_price(url, fetch=fetch):
    """Preis einer Guthabenkarte von ihrer Shopseite: (Preis, Währung) oder None."""
    return parse_ld_price(fetch(url))
