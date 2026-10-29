"""HTTP allow/deny for installed client public keys.

POST /authorize with JSON {"pubkey": "..."}. 200 if installed, 403 if not.
There is no /register route. Identities come only from the operator file.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

from opennhp_router.identity import decision


def serve(installed, host="0.0.0.0", port=8090):
    allowed = list(installed)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if path != "/authorize":
                self.send_response(404)
                self.end_headers()
                return
            pubkey = _read_pubkey(self)
            if decision(pubkey, allowed) == "allow":
                self.send_response(200)
                body = b'{"result":"allow"}\n'
            else:
                self.send_response(403)
                body = b'{"result":"deny"}\n'
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd, httpd.server_address[1]


def _read_pubkey(handler) -> str:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length) if length else b""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""
    pubkey = payload.get("pubkey", "")
    return pubkey if isinstance(pubkey, str) else ""
