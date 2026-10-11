"""Länderstammdaten.

family: Titel-IDs sind je Region verschieden. EU = Nintendo of Europe
(inkl. Südafrika, Australien, Neuseeland), AM = Amerika, JP = Japan.
pay:    Voreinstellung fürs Bezahlen ("card", "giftcard", "off").
rest_blocks: Restguthaben verhindert den Länderwechsel (Amerika: Guthaben
        muss 0 sein). In Europa verfällt der Rest nur.
"""

FAMILIES = {"EU": "Europa", "AM": "Amerika", "JP": "Japan"}

# Über welche DekuDeals-Länderansicht die IDs einer Region gesucht werden.
FAMILY_LOOKUP = {"EU": ["de", "gb", "au"], "AM": ["us", "br", "mx"], "JP": ["jp"]}

REFERENCE = "DE"

COUNTRIES = [
    # code, name, family, pay, rest_blocks, enabled, lang, note
    ("DE", "Deutschland", "EU", "card", False, True, "de", "Vergleichsbasis"),
    ("PL", "Polen", "EU", "card", False, True, "en", ""),
    ("NO", "Norwegen", "EU", "card", False, True, "en", ""),
    ("DK", "Dänemark", "EU", "card", False, True, "en", ""),
    ("SE", "Schweden", "EU", "card", False, False, "en", ""),
    ("CZ", "Tschechien", "EU", "card", False, False, "en", ""),
    ("GB", "Großbritannien", "EU", "card", False, False, "en", ""),
    ("CH", "Schweiz", "EU", "card", False, False, "de", ""),
    ("ZA", "Südafrika", "EU", "card", False, True, "en",
     "Kartenzahlung unsicher"),
    ("NZ", "Neuseeland", "EU", "giftcard", False, True, "en",
     "Kartenzahlung ungeklärt"),
    ("AU", "Australien", "EU", "giftcard", False, False, "en", ""),
    ("JP", "Japan", "JP", "giftcard", True, True, "ja",
     "keine ausländischen Karten"),
    ("US", "USA", "AM", "giftcard", True, True, "en", ""),
    ("CA", "Kanada", "AM", "giftcard", True, True, "en", ""),
    ("BR", "Brasilien", "AM", "giftcard", True, True, "pt", ""),
    ("MX", "Mexiko", "AM", "giftcard", True, True, "es", ""),
    ("CL", "Chile", "AM", "giftcard", True, False, "es", ""),
    ("CO", "Kolumbien", "AM", "giftcard", True, False, "es", ""),
    ("PE", "Peru", "AM", "giftcard", True, False, "es", ""),
    ("AR", "Argentinien", "AM", "giftcard", True, False, "es", ""),
]

BY_CODE = {
    c[0]: {
        "code": c[0], "name": c[1], "family": c[2], "pay": c[3],
        "rest_blocks": c[4], "enabled": c[5], "lang": c[6], "note": c[7],
    }
    for c in COUNTRIES
}
ORDER = [c[0] for c in COUNTRIES]


def default_country_settings():
    return {
        code: {
            "enabled": c["enabled"],
            "pay": c["pay"],
            "rest_blocks": c["rest_blocks"],
            "balance": 0.0,
            "cards": "",
        }
        for code, c in BY_CODE.items()
    }
