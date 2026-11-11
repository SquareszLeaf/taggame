"""Local server for the sprite editor, the map editor and the game.

    python3 tools/editor_server.py          (opens the sprite editor)
    python3 tools/editor_server.py maps     (opens the map editor)

Sprite editor: http://localhost:5501/tools/sprite-editor.html
Map editor:    http://localhost:5501/tools/map-editor.html
Game:          http://localhost:5501/
Serves the repo folder with caching off, and lets the editors save back into the game files.
"""
import http.server
import json
import os
import re
import sys
import threading
import webbrowser
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_tool  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGS = [a for a in sys.argv[1:] if not a.isdigit()]
PORTS = [int(a) for a in sys.argv[1:] if a.isdigit()]
PORT = PORTS[0] if PORTS else 5501
PAGE = "tools/map-editor.html" if "maps" in ARGS else "tools/sprite-editor.html"
SAVE_PATH = re.compile(r"^images/[A-Za-z0-9_.-]+\.png$")
DATA_LOCK = threading.Lock()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path in ("/api/new-map", "/api/save-map", "/api/map-bg"):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                with DATA_LOCK:
                    if url.path == "/api/new-map":
                        req = json.loads(body)
                        map_tool.new_map(req["name"], req.get("template", "map1"))
                    elif url.path == "/api/save-map":
                        map_tool.save_map(json.loads(body))
                    else:
                        map_tool.set_background(query.get("layout", [""])[0], body)
            except (ValueError, KeyError, TypeError) as e:
                return self.reply(400, {"error": str(e)})
            return self.reply(200, {"ok": True})
        if url.path != "/api/save-image":
            return self.send_error(404)
        path = query.get("path", [""])[0]
        if not SAVE_PATH.match(path) or not os.path.isfile(os.path.join(ROOT, path)):
            return self.send_error(400, "can only overwrite existing PNGs in images/")
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if not body.startswith(b"\x89PNG"):
            return self.send_error(400, "not a PNG")
        with open(os.path.join(ROOT, path), "wb") as f:
            f.write(body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}/{PAGE}"
    print(f"Sprite editor: http://localhost:{PORT}/tools/sprite-editor.html\n"
          f"Map editor:    http://localhost:{PORT}/tools/map-editor.html\n"
          f"Game:          http://localhost:{PORT}/\nCtrl+C to stop.")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
