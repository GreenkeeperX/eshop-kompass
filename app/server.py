"""Kleiner Webserver: liefert die Oberfläche und eine JSON-Schnittstelle."""
import gzip
import ipaddress
import json
import re
import os
import sys
import threading
import traceback
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import countries, planner, sources, store, sync

STATIC = os.path.join(os.path.dirname(__file__), "static")


def _num(x):
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return None


def state():
    with planner.shared_contexts():
        return _state()


def _state():
    settings = store.load_settings()
    data = store.load_data()
    ui = store.load_ui()
    radar = planner.radar(data, settings, ui["targets"])
    pay = planner.pay_info(data, settings)
    return {
        "settings": settings,
        "ui": ui,
        "radar": radar,
        "collection": planner.collection(data, settings, rows=radar),
        "nso": planner.membership(data, settings, bought=store.load_purchases()),
        "nso_items": planner.nso_items(data),
        "extra_offers": planner.extra_offers(data, settings),
        "s2": planner.switch2_paths(data, radar, settings),
        "bundles": planner.bundles(data, radar, settings),
        "levels": planner.price_levels(data, settings),
        "pay": pay,
        "offer_checks": planner.offer_checks(data, settings, pay),
        "card_status": planner.card_status(data, settings),
        "owned_count": len(data.get("owned") or []),
        "countries": [dict(countries.BY_CODE[c], family_name=countries.FAMILIES[
            countries.BY_CODE[c]["family"]]) for c in countries.ORDER],
        "status": sync.status,
        "version": sources.VERSION,
        "last_sync": data.get("last_sync"),
        "checks": data.get("checks"),
        "fallback": sync.fallback_state(data),
        "fx_updated": data["fx"].get("updated"),
        "item_count": sum(1 for it in data["items"].values() if it.get("active")),
        "matrix": planner.matrix(data, settings),
        "lang_todo": planner.lang_todo(data, settings),
        "dlc_fit": planner.dlc_fit(data),
        "eshop": planner.eshop_matches(data)["rows"],
        "eshop_known": planner.known_titles(data) if (data.get("_eshop") or {}).get("entries") else [],
        "eshop_seit": (data.get("_eshop") or {}).get("seit") or 0,
        "eshop_at": (data.get("_eshop") or {}).get("at") or 0,
        "eshop_owned_n": (data.get("_eshop") or {}).get("owned_n"),
    }


# Namen, die nur im eigenen Netz aufgelöst werden (RFC 8375 und üblich): Eine fremde Domain kann
# nicht auf sie zeigen, deshalb gelten sie ohne Eintrag
LOCAL_SUFFIXES = (".home.arpa", ".local", ".lan", ".internal", ".localhost")


def host_allowed(host, extra=None):
    """Schutz gegen DNS-Rebinding (0.99.5): Eine fremde Webseite, deren Domain plötzlich auf den
    Server im Heimnetz zeigt, wäre für den Browser dieselbe Seite und könnte die Sicherung lesen.
    Angenommen werden nur IP-Adressen, localhost, Namen ohne Punkt, Namen im eigenen Netz
    (LOCAL_SUFFIXES) und, was in ALLOWED_HOSTS steht (mit Komma getrennt; „.beispiel.de“ gilt für
    alle Namen darunter)."""
    if not host:
        return True                    # ohne Host-Kopf: kein Browser
    name = host.strip().lower()
    if name.startswith("["):
        name = name[1:].split("]")[0]  # IPv6 mit Port
    elif name.count(":") == 1:
        name = name.split(":")[0]
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        pass
    name = name.rstrip(".")
    if "." not in name or name.endswith(LOCAL_SUFFIXES):
        return True
    extra = os.environ.get("ALLOWED_HOSTS", "") if extra is None else extra
    for e in (x.strip().lower().rstrip(".") for x in extra.split(",")):
        if e and (name == e or (e.startswith(".") and name.endswith(e))):
            return True
    return False


def plaene(basket=..., overrides=None):
    """Länderkarten, Korb und Kaufplan. Korb und eigene Änderungen kommen aus der Anfrage, wie bei
    /api/plans, sonst aus der gespeicherten Auswahl."""
    ui = store.load_ui()
    data, settings = store.load_data(), store.load_settings()
    basket = ui.get("basket") if basket is ... else basket
    overrides = (ui.get("overrides") if overrides is None else overrides) or {}
    basket = [str(x) for x in basket] if isinstance(basket, list) else None
    overrides = overrides if isinstance(overrides, dict) else {}
    with planner.shared_contexts():
        res, _ = planner.plans(data, settings, overrides=overrides, with_mix=True)
        bres, bmix = planner.plans(data, settings, overrides=overrides, basket=basket,
                                   with_mix=True) if basket else ([], None)
        kauf = planner.purchase_plan(data, settings, ui["targets"], include_good=ui["plan_good"],
                                     bought=store.load_purchases(), fill=ui["plan_fill"], skip=ui["plan_skip"])
    return {"plans": res, "bplans": bres, "mix": bmix, "kauf": kauf}


class Handler(BaseHTTPRequestHandler):
    server_version = "eshop-kompass"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        # Gepackt, wenn der Browser es kann (0.99): Zustand und Pläne sind über 1 MB, gepackt ein Zehntel
        packed = len(body) > 20_000 and "gzip" in (self.headers.get("Accept-Encoding") or "")
        if packed:
            body = gzip.compress(body, compresslevel=5)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if packed:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # Nicht in fremde Seiten einbetten (eigene dürfen: Selbsttest), Typen nicht raten, keine Adresse an verlinkte Seiten (0.99.1)
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _body(self, limit=1_000_000):
        # Nur JSON annehmen: Ein einfaches Formular einer fremden Seite im
        # Browser kann so keine Einstellungen ändern oder Abgleiche starten.
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise ValueError("nur application/json")
        n = int(self.headers.get("Content-Length") or 0)
        if n < 0 or n > limit:          # negativ hieße: lesen bis zum Ende (0.99.1)
            raise ValueError("zu groß")
        body = json.loads(self.rfile.read(n) or b"{}")
        if not isinstance(body, dict):
            raise ValueError("JSON-Objekt erwartet")
        return body

    def _foreign(self):
        if host_allowed(self.headers.get("Host")):
            return False
        self._send(421, {"error": "Unbekannte Adresse. Erlaubte Namen stehen in ALLOWED_HOSTS (siehe README)."})
        return True

    def do_GET(self):
        path = self.path.split("?")[0]
        if self._foreign():
            return
        try:
            if path in ("/", "/index.html"):
                with open(os.path.join(STATIC, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif re.fullmatch(r"/(style\.css|js/[a-z-]+\.js)", path) and os.path.isfile(os.path.join(STATIC, path[1:])):
                # Teile der Oberfläche (0.86): nur diese Namen, kein Pfad aus der Anfrage sonst
                with open(os.path.join(STATIC, path[1:]), "rb") as f:
                    self._send(200, f.read(), "text/css; charset=utf-8" if path.endswith(".css")
                               else "text/javascript; charset=utf-8")
            elif path == "/api/state":
                self._send(200, state())
            elif path == "/api/status":
                self._send(200, dict(sync.status, last_sync=store.load_data().get("last_sync")))
            elif path == "/api/kaufplan":
                ui = store.load_ui()
                with planner.shared_contexts():
                    out = planner.purchase_plan(store.load_data(), store.load_settings(), ui["targets"],
                                                include_good=ui["plan_good"],
                                                bought=store.load_purchases(), fill=ui["plan_fill"],
                                                skip=ui["plan_skip"])
                self._send(200, out)
            elif path == "/api/verlauf":
                q = urllib.parse.parse_qs(self.path.partition("?")[2])
                slug = (q.get("slug") or [""])[0]
                out = planner.price_history(store.load_data(), store.load_settings(),
                                            store.load_history(), slug)
                out["target"] = store.load_ui()["targets"].get(slug)
                self._send(200, out)
            elif path == "/api/fall":
                q = urllib.parse.parse_qs(self.path.partition("?")[2])
                slug = (q.get("slug") or [""])[0]
                out = planner.case_export(store.load_data(), store.load_settings(),
                                          store.load_history(), slug)
                out["version"] = sources.VERSION
                self._send(200, out)
            elif path == "/api/abgleich":
                # Abgleichsdaten und Protokoll zum Nachprüfen; keine Einstellungen, also auch
                # kein Wishlist- oder Sammlungslink, und ab 0.99.1 ohne Kaufverlauf (steht in der Sicherung)
                self._send(200, {"app": "eshop-kompass", "version": sources.VERSION,
                                 "data": {k: v for k, v in store.load_data().items() if k != "_eshop"},
                                 "log": [re.sub(r"/(wishlist|collection)/[^/?\s]+", r"/\1/…", line)
                                         for line in sync.status["log"]]})
            elif path == "/api/export":
                self._send(200, {"app": "eshop-kompass", "version": sources.VERSION,
                                 "settings": store.load_settings(), "ui": store.load_ui(),
                                 "purchases": store.load_purchases(), "history": store.load_history(),
                                 "eshop_history": store.load_eshop_history()})
            else:
                self._send(404, {"error": "nicht gefunden"})
        except Exception as e:
            self._fail(path, e)

    def do_POST(self):
        path = self.path.split("?")[0]
        if self._foreign():
            return
        try:
            # Eine Sicherung wächst mit Preisaufzeichnung und Kaufverlauf über 1 MB (0.99.2)
            body = self._body(50_000_000 if path == "/api/import" else 1_000_000)
            if path == "/api/plans":
                with planner.shared_contexts():
                    res, split = planner.plans(store.load_data(), store.load_settings(),
                                               overrides=body.get("overrides") or {},
                                               must=body.get("must") or [],
                                               basket=body.get("basket") or [], with_mix=True,
                                               only=[c for c in body.get("only") or [] if isinstance(c, str)] or None)
                self._send(200, {"plans": res, "mix": split})
            elif path == "/api/plaene":
                # Länderkarten, Korb und Kaufplan in einer Anfrage (0.99): ein Datenstand, ein
                # gemeinsamer Zwischenspeicher, und die Oberfläche speichert vorher mit (`ui`), statt
                # parallel zu speichern und zu rechnen
                if isinstance(body.get("ui"), dict):
                    store.save_ui(body["ui"])
                self._send(200, plaene(body.get("basket", ...), body.get("overrides")))
            elif path == "/api/settings":
                self._send(200, {"settings": store.save_settings(body)})
            elif path == "/api/ui":
                self._send(200, {"ui": store.save_ui(body)})
            elif path == "/api/import":
                # Sicherung einlesen: nur bekannte Felder, fehlende bleiben wie sie sind
                if isinstance(body.get("settings"), dict):
                    store.save_settings(body["settings"])
                if isinstance(body.get("ui"), dict):
                    store.save_ui(body["ui"])
                if isinstance(body.get("purchases"), list) and not store.load_purchases():
                    store.save_purchases([p for p in body["purchases"] if isinstance(p, dict)][-500:])
                if isinstance(body.get("history"), dict):
                    store.merge_history(body["history"])
                eh = body.get("eshop_history")
                if isinstance(eh, dict) and isinstance(eh.get("entries"), list):
                    store.merge_eshop_history([e for e in eh["entries"] if isinstance(e, dict) and e.get("key")], eh.get("at"), eh.get("seit") or 0)
                    for k, v in (eh.get("picks") if isinstance(eh.get("picks"), dict) else {}).items():
                        try:
                            store.pick_eshop_history(str(k), str(v or ""))
                        except ValueError:
                            pass          # unbekannter Titel: diese Zuordnung fällt weg, der Rest kommt (0.99.2)
                self._send(200, {"ok": True})
            elif path == "/api/bought":
                slugs = [str(x) for x in (body.get("slugs") or [])][:200]
                entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "code": str(body.get("code") or ""), "slugs": slugs,
                         "titles": [str(x) for x in (body.get("titles") or [])][:200],
                         "cost": _num(body.get("cost")), "de": _num(body.get("de")),
                         "games": _num(body.get("games")),
                         "rest": _num(body.get("rest")), "currency": str(body.get("currency") or "")}
                self._send(200, {"purchases": store.record_purchase(entry)})
            elif path == "/api/bought/undo":
                self._send(200, {"purchases": store.undo_purchase()})
            elif path == "/api/jp_langs":
                try:
                    res = sync.import_jp_langs(str(body.get("text") or ""))
                except RuntimeError as e:
                    self._send(409, {"error": str(e)})
                    return
                self._send(200, dict(res, lang_todo=planner.lang_todo(store.load_data(), store.load_settings())))
            elif path == "/api/eshop_history":
                res = sync.import_eshop_history(str(body.get("text") or ""))
                self._send(200, dict(res, eshop=planner.eshop_matches(store.load_data())["rows"]))
            elif path == "/api/eshop_history/pick":
                store.pick_eshop_history(str(body.get("key") or ""), str(body.get("slug") or ""))
                self._send(200, {"eshop": planner.eshop_matches(store.load_data())["rows"]})
            elif path == "/api/diag":
                # POST (0.99.1): Der Verbindungstest fragt Quellen ab; eine fremde Seite soll ihn
                # nicht über ein Bild auslösen können
                self._send(200, {"lines": sync.diagnose()})
            elif path == "/api/sync":
                self._send(200, {"started": sync.start_sync(by_hand=True)})
            else:
                self._send(404, {"error": "nicht gefunden"})
        except ValueError as e:
            self._send(400, {"error": str(e)})      # Eingabefehler: Text für dich gedacht
        except Exception as e:
            self._fail(path, e)

    def _fail(self, path, e):
        """Unerwarteter Fehler (0.82): Einzelheiten ins Protokoll des Containers, an den Browser
        nur die Art des Fehlers, keine Pfade oder Innereien des Servers."""
        print(f"Fehler bei {path}:", file=sys.stderr)
        traceback.print_exception(e, file=sys.stderr)
        self._send(500, {"error": f"Interner Fehler ({type(e).__name__}), Einzelheiten im Protokoll des Containers"})


def main():
    port = int(os.environ.get("PORT", "8787"))
    if os.environ.get("NO_SCHEDULER") != "1":
        threading.Thread(target=sync.scheduler, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"eShop-Kompass läuft auf Port {port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
