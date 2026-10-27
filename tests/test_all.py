import gzip
import html
import json
import os
import re
import urllib.parse
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

from app import countries, kaufplan, planner, sources, store, sync  # noqa: E402

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


_head_patch = mock.patch.object(sources, "head", lambda url, timeout=20: {
    "status": 200, "error": "", "size": "25000000", "modified": "Mon, 12 Oct 2026 08:00:00 GMT"})


def setUpModule():
    _head_patch.start()          # Kopfdaten-Proben (titledb) ohne Netz


def tearDownModule():
    _head_patch.stop()


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
        self.assertEqual(runs, [["2024-05-04", 6.65, "2024-05-05"], ["2024-05-09", 7.99, "2024-05-09"]])
        self.assertEqual(sources.sale_runs(series, since="2024-05-06"), [["2024-05-09", 7.99, "2024-05-09"]])
        self.assertEqual(sources.parse_item_page(page)["history"], series)
        self.assertEqual(sources.parse_history("<html>ohne Verlauf</html>"), [])

    def test_languages_americas(self):
        page = ('<script id="__NEXT_DATA__">{"product":{"supportedLanguages":'
                '["English","French","Spanish"]}}</script>')
        self.assertEqual(sources.parse_langs_am(page), "english, french, spanish")
        page = '<h3>Supported languages</h3><p>English, German</p>'
        self.assertEqual(sources.parse_langs_am(page), "english, german")
        self.assertIsNone(sources.parse_langs_am("<p>Nichts</p>"))
        # Pakete liegen unter bundles, Spiele und DLC unter titles
        urls = []
        sources.fetch_langs_am("70070000000001", fetch=lambda u: urls.append(u) or "")
        sources.fetch_langs_am("70010000000001", fetch=lambda u: urls.append(u) or "")
        self.assertEqual(urls, ["https://ec.nintendo.com/US/en/bundles/70070000000001",
                                "https://ec.nintendo.com/US/en/titles/70010000000001"])
        self.assertEqual(sources.ec_url(planner.LANG_CHECK_URL["JP"], "70070000000001"),
                         "https://store-jp.nintendo.com/item/software/D70070000000001")

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
        # Zahlen ohne Währung sind keine Preise (1.0.5): Verbindungstest zeigte 768 und 100
        self.assertEqual(sources.parse_lows("All time low <div style='max-width:768'>100</div> Time range"), [])
        self.assertEqual(sources.parse_lows("All time low 3 offers Digital 62,00 kr Time range"), [62.0])
        self.assertIn("Digital", sources.low_snippet("<b>All time low</b> <td>Digital</td> €5,91"))

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
    settings["deal_eur"]["mini"] = 0   # die Beispielpreise sind klein; Kleinkram prüft MiniTest
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


class MiniTest(unittest.TestCase):
    """Kleinkram unter deal_eur.mini (0.92): keine größere Guthabenkarte, „kaufen“ nur bis 2 %."""
    def setUp(self):
        self.data, self.settings = sample()
        self.settings["deal_eur"]["mini"] = 2.0
        self.settings["current_country"] = "DE"
        for code, c in self.settings["countries"].items():
            c["enabled"] = code in ("DE", "BR")
        items, de, br = {}, {}, {}
        for i, (slug, eur, brl) in enumerate([("big", 49.99, 47), ("m1", 1.99, 4), ("m2", 1.99, 3),
                                               ("m3", 1.99, 2.5)]):
            items[slug] = {"title": slug.title(), "parent": None, "active": True, "order": i,
                           "ids": {"EU": ["1"]}, "ids_checked": {}}
            de[slug] = {"status": "onsale", "currency": "EUR", "regular": eur}
            br[slug] = {"status": "onsale", "currency": "BRL", "regular": brl}
        self.data.update(items=items, prices={"DE": de, "BR": br})

    def plan(self):
        return planner.purchase_plan(self.data, self.settings, now=NOW)

    def test_minis_only_fill_the_rest(self):
        # Ab 0.98 nie von selbst: Kleinkram wartet und steht unter „Passt in den Rest“ zur Auswahl
        k = self.plan()
        br = next(p for p in k["steps"] if p["code"] == "BR")
        self.assertEqual([i["slug"] for i in br["items"]], ["big"])
        self.assertEqual([(c["face"], c["count"]) for c in br["cards"]], [(50.0, 1)])
        self.assertEqual(sorted(x["slug"] for x in k["small"]), ["m1", "m2", "m3"])
        self.assertEqual(sorted(f["slug"] for f in br["fill"]), ["m2", "m3"])     # 3 R$ Rest
        self.assertNotIn("DE", [p["code"] for p in k["steps"]])

    def test_mini_follows_best_price(self):
        # Kleinkram nach dem Bestpreis wie beim Urteil, im Kaufplan nicht nach dem heutigen Preis (0.99.5)
        ctx = planner.Context(self.data, self.settings, NOW)
        ctx.champ_all.update(x=(1.80, None), y=(2.50, None))
        self.assertTrue(ctx.mini("x", 2.40))
        self.assertFalse(ctx.mini("y", 1.50))
        self.assertTrue(ctx.mini("ohne-bestpreis", 1.50))

    def test_taken_filler_counts_like_a_big_title(self):
        # Selbst in den Schritt genommen: bleibt drin, und der Kleinkram füllt den Rest danach
        k = planner.purchase_plan(self.data, self.settings, now=NOW, fill={"BR": ["m1"]})
        br = next(p for p in k["steps"] if p["code"] == "BR")
        self.assertIn("m1", [i["slug"] for i in br["items"]])
        self.assertNotIn("m1", [x["slug"] for x in k["small"]])

    def test_waiting_minis_are_grouped_as_a_suggestion(self):
        # Je Land mit Summe; füllt der Kleinkram eine Karte fast ganz, ist das nur ein Vorschlag (0.93)
        k = self.plan()
        g = k["small_groups"][0]
        self.assertEqual((g["code"], sorted(g["slugs"]), g["local"], g["step"]), ("BR", ["m1", "m2", "m3"], 9.5, True))
        self.assertFalse(g["full"])                                   # 9,50 von 15: weit weg
        for slug, brl in (("m4", 3.9), ("m5", 1.1)):                  # 9,5 + 5 = 14,5 von 15
            self.data["items"][slug] = dict(self.data["items"]["m1"], title=slug)
            self.data["prices"]["DE"][slug] = dict(self.data["prices"]["DE"]["m1"])
            self.data["prices"]["BR"][slug] = dict(self.data["prices"]["BR"]["m1"], regular=brl)
        g = self.plan()["small_groups"][0]
        self.assertTrue(g["full"])
        self.assertEqual([(c["face"], c["count"]) for c in g["cards"]], [(15.0, 1)])
        br = next(p for p in self.plan()["steps"] if p["code"] == "BR")
        self.assertEqual([i["slug"] for i in br["items"]], ["big"])   # nichts still dazu

    def test_without_limit_minis_enlarge_the_cards(self):
        self.settings["deal_eur"]["mini"] = 0
        k = self.plan()
        br = next(p for p in k["steps"] if p["code"] == "BR")
        self.assertEqual(len(br["items"]), 4)
        self.assertEqual(k["small"], [])
        self.assertGreater(sum(c["face"] * c["count"] for c in br["cards"]), 50)

    def test_minis_alone_wait_for_a_rest(self):
        del self.data["items"]["big"]
        k = self.plan()
        self.assertEqual([p["code"] for p in k["steps"]], [])
        self.assertEqual(len(k["small"]), 3)
        # Auch Guthaben, das schon dort liegt, füllen sie ab 0.98 nicht mehr von selbst
        self.settings["current_country"] = "BR"
        self.settings["countries"]["BR"]["balance"] = 7
        k = self.plan()
        self.assertEqual([p["code"] for p in k["steps"]], [])
        self.assertEqual(len(k["small"]), 3)

    def test_minis_paid_by_card_stay(self):
        self.settings["countries"]["BR"]["pay"] = "card"
        k = self.plan()
        self.assertEqual(len(next(p for p in k["steps"] if p["code"] == "BR")["items"]), 4)
        self.assertEqual(k["small"], [])

    def test_buy_only_within_two_percent(self):
        ctx = planner.Context(self.data, self.settings, NOW)
        ctx.champ_all["m1"] = (1.00, "BR", False)
        self.assertEqual(ctx.grade(1.02, "m1"), "buy")
        self.assertEqual(ctx.grade(1.10, "m1"), "good")
        self.settings["deal_eur"]["mini"] = 0
        self.assertEqual(ctx.grade(1.10, "m1"), "buy")      # 0,50 € darüber wie bisher


class OwnOfferTest(unittest.TestCase):
    """Eigene Angebote für Titel (ab 0.62), etwa Codes bei Amazon Japan."""
    def test_own_offer_replaces_dearer_eshop_and_pays_by_card(self):
        data, settings = sample()
        raw = [{"slug": "spiritfarer", "code": "BR", "price": 30, "src": "Amazon", "url": "https://www.amazon.example/dp/1"},
               {"slug": "hades", "code": "BR", "price": 90, "src": "Amazon"},          # teurer als der eShop
               {"slug": "Kein Slug!", "code": "BR", "price": 5},
               # Anführungszeichen im Link (0.99.1): käme sonst als Attribut in die Oberfläche
               {"slug": "hades", "code": "BR", "price": 5, "url": 'https://a.example/" onmouseover="x'}]
        settings["own_offers"] = [x for x in (store._own_offer(e, settings["countries"]) for e in raw) if x]
        self.assertEqual(len(settings["own_offers"]), 2)
        ctx = planner.Context(data, settings, NOW)
        unit = 1 / 100 / 5.6086 * (1 + settings["card_fee_pct"] / 100)
        o = ctx.countries["BR"]["offers"]["spiritfarer"]
        self.assertAlmostEqual(o["direct"], 3000 * unit)
        self.assertEqual(o["own"]["src"], "Amazon")
        self.assertIsNone(ctx.countries["BR"]["offers"]["hades"].get("direct"))
        # Im Korb: Guthaben nur für den eShop-Titel, der Code kommt obendrauf
        both = {p["code"]: p for p in planner.plans(data, settings, basket=["hades", "spiritfarer"], now=NOW)}["BR"]
        alone = {p["code"]: p for p in planner.plans(data, settings, basket=["hades"], now=NOW)}["BR"]
        self.assertAlmostEqual(both["total"], alone["total"])
        self.assertAlmostEqual(both["cost"], round(alone["cost"] + 3000 * unit, 2), places=2)
        self.assertEqual(both["direct_n"], 1)
        sf = next(i for i in both["items"] if i["slug"] == "spiritfarer")
        self.assertAlmostEqual(sf["eur"], round(3000 * unit, 2))
        self.assertEqual(sf["own"]["src"], "Amazon")
        # Der gelesene Preis gilt vor dem eingetragenen
        data["offer_prices"] = {"https://www.amazon.example/dp/1": {"price": 20.0, "currency": "BRL", "ok": NOW.timestamp(), "checked": NOW.timestamp()}}
        ctx = planner.Context(data, settings, NOW)
        self.assertAlmostEqual(ctx.countries["BR"]["offers"]["spiritfarer"]["direct"], 2000 * unit)


    def test_own_offer_is_no_filler_and_code_rules(self):
        # Ein Code zahlt die Kreditkarte, nicht das Guthaben: kein „passt in den Rest“ (0.63)
        data, settings = sample()
        ctx = planner.Context(data, settings, NOW)
        fill = lambda ctx: [x["slug"] for x in planner._rest_fill(ctx, ctx.countries["BR"], {"rest": 100}, set(), set())]
        self.assertIn("spiritfarer", fill(ctx))
        settings["own_offers"] = [store._own_offer({"slug": "spiritfarer", "code": "BR", "price": 5, "src": "Amazon"},
                                                   settings["countries"])]
        ctx = planner.Context(data, settings, NOW)
        self.assertIsNotNone(ctx.countries["BR"]["offers"]["spiritfarer"].get("direct"))
        self.assertNotIn("spiritfarer", fill(ctx))
        # Ein Code zählt immer zum Kurs plus Kartengebühr, im Euro-Land zum Betrag selbst
        self.assertAlmostEqual(ctx.code_unit(ctx.countries["DE"]), 0.01)
        self.assertAlmostEqual(ctx.code_unit(ctx.countries["BR"]), 1 / 100 / 5.6086 * (1 + settings["card_fee_pct"] / 100))
        # Mitgliedschaft im Rest nur aus dem eShop, nicht als Code
        settings["nso_extra"] = [{"key": "m12", "code": "BR", "price": 1, "src": "Amazon"}]
        plan = planner.purchase_plan(data, settings, now=NOW)
        for p in plan["steps"]:
            self.assertTrue(all(f["local"] != 1 for f in p.get("fill_nso", [])))

    def test_card_with_link_but_no_price_is_ignored(self):
        # Eine Karte mit Link ohne gelesenen Preis geht nicht still als Schätzung in die Rechnung (0.63)
        data, settings = sample()
        before = {p["code"]: p for p in planner.plans(data, settings, basket=["hades"], now=NOW)}["BR"]
        settings["countries"]["BR"]["cards"] += "\n10 | https://shop.example/br10"
        after = {p["code"]: p for p in planner.plans(data, settings, basket=["hades"], now=NOW)}["BR"]
        self.assertEqual((after["cost"], after["estimated"]), (before["cost"], before["estimated"]))
        # Ohne jede Karte mit Preis bleibt nur die Schätzung, sichtbar als solche
        settings["countries"]["BR"]["cards"] = "50 | https://shop.example/br50"
        ctx = planner.Context(data, settings, NOW)
        self.assertTrue(ctx.countries["BR"]["estimated"])

    def test_own_low_outside_window(self):
        data, settings = sample()
        data["lows"] = {"BR": {"hades": {"low": 40.0, "own_low": 10.0, "own_since": "2020-01-01T00:00:00+00:00"}}}
        self.assertEqual(planner.Context(data, settings, NOW).low_value("BR", "hades"), 40.0)
        data["lows"]["BR"]["hades"]["own_since"] = NOW.isoformat()
        self.assertEqual(planner.Context(data, settings, NOW).low_value("BR", "hades"), 10.0)

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
        self.only_sales()
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
        # Ab 0.36 blockiert ein Rest ab Werk nirgends mehr den Wechsel
        self.assertNotIn("Rest blockiert", " ".join(br["warnings"]))
        self.assertIn("DLC", " ".join(br["warnings"]))
        # Nidhogg 2 (7,50 BRL) braucht eine Karte mehr, spart aber gegenüber 14,99 € in DE
        first = br["fillers"][0]
        self.assertEqual(first["slugs"], ["nidhogg-2"])
        self.assertAlmostEqual(first["extra"], 9.50 - 7.80)   # 50er statt 15+25
        self.assertAlmostEqual(first["rest"], 50 - 45.09)
        self.assertIsNotNone(first["champ"])
        # 0.77: Ein Füllartikel weit über seinem Bestpreis fällt weg, auch wenn er heute spart
        real = planner.Context._champions

        def cheap(ctx):
            real(ctx)
            e, code, est = ctx.champ_all["nidhogg-2"]
            ctx.champ_all["nidhogg-2"] = (e / 3, code, est)
        self.settings["deal_eur"] = {"buy": 0, "good": 0}   # sonst gilt der billige Titel bis 2 € darüber als gut
        with mock.patch.object(planner.Context, "_champions", cheap):
            br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        self.assertNotIn("nidhogg-2", [x for f in br["fillers"] for x in f["slugs"]])

    def test_override_and_balance(self):
        self.only_sales()
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
        # Deutschland ist die Vergleichsbasis: gegen sich selbst keine Ersparnis.
        # Ohne Kontoland gilt es als Konto und braucht keine Schwelle
        self.assertAlmostEqual(de["saving"], 0)
        self.assertTrue(de["home"])
        self.assertTrue(de["worth"])
        late = datetime(2026, 10, 21, tzinfo=timezone.utc)
        no = self.by(planner.plans(self.data, self.settings, now=late))["NO"]
        self.assertEqual(no["items"], [])

    def test_return_to_germany_needs_the_easy_threshold(self):
        SALE = {"start": "2026-10-01T00:00:00Z", "end": "2026-10-20T00:00:00Z"}
        # Fall F8c: Das Konto steht in Norwegen, VS-Foscari ist in Deutschland 6 Cent
        # günstiger. Der Weg zurück nach Deutschland ist ein Wechsel wie jeder leichte
        # und schafft die 3-€-Schwelle nicht: Der Titel bleibt in Norwegen
        d, s = sample()
        s["current_country"] = "NO"
        d["prices"]["DE"]["spiritfarer"] = {"status": "onsale", "currency": "EUR", "regular": 24.99}
        d["prices"]["NO"]["hades"] = {"status": "onsale", "currency": "NOK", "regular": 250}
        d["prices"]["JP"] = {}
        d["prices"]["BR"] = {}
        d["prices"]["NO"]["vs-foscari"] = {"status": "onsale", "currency": "NOK", "regular": 20,
                                          "discount": 19.5, **SALE}
        d["prices"]["DE"]["vs-foscari"] = dict(d["prices"]["DE"]["vs-foscari"], discount=1.79, **SALE)
        k = planner.purchase_plan(d, s, now=NOW, include_good=True)
        self.assertEqual([p["code"] for p in k["steps"]], ["NO"])
        self.assertIn("vs-foscari", [i["slug"] for i in k["steps"][0]["items"]])
        de = [x for x in k["dropped"] if x["code"] == "DE"][0]
        self.assertAlmostEqual(de["gain"], 0.06)
        self.assertEqual(de["threshold"], 3.0)
        # Was es nur in Deutschland gibt, steht unter dem herausgefallenen Land
        self.assertEqual(de["open_slugs"], ["good-job", "nidhogg-2"])
        # Andere Länder am Schritt (0.74): dieselben Titel anderswo, nach Mehrkosten
        others = k["steps"][0]["others"]
        self.assertNotIn("NO", [o["code"] for o in others])
        self.assertIn("DE", [o["code"] for o in others])
        keys = [(len(o["missing"]), o["diff"]) for o in others]
        self.assertEqual(keys, sorted(keys))
        o = [o for o in others if o["code"] == "DE"][0]
        if not o["missing"]:
            self.assertAlmostEqual(o["diff"], round(o["games_cost"] - k["steps"][0]["games_cost"] + (k["steps"][0].get("rest_lost") or 0), 2))
        # Mit Konto in Deutschland (oder ohne Kontoland) ist es kein Wechsel
        for cur in ("DE", ""):
            s["current_country"] = cur
            k = planner.purchase_plan(d, s, now=NOW, include_good=True)
            self.assertEqual([p["code"] for p in k["steps"]], ["DE"])

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
        self.only_sales()
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
        self.only_sales()
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
        self.only_sales()
        self.settings["countries"]["BR"]["tax_pct"] = 10
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        hades = [i for i in br["items"] if i["slug"] == "hades"][0]
        self.assertAlmostEqual(hades["local"], 36.95)      # 33,59 + 10 %
        self.assertEqual(hades["pct"], 60)
        self.assertAlmostEqual(br["total"], 36.95 + 4.40)
        self.data.setdefault("lows", {}).update({"BR": {"hades": {"low": 33.59}}})
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        self.assertTrue([i for i in br["items"] if i["slug"] == "hades"][0]["at_low"])

    def test_tier_threshold(self):
        self.only_sales()
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

    def test_wishlist_dlc_takes_language_of_its_game_page(self):
        # DLC auf der Wishlist, Hauptspiel nicht: Die DLC-Seite fehlt in Amerika oft ganz.
        # Seit 0.68 zählt die Seite des Spiels, wie bei den fehlenden DLC der Sammlung
        items = self.data["items"]
        items["vs-foscari"]["langs"] = {"EU": "english, german"}
        items["vs-foscari"]["ids"].update(AM=["70050000000009"])
        rows = {(t["slug"], t["family"]): t for t in planner.lang_todo(self.data, self.settings, now=NOW)}
        self.assertEqual(rows[("vs-foscari", "AM")]["nsuid"], "70050000000009")
        self.assertIsNone(rows[("vs-foscari", "AM")]["state"])
        self.data["glangs"] = {"vampire-survivors": {"ids": {"AM": ["70010000000007"]}, "langs": {"AM": "english, german"}}}
        rows = {(t["slug"], t["family"]): t for t in planner.lang_todo(self.data, self.settings, now=NOW)}
        self.assertEqual((rows[("vs-foscari", "AM")]["nsuid"], rows[("vs-foscari", "AM")]["state"]), ("70010000000007", True))
        self.assertIn("/titles/70010000000007", rows[("vs-foscari", "AM")]["url"])
        self.assertEqual(planner.wish_dlc_parents(self.data), {"vampire-survivors": ["vs-foscari"]})
        self.assertEqual(sync.game_ids(self.data, "AM"), {"vampire-survivors": "70010000000007"})
        # 1.4.4: Mit der Liste der wirklich fehlenden DLC bleiben Spiele ohne fehlende DLC draußen
        self.data["extra"] = {"vs-old": {"parent": "graveyard-keeper", "ids": {"AM": ["70050000000099"]}}}
        self.assertEqual(sync.game_ids(self.data, "AM", wanted={}), {"vampire-survivors": "70010000000007"})
        self.assertEqual(sync.game_ids(self.data, "AM", wanted={"vs-old": 1})["graveyard-keeper"], "70050000000099")

    def test_package_distance_to_optimum(self):
        self.only_sales()
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
        self.data.setdefault("lows", {}).update({"BR": {"hades": {"low": 33.59}}, "NO": {"hades": {"low": 80.0}}})
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
        # Good-Job hat nirgends Rabatt, ist in Brasilien aber dauerhaft am Bestpreis: kaufen
        self.assertEqual((rows["good-job"]["verdict"], rows["good-job"]["reason"]),
                         ("buy", "Bestpreis in Brasilien (schwer), Normalpreis"))
        self.assertEqual(rows["good-job"]["hard"]["mark"], "best")
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
        # Karte ohne Fremdwährungsgebühr: genau zum Kurs
        self.settings["countries"]["JP"]["cards"] = "500 1000 2000 3000 5000 9000"
        self.settings["card_fee_pct"] = 0
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
        self.assertEqual(cp["https://shop.example/br50"], {"checked": t0, "ok": t0, "price": 8.9, "currency": "EUR"})
        self.assertEqual(cp["https://shop.example/br25"]["error"], "Seite nennt keinen Preis")
        # 0.54: das Protokoll nennt, welche Karte keinen Preis lieferte
        self.assertIn("Kartenpreise: 1 von 2 gelesen; ohne Preis: BR 25 (kein Preis)", sync.status["log"][-1])
        sync.sync_card_prices(self.data, self.settings, fake, lambda s: None, now=t0 + 3600)
        self.assertEqual(len(calls), 2)                       # höchstens einmal am Tag
        self.assertIn("Kartenpreise: alle 2 aktuell", sync.status["log"][-1])     # auch ohne Abruf eine Zeile
        # Der gelesene Preis ersetzt den von Hand eingetragenen, mit der Servicegebühr des Shops
        st = planner.card_status(self.data, self.settings, now=NOW)["BR"]
        self.assertEqual(st[2]["cost"], round(8.90 * 1.0775 + 0.40, 2))   # Vorgabe 0,40 € + 7,75 %
        # Die Vorgabe trifft echte Eneba-Käufe auf den Cent
        for sub, fee in ((5.57, 0.83), (16.58, 1.68), (49.26, 4.22), (93.03, 7.61)):
            self.assertAlmostEqual(sub * 0.0775 + 0.40, fee, delta=0.006)
        self.settings["shop_fee_pct"], self.settings["shop_fee_eur"] = 0, 0
        info = planner.pay_info(self.data, self.settings, now=NOW)["BR"]
        self.assertEqual((info["card"]["face"], info["card"]["cost"], info["card"]["live"]), (50.0, 8.9, t0))
        st = planner.card_status(self.data, self.settings, now=NOW)["BR"]
        self.assertEqual([(r["face"], r["cost"], r["manual"], r["error"]) for r in st],
                         [(15.0, 3.0, 3.0, None), (25.0, 4.8, 4.8, "Seite nennt keinen Preis"), (50.0, 8.9, 9.5, None)])
        # Ein gescheiterter Abruf löscht den Preis nicht: Er gilt mit seinem Datum weiter (0.52.1)
        sync.sync_card_prices(self.data, self.settings, lambda u, ua=None: "<p>leer</p>", lambda s: None, now=t0 + 86400)
        self.assertEqual((cp["https://shop.example/br50"]["price"], cp["https://shop.example/br50"]["ok"]), (8.9, t0))
        mid = datetime.fromtimestamp(t0 + 5 * 86400, timezone.utc)
        info = planner.pay_info(self.data, self.settings, now=mid)["BR"]
        self.assertEqual((info["card"]["cost"], info["card"]["live"]), (8.9, t0))
        # Veraltet: nach 14 Tagen ohne Erfolg gilt wieder der Wert von Hand
        later = datetime.fromtimestamp(t0 + 15 * 86400, timezone.utc)
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

    def test_card_factor_and_rating(self):
        # Faktor = Preis ÷ Wert zum Mittelkurs, bewertet je nach Land (0.53)
        rate_no = self.data["fx"]["rates"]["NOK"]
        self.settings["countries"]["NO"].update(pay="auto", cards="500 = 50,63")
        row = planner.card_status(self.data, self.settings, now=NOW)["NO"][0]
        self.assertAlmostEqual(row["factor"], round(50.63 / (500 / rate_no), 4))
        # 0.53.5: Spalte und Bewertungstext runden gleich (vorher 1,11 in der Spalte, 1,10 im Text)
        self.assertEqual(planner._fac(1.10476), "1,10")
        self.assertEqual(planner._fac(1.10496), "1,11")
        self.assertEqual(planner._fac(1.105), "1,11")
        self.assertEqual(row["value"], round(500 / rate_no, 2))
        self.assertEqual(row["rating"]["level"], "dearer" if row["factor"] > 1.0175 else "cheaper")
        self.assertFalse(row["used"] and row["rating"]["level"] == "dearer")
        # Euro-Guthaben: feste Stufen, einstellbar
        self.settings["countries"]["DG"].update(enabled=True, cards="50 = 41,00\n25 = 22,00")
        rows = planner.card_status(self.data, self.settings, now=NOW)["DG"]
        self.assertEqual([(r["factor"], r["rating"]["text"], r["used"]) for r in rows],
                         [(0.88, "teuer", False), (0.82, "gut", True)])
        info = planner.pay_info(self.data, self.settings, now=NOW)["DG"]
        self.assertEqual((info["factor"], info["rating"]["level"]), (0.82, "good"))
        self.settings["eur_card_steps"]["top"] = 0.82
        self.assertEqual(planner.card_status(self.data, self.settings, now=NOW)["DG"][1]["rating"]["text"], "Top")
        # Nur Guthaben: gegen den eigenen Bestwert der Karte, erst nach zwei Wochen Verlauf
        url = "https://shop.example/br50"
        self.settings["countries"]["BR"].update(pay="giftcard", cards=f"50 | {url}")
        rate_br = self.data["fx"]["rates"]["BRL"]
        self.settings["shop_fee_pct"], self.settings["shop_fee_eur"] = 0, 0
        t0 = NOW.timestamp()
        for day, price in ((0, 50 / rate_br * 1.0), (1, 50 / rate_br * 1.01), (20, 50 / rate_br * 1.04)):
            self.data["card_prices"] = {url: {"checked": t0 + day * 86400, "ok": t0 + day * 86400,
                                              "price": round(price, 2), "currency": "EUR"}}
            sync.record_card_factors(self.data, self.settings, now=t0 + day * 86400)
            when = datetime.fromtimestamp(t0 + day * 86400, timezone.utc)
            rating = planner.card_status(self.data, self.settings, now=when)["BR"][0]["rating"]
            if day < 14:
                # 0.53.6: nennt den Tag, ab dem bewertet wird
                start = datetime.fromtimestamp(t0, timezone.utc) + timedelta(days=14)
                self.assertEqual(rating["text"], f"Bewertung ab {start:%d.%m.}")
        self.assertEqual(len(self.data["card_hist"][url]), 3)
        self.assertEqual(rating["level"], "ok")                  # 4 % über dem Bestwert 1,00
        info = planner.pay_info(self.data, self.settings, now=when)["BR"]
        self.assertEqual((round(info["card"]["factor"], 3), info["rating"]["level"]), (1.04, "ok"))
        self.assertAlmostEqual(info["card"]["value"], round(50 / rate_br, 2))
        # Verlauf: Älteres als 90 Tage und entfernte Links fallen weg
        sync.record_card_factors(self.data, self.settings, now=t0 + 100 * 86400)
        self.assertEqual(len(self.data["card_hist"][url]), 1)
        self.data["card_prices"] = {}
        sync.record_card_factors(self.data, self.settings, now=t0 + 100 * 86400)
        self.assertEqual(self.data["card_hist"], {})

    def test_auto_never_picks_an_estimate(self):
        # „das Günstigere“ ohne Kartenpreis: Kreditkarte, auch wenn die Schätzung niedriger wäre
        self.settings["countries"]["NO"].update(pay="auto", cards="")
        self.settings["gift_markup_pct"] = -10
        info = planner.pay_info(self.data, self.settings, now=NOW)["NO"]
        self.assertEqual((info["via"], info["vs_mid"]), ("card", 1.8))

    def test_card_prices_take_turns(self):
        # Der Shop sperrt nach einigen Abrufen. Gelesen wird reihum, die ältesten zuerst,
        # sonst kämen die hinteren Links nie dran
        urls = [f"https://shop.example/br{v}" for v in (15, 25, 50, 100)]
        self.settings["countries"]["BR"]["cards"] = "\n".join(
            f"{v} | {u}" for v, u in zip((15, 25, 50, 100), urls))
        ld = ('<script type="application/ld+json">{"@type":"Offer","price":"5.00",'
              '"priceCurrency":"EUR"}</script>')
        t0, calls = NOW.timestamp(), []

        def twice(url, ua=None):          # Sperre nach zwei Abrufen
            calls.append(url)
            if len(calls) % 3 == 0:
                raise sources.FetchError(url, 429)
            return ld
        for day in range(3):
            sync.sync_card_prices(self.data, self.settings, twice, lambda s: None,
                                  now=t0 + day * 86400)
        read = {u for u in urls if self.data["card_prices"].get(u, {}).get("price")}
        self.assertEqual(read, set(urls))

    def test_card_prices_of_the_plan_first(self):
        # Die Karten der Länder im Kaufplan zählen gerade: Sie kommen vor den ältesten dran
        old, plan = "https://shop.example/jp1000", "https://shop.example/br50"
        self.settings["countries"]["JP"]["cards"] = f"1000 | {old}"
        self.settings["countries"]["BR"]["cards"] = f"50 | {plan}"
        t0, calls = NOW.timestamp(), []
        self.data["card_prices"] = {old: {"checked": t0 - 9 * 86400, "price": 6.0, "currency": "EUR"},
                                    plan: {"checked": t0 - 2 * 86400, "price": 8.9, "currency": "EUR"}}

        def once(url, ua=None):
            calls.append(url)
            raise sources.FetchError(url, 429)
        with mock.patch.object(sync, "_plan_card_urls", return_value={plan}):
            sync.sync_card_prices(self.data, self.settings, once, lambda s: None, now=t0)
        self.assertEqual(calls, [plan])
        calls.clear()
        with mock.patch.object(sync, "_plan_card_urls", return_value=set()):
            sync.sync_card_prices(self.data, self.settings, once, lambda s: None, now=t0)
        self.assertEqual(calls, [old])

    def test_plan_card_urls(self):
        u, j = "https://shop.example/br50", "https://shop.example/jp1000"
        self.settings["current_country"] = "DE"
        self.settings["countries"]["BR"]["cards"] = f"50 | {u}\n25 8,90\n15 5,50"
        self.settings["countries"]["JP"]["cards"] += f"\n1000 | {j}"
        self.data["card_prices"] = {u: {"checked": NOW.timestamp(), "price": 8.9, "currency": "EUR"}}
        steps = planner.purchase_plan(self.data, self.settings, now=NOW)["steps"]
        self.assertIn("BR", [p["code"] for p in steps])
        self.assertNotIn("JP", [p["code"] for p in steps])
        self.assertEqual(sync._plan_card_urls(self.data, self.settings, NOW.timestamp()), {u})

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

    def test_implausible_card_prices_are_ignored(self):
        # 50 BRL zum Mittelkurs sind 8,91 €: 0,99 € (Gebührenhinweis statt Preis) ist ein Lesefehler
        self.settings["countries"]["BR"]["cards"] = ("15=3.00\n25=4.80\n50=9.50 | https://shop.example/br50\n"
                                                    "100 | https://shop.example/br100\n"
                                                    "200 | https://shop.example/br200")
        self.data["card_prices"] = {
            "https://shop.example/br50": {"checked": NOW.timestamp(), "price": 0.99, "currency": "EUR"},
            "https://shop.example/br100": {"checked": NOW.timestamp(), "price": 16.10, "currency": "EUR"},
            "https://shop.example/br200": {"checked": NOW.timestamp(), "price": 90.0, "currency": "EUR"}}
        ctx = planner.Context(self.data, self.settings, NOW)
        by = {x["face"] // 100: x for x in ctx.countries["BR"]["cards"]}
        self.assertEqual(by[50]["cost"], 9.50)              # unglaubhaft: dein Eintrag gilt
        self.assertAlmostEqual(by[100]["cost"], 17.75)      # rund 100 % vom Mittelkurs: zählt
        self.assertIsNone(by[200]["cost"])                  # 273 %: zählt nicht
        self.assertEqual(sorted((i["src"], i["face"]) for i in ctx.countries["BR"]["implausible"]),
                         [("shop", 50.0), ("shop", 200.0)])
        rows = planner.card_status(self.data, self.settings, now=NOW)["BR"]
        self.assertIn("unglaubhaft", next(r for r in rows if r["face"] == 50)["error"])
        # Deutschland: eine 20-€-Karte für 0,35 € senkt die Vergleichsbasis nicht
        self.settings["countries"]["DG"]["cards"] = "20 | https://shop.example/de20"
        self.data["card_prices"]["https://shop.example/de20"] = {
            "checked": NOW.timestamp(), "price": 0.35, "currency": "EUR"}
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
        # Japan ohne Kartenliste: Schätzung mit dem allgemeinen Aufschlag (seit 0.52.1 keiner je Land)
        self.assertEqual((info["JP"]["card"], info["JP"]["vs_mid"]), (None, 5.0))
        jp = self.by(planner.plans(self.data, self.settings, now=NOW))["JP"]
        self.assertAlmostEqual(jp["cost"], round(1400 / 177.3267 * 1.05, 2))
        self.assertTrue(jp["estimated"])
        # Werte ohne Link: Guthaben zum Kurs, 1400 ¥ -> 2x 1000 ¥ zum Nennwert, keine Schätzung
        self.settings["countries"]["JP"]["cards"] = "1000\n3000"
        jp = self.by(planner.plans(self.data, self.settings, now=NOW))["JP"]
        self.assertAlmostEqual(jp["cost"], round(2000 / 177.3267 * 1.0175, 2))   # mit Kartengebühr
        self.assertEqual(jp["rest"], 600.0)
        self.assertEqual(planner.pay_info(self.data, self.settings, now=NOW)["JP"]["vs_mid"], 1.8)

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

    def test_plans_only_one_country(self):
        # „Andere Länder“ am Schritt rechnet nur das eine Land (1.0.3), mit demselben Ergebnis
        basket = ["hades", "spiritfarer"]
        full, _ = planner.plans(self.data, self.settings, basket=basket, now=NOW, with_mix=True)
        one, split = planner.plans(self.data, self.settings, basket=basket, now=NOW, with_mix=True, only=["NO"])
        self.assertEqual(sorted(p["code"] for p in one), ["DE", "NO"])
        self.assertIsNone(split)
        self.assertEqual(self.by(one)["NO"], self.by(full)["NO"])

    def test_owned_flags(self):
        self.data["owned"] = ["hades", "vampire-survivors"]
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        rows = {i["slug"]: i for i in br["items"]}
        self.assertTrue(rows["hades"]["owned"])
        self.assertEqual((rows["vs-foscari"]["owned"], rows["vs-foscari"]["parent_owned"]), (False, True))
        self.assertIsNone(rows["hades"]["parent_owned"])        # kein DLC

    def test_dlc_needing_parent_marked(self):
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        rows = {i["slug"]: i for i in br["items"]}
        self.assertTrue(rows["vs-foscari"]["needs_parent"])     # Hauptspiel nicht im Korb
        self.assertFalse(rows["hades"]["needs_parent"])         # kein DLC
        self.assertIn("DLC braucht in der Regel das Hauptspiel aus Amerika (1 DLC)", br["warnings"])

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

    def only_sales(self):
        # Good-Job und Nidhogg 2 waren in DE schon einmal billiger: In Brasilien sind sie dann
        # kein Kauf, die Länderkarte zeigt dort wie bisher nur die Angebote
        self.data.setdefault("lows", {}).setdefault("DE", {}).update(
            {"good-job": {"low": 5.0}, "nidhogg-2": {"low": 0.5}})

    def without_lasting(self):
        # Ohne die beiden Titel, die in Brasilien dauerhaft am Bestpreis sind
        for slug in ("good-job", "nidhogg-2"):
            del self.data["items"][slug]

    def test_purchase_plan_drops_weak_countries(self):
        self.without_lasting()
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        steps = [(s["code"], [i["slug"] for i in s["items"]]) for s in plan["steps"]]
        # Hades liegt nur in Brasilien am Bestpreis aller Länder. Brasilien spart 19,64 €
        # (ohne den Rest) und verfehlt die Schwelle von 20 € der Stufe schwer. Japan ist
        # zu weit vom Bestpreis weg, also warten Hades und VS Foscari.
        self.assertEqual(steps, [("DE", ["spiritfarer"])])
        self.assertEqual([d["code"] for d in plan["dropped"]], ["BR"])
        self.assertAlmostEqual(plan["dropped"][0]["saving"], 19.65)
        # Jeder Titel steht nur einmal unter "Nicht im Plan": Hades und VS Foscari unter
        # Brasilien, dessen Wechsel nicht lohnt, nicht noch einmal unter "lieber warten"
        self.assertEqual(plan["dropped"][0]["open_slugs"], ["hades", "vs-foscari"])
        self.assertEqual(plan["later"], [])
        self.assertAlmostEqual(plan["cost"], 6.24)
        self.assertEqual(plan["count"], 1)

    def test_dropped_country_stays_visible_when_its_titles_move(self):
        # 0.95: Kommt ein Titel eines herausgefallenen Lands woanders in den Plan, nennt der
        # Grund am Titel das günstigere Land, und das Land steht mit „moved“ unter „Nicht im Plan“
        self.without_lasting()
        self.settings["tier_min_saving"]["3"] = 15
        plan = planner.purchase_plan(self.data, self.settings, now=NOW, include_good=True)
        br = next(d for d in plan["dropped"] if d["code"] == "BR")
        self.assertEqual(br["moved"], [{"slug": "vs-foscari", "short": br["moved"][0]["short"], "to": "DE"}])
        de = next(p for p in plan["steps"] if p["code"] == "DE")
        self.assertTrue(de["reasons"]["vs-foscari"].startswith("günstiger in Brasilien, aber der Wechsel dorthin spart nur"))
        # Jeder Titel nur einmal
        self.assertEqual(sum(1 for d in plan["dropped"] for m in d["moved"] if m["slug"] == "vs-foscari"), 1)

    def test_taken_fill_item_moves_out_of_another_step(self):
        # 1.2.0: Steht ein Titel schon in einem anderen Schritt, zieht er beim Dazunehmen um.
        # Vorher blieb er dort, und das Dazunehmen zeigte keine Wirkung
        plan = planner.purchase_plan(self.data, self.settings, now=NOW, include_good=True)
        self.assertIn("vs-foscari", [i["slug"] for i in self.by(plan["steps"])["BR"]["items"]])
        moved = self.by(planner.purchase_plan(self.data, self.settings, now=NOW, include_good=True,
                                              fill={"DE": ["vs-foscari"]})["steps"])
        self.assertEqual([i["slug"] for i in moved["DE"]["items"]], ["spiritfarer", "vs-foscari"])
        self.assertEqual(moved["DE"]["fill_slugs"], ["vs-foscari"])
        self.assertNotIn("vs-foscari", [i["slug"] for i in moved["BR"]["items"]])

    def test_taken_fill_creates_its_own_step(self):
        # 1.3.0: Titel, die du in ein Land ohne Schritt nimmst (etwa „In Jetzt übernehmen“ im Korb),
        # bekommen dort einen Schritt, und der fällt nicht an der Schwelle heraus
        plan = self.by(planner.purchase_plan(self.data, self.settings, now=NOW, include_good=True,
                                             fill={"NO": ["hades", "spiritfarer", "vs-foscari"]})["steps"])
        self.assertEqual([i["slug"] for i in plan["NO"]["items"]], ["hades", "spiritfarer", "vs-foscari"])
        self.assertFalse(plan["NO"]["worth"])
        self.assertNotIn("DE", plan)
        self.assertEqual([i["slug"] for i in plan["BR"]["items"]], ["good-job", "nidhogg-2"])

    def test_assumed_price_changes_the_plan(self):
        # 1.3.0: „Was wäre, wenn“: ein angenommener Preis gilt wie ein Angebot, der Titel ist markiert
        before = json.dumps(self.data["prices"], sort_keys=True)
        plan = planner.purchase_plan(self.data, self.settings, now=NOW, include_good=True,
                                     assume={"NO": {"spiritfarer": 10}})
        no = self.by(plan["steps"])["NO"]
        self.assertEqual([(i["slug"], i["local"], i.get("assumed")) for i in no["items"]], [("spiritfarer", 10, True)])
        self.assertEqual([(x["code"], x["slug"], x["to"]) for x in plan["assumed"]], [("NO", "spiritfarer", "NO")])
        self.assertEqual(json.dumps(self.data["prices"], sort_keys=True), before)
        # Ohne Annahme wie bisher, die Daten bleiben unverändert
        plain = planner.purchase_plan(self.data, self.settings, now=NOW, include_good=True)
        self.assertNotIn("NO", self.by(plain["steps"]))
        self.assertEqual(plain["assumed"], [])

    def test_taken_fill_items_without_step_stay_visible(self):
        # 0.95: Übernommenes für ein Land ohne Schritt verschwindet nicht still
        self.without_lasting()
        plan = planner.purchase_plan(self.data, self.settings, now=NOW, fill={"JP": ["spiritfarer"]})
        self.assertNotIn("JP", [p["code"] for p in plan["steps"]])
        self.assertEqual([(x["code"], x["slug"], x["to"], x["step"]) for x in plan["fill_idle"]],
                         [("JP", "spiritfarer", "DE", False)])
        self.assertEqual(planner.purchase_plan(self.data, self.settings, now=NOW)["fill_idle"], [])

    def test_verdict_without_history_is_marked(self):
        # 0.95: Ohne Tiefstpreis von DekuDeals trägt ein Kauf-Urteil „noch ohne Verlauf“
        self.data["lows"] = {}
        rows = [r for r in planner.radar(self.data, self.settings, now=NOW) if r["verdict"] in ("buy", "good")]
        self.assertTrue(rows)
        self.assertTrue(all(r["nohist"] for r in rows))
        data, settings = sample()
        self.assertFalse(any(r["nohist"] for r in planner.radar(data, settings, now=NOW)
                             if planner._context(data, settings, now=NOW).has_history(r["slug"])))

    def test_stale_prices_are_flagged_per_country(self):
        # 0.95: Scheiterte der letzte Abruf in einem Land, sagt der Plan, von wann die Preise sind
        for shop, t in self.data["prices"].items():
            for p in t.values():
                p["fetched"] = "2026-10-11T04:00:00+00:00"
        for p in self.data["prices"]["BR"].values():
            p["fetched"] = "2026-10-09T04:00:00+00:00"
        by = self.by(planner.plans(self.data, self.settings, now=NOW))
        self.assertTrue(by["BR"]["price_stale"])
        self.assertEqual(by["BR"]["price_at"], "2026-10-09T04:00:00+00:00")
        self.assertFalse(by["NO"]["price_stale"])
        # Ohne Zeitstempel (alte Daten): nichts markiert
        data, settings = sample()
        self.assertFalse(any(p["price_stale"] for p in planner.plans(data, settings, now=NOW)))

    def test_no_cards_warning_names_the_cause(self):
        c = {"cards": []}
        self.assertTrue(planner.no_cards_warning(c).startswith("Keine Guthabenkarten eingetragen"))
        c["cards"] = [{"face": 5000, "stock": False}]
        self.assertTrue(planner.no_cards_warning(c).startswith("Keine Guthabenkarte vorrätig"))
        c["cards"] = [{"face": 5000, "stock": True}]
        self.assertTrue(planner.no_cards_warning(c).startswith("Keine Guthabenkarte mit Preis"))

    def test_ui_fields_for_signals(self):
        # Die Oberfläche färbt Preise nach dem Urteil und nennt Titel, deren Wechsel nicht lohnt
        self.without_lasting()
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

    def test_collection_titles_stay_out_of_the_plan(self):
        # Was in der Sammlung steht, ist gekauft, auch wenn es noch auf der Wishlist steht
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        planned = {i["slug"] for p in plan["steps"] for i in p["items"]}
        self.assertIn("hades", planned)
        self.data["owned"] = ["hades"]
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        self.assertNotIn("hades", {i["slug"] for p in plan["steps"] for i in p["items"]})
        self.assertIn("Hades", plan["bought_waiting"])

    def test_plan_order_same_without_account_country(self):
        # Ohne Kontoland gilt Deutschland als Konto: dieselbe Reihenfolge wie mit Konto in DE,
        # auch wenn ein Angebot in Norwegen früher endet
        self.data["prices"]["NO"]["good-job"] = {"status": "onsale", "currency": "NOK", "regular": 200, "discount": 10,
                                                 "start": "2026-10-01T00:00:00Z", "end": "2026-10-15T00:00:00Z"}
        self.settings["current_country"] = ""
        a = [p["code"] for p in planner.purchase_plan(self.data, self.settings, now=NOW, include_good=True)["steps"]]
        self.settings["current_country"] = "DE"
        b = [p["code"] for p in planner.purchase_plan(self.data, self.settings, now=NOW, include_good=True)["steps"]]
        self.assertEqual(a, b)
        self.assertEqual(a, ["DE", "NO"])

    def test_rest_blocks_nowhere_by_default(self):
        # Ab 0.36: Guthaben in Brasilien hält den Plan nicht mehr dort fest
        self.settings["current_country"] = "BR"
        self.settings["countries"]["BR"]["balance"] = 2.41
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        self.assertIsNone(plan["lock"])
        self.assertEqual(plan["held"], [])

    def test_price_history_counts_dekudeals_sales(self):
        h = {"BR": {"hades": [["2026-10-01T00:00:00+00:00", 33.59]]}}
        self.data.setdefault("lows", {}).setdefault("BR", {})["hades"] = {
            "low": 33.59, "src": "deku", "sales": [["2025-12-01", 41.99], ["2026-10-01", 33.59]]}
        br = next(c for c in planner.price_history(self.data, self.settings, h, "hades", now=NOW)["countries"]
                  if c["code"] == "BR")
        self.assertEqual((br["sale_count"], br["deku_sales"]), (1, 2))

    def test_purchase_plan_keeps_country_above_threshold(self):
        # Gegenüber Deutschland spart Brasilien 19,65 €, gegenüber Japan und Norwegen nur
        # 2,60 €: Bei einer Schwelle von 15 € lohnt der Wechsel nach Amerika nicht
        self.without_lasting()
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

    def test_package_check_moves_a_step_to_a_cheaper_country(self):
        # 0.83: Kosten die Titel eines Schritts zusammen in einem Land gleicher oder leichterer
        # Stufe weniger, kommt der Schritt dorthin; nie in ein Land, das schon ein Schritt ist,
        # und nie zweimal dieselbe Verschiebung
        ctx = planner._context(self.data, self.settings, NOW)
        codes = [c for c, x in ctx.countries.items() if x["unit"] is not None]
        jp = planner.plan_country(ctx, "JP", basket=["hades"], allowed=codes, fillers=False)
        jp["games_cost"] = 10.0                         # teurer als Norwegen (9,50 €) als Paket
        tried = set()
        self.assertEqual(planner._package_moves(ctx, [jp], codes, "", tried), {"NO": ["hades"]})
        self.assertEqual(planner._package_moves(ctx, [jp], codes, "", tried), {})
        no = planner.plan_country(ctx, "NO", basket=["spiritfarer"], allowed=codes, fillers=False)
        self.assertNotIn("NO", planner._package_moves(ctx, [jp, no], codes, "", set()))
        # Brasilien (Stufe schwer) zählt für einen Schritt der Stufe mittel nicht
        jp["games_cost"] = 8.03
        self.assertEqual(planner._package_moves(ctx, [jp], codes, "", set()), {})

    def test_purchase_plan_counts_rest_before_a_switch(self):
        # Konto steht in Japan (Stufe mittel): Japan kommt zuerst, danach Deutschland. Der Rest
        # in Japan verfällt beim Wechsel und zählt deshalb als Kosten
        self.without_lasting()
        self.settings["current_country"] = "JP"
        self.settings["countries"]["JP"]["cards"] = "1000 2000"
        self.data["prices"]["JP"]["hades"]["discount"] = 1100
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        self.assertEqual([s["code"] for s in plan["steps"]], ["JP", "DE"])
        jp = plan["steps"][0]
        self.assertEqual(jp["rest"], 900)
        self.assertGreater(jp["rest_lost"], 4)
        self.assertAlmostEqual(jp["games_cost"], 2000 / 177.3267 * 1.0175, places=1)
        self.assertAlmostEqual(plan["rest_lost"], jp["rest_lost"])
        self.assertNotIn("rest_lost", plan["steps"][1])         # letzter Schritt: Rest bleibt

    def test_plan_skip_takes_a_title_out_of_one_step(self):
        # × im Kaufplan (0.94): dort nicht kaufen, sichtbar mit dem Land, in das er nun geht
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        step = next(p for p in plan["steps"] if len(p["items"]) > 1)
        slug = step["items"][0]["slug"]
        k = planner.purchase_plan(self.data, self.settings, now=NOW, skip={step["code"]: [slug]})
        here = next((p for p in k["steps"] if p["code"] == step["code"]), None)
        self.assertNotIn(slug, [i["slug"] for i in here["items"]])
        moved = next((p["code"] for p in k["steps"] if slug in [i["slug"] for i in p["items"]]), None)
        self.assertEqual(here["skipped"], [{"slug": slug, "short": here["skipped"][0]["short"],
                                            "title": here["skipped"][0]["title"], "to": moved}])
        self.assertEqual(k["skipped"], [])
        # Fällt der ganze Schritt weg, steht das Herausgenommene unter „Nicht im Plan“
        all_out = planner.purchase_plan(self.data, self.settings, now=NOW,
                                        skip={step["code"]: [i["slug"] for i in step["items"]]})
        self.assertNotIn(step["code"], [p["code"] for p in all_out["steps"]])
        self.assertEqual(sorted(x["slug"] for x in all_out["skipped"]), sorted(i["slug"] for i in step["items"]))

    def test_country_cards_get_rest_suggestions(self):
        # Länderkarten zeigen „Passt in den Rest“ wie der Kaufplan (0.94)
        res, _ = planner.plans(self.data, self.settings, now=NOW, with_mix=True)
        for p in res:
            self.assertIn("fill", p)
            if p["fill"]:
                self.assertTrue(all(f["local"] <= p["rest"] + 1e-9 for f in p["fill"]))
                self.assertFalse({f["slug"] for f in p["fill"]} & {i["slug"] for i in p["items"]})

    def test_plan_fills_the_rest(self):
        # 900 ¥ bleiben in Japan. Celeste (800 ¥) passt hinein, auch ohne Urteil „kaufen“
        self.without_lasting()
        self.settings["current_country"] = "JP"
        self.settings["countries"]["JP"]["cards"] = "1000 2000"
        self.data["prices"]["JP"]["hades"]["discount"] = 1100
        self.data["items"]["celeste"] = {"title": "Celeste", "parent": None, "active": True,
                                         "order": 9, "ids": {"EU": ["9"]}, "ids_checked": {}}
        self.data["prices"]["DE"]["celeste"] = {"status": "onsale", "currency": "EUR", "regular": 19.99}
        self.data["prices"]["JP"]["celeste"] = {"status": "onsale", "currency": "JPY", "regular": 800}
        self.data["lows"] = {"DE": {"celeste": {"low": 1.0}}}
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        jp = plan["steps"][0]
        self.assertEqual([(f["slug"], f["left"]) for f in jp["fill"]], [("celeste", 100.0)])
        self.assertEqual(plan["steps"][1]["fill"], [])                 # kein Rest in DE
        # Übernommen: Celeste kommt in den Schritt, der verfallende Rest wird kleiner
        filled = planner.purchase_plan(self.data, self.settings, now=NOW, fill={"JP": ["celeste"]})
        jp2 = filled["steps"][0]
        self.assertEqual([i["slug"] for i in jp2["items"]], ["hades", "celeste"])
        self.assertEqual((jp2["fill_slugs"], jp2["rest"], jp2["fill"]), (["celeste"], 100.0, []))
        self.assertLess(jp2["rest_lost"], jp["rest_lost"])
        # Schon in der Sammlung oder gekauft: kein Vorschlag, kein Füller
        self.data["owned"] = ["celeste"]
        self.assertEqual(planner.purchase_plan(self.data, self.settings, now=NOW)["steps"][0]["fill"], [])
        self.data["owned"] = []
        bought = [{"slugs": ["celeste"]}]
        again = planner.purchase_plan(self.data, self.settings, now=NOW, fill={"JP": ["celeste"]}, bought=bought)
        self.assertEqual([i["slug"] for i in again["steps"][0]["items"]], ["hades"])

    def test_blocking_rest_only_in_the_last_step(self):
        for code in ("BR", "MX"):                     # Wahl in den Einstellungen, ab Werk aus
            self.settings["countries"][code]["rest_blocks"] = True
        # Echter Fall: Konto in Brasilien ohne Guthaben. Ein Rest in Brasilien blockiert den
        # Wechsel, also kommt Brasilien zuletzt; dorthin ist es dann ein Wechsel wie jeder andere
        self.settings["current_country"] = "BR"
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        self.assertEqual([s["code"] for s in plan["steps"]], ["DE", "BR"])
        br = plan["steps"][-1]
        self.assertFalse(br["current"])
        self.assertTrue(br["worth"])                             # 24,61 € über 20 €
        self.assertEqual(plan["rest_lost"], 0)
        self.assertIsNone(plan["lock"])

    def test_two_blocking_countries_keep_the_stronger(self):
        for code in ("BR", "MX"):                     # Wahl in den Einstellungen, ab Werk aus
            self.settings["countries"][code]["rest_blocks"] = True
        sale = {"start": "2026-10-01T00:00:00Z", "end": "2026-10-20T00:00:00Z"}
        self.settings["tier_min_saving"]["3"] = 1
        self.settings["countries"]["MX"]["enabled"] = True
        self.settings["countries"]["MX"]["cards"] = "100=5.00 200=9.80 500=24.00"
        self.data["fx"]["rates"]["MXN"] = 21.5
        self.data["prices"]["MX"] = {"spiritfarer": {"status": "onsale", "currency": "MXN",
                                                     "regular": 400, "discount": 80, **sale}}
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        self.assertEqual([s["code"] for s in plan["steps"]], ["BR"])
        self.assertEqual([(d["code"], d["blocked_by"]) for d in plan["dropped"]], [("MX", ["Brasilien"])])

    def test_balance_in_blocking_country_locks_the_plan(self):
        for code in ("BR", "MX"):                     # Wahl in den Einstellungen, ab Werk aus
            self.settings["countries"][code]["rest_blocks"] = True
        # Am Tag nach dem Kauf in Brasilien: 2,41 R$ liegen dort. Ein Wechsel geht erst, wenn
        # sie aufgebraucht sind, also plant der Plan nur in Brasilien
        self.settings["current_country"] = "BR"
        self.settings["countries"]["BR"]["balance"] = 2.41
        plan = planner.purchase_plan(self.data, self.settings, now=NOW,
                                     bought=[{"slugs": ["hades", "vs-foscari"], "code": "BR"}])
        self.assertEqual([(s["code"], [i["slug"] for i in s["items"]]) for s in plan["steps"]],
                         [("BR", ["good-job", "nidhogg-2"])])
        self.assertEqual([h["slug"] for h in plan["held"]], ["spiritfarer"])
        self.assertEqual((plan["lock"]["code"], plan["lock"]["balance"]), ("BR", 2.41))
        # Was wartet, steht nicht zugleich unter „passt hinein“
        self.assertFalse(set(plan["lock"]["fits"]) & {h["short"] for h in plan["held"]})
        # Auch ohne Preise im Kontoland (oder abgeschaltet) bleibt das Konto gesperrt
        self.settings["current_country"] = "MX"
        self.settings["countries"]["BR"]["balance"] = 0
        self.settings["countries"]["MX"]["balance"] = 50
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        self.assertEqual(plan["steps"], [])
        self.assertEqual((len(plan["held"]), plan["nowhere"]), (5, []))

    def test_balance_left_behind_counts_as_cost(self):
        # Konto in Japan mit 1000 Yen, der Plan kauft nur woanders: Das Guthaben verfällt
        self.settings["current_country"] = "JP"
        self.settings["countries"]["JP"]["balance"] = 1000
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        first = plan["steps"][0]
        self.assertEqual(first["code"], "DE")
        self.assertAlmostEqual(first["balance_lost"], round(1000 / 177.3267 * 1.0175, 2), places=2)
        self.assertAlmostEqual(plan["rest_lost"], first["balance_lost"])

    def test_disabled_country_is_left_out_everywhere(self):
        # „Aktiv“ aus: kein Land in Tabelle, Plan und Bestpreis, die Einstellung bleibt gespeichert
        saved = store.save_settings({"countries": {"NO": {"enabled": False}}})
        self.assertFalse(saved["countries"]["NO"]["enabled"])
        self.assertFalse(store.load_settings()["countries"]["NO"]["enabled"])
        store.save_settings({"countries": {"NO": {"enabled": True}}})
        self.settings["countries"]["NO"]["enabled"] = False
        codes = {p["code"] for p in planner.plans(self.data, self.settings, now=NOW)}
        self.assertNotIn("NO", codes)
        self.assertIn("BR", codes)
        for r in planner.radar(self.data, self.settings, now=NOW):
            self.assertNotEqual((r["at"] or {}).get("code"), "NO")
        steps = planner.purchase_plan(self.data, self.settings, now=NOW)["steps"]
        self.assertNotIn("NO", [p["code"] for p in steps])

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
        # Good-Job ist in Brasilien dauerhaft günstiger. Ein teureres Angebot in Deutschland
        # macht daraus kein "warten": Das Urteil gilt dem günstigsten Preis jetzt
        sale = {"start": "2026-10-01T00:00:00Z", "end": "2026-10-20T00:00:00Z"}
        de = self.data["prices"]["DE"]
        de["good-job"] = dict(de["good-job"], discount=15.99, **sale)
        r = {x["slug"]: x for x in planner.radar(self.data, self.settings, now=NOW)}["good-job"]
        self.assertEqual((r["verdict"], r["at"]["code"]), ("buy", "BR"))
        self.assertEqual(r["reason"], "Bestpreis in Brasilien (schwer), Normalpreis")

    def test_lasting_prices_make_a_switch_worth_it(self):
        # Review 0.18, Fall F10: Mit den dauerhaft günstigen Titeln schafft Brasilien die
        # Schwelle von 20 €; ohne sie wären Hades und VS Foscari am Bestpreis "lieber warten"
        plan = planner.purchase_plan(self.data, self.settings, now=NOW)
        steps = [(s["code"], [i["slug"] for i in s["items"]]) for s in plan["steps"]]
        self.assertEqual(steps, [("DE", ["spiritfarer"]),
                                 ("BR", ["hades", "vs-foscari", "good-job", "nidhogg-2"])])
        self.assertAlmostEqual(plan["steps"][1]["gain"], 24.61)
        self.assertEqual((plan["dropped"], plan["later"]), ([], []))

    def test_country_card_shows_lasting_prices(self):
        # Die Länderkarte zeigt dieselben Titel wie der Kaufplan: auch dauerhaft günstige
        # Normalpreise mit dem Urteil "kaufen". Der Wechsel lohnt dort dann wie im Plan
        br = self.by(planner.plans(self.data, self.settings, now=NOW))["BR"]
        self.assertEqual([i["slug"] for i in br["items"]], ["hades", "vs-foscari", "good-job", "nidhogg-2"])
        self.assertEqual((br["gain"], br["worth"]), (24.61, True))
        self.assertEqual(br["fillers"], [])
        # Deutschland zum Normalpreis bleibt draußen, Norwegen zeigt nur sein Angebot
        by = self.by(planner.plans(self.data, self.settings, now=NOW))
        self.assertEqual([i["slug"] for i in by["DE"]["items"]], ["spiritfarer"])
        self.assertEqual([i["slug"] for i in by["NO"]["items"]], ["hades"])

    def test_no_price_known_is_no_verdict(self):
        for slug in list(self.data["prices"]["BR"]):
            self.data["prices"]["BR"][slug] = {"status": "not_found"}
        self.data["prices"]["DE"]["good-job"] = {"status": "not_found"}
        r = {x["slug"]: x for x in planner.radar(self.data, self.settings, now=NOW)}["good-job"]
        # Nintendo kennt den Titel nirgends als kaufbar: etwa nur im Abo oder in einem Paket
        self.assertEqual((r["verdict"], r["reason"][:29]), ("none", "im eShop nicht einzeln kaufba"))
        self.data["prices"]["DE"]["good-job"] = {"status": "unreleased"}
        r = {x["slug"]: x for x in planner.radar(self.data, self.settings, now=NOW)}["good-job"]
        self.assertEqual(r["reason"], "noch nicht erschienen")
        # Kostenlose Titel brauchen kein Urteil
        self.data["prices"]["DE"]["good-job"] = {"status": "onsale", "currency": "EUR", "regular": 0}
        r = {x["slug"]: x for x in planner.radar(self.data, self.settings, now=NOW)}["good-job"]
        self.assertEqual((r["verdict"], r["reason"]), ("none", "kostenlos"))


class StepRowsTest(unittest.TestCase):
    """Preise je Zeile eines Schritts (0.99.3): was du zahlst, auf den Cent die Spiele des Schritts."""
    def test_card_payment_rows_and_cent_sum(self):
        data, s = sample()
        s["countries"]["BR"]["pay"] = "auto"
        s["countries"]["BR"]["cards"] = "100=16.00"
        for slug, reg, disc in (("hades", 150, 90), ("spiritfarer", 200, 150)):
            data["prices"]["BR"][slug] = {"status": "onsale", "currency": "BRL", "regular": reg, "discount": disc,
                                          "start": "2026-10-01T00:00:00Z", "end": "2026-10-20T00:00:00Z"}
        br = {p["code"]: p for p in planner.plans(data, s, basket=["hades", "spiritfarer"], now=NOW)}["BR"]
        self.assertEqual(br["via"], "card")
        self.assertAlmostEqual(sum(i["eur"] for i in br["items"]), br["games_cost"], places=2)
        for i in br["items"]:
            self.assertEqual(i["over"], i["alt"] is not None and i["eur"] > i["alt"] + 0.005)
        # Auf den Cent: Zeilen ergeben zusammen die Spiele, in jedem Land mit Kartenpreis
        for p in planner.plans(data, sample()[1], basket=["hades", "spiritfarer", "celeste"], now=NOW):
            if p.get("games_cost") is not None and not p["estimated"] and not p["direct_n"]:
                self.assertAlmostEqual(sum(i["eur"] for i in p["items"]), p["games_cost"], places=2, msg=p["code"])


class StoreTest(unittest.TestCase):
    def test_backup_adds_price_recording(self):
        # Die eigene Preisaufzeichnung lässt sich nicht neu laden: Die Sicherung ergänzt sie
        store.save_history({"BR": {"hades": [["2026-10-01T00:00:00Z", 33.59]]}})
        store.merge_history({"BR": {"hades": [["2026-09-01T00:00:00Z", 67.19],
                                              ["2026-10-01T00:00:00Z", 33.59], ["kaputt"]]},
                             "JP": {"celeste": [["2026-09-02T00:00:00Z", 2050]]}, "XX": "nein"})
        h = store.load_history()
        self.assertEqual(h["BR"]["hades"], [["2026-09-01T00:00:00Z", 67.19], ["2026-10-01T00:00:00Z", 33.59]])
        self.assertEqual(list(h), ["BR", "JP"])
        store.save_history({})

    def test_broken_file_is_kept_not_overwritten(self):
        # Kaputte Datei (0.99.2): Vorgabe laden, die Datei aber aufheben statt sie beim nächsten Speichern zu verlieren
        path = os.path.join(store.DATA_DIR, "history.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"BR": {"hades": [["2026-10')
        with mock.patch("builtins.print"):
            self.assertEqual(store.load_history(), {})
        kept = [n for n in os.listdir(store.DATA_DIR) if n.startswith("history.json.kaputt-")]
        self.assertEqual(len(kept), 1)
        os.remove(os.path.join(store.DATA_DIR, kept[0]))
        with open(path, "w", encoding="utf-8") as f:
            f.write("[]")                         # falsche Form zählt genauso
        with mock.patch("builtins.print"):
            self.assertEqual(store.load_history(), {})
        for n in os.listdir(store.DATA_DIR):
            if n.startswith("history.json.kaputt-"):
                os.remove(os.path.join(store.DATA_DIR, n))
        store.save_history({})

    def test_backup_keeps_cards_of_germany_with_balance(self):
        # Eine Sicherung hat für Deutschland leere Karten; die leerten bis 0.99.1 die von DG (0.99.2)
        before = store.load_settings()
        store.save_settings({"countries": {"DG": {"cards": "25 | 20.50"}}})
        s = store.load_settings()
        store.save_settings(s)
        self.assertEqual(store.load_settings()["countries"]["DG"]["cards"], "25 | 20.50")
        # Ältere Datei mit Karten bei Deutschland: kommen weiter zu DG, wenn DG keine hat
        store.save_settings({"countries": {"DG": {"cards": ""}, "DE": {"cards": "50 | 45"}}})
        self.assertEqual(store.load_settings()["countries"]["DG"]["cards"], "50 | 45")
        store.save_settings({"countries": {"DG": before["countries"]["DG"]}})

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
        # Angenommene Preise (1.3.0): nur Zahlen ab 0, leere Länder fallen weg
        ui = store.save_ui({"plan_assume": {"BR": {"hades": "12.5", "x": "nein", "y": -1}, "JP": {}, "NO": "x"}})
        self.assertEqual(ui["plan_assume"], {"BR": {"hades": 12.5}})
        self.assertEqual(store.save_ui({"plan_fill": {"BR": [str(n) for n in range(150)]}})["plan_fill"]["BR"][-1], "99")
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
        self.assertEqual(s["deal_eur"], {"buy": 0.5, "good": 2.0, "mini": 2.0})
        s = store.save_settings({"deal_eur": {"buy": "0,3", "good": -4, "x": 1}})
        self.assertEqual(s["deal_eur"], {"buy": 0.5, "good": 0.0, "mini": 2.0})
        s = store.save_settings({"eur_card_steps": {"top": "0.8", "good": 2, "x": 1}})
        self.assertEqual(s["eur_card_steps"], {"top": 0.8, "good": 1.0, "ok": 0.86})
        s = store.save_settings({"countries": {"JP": {"rest_blocks": True}}})
        self.assertTrue(store.load_settings()["countries"]["JP"]["rest_blocks"])  # deine Wahl bleibt
        # Stand 0.35: Amerika blockierte ab Werk, ab 0.36 nirgends mehr
        with open(os.path.join(store.DATA_DIR, "settings.json"), "w") as f:
            json.dump({"settings_v": 3, "countries": {"US": {"rest_blocks": True}}}, f)
        self.assertFalse(store.load_settings()["countries"]["US"]["rest_blocks"])
        store.save_settings({"countries": {"JP": {"rest_blocks": False}}})
        # „Deutschland (Guthaben)“ ist kein eigenes Konto, sondern das deutsche (0.63)
        with open(os.path.join(store.DATA_DIR, "settings.json"), "w") as f:
            json.dump({"current_country": "DG"}, f)
        self.assertEqual(store.load_settings()["current_country"], "DE")
        self.assertEqual(store.save_settings({"current_country": "DG"})["current_country"], "DE")
        self.assertEqual(store.save_settings({"current_country": ""})["current_country"], "")
        # 0.8.1 speicherte pauschal 10,5 % Eneba-Gebühr: wird zur gemessenen Formel
        with open(os.path.join(store.DATA_DIR, "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"settings_v": 1, "shop_fee_pct": 10.5}, f)
        s = store.load_settings()
        self.assertEqual((s["shop_fee_pct"], s["shop_fee_eur"], s["settings_v"]), (7.75, 0.4, 5))
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
        sync.status["log"] = []
        sync.sync_ids(data, settings, deny, lambda s: None, now=10 ** 9)
        # 0.54: Die Sperre beendet nur die ID-Suche, der Abgleich läuft mit Preisen weiter
        self.assertTrue(any("HTTP 429" in l and "5 offen" in l for l in sync.status["log"]))
        self.assertEqual(len(calls), 1)                    # nach der ersten Sperre Schluss
        self.assertTrue(all(not it["ids_checked"] for it in data["items"].values()))
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
            # Pläne in einer Anfrage (0.99): speichert die mitgeschickte Auswahl vorher, packt auf Wunsch
            c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
            c.request("POST", "/api/plaene", body=json.dumps({"ui": {"plan_good": True}}),
                      headers={"Content-Type": "application/json", "Accept-Encoding": "gzip"})
            r = c.getresponse()
            raw = r.read()
            c.close()
            self.assertEqual(r.status, 200)
            if r.getheader("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            body = json.loads(raw)
            self.assertEqual(set(body), {"plans", "bplans", "mix", "kauf"})
            self.assertTrue(store.load_ui()["plan_good"])
            store.save_ui({"plan_good": False})
            # Grenzen der Eingabe (0.99.1): negative Länge, kein JSON-Objekt, Verbindungstest nur per POST
            for length, raw_body in (("-1", b'{"dense": true}'), (None, b"[]")):
                c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
                c.putrequest("POST", "/api/ui")
                c.putheader("Content-Type", "application/json")
                c.putheader("Content-Length", length or str(len(raw_body)))
                c.endheaders()
                c.send(raw_body)
                r = c.getresponse()
                r.read()
                c.close()
                self.assertEqual(r.status, 400, length)
            c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
            c.request("GET", "/api/diag")
            r = c.getresponse()
            r.read()
            c.close()
            self.assertEqual(r.status, 404)
            self.assertEqual(r.getheader("X-Content-Type-Options"), "nosniff")
            # Fremde Adresse (0.99.5, DNS-Rebinding): abgewiesen; Namen im eigenen Netz und Eingetragenes gelten
            c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
            c.request("GET", "/api/export", headers={"Host": "angreifer.example"})
            r = c.getresponse()
            r.read()
            c.close()
            self.assertEqual(r.status, 421)
            self.assertTrue(server.host_allowed("kompass.home.arpa:8787", ""))
            self.assertTrue(server.host_allowed("[::1]:8787", ""))
            self.assertTrue(server.host_allowed("a.beispiel.de", ".beispiel.de"))
            self.assertFalse(server.host_allowed("beispiel.de.angreifer.example", ".beispiel.de"))
            # Abgleichsdaten ohne Kaufverlauf (0.99.1)
            with mock.patch.object(store, "load_data", return_value={"_eshop": {"entries": [1]}, "items": {}}):
                c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
                c.request("GET", "/api/abgleich")
                body = json.loads(c.getresponse().read())
                c.close()
            self.assertNotIn("_eshop", body["data"])
            # Unerwartete Fehler (0.82): an den Browser nur die Art, keine Pfade oder Innereien
            boom = mock.patch.object(planner, "case_export", side_effect=KeyError("/geheimer/pfad"))
            with boom, mock.patch.object(server.traceback, "print_exception"), mock.patch("builtins.print"):
                c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
                c.request("GET", "/api/fall?slug=x")
                r = c.getresponse()
                body = json.loads(r.read())
                c.close()
            self.assertEqual(r.status, 500)
            self.assertIn("KeyError", body["error"])
            self.assertNotIn("geheimer", body["error"])
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
            lines = sync.diagnose(sleep=lambda s: None)
        finally:
            sources.request = old
            store.save_settings({"countries": {"US": {"cards": ""}}})
        text = "\n".join(lines)
        self.assertIn("Guthabenkarte US (www.eneba.com)", text)
        self.assertIn("Preis in Produktdaten: (52.37, 'EUR')", text)
        self.assertIn("Sprachen Japan", text)
        self.assertIn("price_history_data: nicht gefunden", text)
        self.assertEqual(set(seen), {None})                # immer die eigene Kennung


    def test_diagnose_probes_membership_prices(self):
        # Vorarbeit Online-Mitgliedschaft: DekuDeals je Land nennt die eShop-ID im Link der
        # Preistabelle (0.53.6), damit fragt der Test die Preis-Schnittstelle; nichts wird gespeichert
        store.save_settings({"wishlist_url": "https://www.dekudeals.com/wishlist/abc"})
        urls = []
        hist = json.dumps({"headers": ["Nintendo eShop"], "data": [["2026-10-12", None, 109.9], ["2026-10-13", None, 109.9]]})

        def page(cc, nsuid):
            return (f'<title>NSO</title><script id="price_history_data" type="application/json">{hist}</script>'
                    '<script id="price_history_indices" type="application/json">{"all":[0,1,2],"physical":[0,1],"digital":[0,1,2]}</script>'
                    f"<a data-out-analytics-id='eshop_{cc}:{nsuid}' href='https://ec.nintendo.com/X/x/membership'>eShop</a>")

        def request(url, ua=None, timeout=25):
            urls.append(url)
            text = (page("de", "70080000000189") if "country=de" in url else page("br", "70080000000186")) \
                if sync.MEMBERSHIP_SLUG in url else '{"prices":[]}' if "/v1/price" in url else ""
            return {"url": url, "status": 200, "text": text, "enc": "", "server": "t", "error": ""}
        with mock.patch.object(sources, "request", request):
            text = "\n".join(sync.diagnose(sleep=lambda s: None))
        self.assertIn("Mitgliedschaft DekuDeals (DE): HTTP 200", text)
        self.assertIn("eShop-IDs ['70080000000189'], alle Länder ['DE'], Verlauf: 2 Tage, zuletzt [('2026-10-12', 109.9), ('2026-10-13', 109.9)]", text)
        self.assertIn("weitere Varianten: keine verlinkt", text)
        self.assertTrue(any("country=DE" in u and "ids=70080000000189" in u for u in urls))
        self.assertTrue(any("country=BR" in u and "ids=70080000000186" in u for u in urls))
        self.assertIn("Mitgliedschaft Nintendo-Preise (BR): HTTP 200", text)
        # 0.54.1: auch Ersatzquelle der Kurse und titledb (nur Kopfdaten)
        self.assertIn("Wechselkurse, Ersatzquelle: HTTP 200", text)
        self.assertIn("titledb (JP.ja): HTTP 200, Größe 25 MB", text)

    def test_diagnose_with_dlc_sections(self):
        # 0.50 bis 0.53.2: Die Liste der gefundenen Abschnitte (Texte) brach den Test ab,
        # sobald das Spiel DLC hatte („too many values to unpack“)
        store.save_settings({"wishlist_url": "https://www.dekudeals.com/wishlist/abc"})

        def request(url, ua=None, timeout=25):
            return {"url": url, "status": 200, "text": GAME_PAGE if "/items/" in url else "",
                    "enc": "", "server": "t", "error": ""}
        with mock.patch.object(sources, "request", request):
            text = "\n".join(sync.diagnose(sleep=lambda s: None))
        self.assertIn("Abschnitte: ", text)
        self.assertNotIn("nicht auswertbar", text)

    def test_diagnose_skips_nintendo_co_jp(self):
        # 4.6 entschieden (13.10.2026): nintendo.co.jp kennt kaum Titel, der Test fragt es nicht mehr
        store.save_settings({"wishlist_url": "https://www.dekudeals.com/wishlist/abc"})
        urls = []

        def request(url, ua=None, timeout=25):
            urls.append(url)
            return {"url": url, "status": 200, "text": "", "enc": "", "server": "t", "error": ""}
        with mock.patch.object(sources, "request", request):
            sync.diagnose(sleep=lambda s: None)
        self.assertFalse(any("nintendo.co.jp" in u for u in urls))

    def test_diagnose_probes_game_infos(self):
        # 1.4.1: Spielinfos für die Sammlung. Felder der Europa-Suche zu Spielen der Sammlung und
        # Fundstellen auf der Shopseite des ersten; Adressen außerhalb von nintendo.com nicht
        store.save_settings({"wishlist_url": "https://www.dekudeals.com/wishlist/abc"})
        data = store.load_data()
        saved = json.loads(json.dumps(data))
        data["owned"] = ["snipperclips"]
        data["items"]["snipperclips"] = {"ids": {"EU": ["70010000000038"]}}
        store.save_data(data)
        self.addCleanup(store.save_data, saved)
        urls = []
        solr = json.dumps({"response": {"docs": [{
            "title": "Snipperclips", "nsuid_txt": ["70010000000038"], "players_to": 4,
            "pretty_game_categories_txt": ["Puzzle"], "url": "/de-de/Spiele/snipperclips"}]}})

        def request(url, ua=None, timeout=25):
            urls.append(url)
            if "GameShare-2785626" in url:
                return {"url": url, "status": 404 if "/de-de/" in url else 200, "enc": "", "server": "t", "error": "",
                        "text": "<title>GameShare</title><table><tr><th>Spiel</th><th>Local</th></tr><tr><td>Mario</td><td>Sí</td></tr></table>"}
            text = solr if "fl=%2A" in url else wiki if "wikidata" in url else \
                "<title>Snipperclips</title><p>Bis zu 4 Spieler im Koop, GameShare</p>" if "/de-de/" in url else \
                "<dl><dt>Genre</dt><dd>Puzzle</dd><dt>Players</dt><dd>1-4</dd></dl>" if "/items/" in url else ""
            return {"url": url, "status": 200, "text": text, "enc": "", "server": "t", "error": ""}
        wiki = json.dumps({"results": {"bindings": [{"name": {"value": "Snipperclips"}, "modes": {"value": "multiplayer video game, co-op"},
                                                      "maxp": {"value": "4"}}]}})
        with mock.patch.object(sources, "request", request), mock.patch.object(store, "load_keys", lambda: dict(store.KEYS)):
            text = "\n".join(sync.diagnose(sleep=lambda s: None))
        self.assertTrue(any("nsuid_txt%3A%2870010000000038%29" in u for u in urls))
        self.assertIn("Spielinfos DekuDeals (snipperclips, schon gelesen): Genre Puzzle Players 1-4", text)
        self.assertIn('Spielinfos DekuDeals gelesen: {}', text)          # dt/dd ohne Doppelpunkt: kein Kasten „Details“
        self.assertIn("GameShare-Liste: HTTP 404", text)            # erst Deutschland, dann Spanien
        self.assertIn("Tabellenzeilen 2, Anfang der Tabelle: Spiel Local Mario Sí", text)
        self.assertIn("Wikidata: HTTP 200", text)
        self.assertIn("„Snipperclips“: Modus multiplayer video game, co-op; Genre –; Spieler ––4", text)
        self.assertIn("IGDB: kein Schlüssel", text)
        self.assertIn("„Snipperclips“: players_to=4; pretty_game_categories_txt=['Puzzle']", text)
        self.assertIn("Spielinfos Shopseite: HTTP 200", text)
        self.assertIn("4 Spieler im Koop, GameShare", text)
        self.assertIn("https://www.nintendo.com/de-de/Spiele/snipperclips", urls)
        # Fremde Adresse in der Antwort: nicht abrufen
        solr = solr.replace("/de-de/Spiele/snipperclips", "https://example.org/x")
        urls.clear()
        with mock.patch.object(sources, "request", request):
            text = "\n".join(sync.diagnose(sleep=lambda s: None))
        self.assertIn("außerhalb von nintendo.com (example.org), nicht angefragt", text)
        self.assertNotIn("https://example.org/x", urls)

    def test_igdb_probe_keeps_key_secret(self):
        # 1.4.2: IGDB nur mit Schlüssel aus der Umgebung; Twitch-Zugang per POST, Schlüssel nie in der Ausgabe
        calls = []

        def request(url, ua=None, timeout=25, data=None, headers=None):
            calls.append((url, data, headers or {}))
            if "twitch" in url:
                return {"url": url, "status": 200, "text": '{"access_token": "tok"}', "enc": "", "server": "t", "error": ""}
            games = [{"id": 1, "name": "Snipperclips", "game_modes": [{"id": 3, "name": "Co-operative"}],
                      "genres": [{"id": 9, "name": "Puzzle"}],
                      "multiplayer_modes": [{"id": 5, "offlinecoop": True, "offlinecoopmax": 4}]}]
            return {"url": url, "status": 200, "text": json.dumps(games), "enc": "", "server": "t", "error": ""}
        with mock.patch.object(sources, "request", request):
            lines = sync.igdb_probe(["Snipperclips™"], sleep=lambda s: None,
                                    keys={"igdb_id": "cid", "igdb_secret": "geheim123"})
        text = "\n".join(lines)
        self.assertIn("Modi ['Co-operative']; Genres ['Puzzle']", text)
        self.assertIn("'offlinecoopmax': 4", text)
        self.assertNotIn("geheim123", text)
        self.assertNotIn("geheim123", calls[0][0])                  # nicht in der Adresse, nur im Inhalt
        self.assertIn(b"client_secret=geheim123", calls[0][1])
        self.assertEqual(calls[1][1], b'search "Snipperclips"; ' + sync.IGDB_FIELDS.encode())
        self.assertEqual(calls[1][2]["Authorization"], "Bearer tok")
        self.assertEqual(sync.igdb_probe(["x"], keys={}), ["IGDB: kein Schlüssel eingetragen (Einstellungen, Quellen), nicht angefragt"])

    def test_sources_state_from_log(self):
        # 1.5.0: Zustand je Quelle aus dem Protokoll; ein Problem schlägt jede gute Zeile, eine Quelle
        # ohne Zeile behält den letzten Zustand, Wishlist-Kennungen bleiben verdeckt
        data = {"sources": {"titledb": {"ok": False, "note": "titledb: nicht abrufbar", "at": "x"}}}
        sync.remember_sources(data, [
            "23:06:37 Wishlist: HTTP 403 bei https://www.dekudeals.com/wishlist/geheim1",
            "23:06:39 Sammlung: 108 Titel",
            "23:06:46 DE: 114 von 119 Titeln kaufbar",
            "23:08:25 Kartenpreise: Shop lehnt Abrufe ab (429 bei https://shop.example/x), Werte von Hand gelten weiter",
            "23:08:25 Kartenpreise: 10 von 12 gelesen",
            "23:09:19 Sprachen Japan: 2 Seiten offen, der Store zeigte zuletzt den Warteraum",
            "23:09:19 Sprachen Europa: nichts fällig",
            "23:09:20 Spielinfos DekuDeals: 40 von 108 Spielen der Sammlung, 68 folgen",
            "23:09:21 Spielinfos Nintendo nicht abrufbar (HTTP 503)"], now=1e9)
        src = data["sources"]
        self.assertEqual((src["deku"]["ok"], src["deku"]["note"]), (False, "Wishlist: HTTP 403 bei https://www.dekudeals.com/wishlist/…"))
        self.assertTrue(src["prices"]["ok"])
        self.assertFalse(src["cards"]["ok"])
        self.assertIn("429", src["cards"]["note"])
        self.assertFalse(src["lang_jp"]["ok"])
        self.assertTrue(src["lang_eu"]["ok"])
        self.assertEqual(src["titledb"]["note"], "titledb: nicht abrufbar")       # nichts gesagt: bleibt
        self.assertNotIn("fx", src)
        self.assertFalse(src["ginfo"]["ok"])

    def test_wishlist_env_only_as_start_value(self):
        # 1.5.0: WISHLIST_URL füllt nur eine frische Installation, ein geleertes Feld bleibt leer
        path = store._path("settings.json")
        saved = store.load_settings() if os.path.exists(path) else None

        def back():
            if os.path.exists(path):
                os.remove(path)
            if saved is not None:
                store._save("settings.json", saved)
        self.addCleanup(back)
        if os.path.exists(path):
            os.remove(path)
        with mock.patch.dict(os.environ, {"WISHLIST_URL": "https://www.dekudeals.com/wishlist/start"}):
            self.assertEqual(store.load_settings()["wishlist_url"], "https://www.dekudeals.com/wishlist/start")
            store.save_settings({"wishlist_url": ""})
            self.assertEqual(store.load_settings()["wishlist_url"], "")

    def test_keys_stay_out_of_settings_and_backup(self):
        # 1.4.3: Schlüssel in keys.json, nicht in den Einstellungen; die Oberfläche sieht nur „eingetragen“
        self.addCleanup(store.save_keys, {"igdb_id": "", "igdb_secret": ""})
        self.assertEqual(store.keys_view(), {"igdb": False})
        store.save_keys({"igdb_id": " cid ", "igdb_secret": "geheim123", "other": "x"})
        self.assertEqual(store.load_keys(), {"igdb_id": "cid", "igdb_secret": "geheim123"})
        self.assertEqual(store.keys_view(), {"igdb": True})
        store.save_settings({"igdb_secret": "nein"})
        self.assertNotIn("igdb_secret", store.load_settings())
        self.assertNotIn("geheim123", json.dumps(store.load_settings()))
        store.save_keys({"igdb_secret": ""})
        self.assertEqual(store.keys_view(), {"igdb": False})

    def test_diagnose_reads_history_from_item_page(self):
        # Bis 0.37 suchte der Verbindungstest den Verlauf in robots.txt statt in der Artikelseite
        store.save_settings({"wishlist_url": "https://www.dekudeals.com/wishlist/abc"})

        def request(url, ua=None, timeout=25):
            text = ('<script id="price_history_data" type="application/json">[1]</script>'
                    if "/items/" in url else "")
            return {"url": url, "status": 200, "text": text, "enc": "", "server": "t", "error": ""}
        with mock.patch.object(sources, "request", request):
            text = "\n".join(sync.diagnose(sleep=lambda s: None))
        self.assertIn("Verlauf, price_history_data: 3 Zeichen", text)

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
            if "ec.nintendo.com/" in url and url.endswith("/membership"):
                return "<html>ohne Mitgliedschaftsdaten</html>"
            if "ec.nintendo.com/US/en/titles/" in url:
                # Seite des Hauptspiels: Der DLC auf der Wishlist übernimmt seine Sprache (0.68)
                return '<script>{"supportedLanguages":["English","German"]}</script>'
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
        self.assertEqual(sum("country=br" in u and "nintendo-switch-online" not in u for u in calls), 1)
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
        self.assertNotIn("card_market", data)                            # gg.deals ist ausgebaut
        self.assertNotIn("DG", data["prices"])                           # kein eigener eShop
        self.assertFalse(any("Preisabruf fehlgeschlagen" in l for l in sync.status["log"]))
        # Stand der ID-Suche einmal, nach titledb, damit er dessen IDs schon enthält
        state = [i for i, l in enumerate(sync.status["log"]) if "Fehlende DLC der Sammlung" in l]
        self.assertEqual(len(state), 1)
        self.assertFalse(any("titledb" in l for l in sync.status["log"][state[0]:]))
        n = len(calls)
        sync.run_sync(fetch=fake, sleep=lambda s: None)
        # zweiter Lauf sucht weder IDs, Sprachen noch Tiefstpreise:
        # Wishlist (2), Sammlung (2), Kurse (1), Preise (19 Länder minus das ruhende Chile)
        self.assertEqual(len(calls) - n, 2 + 2 + 1 + 18)
        self.assertEqual(len(store.load_history()["BR"]["vs-foscari"]), 1)  # kein Preiswechsel
        # Ein Fehler in einem späten Schritt überspringt die übrigen nicht (0.99.2)
        with mock.patch.object(sync, "sync_related", side_effect=KeyError("x"), __name__="sync_related"), \
                mock.patch.object(sync, "sync_titledb") as tdb, mock.patch("traceback.print_exc"):
            sync.run_sync(fetch=fake, sleep=lambda s: None)
        self.assertFalse(sync.status["ok"])
        self.assertTrue(any("sync_related abgebrochen" in l for l in sync.status["log"]))
        self.assertTrue(tdb.called)

    def test_low_is_lowered_by_own_tracking(self):
        data = {"lows": {"BR": {"a": {"low": 5.0, "src": "deku"}, "b": {"low": 99.0}}}}
        table = {"a": {"status": "onsale", "currency": "BRL", "regular": 10, "discount": 4},
                 "b": {"status": "onsale", "currency": "BRL", "regular": 10}}
        hist = {}
        sync._track(data, hist, "BR", table, "2026-10-11T00:00:00+00:00")
        self.assertEqual(data["lows"]["BR"]["a"]["low"], 4.0)
        self.assertEqual(data["lows"]["BR"]["a"]["src"], "own")
        self.assertNotIn("low", data["lows"]["BR"]["b"])   # über Normalpreis: verworfen
        self.assertIn("BR: 1 Tiefstpreis von DekuDeals verworfen, über dem Normalpreis: b (99.00 über 10.00)",
                      sync.status["log"][-1])                 # und im Protokoll (0.95)
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
            self.assertEqual((e["sales"], e["sales_at"]), ([["2025-01-02", 10, "2025-01-02"], ["2025-01-05", 12, "2025-01-05"]], 1736467200))
            sync.sync_lows(data, settings, fetch=None, sleep=lambda s: None, now=1736467200 + 86400)
            self.assertEqual(got, ["a", "b"])                  # frisch: kein zweiter Abruf
            # Seite mit Tiefstpreisen für Switch und Switch 2: Verlauf gilt nicht als Bestpreis
            e = {}
            sync._store_low({"lows": {"DE": {"c": e}}}, settings, "DE", "c", 9.0, 1, series, platforms=2)
            self.assertEqual((e.get("hist_multi"), "hist" in e, e["hist_v"]), (True, False, sync.HIST_V))
        finally:
            sources.fetch_item = orig


class SyncLogTest(unittest.TestCase):
    """0.54: jeder Schritt schreibt eine Zeile, Wechselkurse nur, wenn die Quelle Neues hat."""

    def test_fx_only_when_the_source_has_new_rates(self):
        calls = []

        def fake(url, ua=None):
            calls.append(url)
            return json.dumps({"result": "success", "time_last_update_utc": "Tue, 13 Oct 2026 00:02:31 +0000",
                               "rates": {"NOK": 11.5}})
        t = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc).timestamp()
        data = {"fx": {"rates": {"NOK": 11.0}, "updated": "Mon, 12 Oct 2026 00:02:31 +0000"}}
        sync.status["log"] = []
        sync.sync_fx(data, fake, now=t)
        self.assertEqual((len(calls), data["fx"]["rates"]["NOK"], data["fx"]["src"]), (1, 11.5, "open.er-api"))
        self.assertIn("(open.er-api)", sync.status["log"][-1])
        sync.sync_fx(data, fake, now=t + 6 * 3600)                    # Quelle noch nicht erneuert
        self.assertEqual(len(calls), 1)
        self.assertIn("aktuell, nicht abgerufen", sync.status["log"][-1])
        sync.sync_fx(data, fake, now=t + 21 * 3600)                   # nächster Tag: wieder fragen
        self.assertEqual(len(calls), 2)

    def test_item_page_once_per_sync(self):
        # 0.54.1: Während eines Abgleichs kommt jede Artikelseite höchstens einmal
        calls = []

        def fake(url, ua=None):
            calls.append(url)
            return "<title>X | Deku Deals</title>"
        try:
            sources.item_cache = {}
            sources.fetch_item("x", "de", fetch=fake)
            sources.fetch_item("x", "de", fetch=fake)
            sources.fetch_item("x", "pl", fetch=fake)
        finally:
            sources.item_cache = None
        self.assertEqual(len(calls), 2)
        sources.fetch_item("x", "de", fetch=fake)                       # außerhalb wieder frisch
        self.assertEqual(len(calls), 3)

    def test_old_titles_pruned_after_180_days(self):
        # 0.54.1: weg von Wishlist und Sammlung -> nach 180 Tagen raus aus items, lows, rel
        t0 = 1_800_000_000
        data = {"items": {"a": {"active": True}, "old": {"active": False}, "mine": {"active": False}},
                "owned": ["mine"], "extra": {"dlc": {}},
                "lows": {"DE": {"a": {"low": 1}, "old": {"low": 2}, "dlc": {"low": 3}}},
                "rel": {"old": {}, "mine": {}}, "lchk": {"old": 1}}
        sync.prune_old(data, now=t0)
        self.assertEqual(data["items"]["old"]["gone_at"], t0)              # Frist beginnt
        sync.prune_old(data, now=t0 + 179 * 86400)
        self.assertIn("old", data["items"])
        data["items"]["old"]["active"] = True                              # zurück auf der Wishlist
        sync.prune_old(data, now=t0 + 179 * 86400)
        self.assertNotIn("gone_at", data["items"]["old"])
        data["items"]["old"]["active"] = False
        sync.prune_old(data, now=t0 + 200 * 86400)
        sync.prune_old(data, now=t0 + 381 * 86400)
        self.assertEqual(sorted(data["items"]), ["a", "mine"])
        self.assertEqual(sorted(data["lows"]["DE"]), ["a", "dlc"])
        self.assertEqual((sorted(data["rel"]), data["lchk"]), (["mine"], {}))
        self.assertIn("Aufräumen: 1 Titel (seit 180 Tagen weder auf der Wishlist noch in der Sammlung); "
                      "1 Tiefstpreis-Einträge von 1 Titeln ohne Bezug (old); 1 DLC-Seiten ohne Bezug entfernt", sync.status["log"][-1])

    def test_lows_line_counts_the_wishlist_only(self):
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code == "DE"
        data = {"items": {"a": {"active": True}, "b": {"active": True}, "old": {"active": False}},
                "prices": {}, "lows": {"DE": {"a": {"low": 5.0, "sales": [[1]]}, "old": {"checked": 1}}}}
        sync.status["log"] = []
        sync.sync_lows(data, settings, None, lambda s: None)
        self.assertEqual(sync.status["log"][-1][9:],
                         "Tiefstpreise: nichts fällig; Wishlist 1 von 2 Titeln mit Tiefstpreis, 1 mit Angebotsverlauf")


class EshopHistoryTest(unittest.TestCase):
    """Kaufverlauf aus dem eShop (Browser-Helfer „Käufe lesen“)."""
    def setUp(self):
        for name in ("data.json", "eshop_history.json"):
            try:
                os.remove(os.path.join(store.DATA_DIR, name))
            except FileNotFoundError:
                pass
        data = store.load_data()
        data["items"] = {
            "hades": {"title": "Hades", "active": True, "ids": {"AM": ["70010000012345"]}},
            "celeste": {"title": "Celeste™", "active": True, "ids": {}},
            "spiritfarer": {"title": "Spiritfarer", "active": True, "ids": {}}}
        data["extra"] = {"vs-foscari": {"title": "Tides of the Foscari", "parent": "vampire-survivors",
                                        "ids": {"AM": ["70050000099999"]}}}
        data["owned"] = ["vampire-survivors"]
        store.save_data(data)

    def imp(self, entries, region="BR"):
        return sync.import_eshop_history(json.dumps({"region": region, "entries": entries}), now=1)

    def test_matched_by_id_title_and_kept_after_dlc_leaves_list(self):
        res = self.imp([{"id": "70010000012345", "title": "Hades (pt)", "date": "2026-10-01"},
                        {"id": "", "title": "CELESTE", "date": "2026-09-01"},
                        {"id": "70050000099999", "title": "Marés dos Foscari", "date": "2026-08-01"},
                        {"id": "70010000000001", "title": "Outro jogo", "date": "2026-07-01"}])
        self.assertEqual((res["read"], res["new"], res["matched"], res["open"]), (4, 4, 3, 1))
        data = store.load_data()
        self.assertEqual(planner.owned_set(data), {"vampire-survivors", "hades", "celeste", "vs-foscari"})
        how = {r["title"]: r["how"] for r in planner.eshop_matches(data)["rows"]}
        self.assertEqual(how["Hades (pt)"], "id")
        self.assertEqual(how["CELESTE"], "title")
        # Der gekaufte DLC fällt aus den fehlenden DLC, die Zuordnung bleibt trotzdem
        del data["extra"]["vs-foscari"]
        self.assertIn("vs-foscari", planner.owned_set(data))
        with open(os.path.join(store.DATA_DIR, "data.json"), encoding="utf-8") as f:
            self.assertNotIn("_eshop", json.load(f))

    def test_pick_any_known_title_shows_name_and_game(self):
        # Ab 0.69: eigene Zuordnung per DekuDeals-Link; Name und Spiel auch für DLC, die nicht
        # mehr unter den fehlenden stehen, sonst ein lesbarer Ersatz statt des Slugs
        self.imp([{"id": "", "title": "Radikale Reptilien", "date": "2026-10-01"},
                  {"id": "", "title": "Etwas", "date": "2026-09-01"}])
        data = store.load_data()
        data["rel"] = {"shell-game": {"title": "Shell Game", "dlc": [["shell-game-radical-reptiles", "Radical Reptiles"]]}}
        store.save_data(data)
        key = {e["title"]: e["key"] for e in store.load_eshop_history()["entries"]}
        store.pick_eshop_history(key["Radikale Reptilien"], "shell-game-radical-reptiles")
        store.pick_eshop_history(key["Etwas"], "some-other-game-70010000012345")
        with self.assertRaises(ValueError):
            store.pick_eshop_history(key["Etwas"], "https://www.dekudeals.com/items/x")
        rows = {r["title"]: r for r in planner.eshop_matches(store.load_data())["rows"]}
        self.assertEqual((rows["Radikale Reptilien"]["name"], rows["Radikale Reptilien"]["game"]), ("Radical Reptiles", "Shell Game"))
        self.assertEqual(rows["Etwas"]["name"], "Some Other Game")
        self.assertEqual(rows["Etwas"]["how"], "pick")

    def test_groups_collection_ticket_unknown(self):
        # 0.71: Was in der DekuDeals-Sammlung steht, fragt das Tool nicht; Mitgliedschaften zählen nicht
        self.imp([{"id": "", "title": "Vampire Survivors", "date": "2026-10-03"},
                  {"id": "", "title": "Hades (pt)", "date": "2026-10-02"},
                  {"id": "", "title": "12 meses", "date": "2026-10-01", "item": "TICKET"},
                  {"id": "", "title": "Etwas ganz anderes", "date": "2026-09-01"},
                  {"id": "70010000012345", "title": "Hades", "date": "2026-08-01"}])
        data = store.load_data()
        data["rel"] = {"vampire-survivors": {"title": "Vampire Survivors", "dlc": []}}
        rows = {r["title"]: r for r in planner.eshop_matches(data)["rows"]}
        self.assertEqual((rows["Vampire Survivors"]["group"], rows["Vampire Survivors"]["coll"]), ("coll", "vampire-survivors"))
        self.assertEqual(rows["12 meses"]["group"], "ticket")
        self.assertEqual(rows["Etwas ganz anderes"]["group"], "unknown")
        self.assertEqual(rows["Hades"]["group"], "plan")            # gekauft, bei DekuDeals nachtragen
        self.assertEqual(rows["Hades (pt)"]["group"], "ask")        # ähnlich zu einem Wishlist-Titel

    def test_english_names_from_titledb(self):
        # 0.72: Japanische Kauftitel bekommen über die Programm-ID den englischen Namen
        self.imp([{"id": "", "title": "セレステ", "date": "2026-10-01"},
                  {"id": "", "title": "ヴァンパイア サバイバーズ", "date": "2026-09-01"},
                  {"id": "", "title": "知らない", "date": "2026-08-01"}], region="JP")
        lists = {"JP.ja": {"1": {"id": "0100AAA0", "name": "セレステ"}, "2": {"id": "0100BBB0", "name": "ヴァンパイア・サバイバーズ"}},
                 "US.en": {"3": {"id": "0100AAA0", "name": "Celeste"}, "4": {"id": "0100BBB0", "name": "Vampire Survivors"}}}
        calls = []

        def fake(url):
            calls.append(url)
            return json.dumps(next(v for k, v in lists.items() if k in url), ensure_ascii=False)
        data = store.load_data()
        data["rel"] = {"vampire-survivors": {"title": "Vampire Survivors", "dlc": []}}
        sync.sync_eshop_names(data, fake, now=2e9)
        self.assertEqual(len(calls), 2)
        rows = {r["title"]: r for r in planner.eshop_matches(data)["rows"]}
        self.assertEqual((rows["セレステ"]["slug"], rows["セレステ"]["how"]), ("celeste", "eng"))
        self.assertEqual((rows["ヴァンパイア サバイバーズ"]["group"], rows["ヴァンパイア サバイバーズ"]["eng"]), ("coll", "Vampire Survivors"))
        self.assertEqual(rows["知らない"]["group"], "unknown")
        sync.sync_eshop_names(data, fake, now=2e9 + 60)    # nichts Neues: kein Abruf
        self.assertEqual(len(calls), 2)

    def test_japanese_names_found_while_account_elsewhere(self):
        # 0.76: Gelesen, als das Konto in Brasilien stand; japanische Titel suchen trotzdem in Japan.
        # Ein alter Fehlversuch in der falschen Liste (ohne Angabe der Liste) wird wiederholt
        self.imp([{"id": "", "title": "セレステ", "date": "2026-01-26"}], region="BR")
        lists = {"JP.ja": {"1": {"id": "0100AAA0", "name": "セレステ"}},
                 "US.en": {"3": {"id": "0100AAA0", "name": "Celeste"}}}
        calls = []

        def fake(url):
            calls.append(url)
            return json.dumps(next(v for k, v in lists.items() if k in url), ensure_ascii=False)
        data = store.load_data()
        data["eshop_names"] = {"セレステ": [None, 2e9 - 86400]}
        sync.sync_eshop_names(data, fake, now=2e9)
        self.assertTrue(any("JP.ja" in u for u in calls))
        self.assertEqual(data["eshop_names"]["セレステ"][0], "Celeste")
        self.assertEqual(sync._name_file("Algo", "BR"), "BR.pt")

    def test_name_lists_wait_each_on_their_own(self):
        # 0.77: Die Woche Ruhe gilt je Liste. Lud der letzte Abgleich nur die Liste des
        # Konto-Landes, lädt die japanische Liste trotzdem gleich
        self.imp([{"id": "", "title": "セレステ", "date": "2026-01-26"},
                  {"id": "", "title": "Algo desconhecido", "date": "2026-01-20"}], region="BR")
        lists = {"JP.ja": {"1": {"id": "0100AAA0", "name": "セレステ"}},
                 "BR.pt": {}, "DE.de": {}, "US.en": {"3": {"id": "0100AAA0", "name": "Celeste"}}}
        calls = []

        def fake(url):
            calls.append(url)
            return json.dumps(next(v for k, v in lists.items() if k in url), ensure_ascii=False)
        data = store.load_data()
        data["eshop_names_at"], data["eshop_names_v"] = 2e9 - 86400, 1
        data["eshop_names"] = {"セレステ": [None, 2e9 - 86400, "BR.pt"], "Algo desconhecido": [None, 2e9 - 86400, "BR.pt"]}
        sync.sync_eshop_names(data, fake, now=2e9)
        self.assertTrue(any("JP.ja" in u for u in calls))
        self.assertFalse(any("BR.pt" in u for u in calls))
        self.assertEqual(data["eshop_names"]["セレステ"][0], "Celeste")
        self.assertEqual(data["eshop_names_files"]["BR.pt"], 2e9 - 86400)
        calls.clear()
        data["eshop_names"]["セレステ"] = [None, 2e9, "JP.ja"]      # nach dem Laden: Woche Ruhe
        sync.sync_eshop_names(data, fake, now=2e9 + 60)
        self.assertEqual(calls, [])

    def test_by_hand_skips_quiet_times_only(self):
        # 0.80: Von Hand gestartet gilt die Woche Ruhe der Listen nicht, die Pause nach einem
        # Fehlschlag auch nicht; das Protokoll nennt, was übergangen wurde
        self.imp([{"id": "", "title": "セレステ", "date": "2026-01-26"}], region="BR")
        calls = []

        def fake(url):
            calls.append(url)
            return "{}"
        data = store.load_data()
        data["eshop_names_v"], data["eshop_names_files"] = 1, {"JP.ja": 2e9 - 3600}
        sync.sync_eshop_names(data, fake, now=2e9)
        self.assertEqual(calls, [])                         # automatisch: Woche Ruhe
        sync.manual.update(on=True, skipped=[])
        try:
            sync.sync_eshop_names(data, fake, now=2e9)
        finally:
            sync.manual["on"] = False
        self.assertTrue(any("JP.ja" in u for u in calls))
        self.assertEqual(sync.manual["skipped"], ["Namen gekaufter Titel: jede Liste einmal die Woche"])
        self.assertFalse(sync._quiet(10, 5, "x"))
        self.assertTrue(sync._quiet(1, 5, "x"))
        self.assertEqual(sync._card_wait(), sync.CARD_RECHECK_SECONDS)

    def test_old_name_misses_looked_up_again_once(self):
        # 0.79: Käufe ohne englischen Namen aus älteren Versionen werden einmal neu nachgeschlagen
        data = {"_eshop": {"entries": [{"key": "a", "title": "x"}]},
                "eshop_names": {"Celeste (pt)": ["Celeste", 1, "BR.pt"], "Algo": [None, 1, "BR.pt"]},
                "eshop_names_files": {"BR.pt": 2e9}}
        with mock.patch.object(planner, "eshop_matches", lambda d: {"rows": []}):
            sync.sync_eshop_names(data, lambda u: "{}", now=2e9)
        self.assertEqual((list(data["eshop_names"]), data["eshop_names_files"], data["eshop_names_v"]),
                         (["Celeste (pt)"], {}, 1))

    def test_passes_editions_and_pairs(self):
        # 0.79: Pässe ohne Programm-ID (Spielname + Pass oder Shop-ID), Spiele, die DekuDeals nur als
        # Switch 2 Edition führt, Käufe „A + B“ und chinesische Titel (Hongkong)
        self.imp([{"id": "", "title": "ねこのぼうけん", "date": "2026-10-05"},
                  {"id": "", "title": "ねこのぼうけん Nintendo Switch 2 Edition アップグレードパス", "date": "2026-10-04"},
                  {"id": "", "title": "うさぎファイト ファイターパス", "date": "2026-10-03"},
                  {"id": "", "title": "うさぎファイト エキスパンション・パス", "date": "2026-10-02"},
                  {"id": "", "title": "ほしのたび + ほしのたび 2", "date": "2026-10-01"},
                  {"id": "", "title": "貓咪大冒險", "date": "2026-09-30"}], region="DE")
        lists = {"JP.ja": {"70010000000001": {"id": "0100AAA0", "name": "ねこのぼうけん"},
                           "70010000000002": {"id": "0100BBB0", "name": "うさぎファイト"},
                           "70050000000003": {"id": None, "name": "ねこのぼうけん Nintendo Switch 2 Edition アップグレードパス"},
                           "70070000000077": {"id": None, "name": "うさぎファイト　エキスパンション・パス"},
                           "70010000000004": {"id": "0100CCC0", "name": "ほしのたび"},
                           "70010000000005": {"id": "0100DDD0", "name": "ほしのたび ２"}},
                 "HK.zh": {"70010000000006": {"id": "0100AAA0", "name": "貓咪大冒險"}},
                 "US.en": {"1": {"id": "0100AAA0", "name": "Cat Adventure™"}, "2": {"id": "0100BBB0", "name": "Bunny Fight"},
                           "3": {"id": "0100CCC0", "name": "Star Trip"}, "4": {"id": "0100DDD0", "name": "Star Trip 2"}}}

        def fake(url):
            return json.dumps(next((v for k, v in lists.items() if k in url), {}), ensure_ascii=False)
        data = store.load_data()
        data["owned"] = ["cat-adventure-switch-2", "bunny-fight", "star-trip-and-star-trip-2"]
        data["rel"] = {"cat-adventure-switch-2": {"title": "Cat Adventure – Nintendo Switch 2 Edition + Extra World", "dlc": []},
                       "bunny-fight": {"title": "Bunny Fight", "dlc": []},
                       "star-trip-and-star-trip-2": {"title": "Star Trip + Star Trip 2", "dlc": []}}
        data["extra"] = {"bunny-fight-fighters-pass": {"title": "Fighters Pass", "parent": "bunny-fight", "ids": {}},
                         "bunny-fight-fighters-pass-vol-2": {"title": "Fighters Pass Vol. 2", "parent": "bunny-fight", "ids": {}},
                         "bunny-fight-expansion-pass": {"title": "Expansion Pass", "parent": "bunny-fight",
                                                        "ids": {"JP": ["70070000000077"]}}}
        sync.sync_eshop_names(data, fake, now=2e9)
        rows = {r["title"]: r for r in planner.eshop_matches(data)["rows"]}
        self.assertEqual((rows["ねこのぼうけん"]["group"], rows["ねこのぼうけん"]["coll"]), ("coll", "cat-adventure-switch-2"))
        up = rows["ねこのぼうけん Nintendo Switch 2 Edition アップグレードパス"]
        self.assertEqual((up["group"], up["coll"], up["eng"]), ("coll", "cat-adventure-switch-2", "Cat Adventure™: Upgrade Pack"))
        self.assertEqual((rows["うさぎファイト ファイターパス"]["slug"], rows["うさぎファイト ファイターパス"]["group"]),
                         ("bunny-fight-fighters-pass", "plan"))
        self.assertEqual((rows["うさぎファイト エキスパンション・パス"]["slug"], rows["うさぎファイト エキスパンション・パス"]["how"]),
                         ("bunny-fight-expansion-pass", "id"))
        self.assertEqual(rows["ほしのたび + ほしのたび 2"]["group"], "coll")
        self.assertEqual(rows["貓咪大冒險"]["eng"], "Cat Adventure™")
        self.assertEqual(sync._name_file("貓咪大冒險", "DE"), "HK.zh")
        # 0.82.2: Der gekaufte Pass fällt danach aus den fehlenden DLC; er bleibt über die DLC-Liste
        # des Spiels zugeordnet, statt wieder unbekannt zu werden
        del data["extra"]["bunny-fight-fighters-pass"]
        data["rel"]["bunny-fight"]["dlc"] = [["bunny-fight-fighters-pass", "Fighters Pass"]]
        rows = {r["title"]: r for r in planner.eshop_matches(data)["rows"]}
        self.assertEqual((rows["うさぎファイト ファイターパス"]["slug"], rows["うさぎファイト ファイターパス"]["group"]),
                         ("bunny-fight-fighters-pass", "plan"))

    def test_latin_titles_also_in_german_list_and_owned_dlc(self):
        # 0.81: Ein deutscher Kauftitel, gelesen, als das Konto in Brasilien stand, findet sich in der
        # deutschen Liste. Ein DLC der Sammlung ohne bekannten Namen zählt über seine Kennung, auch
        # wenn titledb ihn „Spiel: DLC“ nennt
        self.imp([{"id": "", "title": "Katzenreise 2 – Kampfarena", "date": "2026-10-05"},
                  {"id": "", "title": "【ファイター】ねこ", "date": "2026-10-04"}], region="BR")
        lists = {"BR.pt": {}, "DE.de": {"70050000000011": {"id": "0100EEE0001", "name": "Katzenreise 2 – Kampfarena"}},
                 "JP.ja": {"70050000000012": {"id": "0100FFF0001", "name": "【ファイター】ねこ"}},
                 "US.en": {"1": {"id": "0100EEE0001", "name": "Cat Journey 2 - The Arena (Challenge Level)"},
                           "2": {"id": "0100FFF0001", "name": "Bunny Brawl™: Cat Standalone Fighter"}}}
        calls = []

        def fake(url):
            calls.append(url)
            return json.dumps(next((v for k, v in lists.items() if k in url), {}), ensure_ascii=False)
        data = store.load_data()
        data["owned"] = ["cat-journey-2", "bunny-brawl", "cat-standalone-fighter"]
        data["rel"] = {"cat-journey-2": {"title": "Cat Journey 2",
                                         "dlc": [["cat-journey-2-the-arena-challenge-level", "The Arena (Challenge Level)"]]},
                       "bunny-brawl": {"title": "Bunny Brawl", "dlc": []}}
        data["extra"] = {"cat-journey-2-the-arena-challenge-level": {"title": "The Arena (Challenge Level)",
                                                                     "parent": "cat-journey-2", "ids": {}}}
        sync.sync_eshop_names(data, fake, now=2e9)
        self.assertEqual(sync._name_files("Katzenreise 2", "BR"), ["BR.pt", "DE.de"])
        self.assertEqual(sync._name_files("Katzenreise 2", "AT"), ["DE.de"])
        self.assertEqual(data["eshop_names"]["Katzenreise 2 – Kampfarena"][2], "BR.pt,DE.de")
        rows = {r["title"]: r for r in planner.eshop_matches(data)["rows"]}
        arena = rows["Katzenreise 2 – Kampfarena"]
        self.assertEqual((arena["slug"], arena["group"]), ("cat-journey-2-the-arena-challenge-level", "plan"))
        self.assertEqual((rows["【ファイター】ねこ"]["group"], rows["【ファイター】ねこ"]["coll"]), ("coll", "cat-standalone-fighter"))
        n = len(calls)
        sync.sync_eshop_names(data, fake, now=2e9 + 60)       # gefunden: kein neuer Abruf
        self.assertEqual(len(calls), n)

    def test_bought_dlc_stays_matched_after_leaving_missing_list(self):
        # 0.81.3: Ein gekaufter DLC fällt aus den fehlenden DLC, sobald er als Besitz zählt. Er bleibt
        # trotzdem zugeordnet (über die DLC-Liste seines Spiels), statt wieder unbekannt zu werden
        self.imp([{"id": "", "title": "Katzenreise 2 – Kampfarena", "date": "2026-10-05"}], region="DE")
        data = store.load_data()
        data["owned"] = ["cat-journey-2"]
        data["rel"] = {"cat-journey-2": {"title": "Cat Journey 2",
                                         "dlc": [["cat-journey-2-the-arena", "The Arena"]]}}
        data["eshop_names"] = {"Katzenreise 2 – Kampfarena": ["Cat Journey 2 - The Arena", 2e9, "DE.de"]}
        row = planner.eshop_matches(data)["rows"][0]
        self.assertEqual((row["slug"], row["group"], row["how"]), ("cat-journey-2-the-arena", "plan", "eng"))
        self.assertIn("cat-journey-2-the-arena", planner.owned_set(data))

    def test_only_public_targets_are_fetched(self):
        # 0.82: Eigene Links (Karten, Angebote) und Weiterleitungen dürfen weder den Server selbst
        # noch Geräte im Heimnetz ansprechen
        for url in ("http://127.0.0.1:8787/api/settings", "http://localhost/", "http://10.0.0.1/",
                    "http://169.254.169.254/latest/meta-data", "http://[::1]/", "ftp://example.org/x",
                    "https://user:pw@example.org/"):
            self.assertTrue(sources.blocked_target(url), url)
        with mock.patch.object(sources.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))]):
            self.assertEqual(sources.blocked_target("https://shop.example/karte"), "")
        with mock.patch.object(sources.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.1.2.3", 443))]):
            self.assertEqual(sources.blocked_target("https://shop.example/karte"), "Adresse nicht öffentlich")
            self.assertEqual(sources.request("https://shop.example/karte")["error"], "Adresse nicht öffentlich")
        with self.assertRaises(urllib.error.URLError):
            sources._SafeRedirect().redirect_request(None, None, 302, "", {}, "http://127.0.0.1/")

    def test_names_compare_without_accents(self):
        # 0.76: „Pokemon“ im Kaufverlauf ist „Pokémon“; japanische Zeichen bleiben verschieden
        self.assertEqual(planner._tnorm("Pokémon Pokopia"), planner._tnorm("Pokemon Pokopia"))
        self.assertEqual(sources.name_key("Pokémon テスト"), "pokemon テスト")
        self.assertNotEqual(sources.name_key("ズ"), sources.name_key("ス"))

    def test_same_entries_not_added_twice_and_picks(self):
        e = [{"id": "", "title": "Algo desconhecido", "date": "2026-10-01"}]
        self.imp(e)
        self.assertEqual(self.imp(e)["new"], 0)
        key = planner.eshop_matches(store.load_data())["rows"][0]["key"]
        store.pick_eshop_history(key, "spiritfarer")
        self.assertIn("spiritfarer", planner.owned_set(store.load_data()))
        store.pick_eshop_history(key, "-")
        rows = planner.eshop_matches(store.load_data())["rows"]
        self.assertEqual((rows[0]["how"], rows[0]["slug"]), ("none", None))
        store.pick_eshop_history(key, "")
        self.assertIsNone(planner.eshop_matches(store.load_data())["rows"][0]["how"])

    def test_bought_title_leaves_plan(self):
        self.imp([{"id": "70010000012345", "title": "Hades", "date": "2026-10-01"}])
        ctx = planner.Context(store.load_data(), store.load_settings())
        self.assertIn("hades", ctx.owned)

    def test_dlc_with_game_name_refund_and_suggestion(self):
        self.imp([{"k": "1", "title": "Vampire Survivors: Tides of the Foscari", "date": "2026-10-01", "type": "PURCHASE"},
                  {"k": "2", "title": "Spiritfarer®", "date": "2026-10-01", "type": "REFUND"},
                  {"k": "3", "title": "Hades Deluxe", "date": "2026-10-01", "type": "PURCHASE"}])
        rows = {r["title"]: r for r in planner.eshop_matches(store.load_data())["rows"]}
        self.assertEqual(rows["Vampire Survivors: Tides of the Foscari"]["slug"], "vs-foscari")
        self.assertEqual(rows["Spiritfarer®"]["how"], "void")          # erstattet: zählt nicht
        self.assertIsNone(rows["Hades Deluxe"]["slug"])                  # nur ähnlich: Vorschlag
        self.assertEqual([x["slug"] for x in rows["Hades Deluxe"]["suggest"]], ["hades"])
        self.assertEqual(rows["Hades Deluxe"]["key"], "nin:3")

    def test_reading_point_only_after_complete_run(self):
        e = [{"k": "5", "title": "Hades", "date": "2026-10-01"}]
        sync.import_eshop_history(json.dumps({"region": "BR", "complete": False, "newest": 9, "entries": e}))
        self.assertNotIn("seit", store.load_eshop_history())       # abgebrochen: Stand bleibt
        sync.import_eshop_history(json.dumps({"region": "BR", "complete": True, "newest": 7, "entries": e}))
        self.assertEqual(store.load_eshop_history()["seit"], 7)
        sync.import_eshop_history(json.dumps({"region": "BR", "complete": True, "newest": 3, "entries": []}))
        self.assertEqual(store.load_eshop_history()["seit"], 7)    # nie zurück

    def test_no_duplicates_after_country_switch_or_old_keys(self):
        e = [{"k": "5", "title": "Hades", "date": "2026-10-01"}]
        sync.import_eshop_history(json.dumps({"region": "BR", "entries": e}))
        self.assertEqual(sync.import_eshop_history(json.dumps({"region": "PL", "entries": e}))["new"], 0)
        store._save("eshop_history.json", {"entries": [{"key": "nin:BR:7", "title": "A"}, {"key": "nin:PL:7", "title": "A"}],
                                           "picks": {"nin:BR:7": "-"}})
        h = store.load_eshop_history()                       # Schlüssel bis 0.49.2 mit Land
        self.assertEqual(([x["key"] for x in h["entries"]], h["picks"]), (["nin:7"], {"nin:7": "-"}))

    def test_wrong_text_rejected(self):
        with self.assertRaises(ValueError):
            sync.import_eshop_history("kein json")


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

    def test_plan_passes_switch_2_skips_with_slug(self):
        # Der Reiter Titel erkennt aussortierte Wege zur Switch 2 an der Kennung
        data, settings = sample()
        plan = planner.purchase_plan(data, settings, now=NOW)
        planned = [i["slug"] for p in plan["steps"] for i in p["items"]]
        self.assertIn("hades", planned)
        def skip_hades(data, rows, wanted, settings=None):
            return [s for s in wanted if s != "hades"], [{"slug": "hades", "reason": "Grund"}]
        with mock.patch.object(kaufplan, "_switch2_choice", skip_hades):   # der Kaufplan liegt seit 0.86 in kaufplan.py
            plan = planner.purchase_plan(data, settings, now=NOW)
        self.assertNotIn("hades", [i["slug"] for p in plan["steps"] for i in p["items"]])
        self.assertEqual([(x["slug"], x["reason"]) for x in plan["s2_skip"]], [("hades", "Grund")])
        self.assertEqual(plan["bought_slugs"], [])

    def test_plan_names_where_ownership_comes_from(self):
        # 0.95: Sammlung, Paket: der Kaufplan nennt die Quelle statt pauschal „gekauft“
        data, settings = sample()
        data["owned"] = ["bundle"]
        data["links"] = {"bundle": {"hades": {}}}
        data.setdefault("rel", {})["bundle"] = {"title": "Big Bundle"}
        plan = planner.purchase_plan(data, settings, now=NOW)
        self.assertEqual(plan["bought_how"], [{"slug": "hades", "title": "Hades", "how": "pack", "via": "Big Bundle"}])
        data["owned"] = ["hades"]
        plan = planner.purchase_plan(data, settings, now=NOW)
        self.assertEqual([x["how"] for x in plan["bought_how"]], ["collection"])

    def test_plan_skips_bought_titles(self):
        data, settings = sample()
        bought = [{"at": "2026-10-11T20:00:00+00:00", "code": "JP", "slugs": ["hades"],
                   "titles": ["Hades"], "cost": 8.0, "de": 24.99, "rest": 0, "currency": "JPY"}]
        plan = planner.purchase_plan(data, settings, now=NOW, bought=bought)
        self.assertNotIn("hades", [i["slug"] for p in plan["steps"] for i in p["items"]])
        self.assertEqual(plan["bought_waiting"], ["Hades"])
        # Für den Hinweis im Reiter Titel: gekaufte Titel auch als Kennung
        self.assertEqual(plan["bought_slugs"], ["hades"])
        self.assertEqual(plan["bought_how"], [{"slug": "hades", "title": "Hades", "how": "plan", "via": None}])
        self.assertAlmostEqual(plan["bought_saving"], 16.99)
        # „Gekauft“ verlinkt die Titel eines Kaufs über ihre Kennung (1.4.0)
        self.assertEqual(plan["bought"][0]["slugs"], ["hades"])
        # Mit dem Preis der Spiele (ohne den Rest, der als Guthaben bleibt) rechnet die
        # Ersparnis wie der Kaufplan
        bought.append({"at": "2026-10-12T20:00:00+00:00", "code": "BR", "slugs": ["good-job"],
                       "titles": ["Good Job!"], "cost": 9.0, "games": 7.5, "de": 9.99, "rest": 8,
                       "currency": "BRL"})
        plan = planner.purchase_plan(data, settings, now=NOW, bought=bought)
        self.assertAlmostEqual(plan["bought_saving"], 16.99 + 2.49)
        # Der Kaufplan gibt je Schritt mit, was der Kauf ohne Rest kostet
        for p in plan["steps"]:
            self.assertAlmostEqual(p["games_paid"], p["cost"] - p["rest_value"] + (p.get("balance_value") or 0)
                                   + (p.get("balance_lost") or 0))


GAME_PAGE = """<title>Vampire Survivors | Deku Deals</title><h2>Details</h2>
<h3><a href="#dlcCollapse">DLC</a></h3><div id="dlcCollapse" class="collapse">
<div class="cell"><a href="/items/vs-foscari"><img alt="Tides of the Foscari"></a>
<a href="/items/vs-foscari"><h6 class="name">Tides of the Foscari</h6></a><span>€1,99</span> <span>-20%</span></div>
<div class="cell"><a href="/items/vs-emergency-meeting?country=de"><h6>Emergency Meeting</h6> 1,99 €</a></div>
<div class="cell"><a href="/items/vampire-survivors-nintendo-switch-2-edition-upgrade-pack">
<h6>Nintendo Switch 2 Edition Upgrade Pack</h6></a></div></div>
<h3>Included In</h3><a href="/items/vampire-survivors-bundle">Vampire Survivors Bundle</a>
<h3>Other users also liked...</h3><a href="/items/hades">Hades</a>"""


class CollectionTest(unittest.TestCase):
    def test_related_sections(self):
        r = sources.parse_related(GAME_PAGE)
        self.assertEqual(r["dlc"], [("vs-foscari", "Tides of the Foscari"),
                                    ("vs-emergency-meeting", "Emergency Meeting"),
                                    ("vampire-survivors-nintendo-switch-2-edition-upgrade-pack",
                                     "Nintendo Switch 2 Edition Upgrade Pack")])
        self.assertEqual(r["included_in"], [("vampire-survivors-bundle", "Vampire Survivors Bundle")])
        self.assertEqual(r["contains"], [])
        # "Other users also liked" gehört nicht dazu, eine Seite ohne Abschnitte liefert nichts
        self.assertNotIn("hades", [x for x, _ in r["dlc"]])
        self.assertEqual(sources.parse_related("<h3>Details</h3><a href='/items/x'>X</a>"),
                         {"dlc": [], "included_in": [], "contains": [], "found": []})
        bundle = '<h3>Contains</h3><a href="/items/mario-kart-8-deluxe">Mario Kart 8 Deluxe $59.99 $41.97 -30%</a>'
        self.assertEqual(sources.parse_related(bundle)["contains"], [("mario-kart-8-deluxe", "Mario Kart 8 Deluxe")])

    def test_sync_related_is_gentle(self):
        data, settings = sample()
        data["owned"] = ["vampire-survivors", "vs-foscari"]
        calls = []

        def fake(url, ua=None):
            calls.append(url)
            if "/items/vampire-survivors?" in url:
                return GAME_PAGE
            if "/items/vs-foscari?" in url:
                return '<title>Foscari | Deku Deals</title><h4>DLC for <a href="/items/vampire-survivors">VS</a></h4>'
            return "<title>Spiel | Deku Deals</title>"
        t0 = NOW.timestamp()
        sync.sync_related(data, settings, fake, lambda s: None, now=t0)
        # Sammlung zuerst, dann die Wishlist; je Seite einmal
        self.assertEqual(len(calls), 6)
        self.assertIn("/items/vampire-survivors?", calls[0])
        self.assertEqual(len(data["rel"]["vampire-survivors"]["dlc"]), 3)
        self.assertEqual(data["rel"]["vs-foscari"]["parent"], "vampire-survivors")
        sync.sync_related(data, settings, fake, lambda s: None, now=t0 + 86400)
        self.assertEqual(len(calls), 6)                     # monatlich, nicht täglich
        sync.sync_related(data, settings, fake, lambda s: None, now=t0 + 31 * 86400)
        self.assertEqual(len(calls), 12)
        # Höchstens REL_PER_SYNC Seiten, eine Sperre beendet das Lesen
        calls.clear()
        data["rel"] = {}
        data["owned"] = [f"game-{i}" for i in range(60)]
        sync.sync_related(data, settings, fake, lambda s: None, now=t0)
        self.assertEqual(len(calls), sync.REL_PER_SYNC)
        calls.clear()

        def deny(url, ua=None):
            calls.append(url)
            raise sources.FetchError(url, 429)
        sync.sync_related(data, settings, deny, lambda s: None, now=t0)
        self.assertEqual(len(calls), 1)

    def test_game_info_from_item_page(self):
        # 1.6.0: Kasten „Details“ einer DekuDeals-Artikelseite, gelesen aus dem sichtbaren Text
        page = ("<title>X | Deku Deals</title><h4>Details</h4><ul><li><b>MSRP:</b> €59,99</li>"
                "<li><b>Release date:</b> March 20, 2020</li><li><b>Genre:</b> <a>Simulation</a>, <a>Party</a></li>"
                "<li><b>Number of players:</b><ul><li>Offline: 1 - 4</li><li>Local Wireless: 1 - 8</li>"
                "<li>Online: 1 - 8</li></ul></li><li>Developer: Nintendo</li><li>Publisher: Nintendo</li>"
                "<li>Download size: 10.576 GB</li><li>Metacritic: <span>90</span> <span>6.0</span></li>"
                "<li>OpenCritic: 88</li><li>How Long To Beat : <ul><li>Solo: 109½ hours</li><li>Co-op: 18 hours</li>"
                "</ul></li><li>USK Rating: 6</li><li>Play modes: TV, Tabletop, Handheld</li>"
                "<li>Languages: English, German</li></ul><p>Online: 1 - 99 in der Beschreibung zählt nicht</p>")
        self.assertEqual(sources.parse_game_info(page), {
            "genre": ["Simulation", "Party"], "players": {"offline": [1, 4], "local": [1, 8], "online": [1, 8]},
            "modes": ["tv", "tabletop", "handheld"], "mc": 90, "mcu": 6.0, "oc": 88,
            "hltb": {"solo": 109.5, "coop": 18.0}, "released": "2020-03-20", "developer": "Nintendo",
            "publisher": "Nintendo", "age": "USK 6", "size_gb": 10.58})
        self.assertEqual(sources.parse_game_info("<li>Genre: Puzzle</li><li>Number of players: 1-2</li>"),
                         {"genre": ["Puzzle"], "players": {"offline": [1, 2]}})
        self.assertEqual(sources.parse_game_info("<h3>DLC</h3>"), {})

    def test_game_info_for_collection_first(self):
        # 1.6.0: Spiele der Sammlung ohne Spielinfos kommen vor der monatlichen Auffrischung dran, mit
        # europäischer ID; Nintendo bestätigt 40 je Abruf, monatlich, ohne Treffer {"none": true}
        data, settings = sample()
        data["owned"] = ["game-a", "game-b"]
        t0 = NOW.timestamp()
        data["rel"] = {s: {"checked": t0, "v": sync.REL_V, "title": s, "dlc": [], "in": [], "has": []}
                       for s in ("game-a", "game-b") + tuple(data["items"])}
        calls = []

        def fake(url, ua=None):
            calls.append(url)
            if "/items/game-a?" in url:
                return ('<title>A | Deku Deals</title><li>Genre: Puzzle</li>'
                        '<a class="eshop_de:70010000000001" href="https://www.nintendo.com/de-de/x">eShop</a>')
            return "<title>B | Deku Deals</title>"
        sync.sync_related(data, settings, fake, lambda s: None, now=t0 + 3600)
        self.assertEqual(len(calls), 2)                    # nur die beiden Spiele, die Wishlist ist frisch
        a, b = data["rel"]["game-a"], data["rel"]["game-b"]
        self.assertEqual((a["info"], a["eu"], a["iv"]), ({"genre": ["Puzzle"]}, "70010000000001", sync.INFO_V))
        self.assertEqual((b["info"], b["iv"]), ({}, sync.INFO_V))
        self.assertNotIn("eu", b)
        sync.sync_related(data, settings, fake, lambda s: None, now=t0 + 7200)
        self.assertEqual(len(calls), 2)
        asked = []

        def solr(url, ua=None):
            asked.append(url)
            return json.dumps({"response": {"docs": [{
                "nsuid_txt": ["70010000000001"], "pretty_game_categories_txt": ["Action", "Puzzle"],
                "players_from": 1, "players_to": 4, "play_mode_tv_mode_b": True, "play_mode_handheld_mode_b": True,
                "multiplayer_mode": "simultaneous", "paid_subscription_online_play_b": False,
                "publisher": "Nintendo", "age_rating_type": "pegi", "age_rating_value": 3,
                "players_from_system_i": 1, "players_to_system_i": 2, "players_to_online_i": 4}]}})
        sync.sync_game_info_eu(data, solr, lambda s: None, now=t0)
        self.assertEqual(len(asked), 1)
        self.assertIn("nsuid_txt", asked[0])
        self.assertEqual(a["nin"], {"genre": ["Action", "Puzzle"], "players": [1, 4], "modes": ["tv", "handheld"],
                                    "mm": "simultaneous", "online": False, "publisher": "Nintendo",
                                    "age": "PEGI 3", "sys_pl": [1, 2], "on_pl": [1, 4], "at": t0, "v": sync.NIN_V})
        sync.sync_game_info_eu(data, solr, lambda s: None, now=t0 + 86400)
        self.assertEqual(len(asked), 1)                    # monatlich
        a["eu"] = "70010000000002"
        a.pop("nin")
        sync.sync_game_info_eu(data, solr, lambda s: None, now=t0)
        self.assertEqual(a["nin"], {"none": True, "at": t0, "v": sync.NIN_V})
        # Eine neue Seite ohne Kasten behält die alten Angaben, ebenso die Bestätigung
        a["iv"] = 0
        a["info"] = {"genre": ["Puzzle"]}
        sync.sync_related(data, settings, lambda u, ua=None: "<title>A | Deku Deals</title>", lambda s: None, now=t0 + 9000)
        self.assertEqual((data["rel"]["game-a"]["info"], data["rel"]["game-a"]["nin"]["none"]), ({"genre": ["Puzzle"]}, True))

    def test_game_infos_mark_single_source(self):
        # 1.6.1: Ansicht „Spiele“: Genre deutsch und je Quelle bestätigt, Spieler gegen Nintendos
        # Höchstzahl, Jahr und Verlag mit Widerspruch, Switch 2 aus dem Namen, ungelesene Spiele dabei
        data, settings = sample()
        data["owned"] = ["game-a", "game-b-nintendo-switch-2-edition", "game-c"]
        data["rel"] = {
            "game-a": {"title": "Game A", "dlc": [], "iv": 1, "info": {
                "genre": ["Role-Playing", "Puzzle"], "players": {"offline": [1, 4], "online": [1, 8]},
                "modes": ["tv", "handheld"], "mc": 88, "hltb": {"main": 12.5, "coop": 9}, "released": "2020-03-20",
                "publisher": "Nintendo"},
                "nin": {"genre": ["RPG", "Action"], "players": [1, 8], "sys_pl": [1, 2], "on_pl": [1, 8],
                        "modes": ["tv", "handheld"], "online": True,
                        "released": "2019-12-01", "publisher": "Nintendo Co., Ltd.", "at": 1}},
            "game-b-nintendo-switch-2-edition": {"title": "Game B – Nintendo Switch 2 Edition", "dlc": [], "iv": 1,
                                                  "info": {"genre": ["Party"]}, "nin": {"none": True, "at": 1}},
            "game-c": {"title": "Game C", "dlc": []}}
        sp = planner.game_infos(data, settings)
        a, b, c = sp["games"]
        self.assertEqual(a["genre"], [{"n": "Puzzle", "ok": False, "src": "DekuDeals"},
                                      {"n": "Rollenspiel", "ok": True, "src": "beide"},
                                      {"n": "Action", "ok": False, "src": "Nintendo"}])
        self.assertEqual(a["players"]["offline"], {"v": [1, 4], "ok": False, "alt": [1, 2]})
        self.assertEqual(a["players"]["online"], {"v": [1, 8], "ok": True})
        self.assertEqual((a["max"], a["coop"], a["score"], a["hours"]), (8, True, 88, 12.5))
        self.assertEqual(a["modes"], [{"n": "tv", "ok": True}, {"n": "handheld", "ok": True}])
        self.assertEqual((a["year"], a["year_ok"], a["year_alt"]), ("2020", False, "2019"))
        self.assertTrue(a["pub_ok"])
        self.assertEqual((b["s2"], b["nin"], b["genre"][0]["ok"]), ("edition", False, False))
        self.assertEqual((c["read"], c["genre"], c["players"]), (False, [], {}))
        self.assertEqual((sp["read"], sp["with_info"], sp["confirmed"]), (2, 2, 1))
        self.assertIn(("Party", 1), sp["genres"])

    def test_collection_view(self):
        data, settings = sample()
        data["owned"] = ["vampire-survivors", "vs-emergency-meeting", "hades", "unread-game"]
        data["rel"] = {
            "vampire-survivors": {"checked": 1, "title": "Vampire Survivors", "parent": None,
                                  "dlc": [list(x) for x in sources.parse_related(GAME_PAGE)["dlc"]]},
            "hades": {"checked": 1, "title": "Hades", "parent": None, "dlc": []},
            "vs-emergency-meeting": {"checked": 1, "title": "EM", "parent": "vampire-survivors", "dlc": []}}
        c = planner.collection(data, settings, now=NOW)
        self.assertEqual((c["owned"], c["unread"], c["no_dlc"]), (4, 1, 1))
        g, = c["games"]
        self.assertEqual((g["title"], g["have"], g["missing"]), ("Vampire Survivors", 1, 2))
        by = {d["slug"]: d for d in g["dlc"]}
        self.assertTrue(by["vs-emergency-meeting"]["owned"])
        # Foscari steht auf der Wishlist: Urteil und Einkaufspreis wie im Radar
        fos = by["vs-foscari"]
        row = next(r for r in planner.radar(data, settings, now=NOW) if r["slug"] == "vs-foscari")
        self.assertEqual((fos["wish"], fos["verdict"], fos["code"]), (True, row["verdict"], row["shown"]["code"]))
        self.assertIsNotNone(fos["eur"])
        up = by["vampire-survivors-nintendo-switch-2-edition-upgrade-pack"]
        self.assertEqual((up["wish"], up["owned"], up["upgrade"]), (False, False, True))


class NsoItemsTest(unittest.TestCase):
    def test_subscription_items_are_no_missing_dlc(self):
        data = {"owned": ["acnh"], "items": {}, "rel": {"acnh": {"title": "ACNH", "dlc": [
            ["acnh-happy-home-paradise", "Happy Home Paradise"],
            ["acnh-nintendo-switch-online-member-exclusive-items", "Nintendo Switch Online - Member-Exclusive Items"]]}}}
        g = planner.collection(data, {}, rows=[])["games"][0]
        self.assertEqual(([d["slug"] for d in g["dlc"]], g["missing"]), (["acnh-happy-home-paradise"], 1))


class PackLinksTest(unittest.TestCase):
    """Pakete und Verbindungen (0.50): wer das Paket hat, hat die Teile."""
    def rel_page(self, contains=(), included_in=(), found=None):
        r = {"contains": list(contains), "included_in": list(included_in)}
        r["found"] = found if found is not None else [k for k, v in r.items() if v]
        return r

    def test_links_from_both_sides_and_removal_only_after_two_misses(self):
        data = {"rel": {}}
        sync.update_links(data, "pass", self.rel_page(contains=[("d1", "DLC 1"), ("d2", "DLC 2")]), 1)
        sync.update_links(data, "d3", self.rel_page(included_in=[("pass", "Pass")]), 1)
        self.assertEqual(set(data["links"]["pass"]), {"d1", "d2", "d3"})
        # Neue Verbindung auf der schon gelesenen Paketseite: gilt sofort, steht im Protokoll
        notes = sync.update_links(data, "pass", self.rel_page(contains=[("d1", "DLC 1"), ("d2", "DLC 2"), ("d4", "DLC 4")]), 2)
        self.assertEqual(notes, ["pass enthält jetzt auch: DLC 4"])
        # d2 fehlt einmal: bleibt; Abschnitt fehlt ganz: nichts ändert sich; zweites Fehlen: weg
        sync.update_links(data, "pass", self.rel_page(contains=[("d1", "DLC 1"), ("d4", "DLC 4")]), 3)
        self.assertIn("d2", data["links"]["pass"])
        sync.update_links(data, "pass", self.rel_page(found=[]), 4)
        self.assertIn("d2", data["links"]["pass"])
        notes = sync.update_links(data, "pass", self.rel_page(contains=[("d1", "DLC 1"), ("d4", "DLC 4")]), 5)
        self.assertEqual(notes, ["pass enthält nicht mehr: DLC 2"])
        # d3 kennt das Tool von der Seite des Teils: die Paketseite allein nimmt es nicht weg
        self.assertIn("d3", data["links"]["pass"])

    def test_owned_through_nested_packs_and_games_from_editions(self):
        data = {"owned": ["gold", "sr-deluxe"], "items": {}, "rel": {
            "gold": {"title": "Gold Edition", "dlc": []},
            "sr-deluxe": {"title": "SpeedRunners: Deluxe Edition", "dlc": []},
            "speedrunners": {"title": "SpeedRunners", "dlc": [["sr-a", "Pack A"], ["sr-b", "Pack B"], ["sr-new", "Neues Pack"]]}},
            "links": {"gold": {"game": {}, "season-pass": {}}, "season-pass": {"pixel": {}, "dk": {}},
                      "sr-deluxe": {"speedrunners": {}, "sr-a": {}, "sr-b": {}}}}
        self.assertTrue({"game", "season-pass", "pixel", "dk", "speedrunners", "sr-a"} <= planner.owned_set(data))
        self.assertNotIn("sr-new", planner.owned_set(data))
        self.assertNotIn("gold", planner.owned_set({"owned": ["pixel"], "links": data["links"]}))  # nur abwärts
        c = planner.collection(data, {}, rows=[])
        g = next(g for g in c["games"] if g["slug"] == "speedrunners")
        self.assertEqual(g["via"], "SpeedRunners: Deluxe Edition")
        rows = {d["slug"]: d for d in g["dlc"]}
        self.assertEqual((rows["sr-a"]["have"], rows["sr-a"]["via"]), (True, "SpeedRunners: Deluxe Edition"))
        self.assertEqual((g["have"], g["missing"]), (2, 1))           # das neuere Pack fehlt
        self.assertEqual(set(planner.extra_dlc(data, {})), {"sr-new"})
        self.assertEqual(c["owned"], 2)                                # Zahl der DekuDeals-Sammlung

    def test_not_in_pack_mark_and_saved(self):
        # „stimmt nicht“: DekuDeals nennt den DLC im Paket, du hast ihn nicht
        data = {"owned": ["gold", "game"], "items": {}, "rel": {
            "game": {"title": "Spiel", "dlc": [["season-pass", "Season Pass"], ["pixel", "Pixel"], ["dk", "DK"]]}},
            "links": {"gold": {"season-pass": {}}, "season-pass": {"pixel": {}, "dk": {}}}}
        settings = {"dlc_marks": {"pixel": "missing"}}
        self.assertNotIn("pixel", planner.owned_set(data, settings))
        self.assertIn("dk", planner.owned_set(data, settings))
        self.assertEqual(set(planner.extra_dlc(data, settings)), {"pixel"})
        rows = {d["slug"]: d for d in planner.collection(data, settings, rows=[])["games"][0]["dlc"]}
        self.assertTrue(rows["pixel"]["not_in_pack"] and not rows["pixel"]["have"])
        # Auf einem Pass gilt es auch für alles darin
        self.assertFalse({"season-pass", "pixel", "dk"} & planner.owned_set(data, {"dlc_marks": {"season-pass": "missing"}}))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(store, "DATA_DIR", d):
            store.save_settings({"dlc_marks": {"pixel": "missing"}})
            self.assertEqual(store.load_settings()["dlc_marks"], {"pixel": "missing"})

    def test_dlc_no_longer_available_not_missing(self):
        data = {"owned": ["rl"], "items": {}, "rel": {
            "rl": {"title": "Rocket League", "dlc": [["rl-a", "Car A"], ["rl-b", "Car B"], ["rl-c", "Car C"]]}},
            "extra": {"rl-a": {"title": "Car A", "parent": "rl", "ids": {"EU": []}, "ids_checked": {"EU": 1, "AM": 1}, "ids_misses": {"EU": 2, "AM": 3}},
                      "rl-b": {"title": "Car B", "parent": "rl", "ids": {"EU": []}, "ids_checked": {"EU": 1}, "ids_misses": {"EU": 1}},
                      "rl-c": {"title": "Car C", "parent": "rl", "ids": {"EU": ["70010000000001"]}, "ids_checked": {"EU": 1}, "ids_misses": {"EU": 0}}}}
        with mock.patch.object(planner, "extra_context", lambda *a: None):
            g = planner.collection(data, {}, rows=[])["games"][0]
        self.assertEqual([d["slug"] for d in g["dlc"] if d["gone"]], ["rl-a"])
        self.assertEqual((g["missing"], g["gone"]), (2, 1))

    @staticmethod
    def price_row(slug, title, eur):
        return {"slug": slug, "title": title, "verdict": "buy", "reason": "", "shown": {"code": "DE", "name": "Deutschland"},
                "easy": {"code": "DE", "eur": eur}, "hard": None}

    def test_missing_pass_grouped_with_parts(self):
        data = {"owned": ["game", "pixel"], "items": {}, "rel": {
            "game": {"title": "Spiel", "dlc": [["pixel", "Pixel"], ["dk", "DK"], ["season-pass", "Season Pass"], ["ultra", "Ultra"], ["other", "Anderes"]]}},
            "links": {"season-pass": {"pixel": {}, "dk": {}, "ultra": {}}}}
        rows = [self.price_row("season-pass", "Season Pass", 9.99), self.price_row("dk", "DK", 5.0),
                self.price_row("ultra", "Ultra", 6.0), self.price_row("other", "Anderes", 2.0)]
        g = planner.collection(data, {}, rows=rows)["games"][0]
        self.assertEqual([d["slug"] for d in g["dlc"]], ["season-pass", "pixel", "dk", "ultra", "other"])
        sp = g["dlc"][0]
        self.assertEqual(sp["pack"], {"n": 3, "have": 1, "open": 2, "single": 11.0, "cheaper": "pass"})
        self.assertEqual(g["dlc"][2]["in_pack"], "Season Pass")
        # Fehlen: DK, Ultra, Anderes; der Pass zählt nicht extra. Summe: Pass statt einzeln
        self.assertEqual((g["missing"], g["missing_eur"], g["missing_priced"]), (3, 11.99, 3))
        # Einzeln günstiger: dann zählen die Teile
        rows[0] = self.price_row("season-pass", "Season Pass", 12.0)
        g = planner.collection(data, {}, rows=rows)["games"][0]
        self.assertEqual((g["dlc"][0]["pack"]["cheaper"], g["missing_eur"]), ("single", 13.0))

    def test_pass_hint_and_free_dlc(self):
        data = {"owned": ["game"], "items": {}, "rel": {
            "game": {"title": "Spiel", "dlc": [["season-pass", "Season Pass"], ["dk", "DK"], ["ultra", "Ultra"], ["gift", "Geschenk"]]}},
            "links": {"season-pass": {"dk": {}, "ultra": {}}}}
        rows = [dict(self.price_row("dk", "DK", 5.0)), self.price_row("ultra", "Ultra", 6.0)]
        # Pass nicht auf der Wishlist: Preis wie bei fehlenden DLC (hier von Hand gesetzt)
        prices = {"season-pass": 9.99, "gift": 0.0}
        with mock.patch.object(planner, "extra_context", lambda *a: object()), \
                mock.patch.object(planner, "_extra_best", lambda x, s: {"eur": prices[s], "est": False, "code": "DE",
                                                                        "name": "Deutschland", "end": None, "sale": False} if s in prices else None):
            c = planner.collection(data, {}, rows=rows)
        self.assertEqual([(h["title"], h["single"], h["eur"], h["saving"], [w["title"] for w in h["wished"]])
                          for h in c["pass_hints"]], [("Season Pass", 11.0, 9.99, 1.01, ["DK", "Ultra"])])
        self.assertEqual([f["slug"] for f in c["free"]], ["gift"])
        # Steht der Pass selbst auf der Wishlist, plant ihn der Kaufplan schon: kein Hinweis
        rows.append(self.price_row("season-pass", "Season Pass", 9.99))
        with mock.patch.object(planner, "extra_context", lambda *a: None):
            self.assertEqual(planner.collection(data, {}, rows=rows)["pass_hints"], [])

    def test_eshop_history_keeps_collection_size(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(store, "DATA_DIR", d):
            store.merge_eshop_history([{"key": "nin:1", "title": "A"}], 100, 0, 91)
            self.assertEqual((store.load_eshop_history()["owned_n"], store.load_eshop_history()["at"]), (91, 100))
            # Ein voller Lauf ergänzt fehlende Angaben bekannter Einträge, ohne Doppel (0.68.1)
            new, total = store.merge_eshop_history([{"key": "nin:1", "title": "A", "plat": "BEE"}], 101, 0)
            self.assertEqual((new, store.load_eshop_history()["entries"][-1].get("plat")), (0, "BEE"))

    def test_plan_buys_pass_not_its_parts(self):
        data, settings = sample()
        data["links"] = {"hades": {"vs-foscari": {}}}
        plan = planner.purchase_plan(data, settings, now=NOW)
        planned = [i["slug"] for p in plan["steps"] for i in p["items"]]
        self.assertIn("hades", planned)
        self.assertNotIn("vs-foscari", planned)
        self.assertEqual([(x["slug"], x["pack"]) for x in plan["packed"]], [("vs-foscari", "Hades")])

    def test_migration_from_rel(self):
        data = {"rel": {"pass": {"checked": 5, "has": [["d1", "DLC 1"]], "in": []},
                        "game": {"checked": 5, "has": [], "in": [["bundle", "Bundle"]]}}}
        sync.migrate_links(data)
        self.assertEqual({c: set(p) for c, p in data["links"].items()}, {"pass": {"d1"}, "bundle": {"game"}})
        self.assertEqual(data["links_v"], 1)


class CollectionTabTest(unittest.TestCase):
    def test_all_games_of_the_collection(self):
        data = {"owned": ["acnh", "celeste", "hades"], "items": {}, "rel": {
            "acnh": {"title": "ACNH", "dlc": [["acnh-hhp", "Happy Home Paradise"]]},
            "celeste": {"title": "Celeste", "dlc": []}}}
        c = planner.collection(data, {}, rows=[])
        self.assertEqual([g["slug"] for g in c["games"]], ["acnh"])
        self.assertEqual(c["plain"], [{"slug": "celeste", "title": "Celeste", "via": None}])
        self.assertEqual(c["waiting"], [{"slug": "hades", "title": "Hades"}])     # noch nicht gelesen


    def test_dlc_marked_by_hand(self):
        data = {"owned": ["rl"], "items": {}, "rel": {
            "rl": {"title": "Rocket League", "dlc": [["rl-a", "Car A"], ["rl-b", "Car B"], ["rl-c", "Car C"]]}}}
        settings = {"dlc_marks": {"rl-a": "have", "rl-b": "ignore"}}
        g = planner.collection(data, settings, rows=[])["games"][0]
        self.assertEqual((g["have"], g["ignored"], g["missing"]), (1, 1, 1))
        rows = {d["slug"]: d for d in g["dlc"]}
        self.assertTrue(rows["rl-a"]["by_hand"] and rows["rl-b"]["ignored"])
        # Alle DLC des Spiels ignorieren: der abgehakte zählt weiter als vorhanden
        settings["dlc_marks"]["rl"] = "ignore_all"
        g = planner.collection(data, settings, rows=[])["games"][0]
        self.assertEqual((g["have"], g["ignored"], g["missing"], g["ignore_all"]), (1, 2, 0, True))
        # Die DekuDeals-Sammlung geht vor
        data["owned"].append("rl-b")
        g = planner.collection(data, settings, rows=[])["games"][0]
        self.assertEqual((g["have"], g["ignored"]), (2, 1))

    def test_country_markup_removed(self):
        # Bis 0.52.0 gab es einen Aufschlag je Land; seitdem nur den allgemeinen Schätzwert
        with tempfile.TemporaryDirectory() as d, mock.patch.object(store, "DATA_DIR", d):
            s = store.load_settings()
            s["countries"]["JP"]["markup_pct"], s["settings_v"] = 0, 4
            store._save("settings.json", s)
            self.assertNotIn("markup_pct", store.load_settings()["countries"]["JP"])

    def test_dlc_marks_are_saved(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(store, "DATA_DIR", d):
            store.save_settings({"dlc_marks": {"rl-a": "have", "rl": "ignore_all", "x": "bogus"}})
            self.assertEqual(store.load_settings()["dlc_marks"], {"rl-a": "have", "rl": "ignore_all"})
            store.save_settings({"dlc_marks": {"rl-a": None}})
            self.assertEqual(store.load_settings()["dlc_marks"], {"rl": "ignore_all"})


class Switch2Test(unittest.TestCase):
    @staticmethod
    def row(slug, title, eur, code="DE", name="Deutschland", verdict="buy"):
        offer = {"code": code, "eur": eur, "est": False}
        return {"slug": slug, "title": title, "verdict": verdict, "easy": offer, "hard": None,
                "shown": {"code": code, "name": name}}

    def test_upgrade_pack_against_edition(self):
        ed, up = "zelda-totk-nintendo-switch-2-edition", "zelda-totk-nintendo-switch-2-edition-upgrade-pack"
        data = {"owned": ["zelda-totk"], "items": {
            ed: {"title": "Zelda TotK – Nintendo Switch 2 Edition", "active": True},
            up: {"title": "Zelda TotK Nintendo Switch 2 Edition Upgrade Pack", "active": True,
                 "parent": "zelda-totk"}},
            "rel": {"zelda-totk": {"title": "Zelda TotK", "dlc": [[up, "Nintendo Switch 2 Edition Upgrade Pack"]]}}}
        rows = [self.row(ed, data["items"][ed]["title"], 79.99),
                self.row(up, data["items"][up]["title"], 9.99, "NO", "Norwegen")]
        p = planner.switch2_paths(data, rows)
        self.assertEqual(list(p), [ed])                 # das Paket selbst ist keine Edition
        e = p[ed]
        self.assertEqual((e["base"], e["base_owned"], e["upgrade"]), ("zelda-totk", True, up))
        self.assertEqual((e["path_eur"], e["path_saving"], e["upgrade_name"]), (9.99, 70.0, "Norwegen"))
        # Ohne das Spiel: Spiel plus Paket gegen die Edition, wenn beides einen Preis hat
        data["owned"] = []
        self.assertIsNone(planner.switch2_paths(data, rows)[ed]["path_eur"])
        data["items"]["zelda-totk"] = {"title": "Zelda TotK", "active": True}
        rows.append(self.row("zelda-totk", "Zelda TotK", 49.99))
        e = planner.switch2_paths(data, rows)[ed]
        self.assertEqual((e["base_owned"], e["path_eur"], e["path_saving"]), (False, 59.98, 20.01))
        # Ein Titel ohne bekanntes Switch-1-Spiel bekommt keinen Hinweis
        rows.append(self.row("mario-kart-world", "Mario Kart World", 79.99))
        rows.append(self.row("other-nintendo-switch-2-edition", "Other – Nintendo Switch 2 Edition", 69.99))
        self.assertEqual(list(planner.switch2_paths(data, rows)), [ed])

    def test_plan_buys_one_way_to_switch_2(self):
        ed, up, base = "zelda-totk-nintendo-switch-2-edition", "zelda-totk-nintendo-switch-2-edition-upgrade-pack", "zelda-totk"
        data = {"owned": [base], "items": {up: {"title": "Upgrade Pack", "active": True, "parent": base}},
                "rel": {base: {"title": "Zelda TotK", "dlc": [[up, "Nintendo Switch 2 Edition Upgrade Pack"]]}}}
        rows = [self.row(ed, "Zelda TotK – Nintendo Switch 2 Edition", 79.99), self.row(up, "Upgrade Pack", 9.99)]
        # Das Spiel ist da: keine Edition, das Paket bleibt im Plan
        wanted, skip = planner._switch2_choice(data, rows, [ed, up])
        self.assertEqual(wanted, [up])
        self.assertEqual(skip[0]["slug"], ed)
        self.assertIn("Upgrade-Paket genügt", skip[0]["reason"])
        # Ohne das Spiel und beides zum Kauf: der günstigere Weg bleibt
        data["owned"] = []
        rows.append(self.row(base, "Zelda TotK", 49.99))
        wanted, skip = planner._switch2_choice(data, rows, [ed, base, up])
        self.assertEqual((wanted, [x["slug"] for x in skip]), ([base, up], [ed]))
        rows[2]["easy"]["eur"] = 74.99                   # jetzt ist die Edition günstiger
        wanted, skip = planner._switch2_choice(data, rows, [ed, base, up])
        self.assertEqual((wanted, [x["slug"] for x in skip]), ([ed], [base, up]))
        # Ohne Preis für das Paket bleibt die Edition, ein Paket allein ohne Spiel ist nutzlos
        del data["items"][up], data["rel"][base]["dlc"]
        wanted, skip = planner._switch2_choice(data, [rows[0], rows[2]], [ed, base])
        self.assertEqual((wanted, [x["slug"] for x in skip]), ([ed], [base]))
        self.assertIn("unbekannt", skip[0]["reason"])
        data["items"][up] = {"title": "Upgrade Pack", "active": True, "parent": base}
        wanted, skip = planner._switch2_choice(data, rows[:2], [ed, up])
        self.assertEqual((wanted, [x["slug"] for x in skip]), ([ed], [up]))


class BundleTest(unittest.TestCase):
    def test_bundle_against_parts(self):
        row = Switch2Test.row
        pack, game, dlc = "mk8-plus-bcp", "mk8", "mk8-bcp"
        data = {"owned": [], "items": {}, "rel": {
            pack: {"title": "MK8 + BCP", "has": [[game, "MK8"]], "in": []},
            game: {"title": "MK8", "in": [[pack, "MK8 + BCP"]], "dlc": [[dlc, "BCP"]]},
            dlc: {"title": "BCP", "parent": game, "in": [[pack, "MK8 + BCP"]]}}}
        rows = [row(pack, "MK8 + BCP", 59.99), row(game, "MK8", 49.99), row(dlc, "BCP", 24.99)]
        b = planner.bundles(data, rows)
        p = b["packs"][pack]
        # Teile aus "Contains" der Paketseite und "Included In" der Teile
        self.assertEqual(sorted(k["slug"] for k in p["parts"]), [game, dlc])
        self.assertEqual((p["alone"], p["eur"], p["saving"], p["partial"]), (74.98, 59.99, 14.99, False))
        self.assertEqual([i["slug"] for i in b["in"][game]], [pack])
        # Das Spiel ist schon da: nur der DLC zählt, das Paket brächte es doppelt
        data["owned"] = [game]
        p = planner.bundles(data, rows)["packs"][pack]
        self.assertEqual((p["alone"], p["saving"], p["have"]), (24.99, -35.0, ["MK8"]))
        # Ohne Preis für einen fehlenden Teil kein Vergleich; ist nur ein Teil bekannt auch nicht
        data["owned"] = []
        p = planner.bundles(data, rows[:2])["packs"][pack]
        self.assertEqual((p["alone"], p["unpriced"]), (None, ["BCP"]))
        del data["rel"][dlc]
        p = planner.bundles(data, rows)["packs"][pack]
        self.assertEqual((p["partial"], p["saving"]), (True, None))


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
        settings["countries"]["BR"]["cards"] = "50 | https://shop.example/br50"
        data["card_prices"] = {"https://shop.example/br50": {
            "checked": NOW.timestamp(), "price": 0.35, "currency": "EUR"}}
        w = " | ".join(sync.self_check(data, settings, now=NOW)["warnings"])
        self.assertIn("Norwegen: Preis je NOK", w)
        self.assertIn("Brasilien: nur noch 1 statt 5 Titel kaufbar", w)
        self.assertIn("Kartenpreis 50 BRL für 0,78 € vom Shop unglaubhaft", w)
        self.assertIn("Wechselkurse sind 10 Tage alt", w)


class BootSyncTest(unittest.TestCase):
    def test_sync_after_start(self):
        from datetime import datetime, timedelta, timezone
        now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        iso = lambda d: d.isoformat()
        boot = now - timedelta(seconds=1)
        self.assertTrue(sync.sync_due(None, 6, now))
        self.assertFalse(sync.sync_due(iso(now - timedelta(hours=2)), 6, now))
        self.assertTrue(sync.sync_due(iso(now - timedelta(hours=7)), 6, now))
        self.assertTrue(sync.sync_due(iso(now - timedelta(hours=2)), 6, now, boot))     # nach dem Start
        self.assertFalse(sync.sync_due(iso(now - timedelta(hours=2)), 6, now, now + timedelta(minutes=3)))
        self.assertFalse(sync.sync_due(iso(now - timedelta(minutes=10)), 6, now, boot))  # gerade erst
        self.assertFalse(sync.sync_due(iso(now - timedelta(hours=7)), 6, now, boot,
                                       iso(now - timedelta(minutes=20))))              # Fehlschlag


class SaleRhythmTest(unittest.TestCase):
    def ctx(self, sales):
        t = PlanTest("test_owned_flags")
        t.setUp()
        t.data["lows"] = {"BR": {"hades": {"sales": sales, "sales_from": "2024-10-01"}}}
        return planner.Context(t.data, t.settings, NOW)

    def test_regular_sales_give_an_estimate(self):
        sales = [["2025-03-01", 30.0, "2025-03-14"], ["2025-06-01", 30.0, "2025-06-14"],
                 ["2025-09-01", 28.0, "2025-09-14"], ["2025-12-01", 28.0, "2025-12-14"],
                 ["2026-03-01", 28.0, "2026-03-14"], ["2026-06-01", 25.0, "2026-06-14"],
                 ["2026-09-01", 25.0, "2026-09-14"]]
        r = planner.sale_rhythm(self.ctx(sales), "hades")[0]
        self.assertEqual((r["code"], r["count"], r["gap"], r["gap_min"], r["gap_max"]), ("BR", 7, 13, 13, 13))
        self.assertEqual((r["last_start"], r["last_end"], r["weeks_ago"]), ("2026-09-01", "2026-09-14", 6))
        self.assertEqual(r["months"], [3, 6, 9])
        self.assertTrue(r["next"].startswith("2026-11") or r["next"].startswith("2026-12"))

    def test_irregular_sales_without_estimate(self):
        sales = [["2025-01-01", 30.0], ["2025-02-01", 30.0], ["2025-11-01", 30.0], ["2026-08-01", 30.0]]
        r = planner.sale_rhythm(self.ctx(sales), "hades")[0]
        self.assertIsNone(r["next"])                     # Abstände 4 bis 39 Wochen
        self.assertIsNone(r["last_end"])                 # alter Eintrag ohne Ende
        self.assertEqual(r["months"], [])
        self.assertEqual(planner.sale_rhythm(self.ctx([]), "hades"), [])


class ExtraDlcTest(unittest.TestCase):
    def data(self):
        return {"owned": ["rl", "rl-a"], "items": {"rl-w": {"title": "Car W", "active": True, "ids": {}}},
                "rel": {"rl": {"title": "Rocket League", "dlc": [
                    ["rl-a", "Car A"], ["rl-b", "Car B"], ["rl-c", "Car C"], ["rl-w", "Car W"],
                    ["rl-nso", "Nintendo Switch Online - Items"]]}},
                "fx": {"rates": {"EUR": 1.0}}, "prices": {}}

    def test_dlc_ids_for_japan_and_americas_from_titledb(self):
        # Mit der Europa-ID eines DLC findet titledb die Japan- und Amerika-ID über die
        # Programm-ID; DekuDeals sucht nur noch, was titledb nicht kennt
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "JP", "US")
        data = self.data()
        got = []

        def item(slug, country, fetch=None):
            got.append((slug, country))
            return {"nsuids": {"de": ["70050000000001"], "us": ["70050000000002"]}.get(country, []) if slug == "rl-b" else []}
        regions = []

        def titledb(ids, fetch=None, region="JP.ja", apps=None):
            regions.append(region)
            if region == "DE.de":
                return {"70050000000001": {"app": "0100AAAA0000B001"}}
            if region == "JP.ja":
                return {}, {"0100AAAA0000B001": "70050000000777"}
            return {}, {}                                           # Amerika kennt titledb nicht
        t0 = 1736467200
        with mock.patch.object(sources, "fetch_item", item), mock.patch.object(sources, "fetch_titledb", titledb):
            sync.sync_extra_ids(data, settings, fetch=None, sleep=lambda s: None, now=t0)
            rlb = data["extra"]["rl-b"]
            self.assertEqual(rlb["ids"], {"EU": ["70050000000001"]})
            self.assertNotIn(("rl-b", "jp"), got)
            self.assertNotIn(("rl-b", "us"), got)
            self.assertIn("für titledb zurückgestellt", sync.status["log"][-2])
            sync.sync_titledb(data, settings, None, now=t0 + 10)
            self.assertEqual(regions, ["DE.de", "JP.ja", "US.en"])
            self.assertEqual(rlb["ids"]["JP"], ["70050000000777"])
            self.assertNotIn("AM", rlb["ids"])
            self.assertIn("IDs fehlender DLC aus titledb: Amerika 0 von 1, Japan 1 von 1", sync.status["log"][-1])
            got.clear()
            sync.sync_extra_ids(data, settings, fetch=None, sleep=lambda s: None, now=t0 + 20)
            self.assertIn(("rl-b", "us"), got)                      # Rest über DekuDeals
            self.assertNotIn(("rl-b", "jp"), got)
            self.assertEqual(rlb["ids"]["AM"], ["70050000000002"])
            self.assertEqual(rlb["app_same"], {"JP": ["70050000000777", True]})   # über die Programm-ID gefunden
            # titledb einmal je DLC und Region: Der nächste Lauf vergleicht nur noch die Programm-ID
            # der neuen Amerika-ID (ab 0.61); Japan ist schon bestätigt
            sync.sync_titledb(data, settings, None, now=t0 + 2 * 3600)
            self.assertEqual(regions[3:], ["DE.de", "JP.ja", "US.en"])
            self.assertIn("AM", rlb["app_chk"])
            self.assertNotIn("AM", rlb["app_same"])                   # titledb kennt sie nicht
            self.assertTrue(any("DLC-Fassungen: 0 von 1 geprüft" in x for x in sync.status["log"]))
            self.assertEqual(planner.dlc_fit(data), {"rl-b": {"JP": True}})
            # In der Woche danach fragt titledb dafür nicht wieder
            sync.sync_titledb(data, settings, None, now=t0 + 3 * 3600)
            self.assertEqual(len(regions), 6)

        # Fällt titledb aus, sucht DekuDeals wieder alles selbst
        data = self.data()
        data["titledb_fail_at"] = t0
        got.clear()
        with mock.patch.object(sources, "fetch_item", item):
            sync.sync_extra_ids(data, settings, fetch=None, sleep=lambda s: None, now=t0 + 60)
        self.assertIn(("rl-b", "jp"), got)

    def test_dlc_with_own_version_per_region(self):
        # Ein DLC mit eigener Fassung in Japan: andere Programm-ID als in Europa, braucht das
        # Spiel aus Japan; die Marke gilt nur für genau diese Japan-ID
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "JP")
        data = self.data()
        data["extra"] = {"rl-b": {"title": "Car B", "parent": "rl", "ids": {"EU": ["70050000000001"], "JP": ["70050000000900"]}}}

        def titledb(ids, fetch=None, region="JP.ja", apps=None):
            if region == "DE.de":
                return {"70050000000001": {"app": "0100AAAA0000B001"}}
            return {"70050000000900": {"app": "0100BBBB0000B001"}}, {}
        with mock.patch.object(sources, "fetch_titledb", titledb):
            sync.sync_titledb(data, settings, None, now=1736467200)
        self.assertEqual(data["extra"]["rl-b"]["app_same"], {"JP": ["70050000000900", False]})
        self.assertTrue(any("eigene Fassung je Region bei 1: Car B (Japan)" in x for x in sync.status["log"]))
        self.assertEqual(planner.dlc_fit(data), {"rl-b": {"JP": False}})
        data["extra"]["rl-b"]["ids"]["JP"] = ["70050000000901"]      # neue ID: wieder ungeprüft
        self.assertEqual(planner.dlc_fit(data), {})

    def test_dlc_without_id_rechecked_by_titledb_weekly_dekudeals_rarely(self):
        # Kennen titledb und DekuDeals keine Japan-ID, gibt es den DLC dort meist nicht:
        # titledb sieht wöchentlich nach, DekuDeals erst nach drei Monaten wieder
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "JP")
        data = self.data()
        t0 = 1736467200
        data["extra"] = {"rl-b": {"title": "Car B", "parent": "rl", "ids": {"EU": ["70050000000001"], "JP": []},
                                  "ids_checked": {"EU": t0, "JP": t0}, "tdb_ids": {"JP": t0}}}
        data["glangs"] = {"rl": {"ids": {"JP": ["70010000000009"], "EU": ["70010000000008"]},
                                 "ids_checked": {"JP": t0, "EU": t0}, "ids_tdb": {"JP": "70010000000009"}}}
        data["titledb_at"] = t0
        got, regions = [], []
        jp = {}

        def titledb(ids, fetch=None, region="JP.ja", apps=None):
            regions.append(region)
            if region == "DE.de":
                return {"70050000000001": {"app": "0100AAAA0000B001"}}
            return {}, dict(jp)
        with mock.patch.object(sources, "fetch_item", lambda slug, c, fetch=None: got.append(c) or {"nsuids": []}), \
                mock.patch.object(sources, "fetch_titledb", titledb), \
                mock.patch.object(planner, "extra_dlc", lambda d, s: {"rl-b": ("Car B", "rl")}):
            sync.sync_extra_ids(data, settings, fetch=None, sleep=lambda s: None, now=t0 + 15 * 86400)
            self.assertEqual(got, [])                               # nicht nach zwei Wochen
            self.assertIn("Nächste Wiederholung ohne ID: ", sync.status["log"][-1])
            sync.sync_titledb(data, settings, None, now=t0 + 3 * 86400)
            self.assertNotIn("DE.de", regions)                      # DLC-IDs erst nach einer Woche
            jp["0100AAAA0000B001"] = "70050000000777"
            sync.sync_titledb(data, settings, None, now=t0 + 11 * 86400)   # Woche nach dem letzten Laden
            self.assertIn("DE.de", regions)
            self.assertEqual(data["extra"]["rl-b"]["ids"]["JP"], ["70050000000777"])
            # Ohne Treffer: DekuDeals nach drei Monaten wieder
            data["extra"]["rl-b"]["ids"]["JP"] = []
            data["extra"]["rl-b"]["ids_checked"]["JP"] = t0
            sync.sync_extra_ids(data, settings, fetch=None, sleep=lambda s: None, now=t0 + 91 * 86400)
            self.assertEqual(got, ["jp"])

    def test_titledb_wait_for_new_dlc_is_logged(self):
        # Lud titledb vor weniger als einer Stunde, warten neue DLC aufs nächste Mal; das
        # Protokoll sagt es, statt den Schritt still auszulassen
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "JP")
        t0 = 1736467200
        data = {"items": {}, "extra": {"x": {"title": "X", "parent": "g", "ids": {"EU": ["70050000000001"]},
                                             "ids_checked": {"EU": t0}}}, "titledb_at": t0}
        with mock.patch.object(sources, "fetch_titledb", lambda *a, **k: self.fail("titledb geladen")):
            sync.sync_titledb(data, settings, None, now=t0 + 600)
        self.assertIn("IDs fehlender DLC aus titledb: zuletzt um ", sync.status["log"][-1])
        self.assertIn("wieder im nächsten Abgleich ab ", sync.status["log"][-1])

    def test_europe_without_languages_asked_monthly_after_three_tries(self):
        # Europa nennt für DLC meist keine Sprachen: nicht jeden Tag neu fragen
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code == "DE"
        data = {"items": {"d": {"title": "D", "active": True, "ids": {"EU": ["70050000000001"]}}}, "prices": {},
                "langs_jp_reset": 1, "langs_bundle_reset": 1}
        asked = []
        t0 = 1736467200
        with mock.patch.object(sources, "fetch_langs_eu", lambda ids, fetch=None, **kw: asked.append(1) or {}):
            for day in range(5):
                sync.sync_langs(data, settings, None, lambda s: None, now=t0 + day * 86400)
            self.assertEqual(len(asked), 3)
            self.assertEqual(data["items"]["d"]["langs_tries"]["EU"], 3)
            self.assertTrue(any("Sprachen Europa: 0 von 1 Titeln; 1 ohne Angabe (meist DLC), nach 3 Versuchen" in l
                                for l in sync.status["log"]))
            self.assertIn("Sprachen Europa: nichts fällig", sync.status["log"][-1])     # 0.54: immer eine Zeile
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 33 * 86400)
            self.assertEqual(len(asked), 4)                         # danach monatlich

    def test_dlc_without_eshop_entry_searched_rarely(self):
        # Kennt DekuDeals einen DLC zweimal nicht (nur im Spiel kaufbar, abgeschaltet), sucht
        # das Tool nur noch alle drei Monate; frühere erfolglose Suchen zählen als erste
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code == "DE"
        t0 = 1736467200
        data = self.data()
        data["extra"] = {"rl-b": {"title": "Car B", "parent": "rl", "ids": {"EU": []}, "ids_checked": {"EU": t0}}}
        data["glangs"] = {"rl": {"ids": {"EU": ["70010000000008"]}, "ids_checked": {"EU": t0}}}
        got = []
        with mock.patch.object(sources, "fetch_item", lambda slug, c, fetch=None: got.append(slug) or {"nsuids": []}), \
                mock.patch.object(planner, "extra_dlc", lambda d, s: {"rl-b": ("Car B", "rl")}):
            sync.sync_extra_ids(data, settings, None, lambda s: None, now=t0 + 15 * 86400)
            self.assertEqual(data["extra"]["rl-b"]["ids_misses"], {"EU": 2})
            self.assertEqual(len(got), 3)                           # de, gb, au
            got.clear()
            sync.sync_extra_ids(data, settings, None, lambda s: None, now=t0 + 30 * 86400)
            self.assertEqual(got, [])                               # nicht nach zwei Wochen
            sync.sync_extra_ids(data, settings, None, lambda s: None, now=t0 + 106 * 86400)
            self.assertEqual(len(got), 3)
        # Findet die Suche doch eine ID, beginnt die Zählung von vorn
        e = {"ids": {}, "ids_checked": {}, "ids_misses": {"EU": 3}}
        self.assertEqual(sync._recheck(e, "EU"), sync.ID_RECHECK_LONG)
        e["ids_misses"]["EU"] = 0
        self.assertEqual(sync._recheck(e, "EU"), sync.ID_RECHECK_SECONDS)

    def test_which_dlc_need_prices(self):
        data, settings = self.data(), {"dlc_marks": {"rl-c": "ignore"}}
        # rl-a hast du, rl-c ignoriert, rl-w steht auf der Wishlist, Abo-Inhalte zählen nicht
        self.assertEqual(planner.extra_dlc(data, settings), {"rl-b": ("Car B", "rl")})
        settings["dlc_marks"]["rl"] = "ignore_all"
        self.assertEqual(planner.extra_dlc(data, settings), {})

    def test_ids_politely_and_prices_in_the_collection(self):
        settings = store.load_settings()
        data = self.data()
        got, orig = [], sources.fetch_item
        sources.fetch_item = lambda slug, country, fetch=None: (
            got.append((slug, country)) or {"nsuids": ["70050000000001"] if country == "de" else []})
        try:
            with mock.patch.object(sync, "EXTRA_PER_SYNC", 1):
                sync.sync_extra_ids(data, settings, fetch=None, sleep=lambda s: None, now=1736467200)
            self.assertEqual(len(got), 1)                       # höchstens so viele Seiten
            sync.sync_extra_ids(data, settings, fetch=None, sleep=lambda s: None, now=1736467200)
            self.assertEqual(data["extra"]["rl-b"]["ids"]["EU"], ["70050000000001"])
            n = len(got)
            sync.sync_extra_ids(data, settings, fetch=None, sleep=lambda s: None, now=1736467200 + 60)
            self.assertEqual(len(got), n)                       # gefunden: kein neuer Abruf
            # Das Protokoll zeigt den Stand je Region, auch wenn nichts zu suchen ist
            line = sync.status["log"][-1]
            # Japan und Amerika der DLC warten auf titledb, die Spiele selbst sucht DekuDeals
            self.assertIn("Fehlende DLC der Sammlung: 2 DLC, 1 Spiele; IDs EU 2 gefunden (Spiele 1 gefunden); JP 0 gefunden, 2 noch nie gesucht (Spiele 0 gefunden, 1 ohne ID)", line)
            self.assertIn("Nächste Wiederholung ohne ID: 24.01.", line)
            sync.sync_extra_ids(data, settings, fetch=None, sleep=lambda s: None, now=1736467200 + 15 * 86400)
            self.assertIn("IDs fehlender DLC gesucht: ", sync.status["log"][-2])
            self.assertIn("erneut", sync.status["log"][-2])
        finally:
            sources.fetch_item = orig
        # Preis aus der Preisabfrage (xprices), in der Sammlung mit Summe
        data["xprices"] = {"DE": {"rl-b": {"status": "onsale", "currency": "EUR", "regular": 3.99,
                                           "nsuid": "70050000000001"}}}
        c = planner.collection(data, settings, rows=[])
        g = c["games"][0]
        row = {d["slug"]: d for d in g["dlc"]}["rl-b"]
        self.assertEqual((row["eur"], row["code"]), (3.99, "DE"))
        self.assertEqual((g["missing"], g["missing_eur"], g["missing_priced"]), (3, 3.99, 1))   # B, C und W fehlen, B mit Preis
        self.assertEqual(c["missing_eur"], 3.99)
        # Ignoriert: fällt aus der Liste und aus der Summe
        settings["dlc_marks"] = {"rl-b": "ignore", "rl-c": "ignore"}
        self.assertIsNone(planner.collection(data, settings, rows=[])["missing_eur"])
        self.assertIsNone(planner.extra_context(data, settings))

    def test_missing_dlc_get_best_price_marks(self):
        # 0.53.3: Tiefstpreise auch für fehlende DLC, schonend; Güte erst mit DekuDeals-Daten
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code == "DE"
        data = self.data()
        data["xprices"] = {"DE": {"rl-b": {"status": "onsale", "currency": "EUR", "regular": 4.0,
                                           "discount": 2.0, "nsuid": "70050000000001"}}}
        data["extra"] = {"rl-b": {"title": "Car B", "parent": "rl", "ids": {"EU": ["70050000000001"]},
                                  "ids_checked": {"EU": 1}}}
        # ohne Tiefstpreis: Preis und Rabatt, aber kein Stern und keine Güte
        with mock.patch.object(planner, "extra_dlc", lambda d, s: {"rl-b": ("Car B", "rl")}):
            row = {d["slug"]: d for d in planner.collection(data, settings, rows=[])["games"][0]["dlc"]}["rl-b"]
            self.assertEqual((row["eur"], row["pct"], row["grade"], row["at_best"]), (2.0, 50, None, False))
            got = []
            with mock.patch.object(sources, "fetch_item", lambda slug, c, fetch=None: got.append((slug, c))
                                   or {"lows": [1.5], "low": 1.5, "history": []}), \
                    mock.patch.object(sync, "EXTRA_LOWS_PER_SYNC", 1):
                sync.sync_lows(data, settings, None, lambda s: None, now=1736467200)
            self.assertIn(("rl-b", "de"), got)
            self.assertEqual(data["lows"]["DE"]["rl-b"]["low"], 1.5)
            row = {d["slug"]: d for d in planner.collection(data, settings, rows=[])["games"][0]["dlc"]}["rl-b"]
            self.assertEqual((row["champ"], row["at_best"], row["grade"]), (1.5, False, "good"))  # 0,50 € darüber, aber Kleinkram: „kaufen“ nur bis 2 % (0.92)
            data["lows"]["DE"]["rl-b"]["low"] = 2.0
            row = {d["slug"]: d for d in planner.collection(data, settings, rows=[])["games"][0]["dlc"]}["rl-b"]
            self.assertTrue(row["at_best"])

    def test_missing_dlc_can_be_added_to_basket(self):
        # 0.72: Fehlende DLC außerhalb der Wishlist lassen sich in Korb und Plan nehmen, von selbst nie
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code == "DE"
        data = self.data()
        data["xprices"] = {"DE": {"rl-b": {"status": "onsale", "currency": "EUR", "regular": 4.0,
                                           "nsuid": "70050000000001"}}}
        data["extra"] = {"rl-b": {"title": "Car B", "parent": "rl", "ids": {"EU": ["70050000000001"]},
                                  "ids_checked": {"EU": 1}}}
        with mock.patch.object(planner, "extra_dlc", lambda d, s: {"rl-b": ("Car B", "rl")}):
            offers = planner.extra_offers(data, settings)
            self.assertEqual([(o["slug"], o["local"]) for o in offers], [("rl-b", {"DE": 4.0})])
            res = planner.plans(data, settings, basket=["rl-b"])
            de = next(p for p in res if p["code"] == "DE")
            self.assertEqual([i["slug"] for i in de["items"]], ["rl-b"])
            self.assertNotIn("rl-b", {r["slug"] for r in planner.radar(data, settings)})

    def test_prices_of_missing_dlc_are_fetched_separately(self):
        settings = store.load_settings()
        data = {"items": {"a": {"active": True, "ids": {"EU": ["1"]}}},
                "extra": {"x": {"title": "X", "parent": "g", "ids": {"EU": ["2"]}, "ids_checked": {}}},
                "prices": {}}
        asked = []

        def prices(code, ids, fetch=None, lang=None, pause=None):
            asked.append((code, sorted(ids)))
            return {n: {"status": "onsale", "currency": "EUR", "regular": 5.0} for n in ids}
        with mock.patch.object(sources, "fetch_prices", prices), \
                mock.patch.object(countries, "ORDER", ["DE"]):
            sync.sync_prices(data, settings, None, lambda s: None, {})
        self.assertEqual(asked, [("DE", ["1", "2"])])           # ein Abruf für beide
        self.assertEqual((list(data["prices"]["DE"]), list(data["xprices"]["DE"])), (["a"], ["x"]))

    def test_price_fetch_retried_once_after_network_error(self):
        settings = store.load_settings()
        data = {"items": {"a": {"active": True, "ids": {"EU": ["70010000000001"]}}}, "prices": {}}
        calls, pauses = [], []

        def prices(code, ids, fetch=None, lang=None, pause=None):
            calls.append(code)
            if len(calls) == 1:
                raise sources.FetchError("u", 0, "Temporary failure in name resolution")
            return {n: {"status": "onsale", "currency": "EUR", "regular": 5.0} for n in ids}
        with mock.patch.object(sources, "fetch_prices", prices), \
                mock.patch.object(countries, "ORDER", ["DE"]):
            sync.sync_prices(data, settings, None, pauses.append, {})
        self.assertEqual(calls, ["DE", "DE"])
        self.assertIn(sync.NET_RETRY_PAUSE, pauses)
        self.assertEqual(list(data["prices"]["DE"]), ["a"])
        # Antwortet der Server mit einem Status, gibt es keinen zweiten Versuch
        calls.clear()

        def refuse(code, ids, fetch=None, lang=None, pause=None):
            calls.append(code)
            raise sources.FetchError("u", 500)
        with mock.patch.object(sources, "fetch_prices", refuse), \
                mock.patch.object(countries, "ORDER", ["DE"]):
            sync.sync_prices(data, settings, None, lambda s: None, {})
        self.assertEqual(calls, ["DE"])

    def test_only_nintendo_ids_from_links(self):
        page = ('<title>X | Deku Deals</title>'
                '<a href="https://www.nintendo.com/x?id=76971254689271">a</a>'
                '<a href="https://ec.nintendo.com/DE/de/titles/70050000012345">b</a>')
        self.assertEqual(sources.parse_item_page(page)["nsuids"], ["70050000012345"])

    def test_invalid_ids_removed_and_searched_again(self):
        data = {"extra": {"x": {"ids": {"EU": ["70050000012345"], "AM": ["76971254689271"]},
                                "ids_checked": {"EU": 1, "AM": 1}}},
                "items": {"a": {"ids": {"EU": ["70010000000001", "76971254689271"]},
                                "ids_checked": {"EU": 1}}}}
        self.assertEqual(sync.clean_ids(data), 2)
        self.assertEqual(data["extra"]["x"]["ids"], {"EU": ["70050000012345"], "AM": []})
        self.assertEqual(data["extra"]["x"]["ids_checked"], {"EU": 1})     # AM neu suchen
        self.assertEqual(data["items"]["a"]["ids"]["EU"], ["70010000000001"])
        self.assertEqual(data["items"]["a"]["ids_checked"], {"EU": 1})
        self.assertEqual(sync.clean_ids(data), 0)

    def test_languages_of_missing_dlc_once_per_game(self):
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "US", "JP")
        data = self.data()
        data["extra"] = {"rl-b": {"title": "Car B", "parent": "rl", "ids": {"EU": ["2"], "AM": ["12"], "JP": ["22"]}},
                         "rl-c": {"title": "Car C", "parent": "rl", "ids": {"EU": ["3"], "AM": ["13"]}}}
        am, jp = [], []
        with mock.patch.object(sources, "fetch_langs_eu", lambda ids, fetch=None, **kw: {"2": "english, german"}), \
                mock.patch.object(sources, "fetch_langs_am", lambda n, fetch=None: am.append(n) or "english, german"), \
                mock.patch.object(sources, "fetch_langs_jp", lambda n, fetch=None: jp.append(n)):
            sync.sync_langs(data, settings, None, lambda s: None, now=1736467200)
            sync.sync_langs(data, settings, None, lambda s: None, now=1736467200 + 60)
        # Europa je DLC, Amerika und Japan eine Seite je Spiel, und nur einmal
        self.assertEqual(data["extra"]["rl-b"]["langs"], {"EU": "english, german"})
        self.assertEqual((am, jp), (["12"], ["22"]))
        self.assertEqual(data["glangs"]["rl"]["langs"], {"AM": "english, german"})
        # Ein Eintrag je Spiel und Region, unabhängig vom Preis
        rows = {(t["slug"], t["family"]): t for t in planner.lang_todo(data, settings)}
        self.assertEqual(rows[("rl", "AM")]["state"], True)
        self.assertEqual((rows[("rl", "JP")]["state"], rows[("rl", "JP")]["dlc"], rows[("rl", "JP")]["title"]),
                         (None, 2, "Rocket League"))
        # Angabe aus titledb: zählt, aber mit Herkunft
        data["glangs"]["rl"]["langs"]["JP"] = "japanese, german"
        data["glangs"]["rl"]["langs_src"] = {"JP": "titledb"}
        row = {(t["slug"], t["family"]): t for t in planner.lang_todo(data, settings)}[("rl", "JP")]
        self.assertEqual((row["state"], row["src"], row["nsuid"]), (True, "titledb", "22"))
        # Deine Angabe zum Spiel gilt für seine DLC
        settings["lang_confirm"] = {"rl": {"JP": False}}
        xctx = planner.extra_context(data, settings)
        self.assertIs(xctx.german(xctx.items["rl-b"], "JP", "rl-b"), False)
        self.assertIs(xctx.german(xctx.items["rl-b"], "EU", "rl-b"), True)

    def test_missing_dlc_languages_from_game_page(self):
        # Die Shopseite eines DLC nennt oft keine Sprachen (in Japan gibt es sie unter der
        # Adresse gar nicht). Das Tool sucht deshalb die IDs des Spiels selbst und fragt dort.
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "US", "JP")
        data = self.data()
        data["extra"] = {"rl-b": {"title": "Car B", "parent": "rl", "ids": {"EU": ["2"], "AM": ["12"], "JP": ["22"]},
                                  "ids_checked": {"EU": 1, "AM": 1, "JP": 1}}}
        data["glangs"] = {"rl": {"langs_checked": {"JP": 1736467200}, "langs_tries": {"JP": 1}}}
        pages = {("rl", "us"): ["111"], ("rl", "jp"): ["121"], ("rl", "de"): ["101"]}
        asked = []

        def item(slug, country, fetch=None):
            asked.append((slug, country))
            return {"nsuids": pages.get((slug, country), [])}
        with mock.patch.object(planner, "extra_dlc", lambda d, s: {"rl-b": ("Car B", "rl")}), \
                mock.patch.object(sources, "fetch_item", item):
            sync.sync_extra_ids(data, settings, None, lambda s: None, now=1736467200)
        # Europa seit 0.53 auch: Dort nennt kaum ein DLC Sprachen
        self.assertEqual(sorted(asked), [("rl", "de"), ("rl", "jp"), ("rl", "us")])
        g = data["glangs"]["rl"]
        self.assertEqual(g["ids"], {"AM": ["111"], "JP": ["121"], "EU": ["101"]})
        self.assertNotIn("JP", g["langs_tries"])                         # gleich neu fragen
        self.assertEqual(sync.jp_targets(data)["121"], [g])
        jp, am, eu = [], [], []
        with mock.patch.object(sources, "fetch_langs_eu",
                               lambda ids, fetch=None, **kw: eu.append(sorted(ids)) or {"101": "english, german"}), \
                mock.patch.object(sources, "fetch_langs_am", lambda n, fetch=None: am.append(n) or "english, german"), \
                mock.patch.object(sources, "fetch_langs_jp", lambda n, fetch=None: jp.append(n) or "日本語, ドイツ語"):
            sync.sync_langs(data, settings, None, lambda s: None, now=1736467200 + 60)
        self.assertEqual((am, jp, eu), (["111"], ["121"], [["101", "2"]]))
        self.assertEqual(g["langs"]["EU"], "english, german")
        self.assertEqual(data["extra"]["rl-b"]["langs_tries"]["EU"], 1)
        # Kennt das Spiel die Sprache, fragt Europa den DLC nicht mehr eigens
        with mock.patch.object(sources, "fetch_langs_eu", lambda ids, fetch=None, **kw: self.fail(ids)):
            sync.sync_langs(data, settings, None, lambda s: None, now=1736467200 + 2 * 86400)
        self.assertIs(planner.extra_context(data, settings).german(
            planner.extra_context(data, settings).items["rl-b"], "EU", "rl-b"), True)
        data["extra"]["rl-b"]["langs"] = {"EU": "english, german"}
        with mock.patch.object(planner, "extra_dlc", lambda d, s: {"rl-b": ("Car B", "rl")}):
            row = {(t["slug"], t["family"]): t for t in planner.lang_todo(data, settings)}.get(("rl", "JP"))
        self.assertIn("D121", row["url"])

    def test_language_not_found_searches_id_again(self):
        # Keine Seite unter der ID: einmal bei DekuDeals neu suchen. Andere ID übernehmen und
        # die Sprache neu fragen; dieselbe ID gilt danach als geprüft, keine Schleife.
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "US")
        data = {"items": {"a": {"title": "A", "active": True, "ids": {"AM": ["1"]}, "ids_checked": {"AM": 1}},
                          "b": {"title": "B", "active": True, "ids": {"AM": ["2"]}, "ids_checked": {"AM": 1}}},
                "prices": {}}

        def am(n, fetch=None):
            raise sources.FetchError("u", 404)
        t0 = 1736467200
        with mock.patch.object(sources, "fetch_langs_am", am):
            sync.sync_langs(data, settings, None, lambda s: None, now=t0)
        self.assertEqual({s: it.get("ids_suspect") for s, it in data["items"].items()},
                         {"a": {"AM": t0}, "b": {"AM": t0}})
        pages = {"a": ["11"], "b": ["2"]}
        with mock.patch.object(sources, "fetch_item", lambda slug, c, fetch=None: {
                "nsuids": pages[slug], "title": None, "parent": None, "low": None}), \
                mock.patch.object(sync, "_store_low", lambda *a, **k: None):
            sync.sync_ids(data, settings, None, lambda s: None, now=t0 + 60)
        a, b = data["items"]["a"], data["items"]["b"]
        self.assertEqual((a["ids"]["AM"], a["ids_suspect"], a.get("langs_tries", {})), (["11"], {}, {}))
        self.assertEqual((b["ids"]["AM"], b["ids_verified"]["AM"]), (["2"], "2"))
        self.assertFalse(sync.suspect_id(b, "AM", t0 + 120))         # dieselbe ID nicht noch einmal
        self.assertFalse(sync.suspect_id(a, "AM", t0 + 120))

    def test_language_blocks_do_not_count(self):
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "US")
        data = {"items": {f"t{i}": {"title": f"T{i}", "active": True, "ids": {"AM": [str(i)]}}
                          for i in range(3)}, "prices": {}}
        calls, answer = [], {"0": sources.FetchError("u", 429)}

        def am(n, fetch=None):
            calls.append(n)
            a = answer.get(n)
            if isinstance(a, Exception):
                raise a
            return a
        t0 = 1736467200
        with mock.patch.object(sources, "fetch_langs_am", am), mock.patch.object(sync, "LANG_PER_SYNC", 2):
            sync.sync_langs(data, settings, None, lambda s: None, now=t0)
            self.assertEqual(calls, ["0"])                      # gesperrt: sofort Schluss
            self.assertNotIn("langs_checked", data["items"]["t0"])   # zählt nicht als Versuch
            answer.clear()
            calls.clear()
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 60)
            self.assertEqual(len(calls), 2)                     # höchstens zwei je Abgleich
            calls.clear()
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 120)
            self.assertEqual(calls, ["2"])                      # ungeprüfter zuerst, die anderen warten
            # Seite ohne Sprachen: am nächsten Tag noch einmal, nach drei Versuchen monatlich
            for day in range(1, 6):
                sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 120 + day * 86400)
            self.assertEqual({it["langs_tries"]["AM"] for it in data["items"].values()}, {3})
            calls.clear()
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 120 + 7 * 86400)
            self.assertEqual(calls, [])

    def test_japan_retries_reset_once_and_budget_is_shared(self):
        # Bis 0.35 hingen Japan-Titel nach drei leeren Seiten im Monatsrhythmus. 0.36 fragt
        # sie einmal neu; beide Aufrufe eines Abgleichs teilen sich die Seitenzahl.
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "JP")
        t0 = 1736467200
        data = {"items": {f"t{i}": {"title": f"T{i}", "active": True, "ids": {"JP": [str(i)]},
                                    "langs_tries": {"JP": 3}, "langs_checked": {"JP": t0 - 86400}}
                          for i in range(3)}, "prices": {}}
        data["items"]["t2"]["langs"] = {"JP": "ドイツ語"}
        calls = []

        def jp(n, fetch=None):
            calls.append(n)
            return "ドイツ語"
        with mock.patch.object(sources, "fetch_langs_jp", jp), mock.patch.object(sync, "LANG_PER_SYNC", 1):
            budget = {}
            sync.sync_langs(data, settings, None, lambda s: None, now=t0, budget=budget)
            sync.sync_langs(data, settings, None, lambda s: None, now=t0, budget=budget)
            self.assertEqual(len(calls), 1)                     # eine Seite im ganzen Abgleich
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 60)
            self.assertEqual(sorted(calls), ["0", "1"])         # beide wieder dran, t2 hat schon
            self.assertEqual(data["langs_jp_reset"], 1)
            # Nur einmal: Danach gilt wieder der Monatsrhythmus
            data["items"]["t0"].update(langs={}, langs_tries={"JP": 3}, langs_checked={"JP": t0 + 60})
            calls.clear()
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 120)
            self.assertEqual(calls, [])

    def test_americas_bundles_asked_once_more(self):
        # Bis 0.44.2 fragte das Tool Pakete unter titles ab und fand nichts: einmal neu
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "US")
        t0 = 1736467200
        def rec(t, n):
            return {"title": t, "active": True, "ids": {"AM": [n]},
                    "langs_tries": {"AM": 3}, "langs_checked": {"AM": t0 - 86400}}
        data = {"items": {"pack": rec("P", "70070000000001"), "game": rec("G", "70010000000001")},
                "prices": {}, "langs_jp_reset": 1}
        asked = []
        with mock.patch.object(sources, "fetch_langs_am", lambda n, fetch=None: asked.append(n) or "english, german"):
            sync.sync_langs(data, settings, None, lambda s: None, now=t0)
        self.assertEqual(asked, ["70070000000001"])
        self.assertEqual((data["langs_bundle_reset"], data["items"]["pack"]["langs"]["AM"]), (1, "english, german"))

    def test_titledb_read_in_pieces(self):
        # titledb ist groß: Stück für Stück lesen, nur gesuchte IDs mit Sprachen behalten
        doc = json.dumps({"70010000000026": {"name": "Zelda", "languages": ["ja", "en", "de", "zh", "zh"]},
                          "70010000000123": {"name": "Bread", "languages": ["ja", "en"]},
                          "70010000000099": {"name": "Ohne", "languages": None},
                          "70010000000100": {"name": "Leer", "languages": []}}, indent=4, ensure_ascii=False)
        want = {"70010000000026", "70010000000099", "70010000000100"}
        for size in (1, 7, 64, len(doc)):
            chunks = [doc[i:i + size] for i in range(0, len(doc), size)]
            self.assertEqual(sources.parse_titledb(chunks, want),
                             {"70010000000026": "japanese, english, german, chinese"})
        with self.assertRaises(ValueError):
            sources.parse_titledb([doc[:-40]], want)
        self.assertEqual(sources.fetch_titledb(["70010000000123"], fetch=lambda u: doc),
                         {"70010000000123": {"langs": "japanese, english", "app": None}})

    def test_confirm_pages_after_needed_ones(self):
        # 1.4.5: Spiele ohne fehlende DLC bestätigt der Abgleich weiter (Entscheidung 26.10.2026),
        # aber nach denen, deren DLC fehlen, und das Protokoll nennt sie getrennt
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "JP")
        data = {"items": {}, "prices": {}, "langs_jp_reset": 1, "lang_wait": {"JP": 2e9},
                "extra": {"d1": {"parent": "b", "ids": {"JP": ["22"]}}, "d2": {"parent": "a", "ids": {"JP": ["11"]}}},
                "glangs": {"b": {"langs": {"JP": "japanese, german"}, "langs_src": {"JP": "titledb"}}}}
        calls = []

        def jp(n, fetch=None):
            calls.append(n)
            return "japanese, german"
        sync.status["log"].clear()
        with mock.patch.object(planner, "extra_dlc", lambda d, s: {"d2": ("D2", "a")}), \
                mock.patch.object(sources, "fetch_langs_jp", jp):
            sync.sync_langs(data, settings, None, lambda s: None, now=1e9)
            line = next(l for l in sync.status["log"] if "Sprachen Japan" in l)
            self.assertIn("1 Spiele der Sammlung mit fehlenden DLC, 1 Spiele der Sammlung ohne fehlende DLC, "
                          "nur zur Bestätigung, 1 davon schon aus titledb", line)
            data["lang_wait"] = {}
            sync.sync_langs(data, settings, None, lambda s: None, now=1e9)
        self.assertEqual(calls, ["11", "22"])                          # erst, woran etwas hängt

    def test_japan_waiting_room_stops_store_and_titledb_fills(self):
        # store-jp zeigt dem Tool den Warteraum: eine Probe, dann Schluss für diesen Abgleich.
        # titledb füllt die Lücken, gekennzeichnet; Nintendo geht vor, sobald es durchkommt.
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "JP")
        data = {"items": {f"t{i}": {"title": f"T{i}", "active": True, "ids": {"JP": [str(i)]}}
                          for i in range(3)}, "prices": {}, "langs_jp_reset": 1}
        shell = "<html><script>queue</script></html>"
        self.assertRaises(sources.FetchError, sources.fetch_langs_jp, "1", fetch=lambda u: shell)
        self.assertIsNone(sources.fetch_langs_jp("1", fetch=lambda u: "x" * sources.JP_WAITING))
        calls, tdb = [], []

        def jp(n, fetch=None):
            calls.append(n)
            raise sources.FetchError("u", 503, "Warteraum")

        def titledb(ids, fetch=None, region="JP.ja", apps=None):
            tdb.append(sorted(ids))
            found = {"0": {"langs": "japanese, german"}, "1": {"langs": "japanese, english"}}
            return found if apps is None else (found, {})
        t0 = 1736467200
        with mock.patch.object(sources, "fetch_langs_jp", jp), mock.patch.object(sources, "fetch_titledb", titledb):
            sync.sync_titledb(data, settings, None, now=t0)
            sync.sync_titledb(data, settings, None, now=t0 + 60)       # höchstens wöchentlich
            self.assertEqual(tdb, [["0", "1", "2"]])
            sync.sync_langs(data, settings, None, lambda s: None, now=t0)
        self.assertEqual(len(calls), 1)                                 # eine Probe, dann Schluss
        # Zweiter Aufruf im selben Abgleich (Sprachen neuer DLC) klopft nicht noch einmal an
        budget = {}
        sync.status["log"].clear()
        with mock.patch.object(sources, "fetch_langs_jp", jp):
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 1, budget=budget)
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 2, budget=budget)
        # 0.54: Nach dem Warteraum ruht store-jp eine Woche, auch im nächsten Abgleich
        self.assertEqual(len(calls), 1)
        self.assertTrue(any("der Store zeigte zuletzt den Warteraum; nächster Versuch ab" in l for l in sync.status["log"]))
        self.assertFalse(any("Sprachen Japan: 0 von" in l for l in sync.status["log"]))
        with mock.patch.object(sources, "fetch_langs_jp", jp):
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 8 * 86400)
        self.assertEqual(len(calls), 2)                                 # nach der Woche wieder eine Probe
        data["lang_wait"] = {}
        items = data["items"]
        self.assertNotIn("langs_tries", items["t0"])                    # Warteraum zählt nicht
        self.assertEqual((items["t0"]["langs"]["JP"], items["t0"]["langs_src"]["JP"]),
                         ("japanese, german", "titledb"))
        self.assertNotIn("langs", items["t2"])
        # Eine Woche später: nur t2 fehlt noch, aber erst nach einem Monat wieder nachsehen
        with mock.patch.object(sources, "fetch_titledb", titledb):
            sync.sync_titledb(data, settings, None, now=t0 + 8 * 86400)
            self.assertEqual(len(tdb), 1)
            # 0.66: Ist die Datei seitdem unverändert, bringt sie nichts Neues und wird nicht geladen
            sync.sync_titledb(data, settings, None, now=t0 + 31 * 86400)
            self.assertEqual(len(tdb), 1)
            self.assertIn("titledb: Dateien seit dem letzten Laden unverändert", sync.status["log"][-1])
            newer = {"status": 200, "error": "", "size": "25000000", "modified": "Mon, 09 Nov 2026 08:00:00 GMT"}
            with mock.patch.object(sources, "head", lambda url, timeout=20: newer):
                sync.sync_titledb(data, settings, None, now=t0 + 39 * 86400)
            self.assertEqual(tdb[-1], ["2"])
        # store-jp kommt durch: Angabe von Nintendo ersetzt titledb
        with mock.patch.object(sources, "fetch_langs_jp", lambda n, fetch=None: "日本語, 英語"):
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 32 * 86400)
        self.assertEqual(items["t0"]["langs"]["JP"], "日本語, 英語")
        self.assertNotIn("JP", items["t0"]["langs_src"])

    def test_titledb_checks_japan_id_against_europe(self):
        # Kennt titledb in Japan einen Titel mit der Programm-ID aus Europa und ist es nicht
        # die eigene Japan-ID, einmal neu suchen. Ohne Kandidaten hat das Spiel in Japan wohl
        # eine eigene Programm-ID: nichts tun. Unbekannt in titledb: nichts tun.
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "JP")
        lang = {"JP": "日本語, ドイツ語"}
        data = {"items": {"ok": {"title": "Ok", "active": True, "ids": {"EU": ["e1"], "JP": ["j1"]}, "langs": dict(lang)},
                          "bad": {"title": "Bad", "active": True, "ids": {"EU": ["e2"], "JP": ["j2"]}, "langs": dict(lang)},
                          "new": {"title": "New", "active": True, "ids": {"EU": ["e3"], "JP": ["j3"]}, "langs": dict(lang)}},
                "prices": {}}
        regions = []

        data["items"]["odd"] = {"title": "Odd", "active": True, "ids": {"EU": ["e4"], "JP": ["j4"]}, "langs": dict(lang)}

        def titledb(ids, fetch=None, region="JP.ja", apps=None):
            regions.append(region)
            if region == "DE.de":
                return {"e1": {"app": "0100A"}, "e2": {"app": "0100C"}, "e4": {"app": "0100E"}}
            self.assertEqual(apps, {"0100A", "0100C", "0100E"})
            return ({"j1": {"app": "0100A"}, "j2": {"app": "0100B"}, "j4": {"app": "0100F"}},
                    {"0100A": "j1", "0100C": "j9"})            # für 0100E kein Kandidat
        t0 = 1736467200
        with mock.patch.object(sources, "fetch_titledb", titledb):
            sync.sync_titledb(data, settings, None, now=t0)
            self.assertEqual(regions, ["DE.de", "JP.ja"])
            items = data["items"]
            self.assertEqual({s: it.get("ids_suspect") for s, it in items.items()},
                             {"ok": None, "bad": {"JP": t0}, "new": None, "odd": None})
            sync.sync_titledb(data, settings, None, now=t0 + 8 * 86400)
            self.assertEqual(len(regions), 2)                   # jede ID nur einmal abgleichen
            # Neue ID, die titledb noch nie gesehen hat: gleich, nicht erst nach einer Woche
            items["fresh"] = {"title": "F", "active": True, "ids": {"EU": ["e1"], "JP": ["j1x"]}, "langs": dict(lang)}
            sync.sync_titledb(data, settings, None, now=t0 + 8 * 86400 + 3600)
            self.assertEqual(len(regions), 4)
            items["fresh2"] = {"title": "G", "active": True, "ids": {"EU": ["e1"], "JP": ["j1y"]}, "langs": dict(lang)}
            sync.sync_titledb(data, settings, None, now=t0 + 8 * 86400 + 5400)
            self.assertEqual(len(regions), 4)                   # höchstens einmal je Stunde
            sync.sync_titledb(data, settings, None, now=t0 + 8 * 86400 + 7200)
            self.assertEqual(len(regions), 6)
        # Neusuche bei DekuDeals bleibt bei der alten ID: der titledb-Kandidat gilt.
        # Ältere Daten mit leerem Hinweis: die ID bleibt, aber als fraglich markiert
        sync.settle_ids(items["bad"], "JP", ["j2"], t0 + 60, "Bad")
        items["odd"]["ids_hint"] = {"JP": None}
        sync.settle_ids(items["odd"], "JP", ["j4"], t0 + 60, "Odd")
        self.assertEqual((items["bad"]["ids"]["JP"], items["bad"].get("langs", {}).get("JP")), (["j9"], None))
        self.assertEqual((items["odd"]["ids"]["JP"], items["odd"]["ids_doubt"]), (["j4"], {"JP": "j4"}))
        self.assertEqual(items["odd"]["langs"]["JP"], lang["JP"])
        ctx = planner.Context.__new__(planner.Context)
        ctx.settings, ctx.items = {}, items
        self.assertIsNone(ctx.german(items["odd"], "JP", "odd"))       # zählt erst nach deiner Angabe
        self.assertIs(ctx.german(items["ok"], "JP", "ok"), True)
        ctx.settings = {"lang_confirm": {"odd": {"JP": True}}}
        self.assertIs(ctx.german(items["odd"], "JP", "odd"), True)
        self.assertFalse(sync.suspect_id(items["bad"], "JP", t0 + 120))

    def test_old_titledb_doubts_cleared_once(self):
        # Bis 0.44.4 machte eine abweichende Programm-ID ohne Kandidaten die ID fraglich
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code == "DE"
        data = {"items": {"hw": {"title": "HW", "active": True, "ids": {"JP": ["j1"]},
                                 "ids_doubt": {"JP": "j1"}, "ids_verified": {"JP": "j1"}},
                          "nh": {"title": "NH", "active": True, "ids": {"JP": ["j2"]},
                                 "ids_suspect": {"JP": 5}, "ids_hint": {"JP": None}},
                          "ok": {"title": "OK", "active": True, "ids": {"JP": ["j3"]},
                                 "ids_suspect": {"JP": 5}, "ids_hint": {"JP": "j9"}}},
                "prices": {}}
        sync.sync_titledb(data, settings, None, now=10)
        items = data["items"]
        self.assertEqual((items["hw"]["ids_doubt"], items["nh"]["ids_suspect"], items["nh"]["ids_hint"]), ({}, {}, {}))
        self.assertEqual((items["ok"]["ids_suspect"], items["ok"]["ids_hint"]), ({"JP": 5}, {"JP": "j9"}))
        self.assertEqual(data["tdb_doubt_reset"], 1)

    def test_browser_helper_import(self):
        data = {"items": {"a": {"title": "A", "active": True, "ids": {"JP": ["70010000000001"]},
                                "langs": {"JP": "japanese"}, "langs_src": {"JP": "titledb"}},
                          "b": {"title": "B", "active": True, "ids": {"JP": ["70010000000002"]}}},
                "extra": {"g-dlc": {"title": "DLC", "parent": "g", "ids": {"JP": ["70050000000003"]}}},
                "prices": {}}
        store.save_data(data)
        text = json.dumps({"70010000000001": "日本語, 英語, フランス語, ドイツ語",
                           "70010000000002": "", "70050000000003": "日本語", "70019999999999": "日本語"})
        res = sync.import_jp_langs(text, now=5)
        self.assertEqual(res, {"read": 2, "empty": 1, "unknown": 1, "gone": 0})
        # Keine Seite unter der ID: der nächste Abgleich sucht sie neu
        res = sync.import_jp_langs(json.dumps({"70010000000002": "keine Seite"}), now=6)
        self.assertEqual(res["gone"], 1)
        self.assertEqual(store.load_data()["items"]["b"]["ids_suspect"], {"JP": 6})
        d = store.load_data()
        self.assertEqual(d["items"]["a"]["langs"]["JP"], "日本語, 英語, フランス語, ドイツ語")
        self.assertEqual(d["items"]["a"]["langs_src"], {})
        self.assertEqual(d["glangs"]["g"]["langs"]["JP"], "日本語")
        self.assertRaises(ValueError, sync.import_jp_langs, "kein json")
        with sync._lock:
            self.assertRaises(RuntimeError, sync.import_jp_langs, "{}")

    def test_japan_language_checked_monthly(self):
        # Japan: nach einer leeren Seite gleich monatlich, Amerika noch am nächsten Tag
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "JP", "US")
        data = {"items": {"t": {"title": "T", "active": True, "ids": {"JP": ["1"], "AM": ["2"]}}},
                "prices": {}, "langs_jp_reset": 1}
        calls = []

        def page(n, fetch=None):
            calls.append(n)
            return None
        t0 = 1736467200
        with mock.patch.object(sources, "fetch_langs_jp", page), mock.patch.object(sources, "fetch_langs_am", page):
            sync.sync_langs(data, settings, None, lambda s: None, now=t0)
            self.assertEqual(sorted(calls), ["1", "2"])
            calls.clear()
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 86400)
            self.assertEqual(calls, ["2"])
            calls.clear()
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 31 * 86400)
            self.assertIn("1", calls)

    def test_languages_are_cleaned_up(self):
        settings = {"lang_confirm": {"gone": {"JP": True}, "rl": {"JP": False}, "rl-w": {"AM": True}}}
        data = self.data()
        data["items"]["gone"] = {"title": "Gone", "active": False, "langs": {"EU": "german"}, "langs_checked": {"EU": 1}}
        data["items"]["rl-a"] = {"title": "Car A", "active": False, "langs": {"EU": "german"}}
        data["glangs"] = {"rl": {"langs": {"AM": "german"}}, "old": {"langs": {"AM": "german"}}}
        data["extra"] = {"rl-b": {"title": "Car B", "parent": "rl", "ids": {}}}
        saved = []
        with mock.patch.object(store, "save_settings", saved.append):
            sync.prune_langs(data, settings)
        self.assertNotIn("langs", data["items"]["gone"])
        self.assertIn("langs", data["items"]["rl-a"])                 # in der Sammlung: bleibt
        self.assertEqual(list(data["glangs"]), ["rl"])
        # Deine Bestätigungen bleiben, auch für Titel, die gerade nirgends stehen (0.95)
        self.assertEqual(saved, [])
        self.assertEqual(set(settings["lang_confirm"]), {"gone", "rl", "rl-w"})



class ReplayTest(unittest.TestCase):
    # Prüfumgebung: Momentaufnahme ohne Netz durchrechnen, Regeln prüfen, Versionen vergleichen
    def snapshot(self, tmp):
        data, settings = sample()
        for i, it in enumerate(data["items"].values()):
            it["ids"] = {"EU": [f"700100000000{i:02d}"]}
        data["last_sync"] = NOW.isoformat()
        a, b = os.path.join(tmp, "abgleich.json"), os.path.join(tmp, "sicherung.json")
        with open(a, "w") as f:
            json.dump({"data": data, "log": []}, f)
        with open(b, "w") as f:
            json.dump({"settings": settings}, f)
        return a, b

    def replay(self, *args):
        import subprocess
        root = os.path.join(os.path.dirname(__file__), "..")
        r = subprocess.run([sys.executable, "-m", "tools.replay", *args], cwd=root,
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_replay_rules_scenarios_and_compare(self):
        tmp = tempfile.mkdtemp()
        a, b = self.snapshot(tmp)
        code, out = self.replay("--abgleich", a, "--sicherung", b, "--json")
        self.assertEqual(code, 0, out)
        res = json.loads(out)
        self.assertEqual(res["problems"], [])
        self.assertEqual(res["version"], sources.VERSION)
        self.assertIn("hades", res["summary"]["radar"])
        # Szenario: Norwegen aus, Hades landet woanders
        code, out2 = self.replay("--abgleich", a, "--sicherung", b, "--json", "--szenario", "land-aus=NO")
        self.assertEqual(code, 0, out2)
        self.assertNotEqual(json.loads(out2)["summary"]["radar"]["hades"][1], "NO")
        # Regelverstoß: ungültige ID
        with open(a) as f:
            snap = json.load(f)
        snap["data"]["items"]["hades"]["ids"]["EU"] = ["1"]
        with open(a, "w") as f:
            json.dump(snap, f)
        code, out3 = self.replay("--abgleich", a, "--sicherung", b)
        self.assertEqual(code, 1)
        self.assertIn("hat kein gültiges Format", out3)
        self.assertNotIn("Traceback", out3)


def nso_page(base):
    """Nachbau von Nintendos Mitgliedschaftsseite (Aufbau wie im echten HTML, 14.10.2026): Tarife mit
    ticketItemsV2, je Eintrag eine Abo-Fassung, Laufzeit in Minuten, vorneweg eine Probe-Mitgliedschaft.
    IDs: base+1 1 Monat, base 3 Monate, base+2 12 Monate, base+12 Familie, base+40 EP, base+60 EP Familie."""
    def item(n, grant, lim="false"):
        return ('{"nsUid":%d,"ticketItemGroupId":"a","__typename":"NormalTicketItem","subscriptionTicketItem":{"nsUid":%d,'
                '"__typename":"NormalSubscriptionTicketItem","grantMinutes":%d},"isOp2LimitedRight":%s,"grantMinutes":%d}'
                % (n, n + 500, grant, lim, grant))

    def one(n):
        return ('{"nsUid":%d,"ticketItemGroupId":"b","__typename":"NormalTicketItem","subscriptionTicketItem":{"nsUid":%d,'
                '"__typename":"NormalSubscriptionTicketItem"},"grantMinutes":525600}' % (n, n + 500))
    body = ('{"ticketItemGroupsFragment":{"individual":{"ticketItemsV2":['
            + ",".join([item(base + 2000, 12960, "true"), item(base + 1, 43200), item(base, 129600), item(base + 2, 525600)])
            + ']},"family":{"ticketItemsV2":[' + one(base + 12) + ']},"exIndividual":{"ticketItemsV2":[' + one(base + 40)
            + ']},"exFamily":{"ticketItemsV2":[' + one(base + 60) + ']}}}')
    return '<script>self.__next_f.push([1,"' + body.replace('"', '\\"') + '"])</script>'


class MembershipTest(unittest.TestCase):
    """Online-Mitgliedschaft, 12 Monate, einzeln (0.56): IDs je Land aus der DekuDeals-Seite,
    Preise über den normalen Preisabruf, Einkaufspreis je Land wie bei Spielen."""
    PAGE = ("<title>Nintendo Switch Online 12 Month Membership | Deku Deals</title>"
            "<a data-out-analytics-id='eshop_{cc}:{n}' href='https://ec.nintendo.com/X/x/membership'>eShop</a>")

    def setUp(self):
        store.save_settings({"wishlist_url": "https://www.dekudeals.com/wishlist/abc", "nso_until": "",
                             "countries": {c: {"enabled": c in ("DE", "BR")} for c in countries.ORDER}})

    def test_ids_prices_and_view(self):
        settings = store.load_settings()
        data = store.load_data()
        calls = []

        def fake(url, ua=None):
            if url == "https://ec.nintendo.com/DE/de/membership":
                return nso_page(70080000000300)
            if url == "https://ec.nintendo.com/US/en/membership":
                return nso_page(70080000000400)
            calls.append(url)
            i = next(i for i, v in enumerate(v for v in planner.NSO_VARIANTS if v["slug"]) if f"/items/{v['slug']}?" in url)
            if "country=de" in url:
                return self.PAGE.format(cc="de", n=str(70080000000189 + 10 * i))
            if "country=br" in url:
                return self.PAGE.format(cc="br", n=str(70080000000186 + 10 * i))
            raise AssertionError(url)
        # Daten bis 0.56: nur 12 Monate, flach; sie wandern nach v.m12 (alte Dateien laden weiter)
        data["nso"] = {"ids": {"DE": ["70080000000189"]}, "checked": {}, "lows": {}, "urls": {}}
        self.assertEqual(planner.nso_variants(data)["m12"]["ids"], {"DE": ["70080000000189"]})
        sync.sync_nso(data, settings, fake, lambda s: None, now=1e9)
        self.assertNotIn("ids", data["nso"])
        self.assertEqual(data["nso"]["v"]["m12"]["ids"], {"DE": ["70080000000199"], "BR": ["70080000000196"]})
        self.assertEqual(data["nso"]["v"]["m3"]["ids"], {"DE": ["70080000000189"], "BR": ["70080000000186"]})
        slugged = sum(1 for v in planner.NSO_VARIANTS if v["slug"])
        self.assertEqual(len(calls), 2 * slugged)       # je Variante, die DekuDeals führt, und Land eine Seite
        # 0.58: Nintendos Seite je Region liefert alle Varianten, die Laufzeit entscheidet, nicht die Reihenfolge
        self.assertEqual(data["nso"]["page"]["EU"]["ids"], {"m1": "70080000000301", "m3": "70080000000300", "m12": "70080000000302",
                                                            "fam": "70080000000312", "ep": "70080000000340", "epfam": "70080000000360"})
        self.assertNotIn("JP", data["nso"]["page"])     # Japan ist nicht aktiv
        # eigene ID von DekuDeals geht vor, sonst die der Region von Nintendos Seite
        self.assertEqual(sync.nso_ids_for(data, "DE", "m1"), ["70080000000301"])
        self.assertEqual(sync.nso_ids_for(data, "DE", "m12"), ["70080000000199"])
        self.assertEqual(sync.nso_ids_for(data, "MX", "epfam"), ["70080000000460"])
        # monatlich: im nächsten Abgleich nichts fällig
        sync.sync_nso(data, settings, fake, lambda s: None, now=1e9 + 3600)
        self.assertEqual(len(calls), 2 * slugged)
        del data["nso"]["page"]
        self.assertEqual(sync.nso_ids_for(data, "MX"), ["70080000000196"])   # Region Amerika als Ersatz

        def prices(url, ua=None):
            self.assertIn("api.ec.nintendo.com", url)
            if "country=DE" in url:
                self.assertIn("70080000000189", url)
                return ('{"prices":[{"title_id":70080000000199,"sales_status":"onsale","regular_price":{"currency":"EUR","raw_value":"19.99"}},'
                        '{"title_id":70080000000189,"sales_status":"onsale","regular_price":{"currency":"EUR","raw_value":"7.99"}}]}')
            if "country=BR" in url:
                self.assertIn("70080000000196", url)
                return '{"prices":[{"title_id":70080000000196,"sales_status":"onsale","regular_price":{"currency":"BRL","raw_value":"109.9"}}]}'
            return '{"prices":[]}'
        data["items"] = {"t": {"title": "T", "active": True, "ids": {"EU": ["70010000000001"], "AM": ["70010000000002"]}}}
        data["fx"] = {"rates": {"EUR": 1.0, "BRL": 5.5}, "updated": ""}
        sync.sync_prices(data, settings, prices, lambda s: None)
        self.assertEqual(data["nso_prices"]["DE"]["m12"]["regular"], 19.99)
        self.assertEqual(data["nso_prices"]["DE"]["m3"]["regular"], 7.99)
        self.assertEqual(data["nso_prices"]["BR"]["m12"]["regular"], 109.9)
        self.assertNotIn("nso", data["prices"]["DE"])          # nicht in der Wishlist
        settings["current_country"] = "BR"
        settings["nso_until"] = "2026-11-01"
        m = planner.membership(data, settings, now=datetime(2026, 10, 13, tzinfo=timezone.utc))
        self.assertEqual(m["days_left"], 19)
        self.assertTrue(m["due"])
        codes = [r["code"] for r in m["rows"]]
        self.assertEqual(set(codes), {"DE", "BR"})
        de = next(r for r in m["rows"] if r["code"] == "DE")
        self.assertEqual(de["eur"], 19.99)
        self.assertEqual(de["month"], 1.67)
        self.assertTrue(next(r for r in m["rows"] if r["code"] == "BR")["current"])
        self.assertEqual(m["rows"], sorted(m["rows"], key=lambda r: (not r["counts"], r["eur"])))
        # 0.57: alle Varianten, Preis je Monat nach Laufzeit; deine Variante bestimmt rows
        self.assertEqual([v["key"] for v in m["variants"]], planner.NSO_KEYS)
        m3 = next(v for v in m["variants"] if v["key"] == "m3")
        self.assertEqual([(r["code"], r["eur"], r["month"]) for r in m3["rows"]], [("DE", 7.99, 2.66)])
        self.assertEqual(m["mine"], "m12")
        settings["nso_variant"] = "m3"
        self.assertEqual(planner.membership(data, settings)["rows"][0]["eur"], 7.99)
        settings["nso_variant"] = "m12"
        # Preise aus 0.56 (Schlüssel „nso“) zählen als 12 Monate
        self.assertEqual(planner.nso_price({"nso": {"x": 1}}, "m12"), {"x": 1})
        # 0.56.1: Link in den eShop aus der DekuDeals-Seite, Bestpreis, ★ und Abstand wie bei Titeln
        self.assertEqual(de["url"], "https://ec.nintendo.com/X/x/membership")
        self.assertIsNotNone(m["champ"])
        for r in m["rows"]:
            if r["counts"]:
                self.assertEqual(r["at_best"], r["eur"] <= m["champ"] * 1.02 + 0.005)
                self.assertAlmostEqual(r["over"], r["eur"] - m["champ"], places=2)
        self.assertTrue(any(r["at_best"] for r in m["rows"] if r["counts"]) or all(r["low_eur"] is not None for r in m["rows"] if r["counts"]))

    def test_own_low_for_variants_without_dekudeals(self):
        # 0.87: 1 Monat und Familie mit Erweiterungspaket führt DekuDeals nicht; ihr Tiefstpreis kommt
        # aus der eigenen Aufzeichnung, 24 Monate zurück, mit Beginn der Aufzeichnung
        data, history = {}, {}
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        days = lambda n: t0 + timedelta(days=n)
        def track(n, m1, sale=None):
            p = {"status": "onsale", "currency": "EUR", "regular": m1}
            if sale:
                p["discount"] = sale
            sync._track_nso(data, history, "DE", {"m1": p, "m12": {"status": "onsale", "currency": "EUR", "regular": 19.99}},
                            days(n).isoformat(timespec="seconds"), now=days(n))
        track(0, 3.99)
        track(1, 3.99, sale=2.99)
        track(2, 3.99)
        self.assertEqual(history["DE"]["nso-m1"], [[days(0).isoformat(timespec="seconds"), 3.99],
                                                   [days(1).isoformat(timespec="seconds"), 2.99],
                                                   [days(2).isoformat(timespec="seconds"), 3.99]])
        self.assertNotIn("nso-m12", history["DE"])        # 12 Monate kommt von DekuDeals
        e = data["nso"]["v"]["m1"]
        self.assertEqual((e["lows"]["DE"], e["own_since"]["DE"]), (2.99, days(0).isoformat(timespec="seconds")))
        # Nach 24 Monaten fällt das Angebot heraus; der Preis zu Beginn des Zeitraums zählt
        track(800, 3.99)
        self.assertEqual(e["lows"]["DE"], 3.99)
        # In der Oberfläche: Tiefstpreis mit Beginn der Aufzeichnung, bei 12 Monaten ohne
        data["nso_prices"] = {"DE": {"m1": {"status": "onsale", "currency": "EUR", "regular": 3.99},
                                     "m12": {"status": "onsale", "currency": "EUR", "regular": 19.99}}}
        data["fx"] = {"rates": {"EUR": 1.0}, "updated": ""}
        data["items"] = {}
        settings = store.load_settings()
        m = planner.membership(data, settings, now=days(800))
        v = {x["key"]: x for x in m["variants"]}
        de = next(r for r in v["m1"]["rows"] if r["code"] == "DE")
        self.assertEqual((de["low_eur"], de["low_since"]), (3.99, days(0).isoformat(timespec="seconds")))
        self.assertNotIn("low_since", next(r for r in v["m12"]["rows"] if r["code"] == "DE"))

    def test_until_setting(self):
        self.assertEqual(store.save_settings({"nso_until": "2027-02-03"})["nso_until"], "2027-02-03")
        self.assertEqual(store.save_settings({"nso_until": "morgen"})["nso_until"], "2027-02-03")
        self.assertEqual(store.save_settings({"nso_until": ""})["nso_until"], "")
        self.assertEqual(store.save_settings({"nso_variant": "ep"})["nso_variant"], "ep")
        self.assertEqual(store.save_settings({"nso_variant": "jahr"})["nso_variant"], "ep")
        m = planner.membership(store.load_data(), store.load_settings())
        self.assertEqual(m["rows"], [])
        self.assertFalse(m["due"])

    def test_until_suggested_after_marked_purchase(self):
        # 0.88: Ein vermerkter Kauf mit Mitgliedschaft schlägt das neue Ablaufdatum vor, ab Ablauf
        # oder ab dem Kauftag, wenn sie schon abgelaufen war; Käufe vor dem letzten Setzen zählen nicht
        s = {"nso_until": "2026-11-01", "nso_until_set": "2026-10-20T10:00:00+00:00"}
        buy = lambda at, *slugs: {"at": at, "code": "BR", "slugs": list(slugs)}
        self.assertIsNone(planner.until_suggest(s, [buy("2026-10-21T08:00:00+00:00", "hades")]))
        self.assertIsNone(planner.until_suggest(s, [buy("2026-10-19T08:00:00+00:00", "nso-m12")]))
        got = planner.until_suggest(s, [buy("2026-10-21T08:00:00+00:00", "hades", "nso-m12")])
        self.assertEqual(got, {"until": "2027-11-01", "from": [{"label": "12 Monate", "date": "2026-10-21", "code": "BR"}]})
        # Abgelaufen: ab dem Kauftag; zwei Käufe nacheinander zählen zusammen
        s["nso_until"] = "2026-09-01"
        got = planner.until_suggest(s, [buy("2026-10-21T08:00:00+00:00", "nso-m1"), buy("2026-10-22T08:00:00+00:00", "nso-m3")])
        self.assertEqual(got["until"], "2027-02-18")         # 21.10. + 30 Tage + 90 Tage
        # Ohne Datum: ab dem Kauftag
        self.assertEqual(planner.until_suggest({"nso_until": ""}, [buy("2026-10-21T08:00:00+00:00", "nso-fam")])["until"], "2027-10-21")
        # Speichern oder Bestätigen des Datums setzt den Stand neu, der Vorschlag verschwindet
        saved = store.save_settings({"nso_until": "2027-11-01"})
        self.assertGreater(saved["nso_until_set"], "2026-10-19")
        self.assertIsNone(planner.until_suggest(saved, [buy(saved["nso_until_set"], "nso-m12")]))
        # Alte Einstellungen ohne Stand: Käufe vor 0.88 zählen nicht
        self.assertEqual(store.DEFAULT_SETTINGS["nso_until_set"], "2026-10-19T22:00:00+00:00")


class MembershipExtraTest(unittest.TestCase):
    """Angebote der Mitgliedschaft von Hand (0.60), etwa Codes bei Amazon Japan."""
    def test_extra_offer(self):
        store.save_settings({"countries": {c: {"enabled": c in ("DE", "JP")} for c in countries.ORDER}})
        s = store.save_settings({"nso_extra": [
            {"key": "m12", "code": "JP", "price": "2970", "src": "Amazon", "url": "https://example.com/code", "date": "2026-10-14"},
            {"key": "xx", "code": "JP", "price": 1},                   # unbekannte Variante
            {"key": "m3", "code": "JP", "price": -5},                  # kein Preis
            {"key": "m3", "code": "JP", "price": 990, "url": "javascript:alert(1)"}]})
        self.assertEqual(len(s["nso_extra"]), 1)
        data = store.load_data()
        data["nso_prices"] = {"DE": {"m12": {"local": 1999, "regular": 1999, "sale": False, "currency": "EUR"}},
                              "JP": {"m12": {"local": 3000, "regular": 3000, "sale": False, "currency": "JPY"}}}
        data["fx"] = {"rates": {"EUR": 1.0, "JPY": 160.0}, "updated": ""}
        m = planner.membership(data, s, now=datetime(2026, 10, 14, tzinfo=timezone.utc))
        rows = next(v for v in m["variants"] if v["key"] == "m12")["rows"]
        jp = next(r for r in rows if r["code"] == "JP" and r.get("src"))
        self.assertEqual(jp["src"], "Amazon")
        self.assertEqual(jp["extra"], 0)
        # Kreditkarte: Mittelkurs plus Gebühr
        self.assertAlmostEqual(jp["eur"], round(2970 / 160 * (1 + s["card_fee_pct"] / 100), 2), places=2)
        self.assertIsNone(jp["read"])
        # Ab 0.61 liest der Abgleich den Preis vom Link; der gelesene gilt 14 Tage
        now = datetime(2026, 10, 14, tzinfo=timezone.utc).timestamp()
        data["offer_prices"] = {"https://example.com/code": {"price": 2800.0, "currency": "JPY", "ok": now - 3600, "checked": now - 3600}}
        jp = next(r for r in next(v for v in planner.membership(data, s, now=datetime(2026, 10, 14, tzinfo=timezone.utc))["variants"]
                                  if v["key"] == "m12")["rows"] if r.get("src"))
        self.assertEqual((jp["local"], jp["manual"]), (2800.0, 2970))
        self.assertTrue(jp["read"])
        data["offer_prices"]["https://example.com/code"]["ok"] = now - 15 * 86400
        jp = next(r for r in next(v for v in planner.membership(data, s, now=datetime(2026, 10, 14, tzinfo=timezone.utc))["variants"]
                                  if v["key"] == "m12")["rows"] if r.get("src"))
        self.assertEqual(jp["local"], 2970)

    def test_membership_in_basket_and_plan(self):
        # Ab 0.69 lässt sich die Mitgliedschaft in Korb und Kaufplan dazunehmen; Urteil und Plan
        # nehmen sie nie von selbst
        data, settings = sample()
        data["nso_prices"] = {"DE": {"m12": {"status": "onsale", "currency": "EUR", "regular": 19.99}},
                              "BR": {"m12": {"status": "onsale", "currency": "BRL", "regular": 109.9}}}
        self.assertEqual([x["slug"] for x in planner.nso_items(data)], ["nso-m12"])
        self.assertNotIn("nso-m12", {r["slug"] for r in planner.radar(data, settings, now=NOW)})
        res, _ = planner.plans(data, settings, basket=["nso-m12", "hades"], now=NOW, with_mix=True)
        de = next(p for p in res if p["code"] == "DE")
        self.assertEqual({i["slug"] for i in de["items"]}, {"nso-m12", "hades"})
        self.assertIn("Online-Mitgliedschaft 12 Monate", [i["title"] for i in de["items"]])
        self.assertNotIn("nso-m12", data["items"])            # die Daten bleiben unverändert
        self.assertFalse(next(i for i in de["items"] if i["slug"] == "nso-m12").get("lang"))   # keine Sprachmarke
        plan = planner.purchase_plan(data, settings, now=NOW, include_good=True)
        self.assertFalse(any(i["slug"].startswith("nso-") for p in plan["steps"] for i in p["items"]))
        code = plan["steps"][0]["code"]
        plan = planner.purchase_plan(data, settings, now=NOW, include_good=True, fill={code: ["nso-m12"]},
                                     bought=[{"slugs": ["nso-m12"], "code": code}])
        step = next(p for p in plan["steps"] if p["code"] == code)
        self.assertIn(code, ("DE", "BR"))
        self.assertIn("nso-m12", {i["slug"] for i in step["items"]})   # ein früherer Kauf hält nicht ab

    def test_amazon_price(self):
        whole = ('<div id="corePrice_feature_div"><span class="a-price"><span class="a-price-symbol">￥</span>'
                 '<span class="a-price-whole">2,970</span></span></div>')
        self.assertEqual(sources.parse_amazon_price("<span>参考価格 ￥3,980</span>" + whole), (2970.0, "JPY", "Preiskasten"))
        data_div = '<div>{"desktop_buybox_group_1":[{"displayPrice":"￥990","priceAmount":990.00,"currencySymbol":"￥"}]}</div>'
        self.assertEqual(sources.parse_amazon_price(data_div + whole)[:2], (990.0, "JPY"))
        self.assertIsNone(sources.parse_amazon_price("<html>nichts</html>"))
        # Fehlalarm bis 0.60: „robot“ steht auch auf normalen Produktseiten
        self.assertFalse(sources.amazon_captcha("x" * 50000 + "robots" + whole))
        self.assertTrue(sources.amazon_captcha('<form action="/errors/validateCaptcha">'))
        self.assertEqual(sources.parse_shop_price("https://www.amazon.co.jp/dp/B000", whole), (2970.0, "JPY"))
        self.assertIsNone(sources.parse_shop_price("https://www.amazon.co.jp/dp/B000", '<form action="/errors/validateCaptcha">' + whole))

    def test_amazon_currency(self):
        # Amazon zeigt Besuchern aus Deutschland Europreise (bis 0.62 als Yen gelesen)
        eur = '<div>{"desktop_buybox_group_1":[{"displayPrice":"€45.66","priceAmount":45.66,"currencySymbol":"€"}]}</div>'
        self.assertEqual(sources.parse_amazon_price(eur, "JPY"), (45.66, "EUR", "Kaufoptionen"))
        esc = '{"desktop_buybox_group_1":[{"priceAmount":8082,"currencySymbol":"\\uffe5"}]}'
        self.assertEqual(sources.parse_amazon_price(esc)[:2], (8082.0, "JPY"))
        core = '<div id="corePrice_feature_div"><span class="a-offscreen">45,66 €</span></div>'
        self.assertEqual(sources.parse_amazon_price(core, "JPY")[:2], (45.66, "EUR"))
        core = '<div id="corePrice_feature_div"><span class="a-offscreen">￥8,082</span></div>'
        self.assertEqual(sources.parse_shop_price("https://www.amazon.co.jp/-/en/dp/X", core), (8082.0, "JPY"))
        self.assertEqual(sources.amazon_currency("https://www.amazon.co.jp/-/en/dp/X"), "JPY")
        self.assertIsNone(sources.amazon_currency("https://example.com/x"))
        # Die Währungswahl der Seite (Cookie) stellt Yen ein, nur bei Amazon
        seen = []

        class Resp:
            status, headers = 200, {}

            def __init__(self):
                import email.message
                self.headers = email.message.Message()

            def read(self):
                return b"ok"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        old = sources._opener.open
        sources._opener.open = lambda req, timeout=None: seen.append(req.get_header("Cookie")) or Resp()
        try:
            sources.request("https://www.amazon.co.jp/-/en/dp/X")
            sources.request("https://example.com/x")
        finally:
            sources._opener.open = old
        self.assertEqual(seen, ["i18n-prefs=JPY", None])

    def test_offer_plausible(self):
        x = {"code": "JP", "price": 8082, "url": "https://www.amazon.co.jp/dp/X"}
        now = 1e9
        known = {x["url"]: {"price": 45.66, "currency": "EUR", "ok": now, "checked": now}}
        r = planner.read_offer(x, known, "JPY", now)
        self.assertEqual((r["price"], r["read"], r["check"]), (8082, None, "cur"))
        known[x["url"]].update(price=4500.0, currency="JPY")
        self.assertEqual(planner.read_offer(x, known, "JPY", now)["check"], "off")
        known[x["url"]]["price"] = 7980.0
        r = planner.read_offer(x, known, "JPY", now)
        self.assertEqual((r["price"], r["read"], r["check"]), (7980.0, now, None))
        self.assertEqual(planner.read_offer(x, known, "JPY", now + 15 * 86400)["check"], "old")
        self.assertEqual(planner.read_offer(x, {}, "JPY", now)["check"], "wait")
        self.assertEqual(planner.read_offer(x, {x["url"]: {"error": "HTTP 500", "checked": now}}, "JPY", now)["check"], "err")
        self.assertIsNone(planner.read_offer(dict(x, url=""), known, "JPY", now)["check"])
        # Das Protokoll nennt unplausible Werte
        sync.status["log"] = []
        settings = {"own_offers": [dict(x, slug="a", src="Amazon")]}
        sync.sync_offer_prices({}, settings, lambda u: '<div id="corePrice_feature_div"><span class="a-offscreen">€45.66</span></div>',
                               lambda s: None, now=now)
        self.assertTrue(any("nicht plausibel" in str(l) and "EUR statt JPY" in str(l) for l in sync.status["log"]))

    def test_offer_prices_from_before_0_62_1_are_read_again(self):
        # 0.62.0 las Euro als Yen (5,65 statt 1000); solche Werte blieben einen Tag stehen
        settings = {"nso_extra": [{"key": "m3", "code": "JP", "price": 1000, "src": "Amazon", "url": "https://www.amazon.co.jp/dp/A"}]}
        data = {"offer_prices": {"https://www.amazon.co.jp/dp/A": {"price": 5.65, "currency": "JPY", "ok": 1e9, "checked": 1e9}}}
        page = '<div id="corePrice_feature_div"><span class="a-offscreen">￥1,000</span></div>'
        sync.sync_offer_prices(data, settings, lambda u: page, lambda s: None, now=1e9 + 60)
        self.assertEqual(data["offer_prices"]["https://www.amazon.co.jp/dp/A"]["price"], 1000.0)
        data["offer_prices"]["https://www.amazon.co.jp/dp/A"]["price"] = 1.0
        sync.sync_offer_prices(data, settings, lambda u: page, lambda s: None, now=1e9 + 120)
        self.assertEqual(data["offer_prices"]["https://www.amazon.co.jp/dp/A"]["price"], 1.0)   # nur einmal

    def test_offer_prices_sync(self):
        settings = {"nso_extra": [{"key": "m12", "code": "JP", "price": 2970, "src": "Amazon", "url": "https://www.amazon.co.jp/dp/A"},
                                  {"key": "m3", "code": "JP", "price": 990, "src": "Amazon", "url": "https://www.amazon.co.jp/dp/B"},
                                  {"key": "ep", "code": "JP", "price": 5841, "src": "Amazon"}]}
        pages = {"https://www.amazon.co.jp/dp/A": '<div id="corePrice_feature_div"><span class="a-price-whole">2,880</span></div>',
                 "https://www.amazon.co.jp/dp/B": '<form action="/errors/validateCaptcha"></form>'}
        calls = []

        def fetch(url):
            calls.append(url)
            return pages[url]
        data = {"offer_prices": {"https://alt/weg": {"price": 1}}}
        sync.sync_offer_prices(data, settings, fetch, lambda s: None, now=1e9)
        self.assertEqual(data["offer_prices"]["https://www.amazon.co.jp/dp/A"]["price"], 2880.0)
        self.assertEqual(data["offer_prices"]["https://www.amazon.co.jp/dp/B"]["error"], "Prüfseite (Captcha)")
        self.assertNotIn("https://alt/weg", data["offer_prices"])
        self.assertIn("Prüfseite", sync.status["log"][-1])
        sync.sync_offer_prices(data, settings, fetch, lambda s: None, now=1e9 + 3600)     # höchstens einmal am Tag
        self.assertEqual(len(calls), 2)
        self.assertIn("alle 2 Links aktuell", sync.status["log"][-1])


class FetchRulesTest(unittest.TestCase):
    def test_deku_block_stops_all_later_deku_steps(self):
        # 0.56.1: Nach einer Sperre fragt in diesem Abgleich kein Schritt DekuDeals mehr an
        calls = []

        def fake(url, ua=None):
            calls.append(url)
            raise sources.FetchError(url, 429)
        sources.deku_blocked = 0
        try:
            with self.assertRaises(sources.FetchError):
                sources.fetch_item("a", "de", fetch=fake)
            with self.assertRaises(sources.FetchError) as cm:
                sources.fetch_item("b", "de", fetch=fake)
            self.assertEqual(cm.exception.status, 429)
            self.assertEqual(len(calls), 1)
        finally:
            sources.deku_blocked = None
        sources.item_cache = None
        with self.assertRaises(sources.FetchError):     # außerhalb eines Abgleichs: jede Anfrage geht raus
            sources.fetch_item("c", "de", fetch=fake)
        self.assertEqual(len(calls), 2)

    def test_americas_pages_without_languages_are_reported_not_counted(self):
        # 0.66: Nennt keine gelesene Seite Amerikas Sprachen, hat sich eher die Seite geändert
        settings = store.load_settings()
        for code in settings["countries"]:
            settings["countries"][code]["enabled"] = code in ("DE", "US")
        data = {"items": {f"t{i}": {"title": f"T{i}", "active": True, "ids": {"AM": [str(i)]},
                                    "langs_tries": {"AM": 2}, "langs_checked": {"AM": 5}}
                          for i in range(4)}, "prices": {}}
        t0 = 1736467200
        with mock.patch.object(sources, "fetch_langs_am", lambda n, fetch=None: None):
            sync.sync_langs(data, settings, None, lambda s: None, now=t0)
        self.assertIn("keine nannte Sprachen", sync.status["log"][-1])
        for it in data["items"].values():
            self.assertEqual((it["langs_tries"], it["langs_checked"], it.get("ids_suspect", {})),
                             ({"AM": 2}, {"AM": 5}, {}))
        # Nennt eine Seite Sprachen, zählen die übrigen wie bisher als Versuch
        answers = {"0": "english, german"}
        with mock.patch.object(sources, "fetch_langs_am", lambda n, fetch=None: answers.get(n)):
            sync.sync_langs(data, settings, None, lambda s: None, now=t0 + 10)
        self.assertIn("Sprachen Amerika: 1 von 4 Titeln", sync.status["log"][-1])
        self.assertEqual(data["items"]["t1"]["langs_tries"], {"AM": 3})

    def test_file_stamp(self):
        self.assertEqual(sources.file_stamp({"status": 200, "etag": '"abc"'}), '"abc"')
        self.assertEqual(sources.file_stamp({"status": 200, "modified": "M", "size": "9"}), "M|9")
        self.assertIsNone(sources.file_stamp({"status": 0, "error": "x"}))
        self.assertIsNone(sources.file_stamp({"status": 200, "size": "9"}))

    def test_wishlist_errors_never_shorten_or_stop(self):
        # 0.64: Eine Folgeseite mit Serverfehler oder Sperre heißt „nicht lesbar“, nicht „Ende der Liste“
        page1 = '<a href="/items/a-game">A</a><a href="/items/b-game">B</a>'

        def fake(status):
            def f(url, ua=None):
                if url.endswith("page=1"):
                    return page1
                raise sources.FetchError(url, status)
            return f
        self.assertEqual(sources.fetch_wishlist("https://www.dekudeals.com/wishlist/abc123xyz", fetch=fake(404)), ["a-game", "b-game"])
        for status in (500, 429, 0):
            with self.assertRaises(sources.FetchError):
                sources.fetch_wishlist("https://www.dekudeals.com/wishlist/abc123xyz", fetch=fake(status))
        # Ist die Wishlist nicht lesbar, gilt die zuletzt gelesene; der Abgleich läuft weiter
        data = {"items": {"a-game": {"title": "A", "active": True, "ids": {}}}}
        settings = {"wishlist_url": "https://www.dekudeals.com/wishlist/abc123xyz"}
        blocked = lambda url, ua=None: (_ for _ in ()).throw(sources.FetchError(url, 403))
        self.assertIsNone(sync.sync_wishlist(data, settings, blocked, lambda s: None))
        self.assertTrue(data["items"]["a-game"]["active"])
        self.assertIn("zuletzt gelesene", sync.status["log"][-1])
        with self.assertRaises(RuntimeError):            # ohne bekannte Liste geht es nicht
            sync.sync_wishlist({"items": {}}, settings, blocked, lambda s: None)
        # Notbetrieb (0.84): Die Oberfläche sagt, dass mit der alten Liste gerechnet wird
        self.assertEqual(data["wishlist_err"], "HTTP 403")
        self.assertEqual(sync.fallback_state(data)["error"], "HTTP 403")
        ok = lambda url, ua=None: page1 if url.endswith("page=1") else (_ for _ in ()).throw(sources.FetchError(url, 404))
        sync.sync_wishlist(data, settings, ok, lambda s: None)
        self.assertNotIn("wishlist_err", data)
        now = datetime.fromisoformat(data["wishlist_at"]).timestamp()
        self.assertIsNone(sync.fallback_state(data, now=now + 86400))
        self.assertIsNotNone(sync.fallback_state(data, now=now + 4 * 86400))       # zu lange nicht gelesen
        data["deku_wait"] = now + 3600
        self.assertTrue(sync.fallback_state(data, now=now)["until"])

    def test_missing_low_section_keeps_known_low(self):
        settings = store.load_settings()
        data = {"items": {"a": {"active": True}}, "prices": {"DE": {"a": {"status": "onsale", "regular": 44.99}}},
                "lows": {"DE": {"a": {"low": 19.99, "src": "deku", "checked": 0, "lv": sync.LOW_PAGE_V, "hist_v": sync.HIST_V}}}}
        orig = sources.fetch_item
        sources.fetch_item = lambda slug, country, fetch=None: {"low": None, "lows": [], "history": [], "low_found": False}
        try:
            data["lows"]["DE"]["a"].pop("low")             # fällig machen, Wert aber im Verlauf bekannt
            data["lows"]["DE"]["a"]["hist"] = [["2026-01", 19.99]]
            sync.sync_lows(data, settings, fetch=None, sleep=lambda s: None, now=1736467200)
            self.assertEqual(data["lows"]["DE"]["a"]["hist"], [["2026-01", 19.99]])
            self.assertIn("Warnung", sync.status["log"][-1])
        finally:
            sources.fetch_item = orig

    def test_amazon_503_stops_offer_step(self):
        settings = {"own_offers": [{"slug": "a", "code": "JP", "price": 100, "src": "Amazon", "url": f"https://www.amazon.co.jp/dp/{i}"}
                                   for i in range(3)]}
        calls = []

        def fetch(url):
            calls.append(url)
            raise sources.FetchError(url, 503)
        data = {}
        sync.sync_offer_prices(data, settings, fetch, lambda s: None, now=1e9)
        self.assertEqual(len(calls), 1)
        self.assertIn("HTTP 503", sync.status["log"][-1])

    def test_constants_in_docs_exist(self):
        # docs/abrufe.md nennt Konstanten in `…`: Jede muss es im Code geben (Inventur, Abschnitt 2)
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "abrufe.md")
        with open(path, encoding="utf-8") as f:
            names = set(re.findall(r"`([A-Z][A-Z0-9_]{3,})`", f.read()))
        self.assertGreater(len(names), 10)
        missing = [n for n in names if not hasattr(sync, n) and not hasattr(sources, n)]
        self.assertEqual(missing, [])


def ui_sample():
    """Beispieldaten für die Oberflächentests: sample() mit langen Titeln, Angeboten in mehreren
    Ländern und einer Sammlung mit fehlenden DLC, damit jede Ansicht etwas zeigt."""
    data, settings = sample()
    sale = {"start": "2026-10-01T00:00:00Z", "end": "2026-10-20T00:00:00Z"}
    for i in range(6):
        slug = f"long-{i}"
        data["items"][slug] = {"title": f"Ein ausgesprochen langer Spieltitel Nummer {i}: Die vollständige Sammleredition",
                               "parent": None, "active": True, "order": 10 + i, "ids": {"EU": ["1"]}, "ids_checked": {}}
        data["prices"]["DE"][slug] = {"status": "onsale", "currency": "EUR", "regular": 29.99 + i}
        data["prices"]["BR"][slug] = {"status": "onsale", "currency": "BRL", "regular": 99.0 + i, "discount": 19.8 + i, **sale}
        data["prices"]["NO"][slug] = {"status": "onsale", "currency": "NOK", "regular": 299.0, "discount": 99.0 + 3 * i, **sale}
    data["owned"] = ["vampire-survivors"]
    data["rel"] = {"vampire-survivors": {"checked": NOW.timestamp(), "v": 1, "title": "Vampire Survivors", "parent": None,
                                         "dlc": [["vs-foscari", "Tides of the Foscari"], ["vs-emergency-meeting", "Emergency Meeting"]],
                                         "in": [], "has": [], "iv": 1, "eu": "70010000000001",
                                         "info": {"genre": ["Action", "Role-Playing"], "players": {"offline": [1, 4], "online": [1, 4]},
                                                  "modes": ["tv", "tabletop", "handheld"], "mc": 86, "oc": 88,
                                                  "hltb": {"main": 16, "coop": 20}, "released": "2022-12-17",
                                                  "developer": "Studio X", "publisher": "Studio X", "age": "USK 12", "size_gb": 0.9},
                                         "nin": {"genre": ["Action"], "players": [1, 4], "modes": ["tv", "handheld"], "online": False,
                                                 "released": "2022-12-17", "publisher": "Studio X Ltd", "at": NOW.timestamp()}}}
    data["last_sync"] = NOW.isoformat()
    return data, settings


def ui_source():
    """Die ganze Oberfläche als ein Text (seit 0.86 index.html, style.css und js/*.js in der
    Reihenfolge, in der index.html sie lädt)."""
    static = os.path.join(os.path.dirname(__file__), "..", "app", "static")
    with open(os.path.join(static, "index.html"), encoding="utf-8") as f:
        page = f.read()
    parts = [page]
    for ref in re.findall(r'<(?:link rel="stylesheet" href|script src)="([^"]+)"', page):
        with open(os.path.join(static, ref), encoding="utf-8") as f:
            parts.append(f.read())
    return "\n".join(parts)


class UiContractTest(unittest.TestCase):
    """Oberflächentests ohne Zusatzpakete (0.67): Was die Oberfläche liest, liefert der Server, und
    bei Handybreite scrollt keine Ansicht seitlich. Die Oberfläche selbst ist reines JavaScript;
    diese Tests fangen umbenannte Felder und Überlauf, bevor sie jemand am Handy bemerkt."""
    PAGE = os.path.join(os.path.dirname(__file__), "..", "app", "static", "index.html")

    # Felder, die die Oberfläche je Struktur liest. Benennt der Server eines um oder lässt es weg,
    # schlägt der Test fehl; liest die Oberfläche ein neues Feld, gehört es hier dazu.
    CONTRACT = {
        "radar": {"at", "cashback", "champ", "de", "diff", "dlc_of", "easy", "gap", "hard", "no_ids", "nohist", "owned",
                  "parent_owned", "reason", "rhythm", "shown", "slug", "target", "title", "typical", "verdict"},
        "matrix.rows": {"best", "cells", "champ", "dlc_of", "no_ids", "owned", "parent_owned", "slug", "title", "typical"},
        "matrix.cells": {"alone", "champ", "end", "est", "eur", "gap", "grade", "lang", "local", "low", "low_eur", "start", "regular",
                         "na", "nocard", "nsuid", "own", "pct", "sale"},
        "matrix.cols": {"code", "currency", "name", "tier"},
        "kaufplan": {"bought", "bought_how", "cost", "nowhere_slugs", "count", "dropped", "good_left", "held", "later", "lock", "packed",
                     "s2_skip", "saving", "fill_idle", "skipped", "small", "small_groups", "steps", "assumed"},
        "plan": {"alt_codes", "alt_total", "cards", "code", "cost", "currency", "current", "direct", "direct_n",
                 "estimated", "family", "fill", "fill_nso", "fill_pairs", "fill_zero", "fillers", "gain", "games_cost", "games_paid", "grade", "home", "items",
                 "missing", "name", "opt_gap", "opt_pct", "optimum", "pay", "price_at", "price_stale", "rate", "ref_total", "rest", "rest_eur",
                 "saving", "threshold", "tier", "total", "trims", "warnings", "worth"},
        "plan.items": {"alt", "alt_code", "champ", "dlc_of", "end", "est", "eur", "lang", "local", "needs_parent",
                       "over", "own", "owned", "parent_owned", "pct", "ref", "sale", "short", "slug", "title"},
        "plan.others": {"code", "current", "diff", "estimated", "games_cost", "is_ref", "missing", "name", "tier"},
        "collection": {"free", "games", "missing_eur", "missing_priced", "owned", "pass_hints", "plain", "waiting"},
        "collection.games": {"dlc", "have", "missing", "missing_eur", "missing_priced", "slug", "title"},
        "spiele": {"dlc_entries", "entries", "games", "genres", "via_packs"},
        "spiele.games": {"bought", "coop", "developer", "genre", "hltb", "hours", "max", "mc", "mcu", "modes", "nin", "oc", "players",
                         "pub_alt", "pub_ok", "publisher", "read", "released", "s2", "score", "size_gb", "slug", "title", "via",
                         "year", "year_alt", "year_ok", "age"},
        "nso": {"days_left", "due", "ids_known", "mine", "rows", "suggest", "until", "variants"},
        "pay": {"card", "currency", "factor", "fee", "rate", "tax", "unit", "via"},
        "eshop": {"amount", "coll", "coll_game", "coll_name", "date", "eng", "game", "group", "how", "item", "key", "name",
                  "plat", "slug", "suggest", "title"},
    }

    @classmethod
    def setUpClass(cls):
        from app import server
        cls.server = server
        cls.data, cls.settings = ui_sample()
        store.save_data(cls.data)
        store.save_settings(cls.settings)
        cls.page = ui_source()

    def test_state_fields_exist(self):
        state = self.server.state()
        for name in sorted(set(re.findall(r"S\.state\.([A-Za-z_]\w*)", self.page))):
            self.assertIn(name, state, f"Die Oberfläche liest S.state.{name}, der Server liefert es nicht")

    def test_api_paths_exist(self):
        with open(os.path.join(os.path.dirname(self.PAGE), "..", "server.py"), encoding="utf-8") as f:
            routes = set(re.findall(r'"(/api/[a-z_/]+)"', f.read()))
        used = set(re.findall(r'(?:api\(|href=)["`](/api/[a-z_/]+)', self.page))
        self.assertTrue(used)
        self.assertEqual(used - routes, set())

    def test_ui_files_served(self):
        # 0.86: Was index.html lädt, liefert der Server mit passendem Typ; andere Pfade nicht
        import http.client
        import threading
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), self.server.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        def get(path):
            c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=10)
            c.request("GET", path)
            r = c.getresponse()
            out = (r.status, r.getheader("Content-Type"), r.read())
            c.close()
            return out
        try:
            refs = re.findall(r'<(?:link rel="stylesheet" href|script src)="([^"]+)"', get("/")[2].decode())
            self.assertEqual(len(refs), 1 + len(os.listdir(os.path.join(os.path.dirname(self.PAGE), "js"))))
            for ref in refs:
                status, ctype, body = get("/" + ref)
                self.assertEqual(status, 200, ref)
                self.assertTrue(ctype.startswith("text/css" if ref.endswith(".css") else "text/javascript"), ctype)
                self.assertTrue(body)
            for bad in ("/js/../server.py", "/js/fehlt.js", "/js/%2e%2e/server.py", "/server.py", "/js/"):
                self.assertEqual(get(bad)[0], 404, bad)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_structure_contract(self):
        state = self.server.state()
        kauf = planner.purchase_plan(store.load_data(), store.load_settings(), {}, include_good=True, bought=[], fill={})
        plans = planner.plans(store.load_data(), store.load_settings(), now=NOW)
        keys = lambda rows: set().union(*[set(r) for r in rows if isinstance(r, dict)])
        steps = kauf["steps"] + plans
        got = {
            "radar": keys(state["radar"]),
            "matrix.rows": keys(state["matrix"]["rows"]),
            "matrix.cells": keys([c for r in state["matrix"]["rows"] for c in r["cells"].values()]),
            "matrix.cols": keys(state["matrix"]["cols"]),
            "kaufplan": set(kauf),
            "plan": keys(steps),
            "plan.items": keys([i for p in steps for i in p["items"]]),
            "plan.others": keys([o for p in kauf["steps"] for o in p["others"]]),
            "collection": set(state["collection"]),
            "collection.games": keys(state["collection"]["games"]),
            "spiele": set(state["spiele"]),
            "spiele.games": keys(state["spiele"]["games"]) | {"bought", "mcu"},
            "nso": set(state["nso"]),
            "pay": keys(state["pay"].values()),
            "eshop": keys(planner.eshop_matches(dict(store.load_data(), _eshop={"picks": {}, "entries": [
                {"key": "k1", "title": "Tides of the Foscari", "date": "2026-10-01", "item": "DLC"}]}))["rows"]),
        }
        used = set(re.findall(r"\.([a-z_][a-z0-9_]*)\b", self.page))
        for name, fields in self.CONTRACT.items():
            self.assertEqual(fields - got[name], set(), f"{name}: fehlt in der Antwort des Servers")
            self.assertEqual(fields - used, set(), f"{name}: liest die Oberfläche nicht mehr, aus dem Vertrag nehmen")

    def test_phone_width_without_overflow_or_errors(self):
        # Braucht ein Chromium (in GitHub Actions vorhanden); ohne wird der Test übersprungen
        import glob
        import re as re_
        import shutil
        import subprocess
        import threading
        from http.server import ThreadingHTTPServer
        browser = os.environ.get("CHROME_BIN") or next((shutil.which(n) for n in (
            "chromium", "chromium-browser", "google-chrome", "google-chrome-stable") if shutil.which(n)), None) \
            or next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        if not browser:
            # In GitHub Actions (CI=true) zählt ein fehlender Browser als Fehler, sonst wäre der
            # Lauf grün, ohne dass die Oberfläche geprüft wurde (0.82)
            if os.environ.get("CI"):
                self.fail("kein Chromium gefunden, Oberflächentest in CI nicht übersprungen")
            self.skipTest("kein Chromium gefunden")
        with open(os.path.join(os.path.dirname(__file__), "ui_selbsttest.html"), encoding="utf-8") as f:
            probe_page = f.read().encode()
        base = self.server.Handler

        class Handler(base):
            def do_GET(self):
                if self.path == "/selbsttest":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(probe_page)))
                    self.end_headers()
                    self.wfile.write(probe_page)
                    return
                return base.do_GET(self)

            def log_message(self, *a):
                pass
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            out = subprocess.run([browser, "--headless", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=30000",
                                  "--window-size=800,900", "--dump-dom", f"http://127.0.0.1:{srv.server_port}/selbsttest"],
                                 capture_output=True, text=True, timeout=120)
        finally:
            srv.shutdown()
            srv.server_close()
        m = re_.search(r'<pre id="out">(.*?)</pre>', out.stdout, re_.S)
        self.assertTrue(m, "Selbsttest lieferte kein Ergebnis: " + out.stderr[-300:])
        res = json.loads(html.unescape(m.group(1)) or "null")
        self.assertTrue(res, out.stdout[-500:])
        self.assertEqual(res["errors"], [])
        probe = res["tabs"].pop("probe")
        self.assertTrue(probe["wide"], "Der Prüfer erkennt einen zu breiten Kasten nicht")
        self.assertGreaterEqual(len(res["tabs"]), 8)
        for name, t in res["tabs"].items():
            self.assertLessEqual(t["width"], t["view"], f"{name} scrollt seitlich: {t['wide']}")
            self.assertEqual(t["wide"], [], name)
            self.assertEqual(t.get("unnamed", []), [], f"{name}: Knopf ohne Namen")
            self.assertGreater(t["chars"], 200, f"{name} zeigt fast nichts")


class UiThemeTest(unittest.TestCase):
    """Hell, dunkel, System (0.55): Die dunklen Farben stehen zweimal in style.css, für
    „wie das Gerät“ und für die Wahl „Dunkel“. Beide Blöcke müssen gleich bleiben."""
    def test_dark_tokens_match(self):
        import re
        page = ui_source()
        auto = re.search(r"@media \(prefers-color-scheme: dark\)\{:root:not\(\[data-theme=light\]\)\{([^}]*)\}\}", page)
        chosen = re.search(r":root\[data-theme=dark\]\{color-scheme:dark;([^}]*)\}", page)
        self.assertTrue(auto and chosen)
        tokens = lambda css: dict(re.findall(r"(--[\w-]+):\s*([^;]+);", css))
        self.assertGreater(len(tokens(auto.group(1))), 10)
        self.assertEqual(tokens(auto.group(1)), tokens(chosen.group(1)))
        self.assertIn('localStorage.getItem("ek.theme")', page)   # vor dem ersten Zeichnen



class ZeroTest(unittest.TestCase):
    """Auf Null (1.1.0): wo ein Rest stört, der günstigste Weg auf genau 0 und einer auf fast 0."""
    def setUp(self):
        self.data, self.settings = sample()
        self.settings["deal_eur"]["mini"] = 2.0
        self.settings["current_country"] = "DE"
        for code, c in self.settings["countries"].items():
            c["enabled"] = code in ("DE", "BR")
        items, de, br = {}, {}, {}
        for i, (slug, eur, brl) in enumerate([("big", 49.99, 47), ("m1", 1.99, 4), ("m2", 1.99, 3),
                                               ("m3", 1.99, 2.5), ("m4", 1.99, 8)]):
            items[slug] = {"title": slug.title(), "parent": None, "active": True, "order": i,
                           "ids": {"EU": ["1"]}, "ids_checked": {}}
            de[slug] = {"status": "onsale", "currency": "EUR", "regular": eur}
            br[slug] = {"status": "onsale", "currency": "BRL", "regular": brl}
        self.data.update(items=items, prices={"DE": de, "BR": br})

    def br(self, **kw):
        return next(p for p in planner.purchase_plan(self.data, self.settings, now=NOW, **kw)["steps"]
                    if p["code"] == "BR")

    def test_exact_without_extra_cards(self):
        # 50er Karte für 47 R$, 3 R$ Rest: m2 passt genau, ohne Zuzahlung
        br = self.br()
        self.assertEqual(br["rest"], 3.0)
        z = br["fill_zero"]
        self.assertEqual((z["exact"]["slugs"], z["exact"]["extra"], z["exact"]["left"]), (["m2"], 0.0, 0.0))
        self.assertIsNone(z["near"])                  # genau 0 ist nicht teurer
        # Dazugenommen bleibt nichts: Die Karten des Schritts ergeben genau den Vorschlag
        after = self.br(fill={"BR": z["exact"]["slugs"]})
        self.assertEqual(after["rest"], 0.0)
        self.assertIsNone(after["fill_zero"])

    def test_exact_with_more_cards_and_near(self):
        # Nur in Brasilien und Kleinkram (unter 3 €): Sie warten und kommen nur als Vorschlag
        self.settings["deal_eur"]["mini"] = 3.0
        for slug in ("m2", "m3"):
            del self.data["items"][slug], self.data["prices"]["BR"][slug], self.data["prices"]["DE"][slug]
        for slug in ("m1", "m4"):
            del self.data["prices"]["DE"][slug]
        self.data["prices"]["BR"]["m1"]["regular"] = 7.6
        self.data["prices"]["BR"]["m4"]["regular"] = 13
        br = self.br()
        z = br["fill_zero"]
        # 47 + 13 = 60 R$ = 4 × 15: zwei Karten mehr (12,00 € statt 9,50 €), genau 0
        self.assertEqual(z["exact"]["slugs"], ["m4"])
        self.assertEqual([(c["face"], c["count"]) for c in z["exact"]["cards"]], [(15.0, 4)])
        self.assertAlmostEqual(z["exact"]["extra"], 2.5, places=2)
        after = self.br(fill={"BR": z["exact"]["slugs"]})
        self.assertEqual(after["rest"], 0.0)
        self.assertAlmostEqual(after["cost"] - br["cost"], z["exact"]["extra"], places=2)
        # Fast 0: 47 + 7,60 = 54,60 R$ mit 15 + 15 + 25, bleiben 0,40 R$ für 1,30 € mehr
        self.assertEqual((z["near"]["slugs"], z["near"]["left"]), (["m1"], 0.4))
        self.assertAlmostEqual(z["near"]["extra"], 1.3, places=2)
        self.settings["zero"]["near"] = 1.0
        self.assertIsNone(self.br()["fill_zero"]["near"])
        self.settings["zero"]["near"] = 10.0
        self.settings["zero"]["left"] = 0.05          # 0,40 R$ sind etwa 0,07 €
        self.assertIsNone(self.br()["fill_zero"]["near"])

    def test_near_without_extra_is_left_to_rest_row(self):
        # Fast 0 ohne Zuzahlung (m3 lässt 0,50 R$) zeigt schon „Passt in den Rest“
        del self.data["prices"]["BR"]["m2"]
        z = self.br()["fill_zero"]
        self.assertEqual(z["exact"]["slugs"], ["m4"])            # 55 R$ = 15 + 15 + 25
        self.assertIsNone(z["near"])

    def test_no_way_and_not_where_rest_stays(self):
        for s in ("m1", "m2", "m3", "m4"):
            self.data["prices"]["BR"][s]["regular"] = 3.33
        self.settings["zero"]["left"] = 0.1           # bestenfalls 1,34 R$ (0,24 €) übrig
        z = self.br()["fill_zero"]
        self.assertEqual(z, {"exact": None, "near": None})   # die Oberfläche sagt: kein Weg
        # Mittlere Stufe, letzter Schritt: Der Rest bleibt als Guthaben, keine Zeile
        self.settings["countries"]["BR"]["tier"] = 2
        self.assertIsNone(self.br()["fill_zero"])


class ShortTitleTest(unittest.TestCase):
    def test_apostrophes_match(self):
        # 1.1.5: Spiel mit typografischem, DLC mit geradem Apostroph wird trotzdem gekürzt
        ctx = planner.Context.__new__(planner.Context)
        ctx.title = {"dlc": "Game's Tale 3: Party Pack"}.get
        ctx.parent_title = lambda s: "Game’s Tale 3" if s == "dlc" else None
        self.assertEqual(planner.Context.short(ctx, "dlc"), "Party Pack")
        ctx.title = {"dlc": "Game’s Tale 3: Party Pack"}.get
        self.assertEqual(planner.Context.short(ctx, "dlc"), "Party Pack")


class RestPairsTest(unittest.TestCase):
    def test_pairs_fill_rest_better(self):
        # 0.70: zwei Titel zusammen, wenn sie weniger übrig lassen als jeder einzelne
        fill = [{"slug": "a", "short": "A", "title": "A", "local": 6.0, "left": 4.0},
                {"slug": "b", "short": "B", "title": "B", "local": 3.5, "left": 6.5},
                {"slug": "c", "short": "C", "title": "C", "local": 4.0, "left": 6.0},
                {"slug": "x", "short": "X", "title": "X", "local": 1.0, "left": 9.0, "extra": True}]
        pairs = planner._rest_pairs(fill, 10.0)
        self.assertEqual([(f["slugs"], f["left"]) for f in pairs], [(["a", "c"], 0.0), (["a", "b"], 0.5), (["b", "c"], 2.5)])

if __name__ == "__main__":
    unittest.main()
