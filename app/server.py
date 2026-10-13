"""Kleiner Webserver: liefert die Oberfläche und eine JSON-Schnittstelle."""
import json
import re
import os
import threading
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
    settings = store.load_settings()
    data = store.load_data()
    ui = store.load_ui()
    radar = planner.radar(data, settings, ui["targets"])
    return {
        "settings": settings,
        "ui": ui,
        "radar": radar,
        "collection": planner.collection(data, settings, rows=radar),
        "s2": planner.switch2_paths(data, radar, settings),
        "bundles": planner.bundles(data, radar, settings),
        "levels": planner.price_levels(data, settings),
        "pay": planner.pay_info(data, settings),
        "card_status": planner.card_status(data, settings),
        "owned_count": len(data.get("owned") or []),
        "countries": [dict(countries.BY_CODE[c], family_name=countries.FAMILIES[
            countries.BY_CODE[c]["family"]]) for c in countries.ORDER],
        "status": sync.status,
        "version": sources.VERSION,
        "last_sync": data.get("last_sync"),
        "checks": data.get("checks"),
        "fx_updated": data["fx"].get("updated"),
        "item_count": sum(1 for it in data["items"].values() if it.get("active")),
        "matrix": planner.matrix(data, settings),
        "lang_todo": planner.lang_todo(data, settings),
        "eshop": planner.eshop_matches(data)["rows"],
        "eshop_seit": (data.get("_eshop") or {}).get("seit") or 0,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "eshop-kompass"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        # Nur JSON annehmen: Ein einfaches Formular einer fremden Seite im
        # Browser kann so keine Einstellungen ändern oder Abgleiche starten.
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise ValueError("nur application/json")
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            raise ValueError("zu groß")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/index.html"):
                with open(os.path.join(STATIC, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._send(200, state())
            elif path == "/api/status":
                self._send(200, dict(sync.status, last_sync=store.load_data().get("last_sync")))
            elif path == "/api/kaufplan":
                ui = store.load_ui()
                out = planner.purchase_plan(store.load_data(), store.load_settings(), ui["targets"],
                                            include_good=ui["plan_good"],
                                            bought=store.load_purchases(), fill=ui["plan_fill"])
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
            elif path == "/api/diag":
                self._send(200, {"lines": sync.diagnose()})
            elif path == "/api/abgleich":
                # Abgleichsdaten und Protokoll zum Nachprüfen; keine Einstellungen, also auch
                # kein Wishlist- oder Sammlungslink
                self._send(200, {"app": "eshop-kompass", "version": sources.VERSION,
                                 "data": store.load_data(),
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
            self._send(500, {"error": str(e)})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            body = self._body()
            if path == "/api/plans":
                res, split = planner.plans(store.load_data(), store.load_settings(),
                                           overrides=body.get("overrides") or {},
                                           must=body.get("must") or [],
                                           basket=body.get("basket") or [], with_mix=True)
                self._send(200, {"plans": res, "mix": split})
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
                    for k, v in (eh.get("picks") or {}).items():
                        store.pick_eshop_history(str(k), str(v or ""))
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
            elif path == "/api/sync":
                self._send(200, {"started": sync.start_sync()})
            else:
                self._send(404, {"error": "nicht gefunden"})
        except Exception as e:
            self._send(400, {"error": str(e)})


def main():
    port = int(os.environ.get("PORT", "8787"))
    if os.environ.get("NO_SCHEDULER") != "1":
        threading.Thread(target=sync.scheduler, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"eShop-Kompass läuft auf Port {port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
