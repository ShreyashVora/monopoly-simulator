"""Local dev server: serves ui/board.html and the rules-engine JSON API.

Run:  python server.py   (src/) -> http://127.0.0.1:8000

`make_server()` is also used by the pytest API tests with port=0 so tests get
an ephemeral free port and never collide with a running dev server.
"""

import json
import pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rules

UI = pathlib.Path(__file__).resolve().parent.parent / "ui"


def make_handler(game):
    class Handler(BaseHTTPRequestHandler):
        game_ref = game

        def _json(self, payload, code=200):
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _file(self, path):
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/board.html", "/index.html"):
                self._file(UI / "board.html")
            elif self.path.startswith("/api/state"):
                self._json(self.game_ref.public_state())
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path.startswith("/api/action"):
                length = int(self.headers.get("Content-Length", 0))
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    self._json({"ok": False, "error": "Bad JSON"}, 400)
                    return
                res = self.game_ref.act(body.get("type", ""),
                                        body.get("payload") or {})
                self._json(res)
            else:
                self.send_error(404)

        def log_message(self, fmt, *args):
            pass

    return Handler


def make_server(host="127.0.0.1", port=8000, game=None):
    game = game if game is not None else rules.Game()
    return ThreadingHTTPServer((host, port), make_handler(game))


if __name__ == "__main__":
    srv = make_server()
    print(f"Monopoly engine UI -> http://{srv.server_address[0]}:{srv.server_address[1]}")
    srv.serve_forever()
