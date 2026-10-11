"""Datenquellen: DekuDeals (Wishlist, Titel-IDs), Nintendo (Preise), Wechselkurse.

Alle Netzabrufe laufen über `fetch(url)`, damit Tests eine Attrappe
einsetzen können.
"""
import gzip
import html
import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zlib

VERSION = "0.6"

# Kennungen, mit denen das Tool anfragt. Zuerst die ehrliche eigene, sonst eine
# gewöhnliche Browser-Kennung. Bot-Sperren werden nicht umgangen.
UAS = [
    ("tool", f"eshop-kompass/{VERSION} (privates Wishlist-Tool)"),
    ("browser", "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"),
]

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
        "User-Agent": ua or UAS[0][1],
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
_NSUID_RE = re.compile(r"(?<!\d)(7\d{13})(?!\d)")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_PARENT_RE = re.compile(
    r"""DLC for[^<]*(?:<(?!a\b)[^>]*>[^<]*)*<a\b[^>]*href=["']?[^"'>\s]*?/items/([A-Za-z0-9_\-]+)"""
    r"""[^>]*>([^<]*)""", re.S | re.I)
_SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)

attempts = []       # Protokoll der letzten DekuDeals-Abrufe, für die Diagnose
_deku_ua = None     # Kennung, mit der DekuDeals zuletzt brauchbar geantwortet hat


def _norm(page_html):
    return (page_html or "").replace("\\/", "/")


def page_title(page_html):
    m = _TITLE_RE.search(page_html or "")
    return html.unescape(m.group(1)).strip() if m else ""


def describe(page_html):
    """Kurzbeschreibung einer Seite: Länge, Titel, Treffer, sichtbarer Anfang."""
    text = _TAG_RE.sub(" ", _SCRIPT_RE.sub(" ", page_html or ""))
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return (f"{len(page_html or '')} Zeichen, Titel „{page_title(page_html)[:60]}“, "
            f"{len(parse_wishlist_page(page_html))} Titel-Links, Anfang: {text[:140]}")


def _call(fetch, url, ua):
    return fetch(url, ua=ua)


def deku_get(url, ok, fetch=fetch):
    """Holt eine DekuDeals-Seite und prüft mit `ok`, ob sie brauchbar ist."""
    global _deku_ua
    order = [u for u in UAS if u[1] == _deku_ua] + [u for u in UAS if u[1] != _deku_ua]
    del attempts[:]
    last = None
    for label, ua in order:
        try:
            text = _call(fetch, url, ua)
        except FetchError as e:
            attempts.append(f"{label}: Fehler {e.status or ''} {str(e)[-120:] if not e.status else ''}".strip())
            last = e
            if e.status == 404:
                break                     # Seite gibt es nicht, andere Kennung hilft nicht
            continue
        if ok(text):
            _deku_ua = ua
            return text
        attempts.append(f"{label}: {describe(text)}")
        last = FetchError(url, 200, "Seite ohne erwarteten Inhalt")
    raise last


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


def parse_low(page_html):
    """Digitaler Tiefstpreis einer Artikelseite.

    Wo DekuDeals auch Händler führt, stehen zwei Werte auf der Seite
    (Physical und Digital). Für den eShop-Vergleich zählt nur der digitale.
    """
    m = _LOW_RE.search(page_html or "")
    if not m:
        return None
    text = html.unescape(_TAG_RE.sub(" ", m.group(1)))
    text = re.split(r"Time range", text, maxsplit=1, flags=re.I)[0]
    digital = re.search(r"digital", text, re.I)
    if digital:
        return parse_amount(text[digital.end():digital.end() + 60])
    if re.search(r"physical", text, re.I):
        return None                       # nur ein Händler-Tiefstpreis bekannt
    return parse_amount(text)


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
            "nsuids": nsuids, "low": low}


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


def fetch_langs_jp(nsuid, fetch=fetch):
    return parse_langs_jp(fetch(JP_STORE_URL.format(nsuid=nsuid)))


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
