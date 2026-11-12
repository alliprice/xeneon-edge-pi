import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "buttons"))
sys.path.insert(0, str(ROOT / "tests"))

import server  # noqa: E402
from fake_home_assistant import TOKEN, FakeHomeAssistant  # noqa: E402

BUTTONS = [
    {"label": "Desk lamp", "service": "light.toggle", "entity": "light.desk_lamp", "icon": "light"},
    {"label": "Movie time", "service": "scene.turn_on", "entity": "scene.movie_time",
     "data": {"transition": 2}},
    {"label": "Gone", "service": "light.toggle", "entity": "light.removed"},
    {"label": "All off", "service": "script.all_off"},
]


def request(url, method="GET", headers=None):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        with e:
            return e.code, e.read()


class ConfigTest(unittest.TestCase):
    def good(self, **over):
        raw = {"home_assistant": {"url": "http://ha:8123/", "token": "t"}, "button": BUTTONS}
        raw.update(over)
        return raw

    def test_parses_and_derives_ids(self):
        c = server.parse_config(self.good())
        self.assertEqual(c["url"], "http://ha:8123")
        self.assertEqual([b["id"] for b in c["buttons"]],
                         ["desk-lamp", "movie-time", "gone", "all-off"])
        self.assertIsNone(c["buttons"][3]["entity"])

    def test_rejects_bad_configs(self):
        cases = {
            "url": self.good(home_assistant={"url": "ha:8123", "token": "t"}),
            "token": self.good(home_assistant={"url": "http://ha"}),
            "service": self.good(button=[{"label": "x", "service": "toggle"}]),
            "entity": self.good(button=[{"label": "x", "service": "a.b", "entity": "Desk Lamp"}]),
            "label": self.good(button=[{"service": "a.b"}]),
            "twice": self.good(button=[{"label": "x", "service": "a.b"}] * 2),
        }
        for word, raw in cases.items():
            with self.subTest(word):
                with self.assertRaises(server.ConfigError) as cm:
                    server.parse_config(raw)
                self.assertIn(word, str(cm.exception))

    def test_example_config_parses(self):
        c = server.load_config(ROOT / "buttons" / "buttons.example.toml")
        self.assertEqual(len(c["buttons"]), 6)


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.ha = FakeHomeAssistant().start()
        self.addCleanup(self.ha.stop)
        self.start(self.ha.url, TOKEN)

    def start(self, url, token):
        config = server.parse_config({"home_assistant": {"url": url, "token": token},
                                      "button": BUTTONS})
        httpd = server.make_server(config, port=0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def buttons(self):
        status, body = request(self.base + "/buttons")
        self.assertEqual(status, 200)
        return json.loads(body), body

    def test_states(self):
        data, _ = self.buttons()
        self.assertIsNone(data["error"])
        by = {b["id"]: b for b in data["buttons"]}
        self.assertEqual(by["desk-lamp"]["state"], "on")
        self.assertIsNone(by["gone"]["state"])
        self.assertTrue(by["gone"]["has_entity"])
        self.assertFalse(by["all-off"]["has_entity"])

    def test_press_calls_the_service_and_returns_the_new_state(self):
        status, body = request(self.base + "/press/desk-lamp", "POST", {"X-Buttons-Page": "1"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["button"]["state"], "off")
        self.assertEqual(self.ha.calls, [("light", "toggle", {"entity_id": "light.desk_lamp"})])

    def test_press_sends_data_and_works_without_an_entity(self):
        request(self.base + "/press/movie-time", "POST", {"X-Buttons-Page": "1"})
        request(self.base + "/press/all-off", "POST", {"X-Buttons-Page": "1"})
        self.assertEqual(self.ha.calls, [
            ("scene", "turn_on", {"transition": 2, "entity_id": "scene.movie_time"}),
            ("script", "all_off", {})])

    def test_press_needs_the_page_header(self):
        status, _ = request(self.base + "/press/desk-lamp", "POST")
        self.assertEqual(status, 403)
        self.assertEqual(self.ha.calls, [])

    def test_unknown_button(self):
        status, _ = request(self.base + "/press/nope", "POST", {"X-Buttons-Page": "1"})
        self.assertEqual(status, 404)

    def test_token_goes_to_home_assistant_and_nowhere_else(self):
        _, listing = self.buttons()
        _, pressed = request(self.base + "/press/desk-lamp", "POST", {"X-Buttons-Page": "1"})
        _, page = request(self.base + "/")
        self.assertTrue(self.ha.auth_headers)
        self.assertEqual(set(self.ha.auth_headers), {f"Bearer {TOKEN}"})
        for body in (listing, pressed, page):
            self.assertNotIn(TOKEN.encode(), body)

    def test_wrong_token_is_reported(self):
        self.start(self.ha.url, "wrong-secret")
        data, body = self.buttons()
        self.assertIn("refused the token", data["error"])
        self.assertNotIn(b"wrong-secret", body)
        status, body = request(self.base + "/press/desk-lamp", "POST", {"X-Buttons-Page": "1"})
        self.assertEqual(status, 502)
        self.assertNotIn(b"wrong-secret", body)

    def test_home_assistant_down(self):
        self.start("http://127.0.0.1:9", TOKEN)
        data, _ = self.buttons()
        self.assertIn("not answering", data["error"])
        self.assertEqual(len(data["buttons"]), 4)
        status, _ = request(self.base + "/press/desk-lamp", "POST", {"X-Buttons-Page": "1"})
        self.assertEqual(status, 502)

    def test_serves_the_page_and_nothing_outside_ui(self):
        status, body = request(self.base + "/")
        self.assertEqual(status, 200)
        self.assertIn(b"/ui/app.js", body)
        self.assertEqual(request(self.base + "/ui/app.css")[0], 200)
        self.assertEqual(request(self.base + "/ui/../server.py")[0], 404)


if __name__ == "__main__":
    unittest.main()
