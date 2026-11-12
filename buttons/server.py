#!/usr/bin/env python3
"""A page of Home Assistant buttons, and the server that presses them.

    python3 buttons/server.py --config ~/.config/xeneon-edge-pi/buttons.toml

The browser talks only to this server. The Home Assistant URL and token stay
here and are never sent to the page.
"""
import argparse
import json
import mimetypes
import re
import tomllib
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UI = Path(__file__).resolve().parent / "ui"
HA_TIMEOUT = 4  # seconds
# The page sends this header with a press. Another site's page cannot add it
# without a preflight request, which this server never approves.
PRESS_HEADER = "X-Buttons-Page"


class ConfigError(Exception):
    pass


class HomeAssistantError(Exception):
    """The message is shown on the page, so it never includes the token."""


def load_config(path):
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except OSError as e:
        raise ConfigError(f"cannot read {path}: {e.strerror}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e
    return parse_config(raw)


def parse_config(raw):
    ha = raw.get("home_assistant") or {}
    url, token = ha.get("url"), ha.get("token")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ConfigError("home_assistant.url must be an http or https URL")
    if not isinstance(token, str) or not token:
        raise ConfigError("home_assistant.token is missing")
    buttons, seen = [], set()
    for n, b in enumerate(raw.get("button") or [], start=1):
        where = f"button {n}"
        label = b.get("label")
        if not isinstance(label, str) or not label:
            raise ConfigError(f"{where}: label is missing")
        service = b.get("service", "")
        if not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", service):
            raise ConfigError(f"{where} ({label}): service must look like light.toggle")
        entity = b.get("entity")
        if entity is not None and not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", entity):
            raise ConfigError(f"{where} ({label}): entity must look like light.desk")
        data = b.get("data") or {}
        if not isinstance(data, dict):
            raise ConfigError(f"{where} ({label}): data must be a table")
        ident = b.get("id") or re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or str(n)
        if ident in seen:
            raise ConfigError(f"{where} ({label}): id {ident!r} is used twice")
        seen.add(ident)
        buttons.append({"id": ident, "label": label, "icon": b.get("icon", "dot"),
                        "color": b.get("color", ""), "service": service,
                        "entity": entity, "data": data})
    return {"url": url.rstrip("/"), "token": token, "buttons": buttons}


class HomeAssistant:
    def __init__(self, url, token):
        self.url, self.token = url, token

    def _call(self, method, path, body=None):
        req = urllib.request.Request(
            self.url + path, method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=HA_TIMEOUT) as resp:
                return json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as e:
            e.close()
            if e.code == 401:
                raise HomeAssistantError(
                    "Home Assistant refused the token. Make a new long-lived "
                    "token and put it in buttons.toml.") from e
            if e.code == 404:
                raise LookupError(path) from e
            raise HomeAssistantError(f"Home Assistant answered with error {e.code}.") from e
        except (OSError, ValueError) as e:
            raise HomeAssistantError(
                f"Home Assistant is not answering at {self.url}.") from e

    def state(self, entity):
        """The entity's state string, or None if Home Assistant has no such entity."""
        try:
            return self._call("GET", f"/api/states/{entity}").get("state")
        except LookupError:
            return None

    def press(self, button):
        domain, service = button["service"].split(".")
        body = dict(button["data"])
        if button["entity"]:
            body["entity_id"] = button["entity"]
        try:
            self._call("POST", f"/api/services/{domain}/{service}", body)
        except LookupError as e:
            raise HomeAssistantError(
                f"Home Assistant has no service {button['service']}.") from e


def public(button, state):
    return {"id": button["id"], "label": button["label"], "icon": button["icon"],
            "color": button["color"], "state": state,
            "has_entity": bool(button["entity"])}


def make_handler(config):
    ha = HomeAssistant(config["url"], config["token"])
    by_id = {b["id"]: b for b in config["buttons"]}

    class Handler(BaseHTTPRequestHandler):
        server_version = "buttons"

        def log_message(self, fmt, *args):
            pass

        def _json(self, status, obj):
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _file(self, name):
            path = (UI / name).resolve()
            if UI not in path.parents or not path.is_file():
                return self._json(404, {"error": "not found"})
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type",
                             mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                return self._file("index.html")
            if path.startswith("/ui/"):
                return self._file(path[4:])
            if path == "/buttons":
                return self._buttons()
            self._json(404, {"error": "not found"})

        def _buttons(self):
            states, error = {}, None
            for b in config["buttons"]:
                if not b["entity"]:
                    continue
                try:
                    states[b["id"]] = ha.state(b["entity"])
                except HomeAssistantError as e:
                    error = str(e)
                    break
            self._json(200, {"buttons": [public(b, states.get(b["id"]))
                                         for b in config["buttons"]],
                             "error": error})

        def do_POST(self):
            m = re.fullmatch(r"/press/([^/]+)", self.path)
            button = m and by_id.get(m.group(1))
            if not button:
                return self._json(404, {"error": "No such button."})
            if self.headers.get(PRESS_HEADER) != "1":
                return self._json(403, {"error": "Presses come from the buttons page only."})
            try:
                ha.press(button)
                state = ha.state(button["entity"]) if button["entity"] else None
            except HomeAssistantError as e:
                return self._json(502, {"error": str(e)})
            self._json(200, {"button": public(button, state)})

    return Handler


def make_server(config, host="127.0.0.1", port=8480):
    return ThreadingHTTPServer((host, port), make_handler(config))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8480)
    args = ap.parse_args()
    try:
        config = load_config(args.config)
    except ConfigError as e:
        raise SystemExit(f"buttons: {e}")
    server = make_server(config, args.host, args.port)
    print(f"buttons: http://{args.host}:{args.port}/ with {len(config['buttons'])} buttons",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
