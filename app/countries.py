"""Länderstammdaten.

family: Titel-IDs sind je Region verschieden. EU = Nintendo of Europe
        (inkl. Südafrika, Australien, Neuseeland), AM = Amerika, JP = Japan,
        AS = Südostasien.
pay:    Voreinstellung fürs Bezahlen ("card", "giftcard", "auto").
tier:   Wie mühsam der Länderwechsel ist. 1 = leicht (Karte, kein Rest),
        2 = mittel (Guthabenkarten, Rest verfällt), 3 = schwer (Amerika:
        Guthaben muss 0 sein).
tax:    Aufschlag in Prozent, wo der Shop Preise ohne Steuer zeigt.
rest_blocks: Restguthaben verhindert den Länderwechsel.

Länder der Eurozone fehlen bewusst: Dort gelten in aller Regel dieselben
Europreise wie in Deutschland.
"""

FAMILIES = {"EU": "Europa", "AM": "Amerika", "JP": "Japan", "AS": "Asien"}

# Über welche DekuDeals-Länderansicht die IDs einer Region gesucht werden.
FAMILY_LOOKUP = {"EU": ["de", "gb", "au"], "AM": ["us", "br", "mx"], "JP": ["jp"],
                 "AS": ["sg", "my", "th"]}

TIERS = {1: "leicht", 2: "mittel", 3: "schwer"}

REFERENCE = "DE"

COUNTRIES = [
    # code, name, family, pay, tier, tax, rest_blocks, enabled, lang, note
    ("DE", "Deutschland", "EU", "card", 1, 0, False, True, "de", "Vergleichsbasis"),
    ("PL", "Polen", "EU", "card", 1, 0, False, True, "en", ""),
    ("NO", "Norwegen", "EU", "card", 1, 0, False, True, "en", ""),
    ("DK", "Dänemark", "EU", "card", 1, 0, False, True, "en", ""),
    ("SE", "Schweden", "EU", "card", 1, 0, False, False, "en", ""),
    ("CZ", "Tschechien", "EU", "card", 1, 0, False, False, "en", ""),
    ("GB", "Großbritannien", "EU", "card", 1, 0, False, False, "en", ""),
    ("CH", "Schweiz", "EU", "card", 1, 0, False, False, "de", ""),
    ("ZA", "Südafrika", "EU", "card", 1, 0, False, True, "en", "Kartenzahlung unsicher"),
    ("NZ", "Neuseeland", "EU", "giftcard", 2, 0, False, True, "en", "Kartenzahlung ungeklärt"),
    ("AU", "Australien", "EU", "giftcard", 2, 0, False, False, "en", ""),
    ("JP", "Japan", "JP", "giftcard", 2, 0, True, True, "ja", "keine ausländischen Karten"),
    ("SG", "Singapur", "AS", "giftcard", 2, 0, False, False, "en", ""),
    ("MY", "Malaysia", "AS", "giftcard", 2, 0, False, False, "en", ""),
    ("TH", "Thailand", "AS", "giftcard", 2, 0, False, False, "en", ""),
    ("US", "USA", "AM", "giftcard", 3, 8, True, True, "en", ""),
    ("CA", "Kanada", "AM", "giftcard", 3, 13, True, True, "en", ""),
    ("BR", "Brasilien", "AM", "giftcard", 3, 0, True, True, "pt", ""),
    ("MX", "Mexiko", "AM", "giftcard", 3, 0, True, True, "es", ""),
    ("CL", "Chile", "AM", "giftcard", 3, 0, True, False, "es", ""),
    ("CO", "Kolumbien", "AM", "giftcard", 3, 0, True, False, "es", ""),
    ("PE", "Peru", "AM", "giftcard", 3, 0, True, False, "es", ""),
    ("AR", "Argentinien", "AM", "giftcard", 3, 0, True, False, "es", ""),
]

BY_CODE = {
    c[0]: {
        "code": c[0], "name": c[1], "family": c[2], "pay": c[3], "tier": c[4],
        "tax_pct": c[5], "rest_blocks": c[6], "enabled": c[7], "lang": c[8], "note": c[9],
    }
    for c in COUNTRIES
}
ORDER = [c[0] for c in COUNTRIES]


def default_country_settings():
    return {
        code: {
            "enabled": c["enabled"],
            "pay": c["pay"],
            "tier": c["tier"],
            "tax_pct": c["tax_pct"],
            "rest_blocks": c["rest_blocks"],
            "balance": 0.0,
            "cards": "",
            "cards_checked": "",
        }
        for code, c in BY_CODE.items()
    }
