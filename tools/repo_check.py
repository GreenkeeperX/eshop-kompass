"""Prüft, ob im Repository nur hingehört, was hingehört (1.7.32).

Das Repository ist öffentlich. Diese Prüfung läuft in den Tests (tests.test_all, wenn ein Git-Stand
da ist) und in den Workflows. Sie liest die eingecheckten Dateien (`git ls-files`) und meldet:
- Dateien im Wurzelverzeichnis, die nicht in ROOT_ALLOWED stehen,
- Bilder außerhalb von docs/bilder/ (ausgenommen die drei ausdrücklich erlaubten im Wurzelverzeichnis),
- Arbeitsdateien und Protokolle (Momentaufnahmen, Sicherungen, Dateien aus dem Datenordner, .log,
  .har, Reste wie .tmp oder .kaputt-…),
- Wishlist- und Sammlungs-Kennungen und Adressen aus dem Heimnetz im Text.

Namen von Personen findet sie nicht sicher; dafür bleibt das Lesen des eigenen Diffs (CLAUDE.md).

Aufruf: python3 -m tools.repo_check  (Exit 1 bei einem Fund)
Mit --staged prüft sie zusätzlich, was für den nächsten Commit vorgemerkt ist.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")

# Was im Wurzelverzeichnis liegen darf. Neue Dateien dort bewusst hier eintragen
ROOT_ALLOWED = {
    ".dockerignore", ".gitignore", "CLAUDE.md", "Dockerfile", "README.md", "ROADMAP.md",
    "docker-compose.yml",
    # Bildschirmfotos aus früheren Versionen, ausdrücklich erlaubt (Entscheidung 24.11.2026)
    "b-d.png", "b-m.png", "w-m.png",
}
# Ordner im Wurzelverzeichnis
DIRS_ALLOWED = {".github", "app", "docs", "tests", "tools"}

IMAGE = re.compile(r"\.(png|jpe?g|gif|webp|bmp|avif|heic)$", re.I)
IMAGE_DIR = "docs/bilder/"

# Arbeitsdateien, Protokolle und Dateien aus dem Datenordner (store.py), egal wo
FORBIDDEN = [
    (re.compile(r"(^|/)data/"), "Datenordner"),
    (re.compile(r"abgleich[^/]*\.json$|sicherung[^/]*\.json$", re.I), "Momentaufnahme oder Sicherung"),
    (re.compile(r"(^|/)(settings|ui|history|purchases|keys|eshop_history|data)\.json$"),
     "Datei aus dem Datenordner"),
    (re.compile(r"\.(log|har|tmp|bak|orig|rej|swp|sqlite3?|db)$|\.kaputt-|~$", re.I),
     "Arbeitsdatei oder Protokoll"),
    (re.compile(r"(^|/)(graphify-out|__pycache__|\.claude)/"), "lokaler Ordner"),
    (re.compile(r"\.(csv|zip|tar|gz|7z)$", re.I), "Export oder Archiv"),
]

# Inhalte, die nie ins Repository gehören (CLAUDE.md). Beispiel-Kennungen der Tests stehen in
# PLACEHOLDERS; 10.x-Adressen bleiben erlaubt, die Tests brauchen sie für die Prüfung privater Ziele
PLACEHOLDERS = {"abc123xyz", "geheim", "geheim1"}
CONTENT = [
    (re.compile(r"(?:wishlist|collection)/([A-Za-z0-9]{6,})"), "Wishlist- oder Sammlungs-Kennung"),
    (re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b"), "Adresse im Heimnetz"),
]
TEXT = re.compile(r"\.(py|js|html|css|md|yml|yaml|json|txt|toml|cfg|ini)$|(^|/)(Dockerfile|\.gitignore|\.dockerignore)$")
# Diese Datei beschreibt die Muster selbst
CONTENT_SKIP = {"tools/repo_check.py"}


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def check_paths(paths):
    """Fehler für eine Liste von Pfaden (relativ zum Repository, mit /)."""
    out = []
    for p in paths:
        top, sep, _ = p.partition("/")
        if not sep and p not in ROOT_ALLOWED:
            out.append(f"{p}: unbekannte Datei im Wurzelverzeichnis (erlaubt sind {', '.join(sorted(ROOT_ALLOWED))})")
        elif sep and top not in DIRS_ALLOWED:
            out.append(f"{p}: unbekannter Ordner {top}/ im Wurzelverzeichnis")
        if IMAGE.search(p) and sep and not p.startswith(IMAGE_DIR):
            out.append(f"{p}: Bilder nur in {IMAGE_DIR}")
        for rx, why in FORBIDDEN:
            if rx.search(p):
                out.append(f"{p}: {why} gehört nicht ins Repository")
                break
    return out


def check_text(path, text):
    if path in CONTENT_SKIP:
        return []
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for rx, why in CONTENT:
            for m in rx.finditer(line):
                if not (m.groups() and m.group(1) in PLACEHOLDERS):
                    out.append(f"{path}:{n}: {why}")
                    break
    return out


def run(staged=False):
    paths = [p for p in _git("ls-files", "-z").split("\0") if p]
    if staged:
        paths = sorted(set(paths) | {p for p in _git("diff", "--cached", "--name-only", "-z").split("\0") if p})
    problems = check_paths(paths)
    for p in paths:
        full = os.path.join(ROOT, p)
        if TEXT.search(p) and os.path.isfile(full):
            with open(full, encoding="utf-8", errors="replace") as f:
                problems += check_text(p, f.read())
    return problems


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    problems = run(staged="--staged" in argv)
    for p in problems:
        print(p)
    if problems:
        print(f"{len(problems)} Fund(e). Was absichtlich dazukommt, in tools/repo_check.py eintragen.")
        return 1
    print("Repository sauber")
    return 0


if __name__ == "__main__":
    sys.exit(main())
