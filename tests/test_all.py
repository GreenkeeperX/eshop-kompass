import html
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

    def test_price_history_and_sale_runs(self):
        rows = [["2024-05-%02d" % d, None, 13.31] for d in range(1, 11)]
        rows[3][2] = rows[4][2] = 6.65                    # Angebot 4.–5. Mai
        rows[8][2] = 7.99                                 # Angebot 9. Mai, läuft noch
        data = json.dumps({"headers": ["Nintendo eShop"], "data": rows})
        idx = json.dumps({"all": [0, 1, 2], "physical": [0, 1], "digital": [0, 1, 2]})
        page = (f'<title>X | Deku Deals</title><script id="price_history_data" type="application/json">'
                f'{html.escape(data)}</script><script id="price_history_indices">{idx}</script>')
        series = sources.parse_history(page)
        self.assertEqual((len(series), series[3]), (10, ("2024-05-04", 6.65)))
        runs = sources.sale_runs(series)
        self.assertEqual(runs, [["2024-05-04", 6.65], ["2024-05-09", 7.99]])
        self.assertEqual(sources.sale_runs(series, since="2024-05-06"), [["2024-05-09", 7.99]])
        self.assertEqual(sources.parse_item_page(page)["history"], series)
        self.assertEqual(sources.parse_history("<html>ohne Verlauf</html>"), [])

    def test_languages_americas(self):
        page = ('<script id="__NEXT_DATA__">{"product":{"supportedLanguages":'
                '["English","French","Spanish"]}}</script>')
        self.assertEqual(sources.parse_langs_am(page), "english, french, spanish")
        page = '<h3>Supported languages</h3><p>English, German</p>'
        self.assertEqual(sources.parse_langs_am(page), "english, german")
        self.assertIsNone(sources.parse_langs_am("<p>Nichts</p>"))

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
        # Tabelle mit Kopf, dann Werte (Bread & Fred)
        self.assertEqual(sources.parse_lows("All time low | Digital | | Physical | | €5,91 | (-60%) | €29,99 | | Time range"), [5.91])
        # Switch und Switch 2: eine Zeile je Plattform; "Switch 2" ist kein Preis von 2,00
        two = ("<table><tr><th>All time low</th><th>Physical</th><th></th><th>Digital</th></tr>"
               "<tr><td>Switch 2</td><td>€69,99</td><td></td><td>€59,99</td></tr>"
               "<tr><td>Switch</td><td>€49,99</td><td></td><td>€39,99</td><td>(-33%)</td></tr></table> Time range 6m 1y")
        self.assertEqual(sources.parse_lows(two), [59.99, 39.99])
        self.assertEqual(sources.parse_low(two), 59.99)

    def test_low_of_own_platform(self):
        # Je Plattform ein Tiefstpreis: es gilt der höchste, den der Preis jetzt nicht übersteigt
        settings = store.load_settings()
        data = {"items": {"a": {"active": True}}, "prices": {"DE": {"a": {"status": "onsale", "regular": 44.99}}}}
        orig = sources.fetch_item
        sources.fetch_item = lambda slug, country, fetch=None: {"low": 59.99, "lows": [59.99, 39.99], "history": []}
        try:
            sync.sync_lows(data, settings, fetch=None, sleep=lambda s: None, now=1736467200)
            self.assertEqual(data["lows"]["DE"]["a"]["low"], 39.99)
        finally:
            sources.fetch_item = orig

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

    def test_no_disguise_on_challenge_page(self):
        # Eine Prüfseite wird gemeldet, nicht mit einer anderen Kennung umgangen
        calls = []

        def fake(url, ua=None):
            calls.append(ua)
            return "<title>Sperre</title>x"
        with self.assertRaises(sources.FetchError):
            sources.fetch_wishlist("abc123", fetch=fake)
        self.assertEqual(calls, [None])                     # genau ein Versuch
        self.assertEqual(len(sources.attempts), 1)
        self.assertIn("Titel „Sperre“", sources.attempts[0])
        self.assertIn("0 Titel-Links", sources.attempts[0])
        self.assertTrue(sources.USER_AGENT.startswith("eshop-kompass/"))
        with open(sources.__file__, encoding="utf-8") as f:
            self.assertNotIn("Mozilla", f.read())

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
    settings["countries"]["JP"]["cards"] = "500 1000 2000 3000 5000 9000"   # zum Kurs, wie im echten Einsatz
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
        # Der Rest ist kein Verlust: 2,41 von 40 R$ der gekauften Karten sind anteilig
        # 0,47 €, die Spiele selbst also 7,33 €
        self.assertAlmostEqual(br["rest_value"], 0.47, places=2)
        self.assertAlmostEqual(br["games_cost"], 7.33)
        self.assertAlmostEqual(br["saving"], round(24.99 + 1.99 - 7.33, 2))
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
        # Das Guthaben ist schon bezahlt, zählt aber zum Kurs: sonst wirkte das Paket billiger
        self.assertAlmostEqual(br["balance_value"], 0.49, places=2)
        self.assertAlmostEqual(br["games_cost"], 7.80 * 38.50 / 40 + br["balance_value"], places=2)
        # Deckt das Guthaben alles, kostet das Paket trotzdem nicht 0 €
        self.settings["countries"]["BR"]["balance"] = 100
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        self.assertEqual(br["cost"], 0)
        self.assertGreater(br["games_cost"], 6)

    def test_missing_cards_and_must(self):
        self.settings["countries"]["JP"]["cards"] = ""
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
        # Rest 4,01 R$ zum Kartenkurs der 50er (9,50 €) zählt nicht als Kosten
        self.assertAlmostEqual(by["BR"]["saving"],
                               round(24.99 + 19.99 + 14.99 - 20.3 + by["BR"]["rest_value"], 2))
        self.assertGreater(by["BR"]["rest_value"], 0.7)
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
        self.assertFalse(br["worth"])
        # Gegenüber Deutschland spart Brasilien 19,65 €. Ohne diesen Wechsel gäbe es Hades
        # aber in Japan für 8,03 € und VS Foscari in Norwegen für 1,90 €: Der Wechsel
        # bringt nur 2,60 € (Entscheidung 12.10.2026: gemessen wird gegen die Alternative)
        self.assertEqual((br["saving"], br["alt_total"], br["gain"]), (19.65, 9.93, 2.6))
        self.assertEqual(br["alt_codes"], ["JP", "NO"])
        self.assertEqual([(i["alt"], i["alt_code"]) for i in br["items"]], [(8.03, "JP"), (1.9, "NO")])
        self.settings["tier_min_saving"]["3"] = 15
        self.assertFalse(self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]["worth"])
        self.settings["tier_min_saving"]["3"] = 2.5
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
        self.assertEqual(cell["nolang"], True)
        cells = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertEqual(cells["NO"]["lang"], "same")       # dasselbe Produkt: DE✓
        items["hades"]["langs"]["JP"] = "日本語, ドイツ語"
        self.assertEqual(len(self.by(planner.plans(self.data, self.settings, now=NOW))["JP"]["items"]), 1)
        cells = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertEqual(cells["JP"]["lang"], "de")         # in Japan bestätigt
        items["hades"]["langs"] = {"EU": "english, french", "JP": "日本語"}
        by = self.by(planner.plans(self.data, self.settings, now=NOW))
        self.assertEqual(len(by["JP"]["items"]), 1)        # auch in DE kein Deutsch: egal
        self.settings["lang_rule"] = "warn"
        items["hades"]["langs"] = {"EU": "german", "JP": "日本語"}
        by = self.by(planner.plans(self.data, self.settings, now=NOW))
        self.assertIn("ohne deutsche Fassung", " ".join(by["JP"]["warnings"]))

    def test_manual_language_confirmation(self):
        items = self.data["items"]
        items["hades"]["langs"] = {"EU": "english, german"}
        items["hades"]["ids"].update(JP=["70010000000001"], AM=["70010000000002"])
        todo = {(t["slug"], t["family"]) for t in planner.lang_todo(self.data, self.settings, now=NOW)}
        self.assertEqual(todo, {("hades", "JP"), ("hades", "AM")})
        # Prüfen lohnt, wo die Fassung den Bestpreis der zählenden Länder (NO 9,50 €) unterbietet
        rows = {t["family"]: t for t in planner.lang_todo(self.data, self.settings, now=NOW)}
        self.assertEqual((rows["JP"]["matters"], rows["JP"]["here"]["code"], rows["JP"]["champ"]["code"]), (True, "JP", "NO"))
        self.data["prices"]["JP"]["hades"]["discount"] = 2000.0       # 11,47 €: ändert nichts
        rows = {t["family"]: t for t in planner.lang_todo(self.data, self.settings, now=NOW)}
        self.assertFalse(rows["JP"]["matters"])
        self.assertTrue(rows["AM"]["matters"])
        # Von Hand: Japan ohne Deutsch fällt weg, Amerika mit Deutsch zählt
        self.settings["lang_confirm"] = {"hades": {"JP": False, "AM": True}}
        cells = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertTrue(cells["JP"]["nolang"])
        self.assertEqual(cells["BR"]["lang"], "de")
        rows = planner.lang_todo(self.data, self.settings, now=NOW)
        self.assertTrue(all(t["manual"] for t in rows))    # bleibt sichtbar, zum Zurücksetzen
        # Von Hand geht vor Nintendo
        items["hades"]["langs"]["JP"] = "日本語, ドイツ語"
        self.assertTrue(planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]["JP"]["nolang"])

    def test_package_distance_to_optimum(self):
        by = self.by(planner.plans(self.data, self.settings, now=NOW))
        br = by["BR"]
        # Hades und VS Foscari kosten in Brasilien so wenig wie nirgends sonst. Optimum ist
        # die Summe ihrer Bestpreise; das Paket liegt nur um die Kartenstückelung darüber
        self.assertEqual((br["opt_at"], br["opt_known"]), (2, 2))
        self.assertAlmostEqual(br["optimum"], round(br["items"][0]["champ"] + br["items"][1]["champ"], 2))
        self.assertLess(br["opt_gap"], 0.5)
        no, hades_br = by["NO"], br["items"][0]["eur"]
        self.assertAlmostEqual(no["opt_gap"], round(9.50 - hades_br, 2))   # Hades in NO 9,50 €
        self.assertEqual(no["opt_pct"], round(100 * no["opt_gap"] / hades_br))
        self.assertEqual(no["opt_at"], 0)

    def test_best_price_marks(self):
        # Hades: BR 33,59 (Tief 33,59), NO 100 (Tief 80), JP 1400, DE 24,99
        self.data["lows"] = {"BR": {"hades": {"low": 33.59}}, "NO": {"hades": {"low": 80.0}}}
        cells = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertEqual(cells["BR"]["mark"], "best")          # Bestpreis über alle Länder
        self.assertEqual(cells["BR"]["champ_code"], "BR")
        self.assertEqual(cells["NO"]["mark"], "sale")          # Angebot, aber über dem Tief
        self.assertGreater(cells["NO"]["gap"], 20)
        self.assertEqual(cells["DE"]["mark"], "")              # kein Angebot
        # Es zählt nur der Bestpreis über alle Länder: Japan ist das günstigste leichte
        # Land, liegt aber über Brasilien und bekommt keine Bestpreis-Marke
        self.data["lows"]["NO"]["hades"]["low"] = 100.0
        cells = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertEqual(cells["JP"]["mark"], "sale")
        self.assertEqual(cells["NO"]["mark"], "low")           # Landestief

    def test_radar(self):
        self.data["lows"] = {"NO": {"hades": {"low": 100.0}}}
        rows = {r["slug"]: r for r in planner.radar(self.data, self.settings, now=NOW)}
        hades = rows["hades"]
        self.assertEqual((hades["easy"]["code"], hades["hard"]["code"]), ("JP", "BR"))
        self.assertEqual(hades["champ"]["code"], "BR")
        # Der Bestpreis aller Länder liegt jetzt in Brasilien. Das Urteil misst nur die
        # Preisgüte, das Land und seine Stufe stehen dabei; ob sich der Weg lohnt, sagt der Kaufplan
        self.assertEqual((hades["verdict"], hades["reason"]), ("buy", "Bestpreis in Brasilien (schwer)"))
        self.assertEqual(hades["at"], {"code": "BR", "name": "Brasilien", "tier": 3})
        self.assertEqual(rows["good-job"]["verdict"], "none")
        self.assertEqual(rows["good-job"]["easy"]["code"], "DE")      # nur DE und BR, leicht ist DE
        self.assertEqual(rows["spiritfarer"]["easy"]["code"], "DE")   # in DE im Angebot
        # Zielpreis: Nidhogg 2 kostet in DE 14,99 €, Ziel 15 € gilt als erreicht
        rows = planner.radar(self.data, self.settings, {"nidhogg-2": 15}, now=NOW)
        self.assertEqual(rows[0]["verdict"], "buy")
        self.assertIn("nidhogg-2", [r["slug"] for r in rows if r["reason"].startswith("Zielpreis erreicht")])

    def test_verdict_counts_euros_too(self):
        sale = {"start": "2026-10-01T00:00:00Z", "end": "2026-10-20T00:00:00Z"}
        de = self.data["prices"]["DE"]
        de["nidhogg-2"] = dict(de["nidhogg-2"], discount=4.99, **sale)
        self.data["prices"]["BR"].pop("nidhogg-2")          # sonst Bestpreis Brasilien 1,21 €
        self.data["lows"] = {"DE": {"spiritfarer": {"low": 5.99}, "nidhogg-2": {"low": 3.49}}}
        rows = {r["slug"]: r for r in planner.radar(self.data, self.settings, now=NOW)}
        # 0,25 € über dem Bestpreis: kaufen, auch wenn es kein Bestpreis ist
        self.assertEqual((rows["spiritfarer"]["verdict"], rows["spiritfarer"]["diff"]), ("buy", 0.25))
        self.assertEqual(rows["spiritfarer"]["reason"], "nur 0,25 € über Bestpreis in Deutschland")
        # 1,50 € über dem Bestpreis sind 43 %, in Euro aber wenig: gutes Angebot
        n = rows["nidhogg-2"]
        self.assertEqual((n["verdict"], n["diff"], n["gap"]), ("good", 1.5, 43))
        self.assertEqual(n["reason"], "1,50 € (43 %) über Bestpreis in Deutschland")
        self.settings["deal_eur"] = {"buy": 0.1, "good": 1.0}
        rows = {r["slug"]: r for r in planner.radar(self.data, self.settings, now=NOW)}
        self.assertEqual(rows["spiritfarer"]["verdict"], "good")        # 4 % über Bestpreis
        self.assertEqual(rows["nidhogg-2"]["verdict"], "wait")
        self.assertEqual(rows["nidhogg-2"]["reason"], "war 1,50 € günstiger")

    def test_typical_sale_price_is_info_only(self):
        # Spiritfarer: DE jetzt 6,24 €, Allzeit-Tief 4,99 €
        lows = {"spiritfarer": {"low": 4.99, "sales": [["2025-03-01", 7.49], ["2025-07-01", 7.49],
                                                       ["2025-11-01", 9.99]]}}
        self.data["lows"] = {"DE": lows}
        # Das Urteil misst am Bestpreis aller Länder, der typische Preis steht nur daneben,
        # auch wenn eine alte Einstellung ihn noch wählt
        self.settings["verdict_ref"] = "typical"
        r = {x["slug"]: x for x in planner.radar(self.data, self.settings, now=NOW)}["spiritfarer"]
        self.assertEqual((r["typical"]["eur"], r["typical"]["runs"], r["verdict"]), (7.49, 3, "good"))
        self.assertEqual(r["typ_diff"], -1.25)
        # Das letzte Angebot war das tiefste: Es gilt statt des Medians
        lows["spiritfarer"]["sales"][-1] = ["2026-05-01", 6.24]
        r = {x["slug"]: x for x in planner.radar(self.data, self.settings, now=NOW)}["spiritfarer"]
        self.assertEqual(r["typical"]["eur"], 6.24)
        # Angebote älter als zwei Jahre und einzelne Angebote zählen nicht
        lows["spiritfarer"]["sales"] = [["2023-01-01", 2.0], ["2026-05-01", 7.49]]
        r = {x["slug"]: x for x in planner.radar(self.data, self.settings, now=NOW)}["spiritfarer"]
        self.assertIsNone(r["typical"])
        # Den Bestpreis zu erreichen ist ein Kauf
        lows["spiritfarer"]["low"] = 6.24
        r = {x["slug"]: x for x in planner.radar(self.data, self.settings, now=NOW)}["spiritfarer"]
        self.assertEqual((r["verdict"], r["reason"]), ("buy", "Bestpreis in Deutschland"))

    def test_estimated_prices_are_flagged(self):
        # Japan ohne eingetragene Karte: Kurs plus Aufschlag geschätzt. Guthaben gibt es
        # dort dann nicht zu kaufen, also zeigt das Tool das Angebot, entscheidet aber nicht
        self.settings["countries"]["JP"]["cards"] = ""
        rows = {r["slug"]: r for r in planner.radar(self.data, self.settings, now=NOW)}
        self.assertEqual(rows["hades"]["easy"]["code"], "NO")
        self.assertNotEqual(rows["hades"]["champ"]["code"], "JP")
        cells = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertTrue(cells["JP"]["est"])
        self.assertTrue(cells["JP"]["nocard"])
        self.assertNotIn(cells["JP"]["mark"], ("best", "best_easy"))
        # Nur dort kaufbar: kein Urteil, aber der Grund
        for code in ("DE", "NO", "BR"):
            self.data["prices"][code].pop("hades")
        row = next(r for r in planner.radar(self.data, self.settings, now=NOW) if r["slug"] == "hades")
        self.assertEqual(row["verdict"], "none")
        self.assertIn("JP: keine Guthabenkarte mit Preis", row["reason"])
        self.data, self.settings = sample()
        self.settings["countries"]["JP"]["cards"] = ""
        cells = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertFalse(cells["BR"]["est"])          # Karten mit Preis eingetragen
        self.assertFalse(cells["NO"]["est"])          # Kartenzahlung
        self.assertFalse(cells["DE"]["est"])
        # Werte ohne Preis folgen dem Kurs: Amazon Japan zum Nennwert, nur der Rest kostet
        self.settings["countries"]["JP"].update(cards="500 1000 2000 3000 5000 9000", markup_pct=0)
        jp = self.by(planner.plans(self.data, self.settings, now=NOW))["JP"]
        self.assertEqual(jp["cards"], [{"face": 1000.0, "count": 1, "url": ""},
                                       {"face": 500.0, "count": 1, "url": ""}])
        self.assertAlmostEqual(jp["cost"], round(1500 / 177.3267, 2))
        self.assertEqual(jp["rest"], 100.0)
        cells = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertFalse(cells["JP"]["est"])          # feste Werte zum Kurs: keine Schätzung
        self.settings["countries"]["JP"]["cards"] = "1000 | https://shop.example/jp"
        cells = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]
        self.assertTrue(cells["JP"]["est"])           # Shop-Karte ohne bekannten Preis

    def test_card_prices_from_shop_pages(self):
        ld = ('<script type="application/ld+json">{"@type":"Product","offers":{"@type":"Offer",'
              '"price":"%s","priceCurrency":"%s"}}</script>')
        pages = {"https://shop.example/br50": ld % ("8.90", "EUR"),
                 "https://shop.example/br25": "<div id=app></div>"}
        self.settings["countries"]["BR"]["cards"] = (
            "15 = 3,00\n25 = 4,80 | https://shop.example/br25\n50 = 9,50 | https://shop.example/br50")
        calls = []

        def fake(url, ua=None):
            calls.append(url)
            return pages[url]
        t0 = NOW.timestamp()
        sync.sync_card_prices(self.data, self.settings, fake, lambda s: None, now=t0)
        cp = self.data["card_prices"]
        self.assertEqual(cp["https://shop.example/br50"], {"checked": t0, "price": 8.9, "currency": "EUR"})
        self.assertEqual(cp["https://shop.example/br25"]["error"], "Seite nennt keinen Preis")
        sync.sync_card_prices(self.data, self.settings, fake, lambda s: None, now=t0 + 3600)
        self.assertEqual(len(calls), 2)                       # höchstens einmal am Tag
        # Der gelesene Preis ersetzt den von Hand eingetragenen, mit der Servicegebühr des Shops
        st = planner.card_status(self.data, self.settings, now=NOW)["BR"]
        self.assertEqual(st[1]["cost"], round(8.90 * 1.0775 + 0.40, 2))   # Vorgabe 0,40 € + 7,75 %
        # Die Vorgabe trifft echte Eneba-Käufe auf den Cent
        for sub, fee in ((5.57, 0.83), (16.58, 1.68), (49.26, 4.22), (93.03, 7.61)):
            self.assertAlmostEqual(sub * 0.0775 + 0.40, fee, delta=0.006)
        self.settings["shop_fee_pct"], self.settings["shop_fee_eur"] = 0, 0
        info = planner.pay_info(self.data, self.settings, now=NOW)["BR"]
        self.assertEqual((info["card"]["face"], info["card"]["cost"], info["card"]["live"]), (50.0, 8.9, t0))
        st = planner.card_status(self.data, self.settings, now=NOW)["BR"]
        self.assertEqual([(r["face"], r["cost"], r["manual"], r["error"]) for r in st],
                         [(25.0, 4.8, 4.8, "Seite nennt keinen Preis"), (50.0, 8.9, 9.5, None)])
        # Veraltet: nach drei Tagen gilt wieder der Wert von Hand
        later = datetime.fromtimestamp(t0 + 4 * 86400, timezone.utc)
        self.assertEqual(planner.pay_info(self.data, self.settings, now=later)["BR"]["card"]["cost"], 9.5)
        # Sperre beendet das Lesen, gelöschte Links fallen aus dem Speicher
        self.settings["countries"]["BR"]["cards"] = "50 = 9,50 | https://shop.example/br50\n25 | https://shop.example/x"
        calls.clear()

        def deny(url, ua=None):
            calls.append(url)
            raise sources.FetchError(url, 403)
        sync.sync_card_prices(self.data, self.settings, deny, lambda s: None, now=t0 + 2 * 86400)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("https://shop.example/br25", self.data["card_prices"])
        self.assertIn("lehnt Abrufe ab", sync.status["log"][-2])

    def test_fixed_shop_fee_once_per_order(self):
        url = "https://shop.example/br50"
        self.settings["countries"]["BR"]["cards"] = f"50 | {url}"
        self.data["card_prices"] = {url: {"checked": NOW.timestamp(), "price": 8.90, "currency": "EUR"}}
        # Hades 33,59 + Good Job 59,90 = 93,49 R$: zwei 50er-Karten in einer Bestellung
        by = {p["code"]: p for p in planner.plans(self.data, self.settings,
                                                  basket=["hades", "good-job"], now=NOW)}
        br = by["BR"]
        self.assertEqual(br["cards"][0]["count"], 2)
        self.assertAlmostEqual(br["cost"], round(2 * 8.90 * 1.0775 + 0.40, 2), places=2)

    def test_cashback_hint(self):
        url = "https://shop.example/br50"
        self.settings["countries"]["BR"]["cards"] = f"50 | {url}"
        self.data["card_prices"] = {url: {"checked": NOW.timestamp(), "price": 8.90, "currency": "EUR"}}
        self.data["prices"]["JP"].pop("hades")
        # Bestpreis 30 R$, jetzt 33,59 R$; in Norwegen war es auch schon günstiger
        self.data["lows"] = {"BR": {"hades": {"low": 30.0}}, "NO": {"hades": {"low": 80.0}}}
        row = lambda: next(r for r in planner.radar(self.data, self.settings, now=NOW)
                           if r["slug"] == "hades")
        self.assertIsNone(row()["cashback"])                       # Vorgabe 0 %: kein Hinweis
        self.settings["cashback_pct"] = 7.4
        self.assertIsNone(row()["cashback"])                       # 7,4 % reichen nicht
        self.settings["cashback_pct"] = 15
        cb = row()["cashback"]
        self.assertEqual((cb["code"], cb["pct"]), ("BR", 15))
        self.assertNotEqual(row()["verdict"], "buy")               # nur ein Hinweis

    def test_card_prices_from_ggdeals(self):
        page = ('<div class="tile"><a href="/de/gift-card/nintendo-eshop-gift-card-50-brl/"><img></a>'
                '<a href="/de/gift-card/nintendo-eshop-gift-card-50-brl/">Nintendo eShop 50 BRL</a>'
                '<s>9,10€</s> <b>~8,05€</b></div>'
                '<div class="tile"><a href="/de/gift-card/nintendo-eshop-gift-card-60-brl-brazil/">60 BRL</a>'
                '<span>Nicht verfügbar</span></div>'
                '<div class="tile"><a href="/de/gift-card/nintendo-eshop-gift-card-100-brl/">100 BRL</a>'
                '<b>16,10 €</b></div>'
                '<div><a href="/de/gift-card/nintendo-eshop-gift-card-20-usd/">20 USD</a> 17,00€</div>')
        cards = sources.parse_ggdeals_group(page, "BRL")
        self.assertEqual({f: p for f, (p, _) in cards.items()}, {50: 8.05, 100: 16.1})
        self.assertEqual(cards[50][1], "https://gg.deals/de/gift-card/nintendo-eshop-gift-card-50-brl/")
        self.settings["countries"]["BR"]["cards"] = "15=3.00\n25=4.80\n50=9.50\nx 100"
        self.data["card_market"] = {"BR": {"checked": NOW.timestamp(), "cards": {
            "50": {"price": 8.05, "url": "https://gg.deals/a"},
            "100": {"price": 16.10, "url": "https://gg.deals/b"},
            "150": {"price": 23.99, "url": "https://gg.deals/c"},
            "15": {"price": 3.50, "url": "https://gg.deals/d"}}}}
        ctx = planner.Context(self.data, self.settings, NOW)
        by = {x["face"] // 100: x for x in ctx.countries["BR"]["cards"]}
        self.assertEqual(by[50]["cost"], 8.05)            # günstiger als dein Eintrag
        self.assertEqual(by[50]["manual"], 9.50)
        self.assertEqual(by[15]["cost"], 3.00)            # dein Eintrag ist günstiger
        self.assertFalse(by[100]["stock"])                # nicht vorrätig bleibt draußen
        self.assertEqual((by[150]["cost"], by[150]["stock"]), (23.99, True))   # neuer Wert
        self.assertEqual(planner.pay_info(self.data, self.settings, now=NOW)["BR"]["card"]["market"],
                         NOW.timestamp())
        # Abgeschaltet oder älter als drei Tage: nur deine Einträge
        later = datetime.fromtimestamp(NOW.timestamp() + 4 * 86400, timezone.utc)
        self.assertEqual(len(planner.Context(self.data, self.settings, later).countries["BR"]["cards"]), 4)
        self.settings["card_market"] = False
        self.assertEqual(planner.Context(self.data, self.settings, NOW).countries["BR"]["cards"][2]["cost"], 9.5)

    def test_implausible_card_prices_are_ignored(self):
        # 50 BRL zum Mittelkurs sind 8,91 €: 0,35 € (Gebührenhinweis statt Preis) ist ein Lesefehler
        self.data["card_market"] = {"BR": {"checked": NOW.timestamp(), "cards": {
            "50": {"price": 0.35, "url": "https://gg.deals/a"},
            "100": {"price": 16.10, "url": "https://gg.deals/b"},
            "200": {"price": 90.0, "url": "https://gg.deals/c"}}}}
        self.settings["countries"]["BR"]["cards"] = "15=3.00\n25=4.80\n50=9.50 | https://shop.example/br50"
        self.data["card_prices"] = {"https://shop.example/br50": {
            "checked": NOW.timestamp(), "price": 0.99, "currency": "EUR"}}
        ctx = planner.Context(self.data, self.settings, NOW)
        by = {x["face"] // 100: x for x in ctx.countries["BR"]["cards"]}
        self.assertEqual(by[50]["cost"], 9.50)              # beides unglaubhaft: dein Eintrag gilt
        self.assertEqual(by[100]["cost"], 16.10)            # 90 % vom Mittelkurs: zählt
        self.assertNotIn(200, by)                           # 252 %: zählt nicht
        self.assertEqual(sorted((i["src"], i["face"]) for i in ctx.countries["BR"]["implausible"]),
                         [("gg.deals", 50.0), ("gg.deals", 200.0), ("shop", 50.0)])
        rows = planner.card_status(self.data, self.settings, now=NOW)["BR"]
        self.assertIn("unglaubhaft", next(r for r in rows if r["face"] == 50)["error"])
        self.assertIn("50 für 0,35 €", next(r for r in rows if r.get("market_error"))["market_error"])
        # Deutschland: eine 20-€-Karte für 0,35 € senkt die Vergleichsbasis nicht
        self.data["card_market"]["DE"] = {"checked": NOW.timestamp(), "cards": {
            "20": {"price": 0.35, "url": "https://gg.deals/d"}}}
        self.assertEqual(planner.pay_info(self.data, self.settings, now=NOW)["DE"]["via"], "eur")
        self.assertTrue(planner.plausible_card(6.40, 3000, 5.6086))   # kleine Karte mit Gebühr
        self.assertFalse(planner.plausible_card(None, 3000, 5.6086))

    def test_unknown_language_does_not_decide(self):
        # Deutschland hat Deutsch, Japan und Brasilien sind ungeprüft
        self.data["items"]["hades"]["langs"] = {"EU": "english, german"}
        rows = {r["slug"]: r for r in planner.radar(self.data, self.settings, now=NOW)}
        self.assertEqual(rows["hades"]["easy"]["code"], "NO")      # nicht Japan
        self.assertIsNone(rows["hades"]["hard"])                     # nicht Brasilien
        self.assertNotIn(rows["hades"]["champ"]["code"], ("JP", "BR"))
        mx = planner.matrix(self.data, self.settings, now=NOW)
        hades = next(r for r in mx["rows"] if r["slug"] == "hades")
        self.assertEqual(hades["cells"]["JP"]["lang"], "unknown")   # weiter sichtbar
        self.assertNotIn(hades["cells"]["BR"]["mark"], ("best", "best_easy"))
        self.assertNotIn(hades["best"], ("JP", "BR"))
        plan = planner.purchase_plan(self.data, self.settings, now=NOW, include_good=True)
        where = {i["slug"]: p["code"] for p in plan["steps"] for i in p["items"]}
        self.assertNotIn(where.get("hades"), ("JP", "BR"))
        # Nur in ungeprüften Ländern kaufbar: kein Urteil, aber ein Grund
        for code in ("DE", "NO"):
            self.data["prices"][code].pop("hades")
        row = next(r for r in planner.radar(self.data, self.settings, now=NOW) if r["slug"] == "hades")
        self.assertEqual(row["verdict"], "none")
        self.assertEqual(row["lang_unsure"], ["JP", "BR"])
        self.assertIn("JP, BR: Sprache ungeprüft", row["reason"])
        # „nur warnen“ entscheidet wie bisher mit
        self.settings["lang_rule"] = "warn"
        row = next(r for r in planner.radar(self.data, self.settings, now=NOW) if r["slug"] == "hades")
        self.assertEqual(row["easy"]["code"], "JP")

    def test_germany_with_gift_cards_is_its_own_country(self):
        dg = self.settings["countries"]["DG"]
        dg["enabled"] = True
        dg["cards"] = "20 = 21,00\n25 = 22,50 | https://shop.example/de25"
        info = planner.pay_info(self.data, self.settings, now=NOW)
        self.assertEqual(info["DE"]["via"], "eur")                    # Referenz bleibt der Shop-Preis
        self.assertEqual((info["DG"]["via"], info["DG"]["card"]["cost"], info["DG"]["vs_mid"]),
                         ("giftcard", 22.5, -10.0))
        by = self.by(planner.plans(self.data, self.settings, now=NOW))
        self.assertEqual(by["DE"]["cost"], 6.24)                       # Spiritfarer zum Shop-Preis
        # Für Spiritfarer (6,24 €) reicht eine 20er Karte, die hier 21 € kostet: anteilig
        # 6,55 €, also nicht günstiger als im Shop. Die 25er wäre je Euro billiger, kostet
        # aber mehr, als der Einkauf braucht (Entscheidung: Guthaben passend zum Einkauf)
        self.assertEqual(by["DG"]["items"], [])
        row = {r["slug"]: r for r in planner.radar(self.data, self.settings, now=NOW)}["good-job"]
        self.assertEqual(row["de"], 19.99)                              # Vergleichsbasis unverändert
        self.assertEqual(row["easy"]["code"], "DE")                     # DG anteilig 20,99 €
        # Eine 20er für 18 €: Spiritfarer anteilig 5,62 €, der Rest ist kein Verlust
        dg["cards"] = "20 = 18,00\n25 = 22,50"
        dgp = self.by(planner.plans(self.data, self.settings, now=NOW))["DG"]
        self.assertEqual([i["slug"] for i in dgp["items"]], ["spiritfarer"])
        self.assertEqual((dgp["cost"], dgp["rest"], dgp["games_cost"]), (18.0, 13.76, 5.62))
        self.assertAlmostEqual(dgp["saving"], 0.62)
        # Kauf vermerkt in DG: das Konto steht in Deutschland
        self.settings["current_country"] = "DE"
        self.assertTrue(self.by(planner.plans(self.data, self.settings, now=NOW))["DG"]["current"])

    def test_own_low_without_dekudeals(self):
        self.data["lows"] = {"NO": {"hades": {"checked": 1}}}      # DekuDeals ohne Wert
        hist = {}
        sync._track(self.data, hist, "NO", self.data["prices"]["NO"], "2026-10-11T00:00:00+00:00")
        e = self.data["lows"]["NO"]["hades"]
        self.assertEqual((e["own_low"], e.get("low")), (100.0, None))
        cell = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]["NO"]
        self.assertEqual((cell["low"], cell["mark"]), (100.0, "low"))
        # Ein späterer DekuDeals-Wert ersetzt den eigenen nicht, der niedrigere zählt
        sync._store_low(self.data, self.settings, "NO", "hades", 120.0, 2)
        self.assertEqual((e["low"], e["own_low"], e["checked"]), (120.0, 100.0, 2))
        cell = planner.matrix(self.data, self.settings, now=NOW)["rows"][0]["cells"]["NO"]
        self.assertEqual(cell["low"], 100.0)

    def test_price_levels_include_inactive(self):
        self.settings["countries"]["BR"]["enabled"] = False
        levels = planner.price_levels(self.data, self.settings, now=NOW)
        self.assertIn("BR", levels)                          # abgeschaltet, trotzdem bewertet
        self.assertLess(levels["BR"]["level"], 0)
        self.assertEqual(levels["BR"]["titles"], 5)
        self.assertNotIn("JP", levels)                       # nur ein gemeinsamer Titel

    def test_price_composition_and_own_markup(self):
        self.settings["countries"]["JP"]["cards"] = ""
        info = planner.pay_info(self.data, self.settings, now=NOW)
        self.assertEqual((info["NO"]["via"], info["NO"]["vs_mid"]), ("card", 1.8))   # Kartengebühr
        self.assertEqual(info["DE"]["via"], "eur")
        br = info["BR"]                 # beste Karte: 50 BRL für 9,50 €
        self.assertEqual((br["via"], br["card"]["face"], br["card"]["cost"]), ("giftcard", 50.0, 9.5))
        self.assertAlmostEqual(br["vs_mid"], round(100 * (9.5 / (50 / 5.6086) - 1), 1))
        # Japan ohne Kartenliste: voreingestellt Nennwert plus Kartengebühr,
        # ohne eigenen Wert gilt der allgemeine Aufschlag
        self.assertEqual((info["JP"]["card"], info["JP"]["vs_mid"]), (None, 1.8))
        self.settings["countries"]["JP"]["markup_pct"] = ""
        self.assertEqual(planner.pay_info(self.data, self.settings, now=NOW)["JP"]["vs_mid"], 5.0)
        self.settings["countries"]["JP"]["markup_pct"] = 1.75
        jp = self.by(planner.plans(self.data, self.settings, now=NOW))["JP"]
        self.assertAlmostEqual(jp["cost"], round(1400 / 177.3267 * 1.0175, 2))
        # Karten ohne Preis nutzen denselben Aufschlag: 1400 ¥ -> 2x 1000 ¥ zum Nennwert
        self.settings["countries"]["JP"]["cards"] = "1000\n3000"
        jp = self.by(planner.plans(self.data, self.settings, now=NOW))["JP"]
        self.assertAlmostEqual(jp["cost"], round(2000 / 177.3267 * 1.0175, 2))
        self.assertEqual(jp["rest"], 600.0)

    def test_split_basket_over_card_countries(self):
        basket = ["hades", "spiritfarer", "nidhogg-2"]
        _, split = planner.plans(self.data, self.settings, basket=basket, now=NOW, with_mix=True)
        # Hades in Norwegen (9,50 €), Spiritfarer in DE (6,24 €), Nidhogg 2 nur in DE (14,99 €)
        self.assertAlmostEqual(split["cost"], round(100 / 10.7155 * 1.0175 + 6.24 + 14.99, 2))
        self.assertEqual([p["code"] for p in split["parts"]], ["DE", "NO"])
        self.assertEqual(split["parts"][1]["titles"], ["Hades"])
        # Good Job! gibt es in keinem Kartenland außer DE, also bleibt der Mix möglich
        _, split = planner.plans(self.data, self.settings, basket=["good-job"], now=NOW, with_mix=True)
        self.assertEqual([p["code"] for p in split["parts"]], ["DE"])
        self.data["prices"]["DE"]["good-job"] = {"status": "not_found"}
        _, split = planner.plans(self.data, self.settings, basket=["good-job"], now=NOW, with_mix=True)
        self.assertIsNone(split)                    # nur in Brasilien: kein Mix
        _, split = planner.plans(self.data, self.settings, now=NOW, with_mix=True)
        self.assertIsNone(split)                    # ohne gemeinsamen Korb

    def test_owned_flags(self):
        self.data["owned"] = ["hades", "vampire-survivors"]
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        rows = {i["slug"]: i for i in br["items"]}
        self.assertTrue(rows["hades"]["owned"])
        self.assertEqual((rows["vs-foscari"]["owned"], rows["vs-foscari"]["parent_owned"]), (False, True))
        self.assertIsNone(rows["hades"]["parent_owned"])        # kein DLC

    def test_matrix(self):
        m = planner.matrix(self.data, self.settings, now=NOW)
        row = {r["slug"]: r for r in m["rows"]}
        self.assertEqual(row["hades"]["best"], "BR")
        self.assertEqual(row["hades"]["champ"]["code"], "BR")         # Bestpreis-Land
        self.assertIsNone(row["good-job"]["best"])                    # nirgends im Angebot
        self.assertTrue(row["good-job"]["cells"]["NO"]["na"])
        self.assertNotIn("JP", row["good-job"]["cells"])
        # Landestief in Euro zum heutigen Kurs; ohne geladenen Tiefstpreis None
        de = row["hades"]["cells"]["DE"]
        self.assertTrue(de["low_eur"] is None or de["low_eur"] <= de["eur"])
        self.data["lows"] = {"BR": {"hades": {"low": 30.0}}}
        br = {r["slug"]: r for r in planner.matrix(self.data, self.settings, now=NOW)["rows"]}["hades"]["cells"]["BR"]
        self.assertLess(br["low_eur"], br["eur"])

    def test_card_share_fits_the_purchase(self):
        # Eine große Karte ist je Real billiger, aber für ein Spiel zu 7,50 R$ kauft
        # niemand 250 R$: es zählt die 15er Karte, anteilig (Entscheidung 12.10.2026)
        self.settings["countries"]["BR"]["cards"] = "15=3.00 250=40.00"
        cells = {r["slug"]: r for r in planner.matrix(self.data, self.settings, now=NOW)["rows"]}
        nid = cells["nidhogg-2"]["cells"]["BR"]
        self.assertEqual(nid["eur"], 1.5)                       # 3,00 € × 7,50 / 15
        self.assertEqual(nid["alone"]["cards"], [{"face": 15.0, "count": 1}])
        # Im Paket teilen sich die Titel die Karten: die Summe ist, was die Spiele kosten
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        self.assertAlmostEqual(sum(i["eur"] for i in br["items"]), br["games_cost"], places=1)

    def test_alone_bought(self):
        ctx = planner.Context(self.data, self.settings, NOW)
        br = ctx.countries["BR"]
        # Hades allein: 33,59 BRL brauchen 15+25 für 7,80 €, 6,41 BRL bleiben übrig
        a = ctx.alone(br, br["offers"]["hades"]["local"])
        self.assertEqual(a, {"eur": 7.8, "rest": 6.41,
                             "cards": [{"face": 25.0, "count": 1}, {"face": 15.0, "count": 1}]})
        # Ohne Karten gleicht der Einzelpreis dem Anteilspreis: kein Hinweis
        de = ctx.countries["DE"]
        self.assertIsNone(ctx.alone(de, de["offers"]["hades"]["local"]))
        cell = planner.matrix(self.data, self.settings, now=NOW)
        hades = {r["slug"]: r for r in cell["rows"]}["hades"]["cells"]["BR"]
        self.assertEqual(hades["alone"]["eur"], 7.8)

    def test_purchase_plan_drops_weak_countries(self):
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        steps = [(s["code"], [i["slug"] for i in s["items"]]) for s in plan["steps"]]
        # Hades liegt nur in Brasilien am Bestpreis aller Länder. Brasilien spart 19,64 €
        # (ohne den Rest) und verfehlt die Schwelle von 20 € der Stufe schwer. Japan ist
        # zu weit vom Bestpreis weg, also warten Hades und VS Foscari.
        self.assertEqual(steps, [("DE", ["spiritfarer"])])
        self.assertEqual([d["code"] for d in plan["dropped"]], ["BR"])
        self.assertAlmostEqual(plan["dropped"][0]["saving"], 19.65)
        self.assertEqual([x["slug"] for x in plan["later"]], ["hades", "vs-foscari"])
        self.assertAlmostEqual(plan["cost"], 6.24)
        self.assertEqual(plan["count"], 1)

    def test_ui_fields_for_signals(self):
        # Die Oberfläche färbt Preise nach dem Urteil und nennt Titel, deren Wechsel nicht lohnt
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        self.assertEqual(len(plan["dropped"][0]["slugs"]), len(plan["dropped"][0]["titles"]))
        self.assertIn("hades", plan["dropped"][0]["slugs"])
        item = plan["steps"][0]["items"][0]
        self.assertIn(item["grade"], ("buy", "good", "wait", "none"))
        rows = {r["slug"]: r for r in planner.matrix(self.data, self.settings, now=NOW)["rows"]}
        self.assertEqual(rows["hades"]["cells"]["BR"]["grade"], "buy")
        for r in rows.values():
            for c in r["cells"].values():
                self.assertIn(c.get("grade"), ("buy", "good", "wait", "none", None))

    def test_price_history_from_own_records(self):
        h = {"BR": {"hades": [["2026-09-01T00:00:00+00:00", 83.99],
                              ["2026-09-10T00:00:00+00:00", 41.99],
                              ["2026-09-20T00:00:00+00:00", 83.99],
                              ["2026-10-01T00:00:00+00:00", 33.59]]},
             "DE": {"hades": [["2026-09-01T00:00:00+00:00", 24.99]]},
             "SE": {"hades": [["2026-09-01T00:00:00+00:00", 249]]}}   # abgeschaltet
        v = planner.price_history(self.data, self.settings, h, "hades", now=NOW)
        self.assertEqual(v["since"], "2026-09-01T00:00:00+00:00")
        self.assertEqual([c["code"] for c in v["countries"]], ["DE", "BR"])
        br = v["countries"][1]
        # Zwei Angebote: eins abgeschlossen (10 Tage), eins läuft noch
        self.assertEqual(br["sale_count"], 2)
        self.assertEqual([s["end"] for s in br["sales"]], ["2026-09-20T00:00:00+00:00", None])
        self.assertEqual([s["pct"] for s in br["sales"]], [50, 60])
        self.assertEqual(br["typical_days"], 10.0)
        self.assertEqual(br["low"], 33.59)
        self.assertEqual(br["low_eur"], 6.55)    # zum heutigen Kurs, mit 25er und 15er Karte anteilig
        self.assertEqual(br["points"][1][2], 8.4)     # 41,99 R$: drei 15er Karten für 9 €, anteilig
        self.assertEqual(br["on_sale_pct"], round(100 * (10 + 10.7083) / 40.7083))
        de = v["countries"][0]
        self.assertEqual((de["sale_count"], de["on_sale_pct"], de["typical_days"]), (0, 0, None))
        # Ohne Aufzeichnung: leere Liste, kein Fehler
        self.assertEqual(planner.price_history(self.data, self.settings, {}, "hades", now=NOW)
                         ["countries"], [])

    def test_purchase_plan_keeps_country_above_threshold(self):
        # Gegenüber Deutschland spart Brasilien 19,65 €, gegenüber Japan und Norwegen nur
        # 2,60 €: Bei einer Schwelle von 15 € lohnt der Wechsel nach Amerika nicht
        self.settings["tier_min_saving"]["3"] = 15
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        self.assertEqual([s["code"] for s in plan["steps"]], ["DE"])
        self.assertEqual([(d["code"], d["gain"], d["saving"]) for d in plan["dropped"]], [("BR", 2.6, 19.65)])
        self.settings["tier_min_saving"]["3"] = 2
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        steps = [(s["code"], [i["slug"] for i in s["items"]]) for s in plan["steps"]]
        self.assertEqual(steps, [("DE", ["spiritfarer"]), ("BR", ["hades", "vs-foscari"])])
        self.assertEqual(plan["dropped"], [])
        self.assertAlmostEqual(plan["cost"], 14.04)
        # Brasilien ist der letzte Schritt: Der Rest bleibt auf dem Konto und ist kein Verlust
        self.assertAlmostEqual(plan["saving"], 19.65)
        self.assertEqual(plan["rest_lost"], 0)
        # Gute Angebote gibt es im Beispiel nicht, der Schalter ändert nichts
        self.assertEqual(planner.purchase_plan(self.data, self.settings, include_good=True,
                                               now=NOW)["count"], 3)

    def test_purchase_plan_counts_rest_before_a_switch(self):
        # Konto steht in Brasilien: Brasilien kommt zuerst, danach Deutschland. Der Rest in
        # Brasilien verfällt beim Wechsel und zählt deshalb als Kosten
        self.settings["current_country"] = "BR"
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        self.assertEqual([s["code"] for s in plan["steps"]], ["BR", "DE"])
        br = plan["steps"][0]
        self.assertAlmostEqual(br["rest_lost"], 0.47, places=2)
        self.assertAlmostEqual(br["games_cost"], 7.8)          # die Karten ganz
        self.assertAlmostEqual(plan["rest_lost"], 0.47, places=2)
        self.assertAlmostEqual(plan["saving"], round(19.65 - 0.47, 2), places=1)
        self.assertNotIn("rest_lost", plan["steps"][1])         # letzter Schritt: Rest bleibt

    def test_verdict_same_rule_in_every_country(self):
        # Echter Fall: ein DLC in Brasilien wenige Cent über dem Bestpreis war "warten", weil schwere
        # Länder nur genau am Bestpreis zählten. Jetzt gilt dieselbe Grenze überall
        self.data["lows"] = {"BR": {"vs-foscari": {"low": 3.6}}}
        r = {x["slug"]: x for x in planner.radar(self.data, self.settings, now=NOW)}["vs-foscari"]
        self.assertEqual((r["verdict"], r["at"]["code"]), ("buy", "BR"))
        self.assertEqual(r["reason"], "nur 0,08 € über Bestpreis in Brasilien (schwer)")

    def test_best_price_from_history_of_24_months(self):
        # Allzeit 2,00 R$ (2019), in den letzten 24 Monaten nie unter 30 R$: Bestpreis ist 30 R$
        self.data["lows"] = {"BR": {"hades": {"low": 2.0, "hist": [["2019-05", 2.0], ["2025-02", 30.0],
                                                                   ["2026-01", 33.59]]}}}
        ctx = planner.Context(self.data, self.settings, NOW)
        self.assertEqual(ctx.low_value("BR", "hades"), 30.0)
        # Eigene Aufzeichnung zählt mit
        self.data["lows"]["BR"]["hades"]["own_low"] = 29.0
        self.assertEqual(planner.Context(self.data, self.settings, NOW).low_value("BR", "hades"), 29.0)
        # Seite für Switch und Switch 2: offen, zu welcher Fassung der Verlauf gehört, dann Allzeit
        self.data["lows"]["BR"]["hades"].update(hist_multi=True)
        self.assertEqual(planner.Context(self.data, self.settings, NOW).low_value("BR", "hades"), 2.0)
        # Ohne Verlauf im Zeitraum: Allzeit-Tiefstpreis
        self.data["lows"]["BR"]["hades"] = {"low": 25.0, "hist": [["2019-05", 2.0]]}
        self.assertEqual(planner.Context(self.data, self.settings, NOW).low_value("BR", "hades"), 25.0)
        self.assertEqual(sources.month_lows([("2025-01-01", 20), ("2025-01-09", 12), ("2025-02-01", 15)]),
                         [["2025-01", 12], ["2025-02", 15]])

    def test_case_export_without_wishlist_link(self):
        self.settings["wishlist_url"] = "https://www.dekudeals.com/wishlist/geheim"
        out = planner.case_export(self.data, self.settings, {"BR": {"hades": [["2026-10-01", 33.59]]}},
                                  "hades", now=NOW)
        self.assertEqual(out["settings"]["wishlist_url"], "")
        self.assertNotIn("geheim", json.dumps(out))
        self.assertEqual(set(out["prices"]), {"DE", "NO", "BR", "JP"})
        self.assertEqual(out["history"], {"BR": [["2026-10-01", 33.59]]})
        self.assertEqual(out["radar"]["verdict"], "buy")

    def test_lasting_cheaper_regular_price(self):
        # Good-Job ist in Brasilien dauerhaft günstiger. Ein Angebot in Deutschland, das
        # darüber liegt, heißt "warten", mit dem richtigen Grund
        sale = {"start": "2026-10-01T00:00:00Z", "end": "2026-10-20T00:00:00Z"}
        de = self.data["prices"]["DE"]
        de["good-job"] = dict(de["good-job"], discount=15.99, **sale)
        r = {x["slug"]: x for x in planner.radar(self.data, self.settings, now=NOW)}["good-job"]
        self.assertEqual(r["verdict"], "wait")
        self.assertEqual(r["reason"], "in Brasilien dauerhaft 11,98 €")


class StoreTest(unittest.TestCase):
    def test_ui_state_and_settings_validation(self):
        ui = store.save_ui({"basket": ["a", "b"], "targets": {"a": "8,5", "b": "7.5", "c": 0},
                            "hidden": ["NZ"], "sort": "quatsch", "dense": 0,
                            "overrides": {"BR": {"add": ["x"], "remove": None}}})
        self.assertEqual(ui["basket"], ["a", "b"])
        self.assertEqual(ui["targets"], {"b": 7.5})          # nur gültige Zahlen
        self.assertEqual((ui["sort"], ui["dense"], ui["hidden"]), ("optimum", False, ["NZ"]))
        s = store.save_settings({"lang_confirm": {"hades": {"JP": True, "AM": "x", "EU": False}}})
        self.assertEqual(s["lang_confirm"], {"hades": {"JP": True}})
        s = store.save_settings({"lang_confirm": {"hades": {"JP": None}}})
        self.assertEqual(s["lang_confirm"], {})
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


class SafetyTest(unittest.TestCase):
    def test_settings_migration_and_deal_limits(self):
        with open(os.path.join(store.DATA_DIR, "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"countries": {"JP": {"rest_blocks": True}}}, f)     # Stand 0.6
        s = store.load_settings()
        self.assertFalse(s["countries"]["JP"]["rest_blocks"])            # Rest verfällt nur
        self.assertEqual(s["deal_eur"], {"buy": 0.5, "good": 2.0})
        s = store.save_settings({"deal_eur": {"buy": "0,3", "good": -4, "x": 1}})
        self.assertEqual(s["deal_eur"], {"buy": 0.5, "good": 0.0})
        s = store.save_settings({"countries": {"JP": {"rest_blocks": True}}})
        self.assertTrue(store.load_settings()["countries"]["JP"]["rest_blocks"])  # deine Wahl bleibt
        store.save_settings({"countries": {"JP": {"rest_blocks": False}}})
        # 0.8.1 speicherte pauschal 10,5 % Eneba-Gebühr: wird zur gemessenen Formel
        with open(os.path.join(store.DATA_DIR, "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"settings_v": 1, "shop_fee_pct": 10.5}, f)
        s = store.load_settings()
        self.assertEqual((s["shop_fee_pct"], s["shop_fee_eur"], s["settings_v"]), (7.75, 0.4, 3))
        # Bis 0.9.2 standen deutsche Karten bei Deutschland: sie wandern zu „Deutschland mit Guthaben“
        with open(os.path.join(store.DATA_DIR, "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"settings_v": 2, "countries": {"DE": {"cards": "20 | https://shop.example/de20"}}}, f)
        s = store.load_settings()
        self.assertEqual((s["countries"]["DE"]["cards"], s["countries"]["DG"]["cards"],
                          s["countries"]["DG"]["enabled"]), ("", "20 | https://shop.example/de20", True))
        # Eine ältere Einlese-Datei mit Karten für Deutschland landet ebenso dort
        s = store.save_settings({"countries": {"DE": {"cards_add": "25 | https://shop.example/de25"}}})
        self.assertEqual(s["countries"]["DE"]["cards"], "")
        self.assertIn("de25", s["countries"]["DG"]["cards"])

    def test_cards_can_be_added_from_a_file(self):
        store.save_settings({"countries": {"US": {"cards": "x 10 = 8,50\n5 = 4,20\n25 50=41"}}})
        s = store.save_settings({"countries": {"US": {"cards_add":
            "5 | https://shop.example/5\n10 | https://shop.example/10\n50 | https://shop.example/50\n"
            "20 | https://shop.example/20"}}})
        self.assertEqual(s["countries"]["US"]["cards"],
                         "x 10 = 8,50 | https://shop.example/10\n5 = 4,20 | https://shop.example/5\n"
                         "25 50=41\n20 | https://shop.example/20")
        cards = {c["face"]: c for c in planner.parse_card_list(s["countries"]["US"]["cards"])}
        self.assertEqual((cards[500]["cost"], cards[1000]["stock"], cards[5000]["cost"]), (4.2, False, 41.0))
        # zweimal einlesen ändert nichts
        again = store.save_settings({"countries": {"US": {"cards_add": "5 | https://shop.example/5"}}})
        self.assertEqual(again["countries"]["US"]["cards"], s["countries"]["US"]["cards"])
        store.save_settings({"countries": {"US": {"cards": ""}}})

    def test_blocked_sources_stop_the_run(self):
        data = {"items": {f"t{i}": {"title": f"T{i}", "active": True, "ids": {}, "ids_checked": {}}
                          for i in range(5)}, "prices": {}, "lows": {}}
        settings = store.load_settings()
        calls = []

        def deny(url, ua=None):
            calls.append(url)
            raise sources.FetchError(url, 429)
        with self.assertRaises(RuntimeError) as ctx:
            sync.sync_ids(data, settings, deny, lambda s: None, now=10 ** 9)
        self.assertIn("HTTP 429", str(ctx.exception))
        self.assertEqual(len(calls), 1)                    # nach der ersten Sperre Schluss
        for it in data["items"].values():
            it["ids"] = {"EU": ["70010000000001"]}
        calls.clear()
        sync.sync_prices(data, settings, deny, lambda s: None, {})
        self.assertEqual(len(calls), 1)
        self.assertIn("lehnt Preisabrufe ab", sync.status["log"][-1])

    def test_post_needs_json(self):
        import http.client
        import threading
        from http.server import ThreadingHTTPServer
        from app import server
        srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            def post(ctype):
                c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
                c.request("POST", "/api/settings", body='{"wishlist_url": "x"}',
                          headers={"Content-Type": ctype})
                status = c.getresponse().status
                c.close()
                return status
            before = store.load_settings()["wishlist_url"]
            self.assertEqual(post("text/plain"), 400)       # einfaches Formular einer fremden Seite
            self.assertEqual(store.load_settings()["wishlist_url"], before)
            self.assertEqual(post("application/json; charset=utf-8"), 200)
            self.assertEqual(store.load_settings()["wishlist_url"], "x")
            store.save_settings({"wishlist_url": before})
            # Lesende Schnittstellen antworten mit JSON, auch ohne Aufzeichnung
            for path in ("/api/kaufplan", "/api/verlauf?slug=gibt-es-nicht"):
                c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
                c.request("GET", path)
                r = c.getresponse()
                body = json.loads(r.read())
                c.close()
                self.assertEqual(r.status, 200, path)
                self.assertIsInstance(body, dict)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_card_shop_price_and_diagnosis(self):
        page = ('<script type="application/ld+json">{"@type":"Product","offers":'
                '{"@type":"AggregateOffer","lowPrice":"52.37","priceCurrency":"EUR"}}</script>')
        self.assertEqual(sources.parse_ld_price(page), (52.37, "EUR"))
        self.assertIsNone(sources.parse_ld_price("<div id=app></div>"))
        # Mehrere Angebote: das günstigste zählt, nicht das zuletzt genannte oder ein Höchstpreis
        many = ('<script type="application/ld+json">{"@type":"Product","offers":['
                '{"@type":"Offer","price":"18.10","priceCurrency":"EUR"},'
                '{"@type":"Offer","price":"24.38","priceCurrency":"EUR"},'
                '{"@type":"AggregateOffer","highPrice":"30.00","lowPrice":"18.40","priceCurrency":"EUR"}]}</script>')
        self.assertEqual(sources.parse_ld_price(many), (18.10, "EUR"))
        store.save_settings({"wishlist_url": "https://www.dekudeals.com/wishlist/abc",
                             "countries": {"US": {"cards": "50 = 41 | https://www.eneba.com/x"}}})
        seen = []

        def fake_request(url, ua=None, timeout=25):
            seen.append(ua)
            text = page if "eneba" in url else "<title>Seite</title><p>Text</p>"
            return {"url": url, "status": 200, "text": text, "enc": "", "server": "t", "error": ""}
        old = sources.request
        sources.request = fake_request
        try:
            lines = sync.diagnose()
        finally:
            sources.request = old
            store.save_settings({"countries": {"US": {"cards": ""}}})
        text = "\n".join(lines)
        self.assertIn("Guthabenkarte US (www.eneba.com)", text)
        self.assertIn("Preis in Produktdaten: (52.37, 'EUR')", text)
        self.assertIn("Sprachen Japan", text)
        self.assertIn("price_history_data: nicht gefunden", text)
        self.assertEqual(set(seen), {None})                # immer die eigene Kennung


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
            if "/collection/" in url:
                return ('<a href="/items/vampire-survivors">x</a>' if "page=1" in url else "")
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
            if "gg.deals" in url:
                if "brl-brazil" in url:
                    return ('<a href="/de/gift-card/nintendo-eshop-gift-card-50-brl/">50 BRL</a>'
                            '<span>~8,05€</span>')
                return "<p>leer</p>"
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
        self.assertEqual(data["owned"], ["vampire-survivors"])          # Hauptspiel in der Sammlung
        row = planner.radar(data, store.load_settings())[0]
        self.assertEqual((row["owned"], row["parent_owned"]), (False, True))
        price_calls = [u for u in calls if "api.ec.nintendo.com" in u]
        # Preise für alle Länder mit bekannten IDs (Europa und Amerika), nicht für Japan und Asien
        self.assertEqual(len(price_calls), 19)
        self.assertIn("CL", data["price_fail"])
        # gg.deals: eine Seite je aktivem Land mit Guthaben (hier BR, JP). Deutschland zum
        # Shop-Preis braucht keine, „Deutschland mit Guthaben“ ist abgeschaltet
        gg = [u for u in calls if "gg.deals" in u]
        self.assertEqual(len(gg), len(set(gg)))
        self.assertEqual(data["card_market"]["BR"]["cards"]["50"]["price"], 8.05)
        self.assertEqual(set(data["card_market"]), {"BR", "JP"})
        self.assertNotIn("DG", data["prices"])                           # kein eigener eShop
        self.assertFalse(any("Preisabruf fehlgeschlagen" in l for l in sync.status["log"]))
        n = len(calls)
        sync.run_sync(fetch=fake, sleep=lambda s: None)
        # zweiter Lauf sucht weder IDs, Sprachen noch Tiefstpreise:
        # Wishlist (2), Sammlung (2), Kurse (1), Preise (19 Länder minus das ruhende Chile)
        self.assertEqual(len(calls) - n, 2 + 2 + 1 + 18)
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


    def test_low_from_history_when_page_names_none(self):
        # DekuDeals nennt nur einen Händler-Tiefstpreis: der digitale Verlauf hilft aus.
        # Seiten, die früher ohne Tiefstpreis gelesen wurden, kommen einmal neu dran.
        settings = store.load_settings()
        data = {"items": {"a": {"active": True}},
                "prices": {"DE": {"a": {"status": "onsale", "regular": 20}}},
                "lows": {"DE": {"a": {"checked": 1736467200}}}}
        got, orig = [], sources.fetch_item
        sources.fetch_item = lambda slug, country, fetch=None: (
            got.append(slug) or {"low": None, "history": [("2025-01-01", 20.0), ("2025-02-01", 13.0)]})
        try:
            sync.sync_lows(data, settings, fetch=None, sleep=lambda s: None, now=1736467200 + 60)
            self.assertEqual((got, data["lows"]["DE"]["a"]["low"]), (["a"], 13.0))
        finally:
            sources.fetch_item = orig

    def test_sale_history_is_loaded_politely(self):
        settings = store.load_settings()
        data = {"items": {"a": {"active": True}, "b": {"active": True}},
                "prices": {"DE": {"a": {"status": "onsale", "regular": 20, "discount": 10},
                                  "b": {"status": "onsale", "regular": 20}}},
                "lows": {"DE": {"a": {"low": 9.0, "checked": 1}, "b": {"low": 9.0, "checked": 1}}}}
        series = [("2025-01-0%d" % d, v) for d, v in ((1, 20), (2, 10), (3, 20), (4, 20), (5, 12))]
        got, orig = [], sources.fetch_item
        sources.fetch_item = lambda slug, country, fetch=None: (
            got.append(slug) or {"low": 9.0, "history": series})
        try:
            sync.sync_lows(data, settings, fetch=None, sleep=lambda s: None, now=1736467200)
            # Beide einmal: a im Angebot (zuerst), b für die Monatstiefstwerte (seit 0.16)
            self.assertEqual(got, ["a", "b"])
            self.assertEqual(data["lows"]["DE"]["b"]["hist"], [["2025-01", 10]])
            e = data["lows"]["DE"]["a"]
            self.assertEqual((e["sales"], e["sales_at"]), ([["2025-01-02", 10], ["2025-01-05", 12]], 1736467200))
            sync.sync_lows(data, settings, fetch=None, sleep=lambda s: None, now=1736467200 + 86400)
            self.assertEqual(got, ["a", "b"])                  # frisch: kein zweiter Abruf
            # Seite mit Tiefstpreisen für Switch und Switch 2: Verlauf gilt nicht als Bestpreis
            e = {}
            sync._store_low({"lows": {"DE": {"c": e}}}, settings, "DE", "c", 9.0, 1, series, platforms=2)
            self.assertEqual((e.get("hist_multi"), "hist" in e, e["hist_v"]), (True, False, sync.HIST_V))
        finally:
            sources.fetch_item = orig


class GgdealsBlockTest(unittest.TestCase):
    def test_blocked_ggdeals_rests_for_a_day(self):
        data, settings = sample()
        settings["countries"]["JP"]["pay"] = "giftcard"
        calls = []

        def deny(url, ua=None):
            calls.append(url)
            raise sources.FetchError(url, 403)
        t0 = NOW.timestamp()
        sync.sync_card_market(data, settings, deny, lambda s: None, now=t0)
        self.assertEqual(len(calls), 1)                         # nach der ersten Sperre Schluss
        self.assertEqual({c for c, e in data["card_market"].items() if "sperrt" in e["error"]}, {"JP", "BR"})
        sync.sync_card_market(data, settings, deny, lambda s: None, now=t0 + 3600)
        self.assertEqual(len(calls), 1)                         # heute nicht noch einmal
        sync.sync_card_market(data, settings, deny, lambda s: None, now=t0 + 86400)
        self.assertEqual(len(calls), 2)


class PurchaseLogTest(unittest.TestCase):
    def setUp(self):
        for name in ("settings.json", "purchases.json"):
            try:
                os.remove(os.path.join(store.DATA_DIR, name))
            except FileNotFoundError:
                pass

    def test_bought_sets_country_and_rest_and_can_be_undone(self):
        s = store.load_settings()
        s["current_country"] = "DE"
        s["countries"]["US"]["balance"] = 3.0
        store._save("settings.json", s)
        store.record_purchase({"code": "BR", "slugs": ["hades"], "titles": ["Hades"],
                               "cost": 7.8, "de": 24.99, "rest": 2.41, "currency": "BRL"})
        s = store.load_settings()
        self.assertEqual(s["current_country"], "BR")
        self.assertEqual(s["countries"]["BR"]["balance"], 2.41)
        self.assertEqual(s["countries"]["US"]["balance"], 0.0)    # Guthaben geht beim Wechsel nicht mit
        self.assertEqual(len(store.load_purchases()), 1)
        store.undo_purchase()
        s = store.load_settings()
        self.assertEqual((s["current_country"], s["countries"]["US"]["balance"],
                          s["countries"]["BR"]["balance"]), ("DE", 3.0, 0.0))
        self.assertEqual(store.load_purchases(), [])

    def test_plan_skips_bought_titles(self):
        data, settings = sample()
        bought = [{"at": "2026-10-11T20:00:00+00:00", "code": "JP", "slugs": ["hades"],
                   "titles": ["Hades"], "cost": 8.0, "de": 24.99, "rest": 0, "currency": "JPY"}]
        plan = planner.purchase_plan(data, settings, now=NOW, bought=bought)
        self.assertNotIn("hades", [i["slug"] for p in plan["steps"] for i in p["items"]])
        self.assertEqual(plan["bought_waiting"], ["Hades"])
        self.assertAlmostEqual(plan["bought_saving"], 16.99)


class SelfCheckTest(unittest.TestCase):
    def test_self_check_flags_jumps_drops_and_odd_cards(self):
        data, settings = sample()
        data["fx"]["updated"] = "Sat, 10 Oct 2026 00:02:31 +0000"
        first = sync.self_check(data, settings, now=NOW)
        self.assertEqual(first["warnings"], [])
        self.assertIn("NO", first["units"])
        # Kurs springt, Brasilien verliert fast alle Titel, eine Karte ist unglaubhaft
        data["fx"]["rates"]["NOK"] = 10.7155 * 1.3
        data["fx"]["updated"] = "2026-10-01"
        for slug in list(data["prices"]["BR"])[1:]:
            data["prices"]["BR"][slug]["status"] = "not_found"
        data["card_market"] = {"BR": {"checked": NOW.timestamp(), "cards": {
            "50": {"price": 0.35, "url": "https://gg.deals/a"}}}}
        w = " | ".join(sync.self_check(data, settings, now=NOW)["warnings"])
        self.assertIn("Norwegen: Preis je NOK", w)
        self.assertIn("Brasilien: nur noch 1 statt 5 Titel kaufbar", w)
        self.assertIn("Kartenpreis 50 BRL für 0,35 €", w)
        self.assertIn("Wechselkurse sind 10 Tage alt", w)


if __name__ == "__main__":
    unittest.main()
