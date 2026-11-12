import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kiosk"))

import launch  # noqa: E402


class WidthsTest(unittest.TestCase):
    def test_three_to_one(self):
        self.assertEqual(launch.widths_percent([3, 1]), [75, 25])

    def test_always_adds_up_to_100(self):
        for shares in ([1, 1, 1], [1, 2, 4], [1] * 7, [0.5, 1.5, 1], [5]):
            with self.subTest(shares):
                self.assertEqual(sum(launch.widths_percent(shares)), 100)
        self.assertEqual(launch.widths_percent([1, 1, 1]), [34, 33, 33])

    def test_sway_commands_leave_the_last_window_alone(self):
        self.assertEqual(launch.sway_commands(1, [11, 12], [3, 1]),
                         ["[con_id=11] resize set width 75 ppt"])
        self.assertEqual(launch.sway_commands(1, [11], [1]), [])


class ConfigTest(unittest.TestCase):
    def test_parses_pages(self):
        pages = launch.parse_tiles({"page": [
            {"tile": [{"url": "http://a/", "width": 3}, {"url": "https://b/"}]},
            {"tile": [{"url": "http://c/"}]}]})
        self.assertEqual(pages, [[{"url": "http://a/", "width": 3},
                                  {"url": "https://b/", "width": 1}],
                                 [{"url": "http://c/", "width": 1}]])

    def test_rejects_bad_configs(self):
        cases = {
            "no pages": {},
            "no tiles": {"page": [{}]},
            "url": {"page": [{"tile": [{"url": "janus:8470"}]}]},
            "width": {"page": [{"tile": [{"url": "http://a/", "width": 0}]}]},
        }
        for word, raw in cases.items():
            with self.subTest(word):
                with self.assertRaises(launch.ConfigError) as cm:
                    launch.parse_tiles(raw)
                self.assertIn(word, str(cm.exception))

    def test_example_config_and_check_flag(self):
        out = subprocess.run(
            [sys.executable, str(ROOT / "kiosk" / "launch.py"), "--check",
             "--config", str(ROOT / "kiosk" / "tiles.example.toml")],
            capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.splitlines(), [
            "page 1:  75%  http://janus.example:8470/",
            "page 1:  25%  http://127.0.0.1:8480/"])


if __name__ == "__main__":
    unittest.main()
