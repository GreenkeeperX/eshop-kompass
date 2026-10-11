import json
import os
import urllib.parse
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

from app import countries, planner, sources, store, sync  # noqa: E402

NOW = datetime(2026, 10, 11, 17, 0, tzinfo=timezone.utc)

# Echte Antwort der Nintendo-Preisabfrage (Brasilien, 11.10.2026)
BR_JSON = ('{"personalized":false,"country":"BR","prices":[{"title_id":70010000000141,'
           '"sales_status":"onsale","regular_price":{"amount":"R$ 279,90","currency":"BRL",'
           '"raw_value":"279.9"}},{"title_id":70050000042414,"sales_status":"onsale",'
           '"regular_price":{"amount":"R$ 5,00","currency":"BRL","raw_value":"5"},'
           '"discount_price":{"amount":"R$ 4,00","currency":"BRL","raw_value":"4",'
           '"start_datetime":"2026-10-10T16:00:00Z","end_datetime":"2026-11-01T06:59:59Z"}},'
           '{"title_id":70010000000126,"sales_status":"not_found"}]}')

ITEM_US = '''<html><head><title>Vampire Survivors: Tides of the Foscari | Deku Deals</title></head>
<body><h4>DLC for <a href="/items/vampire-survivors">Vampire Survivors</a></h4>
<a href="https://www.nintendo.com/us/store/products/vampire-survivors-tides-of-the-foscari-70050000042414-switch/">Nintendo eShop</a>
<a href="https://www.amazon.com/dp/B0HJBF5DGP?tag=x">Amazon</a>
<a href="/items/vampire-survivors-emergency-meeting">also liked</a></body></html>'''
ITEM_DE = '''<title>Tides &amp; Foscari | Deku Deals</title>
<a href="https://www.nintendo.com/en-gb/Games/Game-2426823.html?nsuid=70050000042405">eShop</a>
<h3>Price history</h3><table><tr><th>All time low</th></tr><tr><td>€1,49</td><td>(-25%)</td></tr></table>'''
ITEM_BR = '''<title>x | Deku Deals</title><table><tr><td><strong>All time low</strong></td><td></td></tr>
<tr><td>R$&nbsp;3,50</td><td>(-30%)</td></tr></table>'''
ITEM_JP = '<title>Hades | Deku Deals</title><a href="https://ec.nintendo.com/JP/ja/titles/70010000033130">x</a>'


class SourcesTest(unittest.TestCase):
    def test_item_pages(self):
        us = sources.parse_item_page(ITEM_US)
        self.assertEqual(us["title"], "Vampire Survivors: Tides of the Foscari")
        self.assertEqual(us["parent"], "vampire-survivors")
        self.assertEqual(us["parent_title"], "Vampire Survivors")
        self.assertEqual(us["nsuids"], ["70050000042414"])
        self.assertEqual(sources.parse_item_page(ITEM_DE)["nsuids"], ["70050000042405"])
        self.assertEqual(sources.parse_item_page(ITEM_DE)["title"], "Tides & Foscari")
        self.assertEqual(sources.parse_item_page(ITEM_JP)["nsuids"], ["70010000033130"])
        self.assertIsNone(sources.parse_item_page(ITEM_JP)["parent"])

    def test_amounts_and_all_time_low(self):
        for text, want in [("62,00 kr (-75%)", 62.0), ("$1.49 (-25%)", 1.49), ("¥1,400", 1400.0),
                           ("1.299,00 zł", 1299.0), ("1,299.00", 1299.0), ("R$ 4,00", 4.0),
                           ("CLP$ 5.990", 5990.0), ("1 049,00 kr", 1049.0), ("$5", 5.0),
                           ("62,00 75", 62.0), ("kein Preis", None)]:
            self.assertEqual(sources.parse_amount(text), want, text)
        self.assertEqual(sources.parse_item_page(ITEM_DE)["low"], 1.49)
        self.assertEqual(sources.parse_item_page(ITEM_BR)["low"], 3.5)
        self.assertIsNone(sources.parse_item_page(ITEM_US)["low"])

    def test_wishlist_paging(self):
        pages = {1: '<a href="/items/a-game"><img></a><a href="/items/a-game">A</a>'
                    '<a href="/items/b-game">B</a>',
                 2: '<a href="https://www.dekudeals.com/items/c-game?x=1">C</a>',
                 3: '<p>leer</p>'}
        calls = []

        def fake(url, ua=None):
            calls.append(url)
            return pages[int(url.rsplit("=", 1)[1])]
        slugs = sources.fetch_wishlist("https://www.dekudeals.com/wishlist/abc123xyz", fetch=fake)
        self.assertEqual(slugs, ["a-game", "b-game", "c-game"])
        self.assertEqual(len(calls), 3)
        self.assertIn("/wishlist/abc123xyz?page=1", calls[0])

    def test_wishlist_links(self):
        page = ("<a class='x' href='/items/one-game'>x</a> <a href=/items/two-game>y</a>"
                '<a href="https://www.dekudeals.com/items/four-game?x=1">z</a>'
                '<a href="/items/one-game#prices">nochmal</a>'
                '<form action="/items/98765/wishlist"></form>'          # kein Verweis
                '<a href="/items/98765/add_to_wishlist">+</a>'          # Unterpfad
                '<div data-path="/items/data-only"></div>'
                '<a href="/collections/items/not-this">n</a>')
        self.assertEqual(sources.parse_wishlist_page(page), ["one-game", "two-game", "four-game"])
        # Seite ohne erkennbare Verweise: lockere Suche als Ersatz
        self.assertEqual(sources.parse_wishlist_page('<div data-url="https:\\/\\/www.dekudeals.com\\/items\\/three-game"></div>'),
                         ["three-game"])
        item = ("<title>Spiel | Deku Deals</title><h4>DLC for <a class=x href='/items/base-game'>"
                "Base Game</a></h4><a href='https://ec.nintendo.com/JP/ja/titles/70010000033130'>e</a>")
        info = sources.parse_item_page(item)
        self.assertEqual((info["parent"], info["parent_title"], info["nsuids"]),
                         ("base-game", "Base Game", ["70010000033130"]))

    def test_low_prefers_digital(self):
        both = ("<h3>Price history</h3><table><tr><td>All time low</td></tr>"
                "<tr><td>Physical</td><td>€27,19</td><td>(-55%)</td></tr>"
                "<tr><td>Digital</td><td>€39,99</td><td>(-33%)</td></tr></table>"
                "<div>Time range 6m 1y 2y All</div><div>Format All Digital Physical</div>")
        self.assertEqual(sources.parse_low(both), 39.99)
        us = "All time low Digital: $6.24 (-75%) Physical: $17.49 (-50%) Time range"
        self.assertEqual(sources.parse_low(us), 6.24)
        self.assertIsNone(sources.parse_low("All time low <b>Physical</b> €27,19 (-55%) Time range"))
        self.assertEqual(sources.parse_low("All time low | ¥700 | (-75%) Time range 6m"), 700.0)
        self.assertIsNone(sources.parse_low("<p>nichts</p>"))

    def test_alias_merge(self):
        data = {"items": {
            "hades": {"title": "Hades", "active": True, "order": 0, "ids": {"EU": ["1"], "AM": ["2"]}},
            "12345": {"title": "Hades", "active": True, "order": 1, "ids": {"AM": ["2"], "EU": ["1"]}},
            "other": {"title": "Other", "active": True, "order": 2, "ids": {"EU": ["3"]}},
            "no-id-a": {"title": "A", "active": True, "order": 3, "ids": {"EU": []}},
            "no-id-b": {"title": "B", "active": True, "order": 4, "ids": {}},
        }}
        self.assertEqual(sync.merge_aliases(data), 1)
        self.assertFalse(data["items"]["12345"]["active"])
        self.assertEqual(data["items"]["12345"]["alias_of"], "hades")
        self.assertTrue(all(data["items"][s]["active"] for s in ("hades", "other", "no-id-a", "no-id-b")))

    def test_user_agent_fallback_and_diagnosis(self):
        sources._deku_ua = None
        seen = []

        def fake(url, ua=None):
            seen.append(ua)
            if ua.startswith("eshop-kompass"):
                return "<title>Prüfung läuft</title><p>Bitte warten</p>"
            return '<a href="/items/a-game">A</a>' if "page=1" in url else ""
        self.assertEqual(sources.fetch_wishlist("abc123", fetch=fake), ["a-game"])
        self.assertEqual(len(seen), 3)                      # Seite 1 zweimal, Seite 2 einmal
        self.assertTrue(seen[2].startswith("Mozilla"))      # funktionierende Kennung gemerkt

        sources._deku_ua = None
        with self.assertRaises(sources.FetchError):
            sources.fetch_wishlist("abc123", fetch=lambda url, ua=None: "<title>Sperre</title>x")
        self.assertEqual(len(sources.attempts), 2)
        self.assertIn("Titel „Sperre“", sources.attempts[0])
        self.assertIn("0 Titel-Links", sources.attempts[0])

    def test_wishlist_ends_on_missing_page(self):
        def fake(url, ua=None):
            if "page=1" in url:
                return '<a href="/items/a-game">A</a>'
            raise sources.FetchError(url, 404)
        self.assertEqual(sources.fetch_wishlist("abc123", fetch=fake), ["a-game"])

        def down(url, ua=None):
            raise sources.FetchError(url, 0, "timeout")
        with self.assertRaises(sources.FetchError):
            sources.fetch_wishlist("abc123", fetch=down)

    def test_prices(self):
        res = sources.parse_prices(json.loads(BR_JSON))
        self.assertEqual(res["70010000000141"]["regular"], 279.9)
        self.assertEqual(res["70050000042414"]["discount"], 4.0)
        self.assertEqual(res["70010000000126"]["status"], "not_found")

    def test_price_batches_and_lang_fallback(self):
        calls = []

        def fake(url, ua=None):
            calls.append(url)
            if "lang=en" in url:
                raise sources.FetchError(url, 400)
            return '{"prices":[]}'
        sources.fetch_prices("BR", [str(70010000000000 + i) for i in range(120)],
                             lang="en", fetch=fake)
        # 1 Fehlversuch (en), dann 3 Abrufe mit der funktionierenden Sprache
        self.assertEqual(len(calls), 4)
        self.assertTrue(all("lang=es" in u for u in calls[1:]))


class CardsTest(unittest.TestCase):
    def test_card_list_formats(self):
        cards = planner.parse_card_list(
            "100 = 16,00 | https://shop/100\n"
            "x 40 = 8 | https://shop/40\n"
            "1.000 = 46\n"
            "¥5,000=31 https://shop/5000\n"
            "x 60 = 0 | https://shop/60\n"          # ohne Preis und nicht vorrätig: entfällt
            "30=5 50=8")
        self.assertEqual([(c["face"], c["cost"], c["stock"]) for c in cards],
                         [(3000, 5.0, True), (4000, 8.0, False), (5000, 8.0, True),
                          (10000, 16.0, True), (100000, 46.0, True), (500000, 31.0, True)])
        self.assertEqual(cards[3]["url"], "https://shop/100")
        self.assertEqual(cards[5]["url"], "https://shop/5000")
        self.assertEqual(planner.parse_cards("x 40=8\n50=8"), [(5000, 8.0)])

    def test_parse(self):
        self.assertEqual(planner.parse_cards("1000, 3000;5000=29,50\n"),
                         [(100000, None), (300000, None), (500000, 29.5)])
        self.assertEqual(planner.parse_cards("abc 0 -5"), [])

    def brute(self, cards, need):
        best = None
        maxface = max(f for f, _ in cards)

        def rec(i, total, cost):
            nonlocal best
            if total >= need:
                key = (round(cost, 6), total)
                if best is None or key < best:
                    best = key
                return
            if i == len(cards) or total > need + maxface:
                return
            f, c = cards[i]
            k = 0
            while total + k * f < need + f:
                rec(i + 1, total + k * f, cost + k * c)
                k += 1
        rec(0, 0, 0.0)
        return best

    def test_solver_matches_brute_force(self):
        cards = [(1500, 3.1), (2500, 4.9), (5000, 9.6), (10000, 18.5)]
        solver = planner.CardSolver(cards, 5.6, 5)
        for need in [1, 399, 1500, 1501, 2316, 4000, 7499, 12345, 27990, 30001]:
            r = solver.solve(need)
            cost, total = self.brute(cards, need)
            self.assertAlmostEqual(r["cost"], cost, places=5, msg=need)
            self.assertEqual(r["rest"], total - need, msg=need)
            self.assertEqual(sum(f * n for f, n in r["cards"]), total, msg=need)

    def test_estimated_card_price(self):
        solver = planner.CardSolver([(100000, None)], 177.3267, 5)
        r = solver.solve(280000)
        self.assertEqual(r["cards"], [(100000, 3)])
        self.assertAlmostEqual(r["cost"], 3 * 1000 / 177.3267 * 1.05, places=4)
        self.assertEqual(r["rest"], 20000)


def sample():
    settings = store.load_settings()
    for code, c in settings["countries"].items():
        c["enabled"] = code in ("DE", "NO", "BR", "JP")
    settings["countries"]["BR"]["cards"] = "15=3.00 25=4.80 50=9.50"
    items = {}
    for i, (slug, parent) in enumerate([("hades", None), ("spiritfarer", None),
                                        ("vs-foscari", "vampire-survivors"), ("good-job", None),
                                        ("nidhogg-2", None)]):
        items[slug] = {"title": slug.title(), "parent": parent, "active": True, "order": i,
                       "ids": {"EU": ["1"]}, "ids_checked": {}}
    sale = {"start": "2026-10-01T00:00:00Z", "end": "2026-10-20T00:00:00Z"}

    def p(cur, reg, disc=None, status="onsale"):
        d = {"status": status, "currency": cur, "regular": reg}
        if disc is not None:
            d.update(discount=disc, **sale)
        return d
    prices = {
        "DE": {"hades": p("EUR", 24.99), "spiritfarer": p("EUR", 24.99, 6.24),
               "vs-foscari": p("EUR", 1.99), "good-job": p("EUR", 19.99),
               "nidhogg-2": p("EUR", 14.99)},
        "NO": {"hades": p("NOK", 250, 100), "spiritfarer": p("NOK", 249),
               "vs-foscari": p("NOK", 20), "good-job": {"status": "not_found"}},
        "BR": {"hades": p("BRL", 83.99, 33.59), "spiritfarer": p("BRL", 99.0),
               "vs-foscari": p("BRL", 5, 4), "good-job": p("BRL", 59.9),
               "nidhogg-2": p("BRL", 7.5)},
        "JP": {"hades": p("JPY", 2800, 1400)},
    }
    data = {"items": items, "prices": prices, "last_sync": None,
            "fx": {"rates": {"EUR": 1, "NOK": 10.7155, "BRL": 5.6086, "JPY": 177.3267},
                   "updated": "x"}}
    return data, settings


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.data, self.settings = sample()

    def by(self, plans):
        return {p["code"]: p for p in plans}

    def test_card_country(self):
        no = self.by(planner.plans(self.data, self.settings, now=NOW))["NO"]
        self.assertEqual([i["slug"] for i in no["items"]], ["hades"])
        self.assertAlmostEqual(no["cost"], round(100 / 10.7155 * 1.0175, 2))
        self.assertEqual(no["rest"], 0)
        self.assertAlmostEqual(no["saving"], round(24.99 - 100 / 10.7155 * 1.0175, 2))
        self.assertEqual(no["cards"], [])

    def test_giftcard_country_and_filler(self):
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        self.assertEqual([i["slug"] for i in br["items"]], ["hades", "vs-foscari"])
        self.assertAlmostEqual(br["total"], 37.59)
        # 37,59 BRL: 15+25 = 40 für 7,80 € ist günstiger als 50 für 9,50 €
        self.assertEqual(br["cards"], [{"face": 25.0, "count": 1, "url": ""},
                                       {"face": 15.0, "count": 1, "url": ""}])
        self.assertAlmostEqual(br["cost"], 7.80)
        self.assertAlmostEqual(br["rest"], 2.41)
        self.assertAlmostEqual(br["saving"], round(24.99 + 1.99 - 7.80, 2))
        self.assertIn("Rest blockiert", " ".join(br["warnings"]))
        self.assertIn("DLC", " ".join(br["warnings"]))
        # Nidhogg 2 (7,50 BRL) braucht eine Karte mehr, spart aber gegenüber 14,99 € in DE
        first = br["fillers"][0]
        self.assertEqual(first["slugs"], ["nidhogg-2"])
        self.assertAlmostEqual(first["extra"], 9.50 - 7.80)   # 50er statt 15+25
        self.assertAlmostEqual(first["rest"], 50 - 45.09)

    def test_override_and_balance(self):
        self.settings["countries"]["BR"]["balance"] = 2.59
        plans = planner.plans(self.data, self.settings,
                              overrides={"BR": {"remove": ["vs-foscari"], "add": ["nidhogg-2"]}},
                              now=NOW)
        br = self.by(plans)["BR"]
        self.assertEqual([i["slug"] for i in br["items"]], ["hades", "nidhogg-2"])
        # 41,09 BRL minus 2,59 Guthaben = 38,50 -> 15+25, Rest 1,50
        self.assertAlmostEqual(br["rest"], 1.50)
        self.assertAlmostEqual(br["cost"], 7.80)

    def test_missing_cards_and_must(self):
        plans = planner.plans(self.data, self.settings, must=["good-job"], now=NOW)
        by = self.by(plans)
        self.assertTrue(by["JP"]["estimated"])
        self.assertIsNone(by["JP"]["rest"])
        self.assertTrue(by["NO"].get("must_missing"))
        self.assertIn("good-job", [i["slug"] for i in by["BR"]["items"]])
        # Länder ohne den Pflichttitel stehen hinter Brasilien, Deutschland am Ende
        self.assertEqual(plans[0]["code"], "BR")
        self.assertEqual(plans[-1]["code"], "DE")

    def test_reference_and_expired_sale(self):
        de = self.by(planner.plans(self.data, self.settings, now=NOW))["DE"]
        self.assertEqual([i["slug"] for i in de["items"]], ["spiritfarer"])
        self.assertAlmostEqual(de["saving"], 24.99 - 6.24)
        late = datetime(2026, 10, 21, tzinfo=timezone.utc)
        no = self.by(planner.plans(self.data, self.settings, now=late))["NO"]
        self.assertEqual(no["items"], [])

    def test_shared_basket(self):
        basket = ["hades", "good-job", "nidhogg-2"]
        plans = planner.plans(self.data, self.settings, basket=basket, now=NOW)
        by = self.by(plans)
        # Brasilien hat alles, Norwegen und Japan nur Hades
        self.assertEqual([p["code"] for p in plans], ["BR", "JP", "NO", "DE"])
        self.assertEqual([i["slug"] for i in by["BR"]["items"]], basket)
        self.assertEqual(by["BR"]["missing"], [])
        self.assertEqual([m["slug"] for m in by["NO"]["missing"]], ["good-job", "nidhogg-2"])
        self.assertEqual([i["slug"] for i in by["NO"]["items"]], ["hades"])
        # 33,59 + 59,90 + 7,50 = 100,99 BRL -> 50 + 25 + 15 + 15 = 20,30 €
        self.assertAlmostEqual(by["BR"]["cost"], 20.30)
        self.assertAlmostEqual(by["BR"]["rest"], 105 - 100.99)
        self.assertAlmostEqual(by["BR"]["saving"], round(24.99 + 19.99 + 14.99 - 20.3, 2))
        self.assertEqual([i["slug"] for i in by["DE"]["items"]], basket)
        # eigene Länder-Auswahl spielt im gemeinsamen Korb keine Rolle
        again = planner.plans(self.data, self.settings, basket=basket, now=NOW,
                              overrides={"BR": {"remove": ["hades"]}})
        self.assertEqual(self.by(again)["BR"]["cost"], by["BR"]["cost"])

    def test_trim_suggestion(self):
        # Spiritfarer kostet in DE 6,24 €. In Brasilien (99 BRL) löst er zwei
        # 50er-Karten aus: Paket 136,59 BRL = 26,80 € statt 7,80 € ohne ihn.
        plans = planner.plans(self.data, self.settings, now=NOW,
                              overrides={"BR": {"add": ["spiritfarer"]}})
        br = self.by(plans)["BR"]
        self.assertAlmostEqual(br["cost"], 26.80)
        trim = br["trims"][0]
        self.assertEqual(trim["slug"], "spiritfarer")
        self.assertAlmostEqual(trim["marginal"], 26.80 - 7.80)
        self.assertAlmostEqual(trim["gain"], round(26.80 - 7.80 - 6.24, 2))
        self.assertTrue([i for i in br["items"] if i["slug"] == "spiritfarer"][0]["over"])
        self.assertEqual(self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]["trims"], [])

    def test_current_country_needs_no_threshold(self):
        self.settings["tier_min_saving"]["1"] = 50
        self.assertFalse(self.by(planner.plans(self.data, self.settings, now=NOW))["NO"]["worth"])
        self.settings["current_country"] = "NO"
        no = self.by(planner.plans(self.data, self.settings, now=NOW))["NO"]
        self.assertTrue(no["worth"] and no["current"])

    def test_short_dlc_titles(self):
        self.data["items"]["vs-foscari"]["title"] = "Vampire Survivors: Tides of the Foscari"
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        row = [i for i in br["items"] if i["slug"] == "vs-foscari"][0]
        self.assertEqual(row["short"], "Tides of the Foscari")
        self.assertEqual(row["dlc_of"], "Vampire Survivors")
        self.assertEqual(br["items"][0]["short"], "Hades")

    def test_low_marker(self):
        self.data["lows"] = {"BR": {"hades": {"low": 33.59}, "vs-foscari": {"low": 3.0}}}
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        rows = {i["slug"]: i for i in br["items"]}
        self.assertTrue(rows["hades"]["at_low"])
        self.assertEqual(rows["hades"]["low_pct"], 60)
        self.assertFalse(rows["vs-foscari"]["at_low"])
        self.assertEqual(rows["vs-foscari"]["low"], 3.0)
        cell = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertTrue(cell["BR"]["at_low"])
        self.assertIsNone(cell["NO"]["low"])

    def test_cards_with_links_and_stock(self):
        self.settings["countries"]["BR"]["cards"] = (
            "15 = 3,00 | https://shop/15\n25=4.80 https://shop/25\nx 50 = 9,50 | https://shop/50")
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        # die 50er ist nicht vorrätig: 37,59 BRL -> 15 + 25
        self.assertEqual(br["cards"], [{"face": 25.0, "count": 1, "url": "https://shop/25"},
                                       {"face": 15.0, "count": 1, "url": "https://shop/15"}])
        self.assertEqual(br["via"], "giftcard")

    def test_pay_auto_takes_cheaper(self):
        no = self.settings["countries"]["NO"]
        no["pay"] = "auto"
        no["cards"] = "100=8.00 250=24"            # 100 NOK für 8 € statt 9,50 € per Karte
        plan = self.by(planner.plans(self.data, self.settings, now=NOW))["NO"]
        self.assertEqual((plan["via"], plan["cost"], plan["rest"]), ("giftcard", 8.0, 0.0))
        no["cards"] = "100=11.00"                  # teurer als die Kartenzahlung
        plan = self.by(planner.plans(self.data, self.settings, now=NOW))["NO"]
        self.assertEqual(plan["via"], "card")
        self.assertAlmostEqual(plan["cost"], round(100 / 10.7155 * 1.0175, 2))

    def test_tax_is_added(self):
        self.settings["countries"]["BR"]["tax_pct"] = 10
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        hades = [i for i in br["items"] if i["slug"] == "hades"][0]
        self.assertAlmostEqual(hades["local"], 36.95)      # 33,59 + 10 %
        self.assertEqual(hades["pct"], 60)
        self.assertAlmostEqual(br["total"], 36.95 + 4.40)
        self.data["lows"] = {"BR": {"hades": {"low": 33.59}}}
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        self.assertTrue([i for i in br["items"] if i["slug"] == "hades"][0]["at_low"])

    def test_tier_threshold(self):
        self.settings["tier_min_saving"]["3"] = 25
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        self.assertEqual((br["tier"], br["tier_name"], br["threshold"]), (3, "schwer", 25.0))
        self.assertFalse(br["worth"])                      # 19,18 € Ersparnis reichen nicht
        self.settings["tier_min_saving"]["3"] = 15
        self.assertTrue(self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]["worth"])

    def test_language_rule(self):
        items = self.data["items"]
        items["hades"]["langs"] = {"EU": "english, german", "JP": "日本語, 英語"}
        by = self.by(planner.plans(self.data, self.settings, now=NOW))
        self.assertEqual(by["JP"]["items"], [])            # Japan ohne Deutsch fällt weg
        cell = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]["JP"]
        self.assertTrue(cell["nolang"])
        self.assertIn("ungeprüfter Sprache", " ".join(by["BR"]["warnings"]))   # Amerika unbekannt
        self.assertEqual(by["NO"]["warnings"], [])         # Europa ist dasselbe Produkt
        items["hades"]["langs"]["JP"] = "日本語, ドイツ語"
        self.assertEqual(len(self.by(planner.plans(self.data, self.settings, now=NOW))["JP"]["items"]), 1)
        items["hades"]["langs"] = {"EU": "english, french", "JP": "日本語"}
        by = self.by(planner.plans(self.data, self.settings, now=NOW))
        self.assertEqual(len(by["JP"]["items"]), 1)        # auch in DE kein Deutsch: egal
        self.settings["lang_rule"] = "warn"
        items["hades"]["langs"] = {"EU": "german", "JP": "日本語"}
        by = self.by(planner.plans(self.data, self.settings, now=NOW))
        self.assertIn("ohne deutsche Fassung", " ".join(by["JP"]["warnings"]))

    def test_best_price_marks(self):
        # Hades: BR 33,59 (Tief 33,59), NO 100 (Tief 80), JP 1400, DE 24,99
        self.data["lows"] = {"BR": {"hades": {"low": 33.59}}, "NO": {"hades": {"low": 80.0}}}
        cells = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertEqual(cells["BR"]["mark"], "best")          # Bestpreis über alle Länder
        self.assertEqual(cells["BR"]["champ_code"], "BR")
        self.assertEqual(cells["NO"]["mark"], "sale")          # Angebot, aber über dem Tief
        self.assertGreater(cells["NO"]["gap"], 20)
        self.assertEqual(cells["DE"]["mark"], "")              # kein Angebot
        # Unter den leichten Ländern (ohne Brasilien) hält Japan den Bestpreis: 1400 ¥ = 8,29 €
        self.data["lows"]["NO"]["hades"]["low"] = 100.0
        cells = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertEqual(cells["JP"]["mark"], "best_easy")
        self.assertEqual(cells["NO"]["mark"], "low")           # Landestief, aber 15 % über Japan

    def test_radar(self):
        self.data["lows"] = {"NO": {"hades": {"low": 100.0}}}
        rows = {r["slug"]: r for r in planner.radar(self.data, self.settings, now=NOW)}
        hades = rows["hades"]
        self.assertEqual((hades["easy"]["code"], hades["hard"]["code"]), ("JP", "BR"))
        self.assertEqual(hades["champ"]["code"], "BR")
        self.assertEqual(hades["champ_easy"]["code"], "JP")
        self.assertEqual(hades["verdict"], "buy")
        self.assertEqual(rows["good-job"]["verdict"], "none")
        self.assertEqual(rows["good-job"]["easy"]["code"], "DE")      # nur DE und BR, leicht ist DE
        self.assertEqual(rows["spiritfarer"]["easy"]["code"], "DE")   # in DE im Angebot
        # Zielpreis: Nidhogg 2 kostet in DE 14,99 €, Ziel 15 € gilt als erreicht
        rows = planner.radar(self.data, self.settings, {"nidhogg-2": 15}, now=NOW)
        self.assertEqual(rows[0]["verdict"], "buy")
        self.assertIn("nidhogg-2", [r["slug"] for r in rows if r["reason"] == "Zielpreis erreicht"])

    def test_price_levels_include_inactive(self):
        self.settings["countries"]["BR"]["enabled"] = False
        levels = planner.price_levels(self.data, self.settings, now=NOW)
        self.assertIn("BR", levels)                          # abgeschaltet, trotzdem bewertet
        self.assertLess(levels["BR"]["level"], 0)
        self.assertEqual(levels["BR"]["titles"], 5)
        self.assertNotIn("JP", levels)                       # nur ein gemeinsamer Titel

    def test_matrix(self):
        m = planner.matrix(self.data, self.settings, now=NOW)
        row = {r["slug"]: r for r in m["rows"]}
        self.assertEqual(row["hades"]["best"], "BR")
        self.assertTrue(row["good-job"]["cells"]["NO"]["na"])
        self.assertNotIn("JP", row["good-job"]["cells"])


class StoreTest(unittest.TestCase):
    def test_ui_state_and_settings_validation(self):
        ui = store.save_ui({"basket": ["a", "b"], "targets": {"a": "8,5", "b": "7.5", "c": 0},
                            "hidden": ["NZ"], "sort": "quatsch", "dense": 0,
                            "overrides": {"BR": {"add": ["x"], "remove": None}}})
        self.assertEqual(ui["basket"], ["a", "b"])
        self.assertEqual(ui["targets"], {"b": 7.5})          # nur gültige Zahlen
        self.assertEqual((ui["sort"], ui["dense"], ui["hidden"]), ("saving", False, ["NZ"]))
        self.assertEqual(ui["overrides"], {"BR": {"add": ["x"], "remove": []}})
        self.assertIsNone(store.save_ui({"basket": []})["basket"])
        s = store.save_settings({"countries": {"US": {"tier": "9", "tax_pct": "7.5", "pay": "auto",
                                                      "cards": "50=41"}},
                                 "lang_rule": "nein", "tier_min_saving": {"3": "25", "9": 1}})
        us = s["countries"]["US"]
        self.assertEqual((us["tier"], us["tax_pct"], us["pay"]), (3, 7.5, "auto"))
        self.assertTrue(us["cards_checked"])
        self.assertEqual(s["lang_rule"], "exclude")
        self.assertEqual(s["tier_min_saving"], {"1": 3.0, "2": 8.0, "3": 25.0})
        # nur genannte Felder ändern sich: so liest die Sicherung auch Teil-Dateien ein
        s = store.save_settings({"countries": {"US": {"balance": 3}}})
        self.assertEqual((s["countries"]["US"]["cards"], s["countries"]["US"]["balance"]), ("50=41", 3.0))


class SyncTest(unittest.TestCase):
    def test_full_sync_with_fake_network(self):
        store.save_settings({"wishlist_url": "https://www.dekudeals.com/wishlist/abc",
                             "countries": {c: {"enabled": c in ("DE", "BR", "JP")}
                                           for c in countries.ORDER}})
        calls = []

        def fake(url, ua=None):
            calls.append(url)
            if "/wishlist/" in url:
                return ('<a href="/items/vs-foscari">x</a>' if "page=1" in url else "")
            if "/items/" in url:
                if "country=us" in url:
                    return ITEM_US
                if "country=de" in url:
                    return ITEM_DE
                if "country=br" in url:
                    return ITEM_BR
                return "<title>Nur physisch | Deku Deals</title>"
            if "er-api" in url:
                return '{"result":"success","rates":{"BRL":5.6,"JPY":177},"time_last_update_utc":"t"}'
            if "search.nintendo-europe.com" in url:
                self.assertIn("70050000042405", urllib.parse.unquote(url))
                return ('{"response":{"docs":[{"nsuid_txt":["70050000042405"],'
                        '"language_availability":"english, german"}]}}')
            if "country=BR" in url:
                return BR_JSON
            if "country=DE" in url:
                self.assertIn("70050000042405", url)
                return ('{"prices":[{"title_id":70050000042405,"sales_status":"onsale",'
                        '"regular_price":{"currency":"EUR","raw_value":"1.99"}}]}')
            if "api.ec.nintendo.com" in url:
                if "country=CL" in url:
                    raise sources.FetchError(url, 500)     # abgeschaltetes Land fällt aus
                return '{"prices":[]}'                     # übrige Länder: nichts im Angebot
            raise AssertionError("unerwarteter Abruf " + url)
        sync.run_sync(fetch=fake, sleep=lambda s: None)
        self.assertTrue(sync.status["ok"], sync.status["log"])
        data = store.load_data()
        it = data["items"]["vs-foscari"]
        self.assertEqual(it["ids"], {"EU": ["70050000042405"], "AM": ["70050000042414"], "JP": []})
        self.assertEqual(it["parent"], "vampire-survivors")
        self.assertEqual(it["parent_title"], "Vampire Survivors")
        self.assertEqual(data["prices"]["BR"]["vs-foscari"]["discount"], 4.0)
        # Tiefstpreis: DE kommt aus der ID-Suche mit, BR wird nachgeladen
        self.assertEqual(data["lows"]["DE"]["vs-foscari"]["low"], 1.49)
        self.assertEqual(data["lows"]["BR"]["vs-foscari"], dict(
            data["lows"]["BR"]["vs-foscari"], low=3.5, src="deku"))
        self.assertEqual(sum("country=br" in u for u in calls), 1)
        hist = store.load_history()
        self.assertEqual(hist["BR"]["vs-foscari"][0][1], 4.0)
        self.assertEqual(len(hist["DE"]["vs-foscari"]), 1)
        self.assertNotIn("JP", data["prices"])  # keine japanische ID, kein Abruf
        self.assertFalse(any("country=JP" in u for u in calls))
        self.assertEqual(it["langs"], {"EU": "english, german"})
        price_calls = [u for u in calls if "api.ec.nintendo.com" in u]
        # Preise für alle Länder mit bekannten IDs (Europa und Amerika), nicht für Japan und Asien
        self.assertEqual(len(price_calls), 19)
        self.assertIn("CL", data["price_fail"])
        self.assertFalse(any("Preisabruf fehlgeschlagen" in l for l in sync.status["log"]))
        n = len(calls)
        sync.run_sync(fetch=fake, sleep=lambda s: None)
        # zweiter Lauf sucht weder IDs, Sprachen noch Tiefstpreise:
        # Wishlist (2), Kurse (1), Preise (19 Länder minus das ruhende Chile)
        self.assertEqual(len(calls) - n, 2 + 1 + 18)
        self.assertEqual(len(store.load_history()["BR"]["vs-foscari"]), 1)  # kein Preiswechsel

    def test_low_is_lowered_by_own_tracking(self):
        data = {"lows": {"BR": {"a": {"low": 5.0, "src": "deku"}, "b": {"low": 99.0}}}}
        table = {"a": {"status": "onsale", "currency": "BRL", "regular": 10, "discount": 4},
                 "b": {"status": "onsale", "currency": "BRL", "regular": 10}}
        hist = {}
        sync._track(data, hist, "BR", table, "2026-10-11T00:00:00+00:00")
        self.assertEqual(data["lows"]["BR"]["a"]["low"], 4.0)
        self.assertEqual(data["lows"]["BR"]["a"]["src"], "own")
        self.assertNotIn("low", data["lows"]["BR"]["b"])   # über Normalpreis: verworfen
        table["a"]["discount"] = 6
        sync._track(data, hist, "BR", table, "2026-10-12T00:00:00+00:00")
        self.assertEqual([p for _, p in hist["BR"]["a"]], [4.0, 6.0])
        self.assertEqual(data["lows"]["BR"]["a"]["low"], 4.0)


if __name__ == "__main__":
    unittest.main()
