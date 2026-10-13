"""Prüfumgebung: eine Momentaufnahme ohne Netz durchrechnen, Regeln prüfen, Versionen vergleichen.

Eingaben sind die Dateien aus der Oberfläche: "Abgleichsdaten herunterladen" (Pflicht) und
"Sicherung herunterladen" (Einstellungen, Zielpreise, Käufe). Beide bleiben außerhalb des
Repositorys. Das Werkzeug schreibt nur in einen Wegwerf-Ordner und ruft nichts ab.

    python3 -m tools.replay --abgleich A.json --sicherung S.json
    python3 -m tools.replay --abgleich A.json --sicherung S.json --szenario konto=PL --szenario kurs=JPY*1.1
    python3 -m tools.replay --abgleich A.json --sicherung S.json --vergleich main

Ausgabe: Kurzfassung, verletzte Regeln, mit --vergleich die Unterschiede zur anderen Version
(gleiche Daten, gleicher Zeitpunkt). Rückgabewert 1, wenn eine Regel verletzt ist.
"""
import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NSUID = re.compile(r"^70\d{12}$")


def _load_app(code_dir, data_dir):
    """app aus code_dir laden, mit Daten in data_dir (DATA_DIR gilt beim Import)."""
    os.environ["DATA_DIR"] = data_dir
    sys.path.insert(0, code_dir)
    for name in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
        del sys.modules[name]
    mods = {n: importlib.import_module(f"app.{n}") for n in ("store", "planner", "sources")}
    sys.path.remove(code_dir)
    return mods


# ------------------------------------------------------------------ Szenarien

def apply_scenarios(data, settings, scenarios):
    """Kleine Abwandlungen der Momentaufnahme, je "name=wert":
    konto=PL            Kontoland
    guthaben=BR:20      Guthaben in Landeswährung
    kurs=JPY*1.1        Wechselkurs je Euro mal Faktor
    land-aus=JP         Land abschalten (land-an=JP einschalten)
    ohne-preis=SLUG     alle Preise eines Titels entfernen
    angebot-endet=SLUG  Angebote eines Titels enden (Normalpreis gilt)
    """
    for sc in scenarios:
        key, _, val = sc.partition("=")
        if key == "konto":
            settings["current_country"] = val
        elif key == "guthaben":
            code, _, amount = val.partition(":")
            settings["countries"][code]["balance"] = float(amount)
        elif key == "kurs":
            cur, _, factor = val.partition("*")
            data["fx"]["rates"][cur] = data["fx"]["rates"][cur] * float(factor)
        elif key in ("land-aus", "land-an"):
            settings["countries"][val]["enabled"] = key == "land-an"
        elif key == "ohne-preis":
            for shop in (data.get("prices") or {}).values():
                shop.pop(val, None)
        elif key == "angebot-endet":
            for shop in (data.get("prices") or {}).values():
                p = shop.get(val)
                if p and "discount" in p:
                    p.pop("discount")
                    p.pop("sale_end", None)
        else:
            raise SystemExit(f"Unbekanntes Szenario: {sc}")


# ------------------------------------------------------------------ Durchrechnen

def run(code_dir, abgleich, sicherung, scenarios, now):
    """Rechnet alles, was die Oberfläche zeigt, und liefert eine vergleichbare Kurzfassung."""
    tmp = tempfile.mkdtemp(prefix="ek-replay-")
    try:
        m = _load_app(code_dir, tmp)
        store, planner = m["store"], m["planner"]
        data = abgleich["data"]
        if sicherung:
            if isinstance(sicherung.get("settings"), dict):
                store.save_settings(sicherung["settings"])
            if isinstance(sicherung.get("ui"), dict):
                store.save_ui(sicherung["ui"])
            if isinstance(sicherung.get("purchases"), list):
                store.save_purchases(sicherung["purchases"])
        settings = store.load_settings()
        apply_scenarios(data, settings, scenarios)
        store.save_data(data)
        data, ui, bought = store.load_data(), store.load_ui(), store.load_purchases()
        radar = planner.radar(data, settings, ui["targets"], now=now)
        plan = planner.purchase_plan(data, settings, ui["targets"], include_good=ui["plan_good"],
                                     now=now, bought=bought, fill=ui["plan_fill"])
        langs = planner.lang_todo(data, settings, now=now)
        coll = planner.collection(data, settings, rows=radar, now=now)
        return {"version": m["sources"].VERSION, "data": data, "settings": settings,
                "radar": radar, "plan": plan, "langs": langs, "collection": coll}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def summary(r):
    """Was sich zwischen zwei Versionen vergleichen lässt, ohne Laufzeit-Zufall."""
    best = lambda row: (row.get("easy") or row.get("hard") or {})
    return {
        "radar": {row["slug"]: [row["verdict"], best(row).get("code"), best(row).get("eur")]
                  for row in r["radar"]},
        "plan": {"steps": [[p["code"], sorted(i["slug"] for i in p["items"]), p["cost"], p.get("rest")]
                           for p in r["plan"]["steps"]],
                 "cost": r["plan"]["cost"], "saving": r["plan"]["saving"],
                 "held": sorted(h["slug"] for h in r["plan"]["held"]),
                 "later": sorted(x["slug"] for x in r["plan"]["later"]),
                 "nowhere": sorted(r["plan"]["nowhere"])},
        "langs_open": sorted(f'{t["slug"]}|{t["family"]}' for t in r["langs"]
                             if not t.get("manual") and t.get("state") is None),
        "collection": {"missing_eur": r["collection"].get("missing_eur"),
                       "missing_priced": r["collection"].get("missing_priced")},
    }


# ------------------------------------------------------------------ Regeln

def check(r):
    """Regeln, die nie verletzt sein dürfen. Liefert Meldungen, leer heißt alles gut."""
    bad = []
    data, plan = r["data"], r["plan"]
    owned = set(data.get("owned") or [])
    seen = {}
    for p in plan["steps"]:
        for i in p["items"]:
            s = i["slug"]
            if s in seen:
                bad.append(f"Plan: {s} in zwei Schritten ({seen[s]}, {p['code']})")
            seen[s] = p["code"]
            if s in owned:
                bad.append(f"Plan: {s} steht in der Sammlung und trotzdem im Plan")
        if p["cost"] is not None and p["cost"] < 0:
            bad.append(f"Plan: Schritt {p['code']} kostet weniger als 0")
    for key in ("held", "later"):
        for x in plan[key]:
            if x["slug"] in seen:
                bad.append(f"Plan: {x['slug']} steht im Plan und unter {key}")
    for t in r["langs"]:
        n, url, fam = str(t.get("nsuid") or ""), t.get("url") or "", t["family"]
        if n and not NSUID.match(n):
            bad.append(f"Sprachen: {t['slug']} ({fam}) ID {n} hat kein gültiges Format")
        if fam != "EU" and n and not url.startswith("https://"):
            bad.append(f"Sprachen: {t['slug']} ({fam}) ohne Link")
        if fam in ("AM", "AS") and n.startswith("7007") and "/bundles/" not in url:
            bad.append(f"Sprachen: Paket {t['slug']} ({fam}) verlinkt nicht auf bundles")
    for row in r["radar"]:
        if row["verdict"] == "buy" and not (row.get("easy") or row.get("hard")):
            bad.append(f"Radar: {row['slug']} ist Kauf ohne Preis")
    for coll in ("items", "extra", "glangs"):
        for slug, rec in (data.get(coll) or {}).items():
            for fam, ids in ((rec or {}).get("ids") or {}).items():
                for n in ids or []:
                    if not NSUID.match(str(n)):
                        bad.append(f"Daten: {coll}/{slug} ({fam}) ID {n} hat kein gültiges Format")
    return bad


def stats(r):
    """Stand der Daten in Zahlen, als Überblick."""
    data = r["data"]
    out = {"Titel aktiv": sum(1 for it in data["items"].values() if it.get("active")),
           "Sammlung": len(data.get("owned") or []),
           "fehlende DLC": len(data.get("extra") or {}),
           "Plan-Schritte": len(r["plan"]["steps"]), "Plan-Kosten": r["plan"]["cost"],
           "Ersparnis": r["plan"]["saving"]}
    verdicts = {}
    for row in r["radar"]:
        verdicts[row["verdict"]] = verdicts.get(row["verdict"], 0) + 1
    out["Urteile"] = verdicts
    open_ = [t for t in r["langs"] if not t.get("manual") and t.get("state") is None]
    out["Sprachen offen"] = {f: sum(1 for t in open_ if t["family"] == f) for f in sorted({t["family"] for t in open_})}
    marks = {}
    for coll in ("items", "glangs"):
        for rec in (data.get(coll) or {}).values():
            for k in ("ids_suspect", "ids_doubt", "ids_hint"):
                marks[k] = marks.get(k, 0) + len((rec or {}).get(k) or {})
    out["ID-Markierungen"] = marks
    return out


def diff(a, b, path=""):
    """Unterschiede zweier Kurzfassungen als Zeilen."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                out.append(f"+ {path}{k}: {json.dumps(b[k], ensure_ascii=False)}")
            elif k not in b:
                out.append(f"- {path}{k}: {json.dumps(a[k], ensure_ascii=False)}")
            else:
                out += diff(a[k], b[k], f"{path}{k}.")
        return out
    if a != b:
        return [f"~ {path.rstrip('.')}: {json.dumps(a, ensure_ascii=False)} -> {json.dumps(b, ensure_ascii=False)}"]
    return []


def worktree(ref):
    """Den Code einer anderen Version in einen Wegwerf-Ordner holen."""
    d = tempfile.mkdtemp(prefix="ek-ref-")
    subprocess.run(["git", "-C", ROOT, "worktree", "add", "--detach", d, ref],
                   check=True, capture_output=True)
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--abgleich", required=True, help="Datei aus 'Abgleichsdaten herunterladen'")
    ap.add_argument("--sicherung", help="Datei aus 'Sicherung herunterladen'")
    ap.add_argument("--szenario", action="append", default=[], help="Abwandlung, mehrfach möglich")
    ap.add_argument("--vergleich", help="Git-Stand zum Vergleich, etwa main oder v0.44.5")
    ap.add_argument("--jetzt", help="Zeitpunkt ISO, sonst der letzte Abgleich der Daten")
    ap.add_argument("--json", action="store_true", help="Kurzfassung als JSON ausgeben")
    a = ap.parse_args(argv)
    with open(a.abgleich, encoding="utf-8") as f:
        abgleich = json.load(f)
    sicherung = None
    if a.sicherung:
        with open(a.sicherung, encoding="utf-8") as f:
            sicherung = json.load(f)
    stamp = a.jetzt or abgleich["data"].get("last_sync")
    now = datetime.fromisoformat(stamp) if stamp else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    def fresh():
        return json.loads(json.dumps(abgleich)), json.loads(json.dumps(sicherung)) if sicherung else None
    ab, si = fresh()
    cur = run(ROOT, ab, si, a.szenario, now)
    problems = check(cur)
    if a.json:
        print(json.dumps({"version": cur["version"], "stats": stats(cur), "summary": summary(cur),
                          "problems": problems}, ensure_ascii=False, indent=1))
    else:
        print(f"Version {cur['version']}, Zeitpunkt {stamp or 'jetzt'}"
              + (f", Szenarien: {', '.join(a.szenario)}" if a.szenario else ""))
        for k, v in stats(cur).items():
            print(f"  {k}: {v}")
        print(f"Regeln: {'alle eingehalten' if not problems else f'{len(problems)} verletzt'}")
        for p in problems:
            print(f"  ! {p}")
    if a.vergleich:
        d = worktree(a.vergleich)
        try:
            ab, si = fresh()
            other = run(d, ab, si, a.szenario, now)
        finally:
            subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", d], capture_output=True)
        lines = diff(summary(other), summary(cur))
        print(f"Vergleich {other['version']} ({a.vergleich}) -> {cur['version']}: "
              f"{len(lines) or 'keine'} Unterschiede")
        for line in lines:
            print(f"  {line}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
