"""Guthabenkarten: günstigste Kartenkombination (CardSolver), Kartenliste lesen, Faktor einer Karte.

Beträge in Landeswährung werden als ganze Hundertstel gerechnet (cents).
"""
import math
import re
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from .sources import parse_amount


MAX_STATES = 3_000_000

# Faktor einer Guthabenkarte = Preis in Euro ÷ Wert zum Mittelkurs (0.53). Reines Guthabenland:
# gemessen am besten Faktor der Karte in CARD_HIST_DAYS Tagen, aussagekräftig ab CARD_HIST_MIN_DAYS
CARD_HIST_DAYS = 90
CARD_HIST_MIN_DAYS = 14
CARD_STEPS = ((1.005, "top", "Top"), (1.02, "good", "gut"), (1.05, "ok", "okay"))


def _fac(f):
    # Wie die Oberfläche: erst auf 4 Stellen (so kommt der Faktor dort an), dann kaufmännisch
    # auf 2, damit Spalte und Bewertungstext dieselbe Zahl zeigen
    return str(Decimal(str(round(f, 4))).quantize(Decimal("0.01"), ROUND_HALF_UP)).replace(".", ",")


def card_hist_window(hist, now):
    """Faktoren einer Karte aus den letzten CARD_HIST_DAYS Tagen: {Datum: Faktor}."""
    since = (now - timedelta(days=CARD_HIST_DAYS)).date().isoformat()
    return {d: f for d, f in hist.items() if d >= since}

# Gelesene Kartenpreise (Shopseite) zählen nur in diesem Bereich, gemessen am
# Nennwert zum Mittelkurs. Ein Lesefehler (etwa ein Gebührenhinweis statt des Preises)
# würde sonst als „günstiger“ alle Vergleiche kippen. Kleine Karten mit Servicegebühr
# liegen bei rund 135 %, deutsche Karten unter Nennwert bei rund 90 %.
CARD_PLAUSIBLE = (0.70, 1.60)


def cents(value):
    return int(round(float(value) * 100))


_OUT_RE = re.compile(r"^\s*(?:[x#!\-]\s+|\(aus\)\s*)", re.I)


def plausible_card(cost_eur, face, rate):
    """Liegt ein gelesener Kartenpreis in Euro im glaubhaften Bereich? face in Hundertstel."""
    if not rate or not face or cost_eur is None:
        return False
    ratio = cost_eur / (face / 100 / rate)
    return CARD_PLAUSIBLE[0] <= ratio <= CARD_PLAUSIBLE[1]


def parse_card_list(text):
    """Kartenliste eines Landes.

    Eine Karte je Zeile: "100 = 16,00 | https://…". Preis und Link sind
    freiwillig, ein vorangestelltes "x " heißt nicht vorrätig. Das alte
    Kurzformat "1000 3000 5000=29,50" wird weiter verstanden.
    """
    cards = {}
    for line in re.split(r"[\n;]+", text or ""):
        line = line.strip()
        if not line:
            continue
        stock = True
        m = _OUT_RE.match(line)
        if m:
            stock, line = False, line[m.end():]
        line = re.sub(r"\s*=\s*", "=", line)
        entries = [line] if ("|" in line or "http" in line.lower()) else line.split()
        for entry in entries:
            url = ""
            mu = re.search(r"https?://\S+", entry)
            if mu:
                url, entry = mu.group(0), entry[:mu.start()]
            head = entry.split("|")[0]
            face_txt, _, cost_txt = head.partition("=")
            if re.match(r"\s*-", face_txt):
                continue
            face = parse_amount(face_txt)
            cost = parse_amount(cost_txt) if cost_txt.strip() else None
            if not face or face <= 0 or (cost is not None and cost <= 0):
                continue
            cards[cents(face)] = {"face": cents(face), "cost": cost, "url": url, "stock": stock}
    return [cards[k] for k in sorted(cards)]


def parse_cards(text):
    """Vorrätige Karten als (Wert in Hundertstel, Preis in Euro oder None)."""
    return [(c["face"], c["cost"]) for c in parse_card_list(text) if c["stock"]]


class CardSolver:
    """Günstigste Kartenkombination, die einen Betrag mindestens deckt."""

    def __init__(self, cards, rate, markup_pct):
        self.cards = [(f, c if c is not None else f / 100 / rate * (1 + markup_pct / 100))
                      for f, c in cards]
        self.g = 0
        for f, _ in self.cards:
            self.g = math.gcd(self.g, f)
        self.n = 0
        self.best, self.pick, self.cover = [0.0], [0], [0]

    def _build(self, limit):
        g = self.g
        maxface = max(f for f, _ in self.cards)
        n = (limit + maxface) // g + 1
        if n > MAX_STATES:
            raise ValueError("Kartenwerte zu kleinteilig für diesen Betrag")
        units = [(f // g, c) for f, c in self.cards]
        inf = float("inf")
        best = [inf] * (n + 1)
        pick = [0] * (n + 1)
        count = [0] * (n + 1)
        best[0] = 0.0
        for s in range(1, n + 1):
            b, p, k = inf, 0, 0
            for u, c in units:
                if s < u:
                    continue
                cost, cards = best[s - u] + c, count[s - u] + 1
                # bei gleichen Kosten (Karten zum Kurs) gewinnen weniger Karten
                if cost < b - 1e-9 or (cost < b + 1e-9 and cards < k):
                    b, p, k = cost, u, cards
            best[s], pick[s], count[s] = b, p, k
        # cover[s]: günstigste erreichbare Summe >= s (bei Gleichstand die kleinere)
        cover = [0] * (n + 2)
        cover[n + 1] = -1
        for s in range(n, -1, -1):
            nxt = cover[s + 1]
            if best[s] < inf and (nxt < 0 or best[s] <= best[nxt] + 1e-9):
                cover[s] = s
            else:
                cover[s] = nxt
        self.n, self.best, self.pick, self.cover = n, best, pick, cover

    def solve(self, need):
        """need in Hundertstel -> Kosten in Euro, Karten, Rest."""
        if need <= 0:
            return {"cost": 0.0, "cards": [], "rest": 0}
        s0 = -(-need // self.g)
        if s0 > self.n - max(f for f, _ in self.cards) // self.g:
            self._build(need * 2)
        s = self.cover[s0]
        counts, cur = {}, s
        while cur > 0:
            u = self.pick[cur]
            counts[u * self.g] = counts.get(u * self.g, 0) + 1
            cur -= u
        return {"cost": self.best[s],
                "cards": sorted(counts.items(), reverse=True),
                "rest": s * self.g - need}
