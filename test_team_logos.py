"""
Team logos: read from ESPN, downloaded, retried, and drawn.

1.3.3 drew a placeholder for every team without a bundled flag:

  * ESPN's cricket feeds give a team's logo as "logo"; only "logos" was read,
    so no team had a logo URL and nothing was ever downloaded.
  * A failed download saved a placeholder under the logo's own name, which the
    "already have it" check then took for the logo: never fetched again.
  * The renderer cached "no crest", so a logo downloaded after a team's first
    frame was not drawn until a restart.
  * National teams never downloaded a logo, so a side without one of the
    thirteen bundled flags only ever had a placeholder.

Run:  python -m unittest test_team_logos  (needs Pillow + requests)
"""

import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import cricket_logo_downloader  # noqa: E402
import cricket_renderer  # noqa: E402
from cricket_data_fetcher import CricketDataFetcher  # noqa: E402
from cricket_logo_downloader import create_placeholder_logo, is_placeholder_logo  # noqa: E402
from test_cricket_plugin import (_load_harness_config, _load_mock_matches,  # noqa: E402
                                 _MockCacheManager, _MockDisplayManager)

QLD_URL = "https://a.espncdn.com/i/teamlogos/cricket/500/459.png"


def _png(colour=(128, 0, 32, 255), size=(500, 500)):
    buf = io.BytesIO()
    Image.new("RGBA", size, colour).save(buf, "PNG")
    return buf.getvalue()


class _Response:
    def __init__(self, body, status=200, content_type="image/png"):
        self.body, self.status_code = body, status
        self.headers = {"content-type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i:i + chunk_size]


class _Session:
    def __init__(self):
        self.calls, self.reply = [], (lambda url: _Response(_png()))

    def get(self, url, **kwargs):
        self.calls.append(url)
        return self.reply(url)


def _team(abbr="QLD", name="Queensland", url=QLD_URL):
    return {"abbr": abbr, "name": name, "id": "459", "logo_url": url}


class TestLogoUrl(unittest.TestCase):
    def test_reads_espns_logo_field(self):
        fetcher = object.__new__(CricketDataFetcher)
        team = fetcher._parse_competitor({"team": {
            "id": "459", "abbreviation": "QLD", "displayName": "Queensland",
            "logo": QLD_URL}})
        self.assertEqual(team["logo_url"], QLD_URL)

    def test_falls_back_to_logos_then_none(self):
        fetcher = object.__new__(CricketDataFetcher)
        listed = fetcher._parse_competitor({"team": {"logos": [{"href": QLD_URL}]}})
        self.assertEqual(listed["logo_url"], QLD_URL)
        self.assertIsNone(fetcher._parse_competitor({"team": {}})["logo_url"])


class _Sandbox(unittest.TestCase):
    """The plugin with its assets in a temp dir and a fake download session."""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "assets").mkdir()
        shutil.copytree(_HERE / "assets" / "flags", tmp / "assets" / "flags")
        self.logos = tmp / "assets" / "logos"
        self.logos.mkdir()
        for patcher in (mock.patch.object(cricket_renderer, "_PLUGIN_DIR", tmp),
                        mock.patch.object(cricket_logo_downloader._downloader, "session",
                                          _Session())):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.session = cricket_logo_downloader._downloader.session


class TestDownload(_Sandbox):
    def test_saves_a_decodable_png(self):
        path = self.logos / "QLD.png"
        self.assertTrue(cricket_logo_downloader.download_missing_logo(
            "cricket", "459", "QLD", path, QLD_URL))
        with Image.open(path) as img:
            self.assertEqual((img.format, img.mode, img.size), ("PNG", "RGBA", (500, 500)))
        self.assertEqual(list(self.logos.iterdir()), [path], "no temp file left behind")

    def test_a_failure_writes_nothing(self):
        path = self.logos / "QLD.png"
        for reply in (lambda u: _Response(b"<html>not found</html>", 200, "text/html"),
                      lambda u: _Response(b"", 404),
                      lambda u: _Response(b"not really a png", 200, "image/png")):
            self.session.reply = reply
            self.assertFalse(cricket_logo_downloader.download_missing_logo(
                "cricket", "459", "QLD", path, QLD_URL))
            self.assertEqual(list(self.logos.iterdir()), [], "no file, no placeholder")

    def test_old_placeholders_are_recognised(self):
        old = self.logos / "QLD.png"
        create_placeholder_logo("QLD", old)
        self.assertTrue(is_placeholder_logo(old))
        real = self.logos / "VIC.png"
        Image.new("RGBA", (500, 500), (0, 40, 120, 255)).save(real)
        self.assertFalse(is_placeholder_logo(real))


class TestPlugin(_Sandbox):
    def setUp(self):
        super().setUp()
        from manager import CricketPlusPlugin
        self.plugin = CricketPlusPlugin("cricket-plus", _load_harness_config(),
                                              _MockDisplayManager(), _MockCacheManager(), None)
        self.plugin.logos_dir = self.logos
        self.clock = 1_000_000.0
        patcher = mock.patch("manager.time.time", lambda: self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def match(self, *teams, key="sheffield-shield"):
        return {"competition_key": key, "teams": list(teams)}

    def test_domestic_team_logo_is_downloaded_and_drawn(self):
        team = _team()
        renderer = self.plugin.renderer
        self.assertIsNone(renderer._load_crest(team, 16), "nothing yet")
        self.plugin._ensure_logos(self.match(team))
        self.assertEqual(self.session.calls, [QLD_URL])
        crest = renderer._load_crest(team, 16)
        self.assertIsNotNone(crest, "drawn straight after the download, no restart")
        self.assertEqual(crest.size, (16, 16))

    def test_a_side_without_a_flag_or_badge_gets_its_logo(self):
        # A national side with flags off, or any team no flag matches, still
        # gets ESPN's logo rather than a placeholder.
        self.plugin.renderer.config["show_country_flags"] = False
        team = _team("NED", "Netherlands", "https://a.espncdn.com/i/teamlogos/cricket/500/15.png")
        self.plugin._ensure_logos(self.match(team, key="international"))
        self.assertTrue((self.logos / "NED.png").exists())

    def test_bundled_flags_are_not_downloaded(self):
        team = _team("AUS", "Australia", "https://a.espncdn.com/i/teamlogos/cricket/500/2.png")
        self.assertTrue(self.plugin.renderer.has_bundled_flag(team))
        self.plugin._ensure_logos(self.match(team, key="international"))
        self.assertEqual(self.session.calls, [])

    def test_an_old_placeholder_is_replaced(self):
        create_placeholder_logo("QLD", self.logos / "QLD.png")
        self.plugin._ensure_logos(self.match(_team()))
        self.assertEqual(self.session.calls, [QLD_URL])
        self.assertFalse(is_placeholder_logo(self.logos / "QLD.png"))

    def test_a_failed_download_is_retried_later_not_every_update(self):
        self.session.reply = lambda u: _Response(b"", 503)
        team = _team()
        self.plugin._ensure_logos(self.match(team))
        self.plugin._ensure_logos(self.match(team))
        self.assertEqual(len(self.session.calls), 1, "backs off")
        self.session.reply = lambda u: _Response(_png())
        self.clock += 31 * 60
        self.plugin._ensure_logos(self.match(team))
        self.assertEqual(len(self.session.calls), 2)
        self.assertTrue((self.logos / "QLD.png").exists())

    def test_an_existing_logo_is_not_fetched_again(self):
        Image.new("RGBA", (500, 500), (128, 0, 32, 255)).save(self.logos / "QLD.png")
        self.plugin._ensure_logos(self.match(_team()))
        self.assertEqual(self.session.calls, [])

    def test_national_side_uses_its_flag_not_espns_logo(self):
        team = {"abbr": "AUS-A", "name": "Australia A", "location": "Australia",
                "is_national": False, "id": "49",
                "logo_url": "https://a.espncdn.com/i/teamlogos/cricket/500/49.png"}
        self.plugin._ensure_logos(self.match(team, key="international"))
        self.assertEqual(self.session.calls, [])

    def test_harness_matches_still_render(self):
        for m in _load_mock_matches():
            self.plugin._ensure_logos(m)


class TestCountryFlags(_Sandbox):
    """National sides get their country's flag, matched by ESPN's location."""

    def code(self, name, location="", national=False):
        import cricket_country_flags
        return cricket_country_flags.flag_code(
            {"name": name, "location": location, "is_national": national})

    def test_national_sides(self):
        cases = [
            ("Australia", "Australia", True, "au"),
            ("Australia A", "Australia", False, "au"),
            ("Australia Women", "Australia", False, "au"),
            ("Australia Under-19s", "Australia", False, "au"),
            ("Australia Women Under-19s", "Australia", False, "au"),
            ("England", "England", True, "gb-eng"),
            ("England Lions", "England", False, "gb-eng"),
            ("Scotland", "Scotland", True, "gb-sct"),
            ("Ireland", "Ireland", True, "ie"),
            ("Oman", "Oman", True, "om"),
            ("United Arab Emirates", "United Arab Emirates", True, "ae"),
            ("Hong Kong", "Hong Kong", True, "hk"),
            ("Myanmar", "Myanmar", True, "mm"),
            ("USA", "United States of America", True, "us"),
            ("Papua New Guinea", "Papua New Guinea", True, "pg"),
            ("Netherlands", "", False, "nl"),            # no location: the name is a country
            ("India A", "", False, "in"),
        ]
        for name, location, national, expected in cases:
            self.assertEqual(self.code(name, location, national), expected, name)

    def test_franchise_and_domestic_teams_keep_their_logos(self):
        for name, location in (("Queensland", "Queensland"), ("Brisbane Heat", "Brisbane"),
                               ("Barbados Royals", "Barbados"), ("Mumbai Indians", "Mumbai"),
                               ("Western Australia", "Western Australia"),
                               ("South Australia", "South Australia"),
                               ("West Indies", "West Indies")):
            self.assertIsNone(self.code(name, location), name)

    def test_every_listed_flag_is_bundled(self):
        import json
        import cricket_country_flags
        codes = set(json.loads((cricket_country_flags.FLAGS_DIR / "countries.json")
                               .read_text(encoding="utf-8"))["countries"].values())
        for code in codes:
            path = cricket_country_flags.FLAGS_DIR / f"{code}.png"
            with Image.open(path) as img:
                self.assertEqual(img.size, (48, 48), code)

    def test_renderer_draws_the_flag_and_the_setting_turns_it_off(self):
        from cricket_renderer import CricketRenderer
        aus_a = {"abbr": "AUS-A", "name": "Australia A", "location": "Australia",
                 "is_national": False}
        aus = {"abbr": "AUS", "name": "Australia", "location": "Australia", "is_national": True}
        on = CricketRenderer(192, 32, {})
        flag = on._load_crest(aus_a, 16)
        self.assertIsNotNone(flag, "Australia A has no badge of its own, but gets the flag")
        # The Australian flag is mostly blue; the old AUS badge is gold.
        r, g, b, _ = flag.convert("RGBA").resize((1, 1), Image.BOX).getpixel((0, 0))
        self.assertGreater(b, r)
        self.assertTrue(on.has_bundled_flag(aus_a))
        off = CricketRenderer(192, 32, {"show_country_flags": False})
        self.assertIsNone(off._load_crest(aus_a, 16))
        badge = off._load_crest(aus, 16)
        r, g, b, _ = badge.convert("RGBA").resize((1, 1), Image.BOX).getpixel((0, 0))
        self.assertGreater(r, b, "the old gold AUS badge")

    def test_parser_reads_country_and_national_flag(self):
        fetcher = object.__new__(CricketDataFetcher)
        team = fetcher._parse_competitor({"team": {
            "id": "49", "abbreviation": "AUS-A", "displayName": "Australia A",
            "location": "Australia", "isNational": False}})
        self.assertEqual((team["location"], team["is_national"]), ("Australia", False))
        national = fetcher._parse_competitor({"team": {"location": "Oman", "isNational": "true"}})
        self.assertTrue(national["is_national"])


class TestInlineCrests(_Sandbox):
    """crest_layout "inline": a small crest right before each team's code."""

    def matches(self):
        import copy
        ms = {m["id"]: copy.deepcopy(m) for m in _load_mock_matches()}
        for m, sides in ((ms["recent-t20"], (("IND-A", "India A", "India"), ("AUS-A", "Australia A", "Australia"))),
                         (ms["live-test"], (("SA", "South Africa", "South Africa"), ("AUS", "Australia", "Australia"))),
                         (ms["upcoming-t20i"], (("OMA", "Oman", "Oman"), ("CAN", "Canada", "Canada")))):
            for team, (abbr, name, location) in zip(m["teams"], sides):
                team.update(abbr=abbr, name=name, short_name=abbr, location=location)
        return ms

    @staticmethod
    def lit_columns(img, rows):
        """Columns with any lit pixel inside ``rows``."""
        rgb = img.convert("RGB")
        return [x for x in range(rgb.width)
                if any(rgb.getpixel((x, y)) != (0, 0, 0) for y in rows)]

    def test_crests_sit_next_to_the_scores_not_in_the_corners(self):
        from cricket_renderer import CricketRenderer
        ms = self.matches()
        for layout, render in (("recent", "render_recent"), ("test", "render_live_test")):
            match = ms["recent-t20"] if layout == "recent" else ms["live-test"]
            inline = getattr(CricketRenderer(192, 32, {}), render)(match)
            edges = getattr(CricketRenderer(192, 32, {"crest_layout": "edges"}), render)(match)
            # The edge layout lights the corners; inline keeps them dark and
            # draws everything on the score lines inside the middle.
            corner = range(0, 6)
            self.assertTrue(self.lit_columns(edges.crop((0, 0, 16, 16)), corner), layout)
            self.assertFalse(self.lit_columns(inline.crop((0, 0, 16, 16)), corner), layout)
            score_rows = range(8, 22)
            cols = self.lit_columns(inline, score_rows)
            self.assertGreater(min(cols), 40, layout)
            self.assertLess(max(cols), 152, layout)

    def test_the_crest_is_drawn_before_the_code(self):
        from cricket_renderer import CricketRenderer
        r = CricketRenderer(192, 32, {})
        img = r.render_recent(self.matches()["recent-t20"]).convert("RGB")
        first = min(self.lit_columns(img, range(8, 14)))
        # Leftmost lit pixel of the first score line is the Australian flag (blue).
        column = [img.getpixel((first + 2, y)) for y in range(7, 15)]
        self.assertTrue(any(b > r_ and b > 60 for r_, g, b in column))

    def test_upcoming_puts_a_crest_either_side_of_the_matchup(self):
        from cricket_renderer import CricketRenderer
        img = CricketRenderer(192, 32, {}).render_upcoming(self.matches()["upcoming-t20i"])
        cols = self.lit_columns(img, range(8, 18))
        self.assertGreater(min(cols), 30)
        self.assertLess(max(cols), 162)
        self.assertGreater(max(cols) - min(cols), 60, "both crests drawn")

    def test_a_line_too_wide_for_the_panel_falls_back_to_the_corners(self):
        from cricket_renderer import CricketRenderer
        img = CricketRenderer(64, 32, {}).render_upcoming(self.matches()["upcoming-t20i"])
        self.assertTrue(self.lit_columns(img.crop((0, 8, 4, 22)), range(0, 14)))

    def test_a_side_with_a_five_letter_code_is_not_cut(self):
        from cricket_renderer import CricketRenderer
        self.assertEqual(CricketRenderer._abbr({"abbr": "AUS-A"}), "AUS-A")
        self.assertEqual(CricketRenderer._abbr({"abbr": "IND-W"}), "IND-W")
        self.assertEqual(CricketRenderer._abbr({"abbr": "PakTV"}), "PakT")
        self.assertEqual(CricketRenderer._abbr({"abbr": "", "short_name": "RCB"}, True), "RCB")


if __name__ == "__main__":
    unittest.main(verbosity=2)
