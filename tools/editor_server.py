"""Local server for the sprite editor (and the game).

    python3 tools/editor_server.py

Opens http://localhost:5501/tools/sprite-editor.html. The game itself is at http://localhost:5501/.
Serves the repo folder with caching off, and lets the editor save PNGs back into images/.
"""
import http.server
import os
import re
import sys
import threading
import webbrowser
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5501
SAVE_PATH = re.compile(r"^images/[A-Za-z0-9_.-]+\.png$")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/api/save-image":
            return self.send_error(404)
        path = parse_qs(url.query).get("path", [""])[0]
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
    url = f"http://localhost:{PORT}/tools/sprite-editor.html"
    print(f"Sprite editor: {url}\nGame:          http://localhost:{PORT}/\nCtrl+C to stop.")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
