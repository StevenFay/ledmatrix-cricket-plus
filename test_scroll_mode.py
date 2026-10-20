#!/usr/bin/env python3
"""
Scroll mode: every match of a mode scrolls across the panel as one strip.

- display_style "scroll" (the default) builds a strip of match cards
  (scroll_settings.card_width wide) and moves it right to left frame by frame;
- the strip runs once, is_cycle_complete() then says so, and the next frame
  starts a fresh strip with the latest scores;
- the slot length is one pass of the strip;
- display_style "switch" is the old one-match-at-a-time screen.

Run: LEDMATRIX_CORE=~/LEDMatrix python3 test_scroll_mode.py
"""

import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_core = os.environ.get("LEDMATRIX_CORE", "")
for _candidate in (_core, str(HERE.parents[2] / "LEDMatrix"), str(Path.home() / "LEDMatrix")):
    if _candidate and (Path(_candidate) / "src" / "common" / "scroll_helper.py").is_file():
        sys.path.insert(0, _candidate)
        break
else:
    print("SKIP: no LEDMatrix core checkout found (set LEDMATRIX_CORE)")
    sys.exit(2)

from test_cricket_plugin import (_load_harness_config, _load_mock_matches,  # noqa: E402
                                 _MockCacheManager, _MockDisplayManager)
from manager import MODE_RECENT, MODE_UPCOMING, CricketPlusPlugin  # noqa: E402


class _ScrollingDisplay(_MockDisplayManager):
    def __init__(self, w=192, h=32):
        super().__init__(w, h)
        self.width, self.height = w, h
        self.refresh_hz = 100
        self.scrolling = []

    def set_scrolling_state(self, on, frame_hold=1):
        self.scrolling.append((on, frame_hold))


def _plugin(**cfg):
    config = dict(_load_harness_config(), **cfg)
    dm = _ScrollingDisplay()
    plugin = CricketPlusPlugin("cricket-plus", config, dm, _MockCacheManager(), None)
    matches = _load_mock_matches()
    plugin.live_matches = [m for m in matches if m["state"] == "in"]
    plugin.recent_matches = [m for m in matches if m["state"] == "post"] * 3
    plugin.upcoming_matches = [m for m in matches if m["state"] == "pre"]
    return plugin, dm


class TestScroll(unittest.TestCase):
    def test_scroll_is_the_default(self):
        plugin, _ = _plugin()
        self.assertIsNotNone(plugin.scroll_helper)
        self.assertTrue(plugin.enable_scrolling, "the core runs it at the scrolling frame rate")
        self.assertTrue(plugin.supports_dynamic_duration())

    def test_the_strip_moves_and_holds_every_match(self):
        plugin, dm = _plugin()
        self.assertTrue(plugin.display(MODE_RECENT, force_clear=True))
        strip = plugin.scroll_helper.cached_image
        n = len(plugin.recent_matches)
        self.assertGreaterEqual(strip.width, n * plugin.card_width + 2 * dm.width)
        self.assertEqual(strip.height, 32)
        self.assertTrue(dm.scrolling and dm.scrolling[-1][0])
        frames = []
        for _ in range(60):
            plugin.display(MODE_RECENT)
            frames.append(dm.image.tobytes())
        self.assertGreater(len(set(frames)), 30, "a new picture as the strip moves")

    def test_one_pass_then_complete_then_a_fresh_strip(self):
        plugin, _ = _plugin()
        plugin.display(MODE_RECENT, force_clear=True)
        self.assertFalse(plugin.is_cycle_complete())
        width = plugin.scroll_helper.total_scroll_width
        for _ in range(width + 50):
            plugin.display(MODE_RECENT)
            if plugin.is_cycle_complete():
                break
        self.assertTrue(plugin.is_cycle_complete())
        # New scores arrive; the next frame rebuilds rather than replaying.
        plugin.recent_matches = plugin.recent_matches[:1]
        plugin.display(MODE_RECENT)
        self.assertFalse(plugin.is_cycle_complete())
        self.assertLess(plugin.scroll_helper.total_scroll_width, width)

    def test_changing_mode_rebuilds(self):
        plugin, _ = _plugin()
        plugin.display(MODE_RECENT, force_clear=True)
        recent_width = plugin.scroll_helper.total_scroll_width
        plugin.display(MODE_UPCOMING)
        self.assertNotEqual(plugin.scroll_helper.total_scroll_width, recent_width)

    def test_slot_is_one_pass(self):
        plugin, _ = _plugin()
        n = len(plugin.recent_matches)
        seconds = plugin.get_cycle_duration(MODE_RECENT)
        speed = plugin._scroll_settings.pixels_per_second
        expected = (2 * 192 + n * (128 + 24)) / speed
        self.assertAlmostEqual(seconds, expected + 1.0, delta=0.5)

    def test_card_width_setting(self):
        plugin, _ = _plugin(scroll_settings={"card_width": 96, "gap_between_cards": 8})
        plugin.display(MODE_UPCOMING, force_clear=True)
        self.assertEqual(plugin.card_renderer.width, 96)
        self.assertEqual(plugin.get_vegas_content()[0].width, 96)

    def test_nothing_to_show(self):
        plugin, _ = _plugin()
        plugin.upcoming_matches = []
        self.assertFalse(plugin.display(MODE_UPCOMING, force_clear=True))

    def test_switch_is_still_one_match_at_a_time(self):
        plugin, dm = _plugin(display_style="switch")
        self.assertIsNone(plugin.scroll_helper)
        self.assertFalse(plugin.enable_scrolling)
        self.assertTrue(plugin.display(MODE_RECENT, force_clear=True))
        first = dm.image.tobytes()
        plugin.display(MODE_RECENT)
        self.assertEqual(dm.image.tobytes(), first, "a still screen")
        self.assertTrue(plugin.is_cycle_complete())

    def test_preview(self):
        """Saves the recent strip to test/scroll_preview.png when PREVIEW=1."""
        if not os.environ.get("PREVIEW"):
            self.skipTest("set PREVIEW=1 to write the strip")
        plugin, _ = _plugin()
        plugin.display(MODE_RECENT, force_clear=True)
        img = plugin.scroll_helper.cached_image
        img.resize((img.width * 4, img.height * 4), 0).save(HERE / "test" / "scroll_preview.png")


if __name__ == "__main__":
    unittest.main(verbosity=2)
