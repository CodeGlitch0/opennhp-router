"""Auth HTTP: POST /authorize allows installed keys and denies the rest."""

import json
import threading
import unittest
import urllib.error
import urllib.request

from opennhp_router.authhttp import serve


class AuthorizeHttpTest(unittest.TestCase):
    def setUp(self):
        self.httpd, self.port = serve(["client-pubkey-a"], host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def _post(self, path, payload):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, exc.read()
            finally:
                exc.close()

    def test_installed_pubkey_returns_200(self):
        status, _ = self._post("/authorize", {"pubkey": "client-pubkey-a"})
        self.assertEqual(status, 200)

    def test_unknown_pubkey_returns_403(self):
        status, _ = self._post("/authorize", {"pubkey": "not-installed"})
        self.assertEqual(status, 403)

    def test_register_route_is_absent(self):
        status, _ = self._post("/register", {"pubkey": "client-pubkey-a"})
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
