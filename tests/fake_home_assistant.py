"""A stand-in for Home Assistant's REST API, for tests and for looking at the
buttons page without a real Home Assistant.

    python3 tests/fake_home_assistant.py --port 8123   # token: fake-token
"""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "fake-token"

DEMO_STATES = {
    "light.desk_lamp": "on",
    "light.office_ceiling": "off",
    "fan.office": "on",
    "scene.movie_time": "2026-11-10T19:02:11.000000+00:00",
    "lock.front_door": "locked",
    "switch.space_heater": "off",
}


class FakeHomeAssistant:
    def __init__(self, states=None, token=TOKEN, port=0):
        self.states = dict(DEMO_STATES if states is None else states)
        self.token = token
        self.calls = []          # (domain, service, body)
        self.auth_headers = []   # every Authorization header received
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def _send(self, status, obj):
                body = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _authorized(self):
                fake.auth_headers.append(self.headers.get("Authorization"))
                if self.headers.get("Authorization") == f"Bearer {fake.token}":
                    return True
                self._send(401, {"message": "Unauthorized"})
                return False

            def do_GET(self):
                if not self._authorized():
                    return
                entity = self.path.removeprefix("/api/states/")
                if self.path.startswith("/api/states/") and entity in fake.states:
                    return self._send(200, {"entity_id": entity, "state": fake.states[entity]})
                self._send(404, {"message": "Entity not found."})

            def do_POST(self):
                if not self._authorized():
                    return
                parts = self.path.split("/")
                if len(parts) != 5 or parts[:3] != ["", "api", "services"]:
                    return self._send(404, {"message": "Not found"})
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                domain, service = parts[3], parts[4]
                fake.calls.append((domain, service, body))
                entity = body.get("entity_id")
                if entity in fake.states:
                    now = fake.states[entity]
                    if service == "toggle":
                        fake.states[entity] = "off" if now == "on" else "on"
                    elif service in ("lock", "unlock"):
                        fake.states[entity] = service + "ed"
                self._send(200, [])

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def start(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8123)
    fake = FakeHomeAssistant(port=ap.parse_args().port)
    print(f"fake Home Assistant at {fake.url}, token {TOKEN}", flush=True)
    try:
        fake.httpd.serve_forever()
    except KeyboardInterrupt:
        pass
