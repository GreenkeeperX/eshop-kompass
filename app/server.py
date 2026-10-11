"""Kleiner Webserver: liefert die Oberfläche und eine JSON-Schnittstelle."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import countries, planner, sources, store, sync

STATIC = os.path.join(os.path.dirname(__file__), "static")


def state():
    settings = store.load_settings()
    data = store.load_data()
    ui = store.load_ui()
    return {
        "settings": settings,
        "ui": ui,
        "radar": planner.radar(data, settings, ui["targets"]),
        "levels": planner.price_levels(data, settings),
        "countries": [dict(countries.BY_CODE[c], family_name=countries.FAMILIES[
            countries.BY_CODE[c]["family"]]) for c in countries.ORDER],
        "status": sync.status,
        "version": sources.VERSION,
        "last_sync": data.get("last_sync"),
        "fx_updated": data["fx"].get("updated"),
        "item_count": sum(1 for it in data["items"].values() if it.get("active")),
        "matrix": planner.matrix(data, settings),
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
            elif path == "/api/diag":
                self._send(200, {"lines": sync.diagnose()})
            elif path == "/api/export":
                self._send(200, {"app": "eshop-kompass", "version": sources.VERSION,
                                 "settings": store.load_settings(), "ui": store.load_ui()})
            else:
                self._send(404, {"error": "nicht gefunden"})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            body = self._body()
            if path == "/api/plans":
                res = planner.plans(store.load_data(), store.load_settings(),
                                    overrides=body.get("overrides") or {},
                                    must=body.get("must") or [],
                                    basket=body.get("basket") or [])
                self._send(200, {"plans": res})
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
                self._send(200, {"ok": True})
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
