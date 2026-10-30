"""Server resource points at the authclient plugin. HTTP login stays off."""

import unittest

from opennhp_router.operator import load_operator_text
from opennhp_router.render import render


OPERATOR = """
window_seconds = 15

[[identities]]
pubkey = "client-pubkey-a"

[[resources]]
name = "app"

[[resources.forwards]]
public_host = "pub.example"
public_port = 443
backend_host = "backend.internal"
backend_port = 8080
protocol = "tcp"
"""


class ServerPluginBindingTest(unittest.TestCase):
    def test_server_resource_binds_authclient_and_http_is_off(self):
        files = render(load_operator_text(OPERATOR))
        resource = files["server/etc/resource.toml"]
        http = files["server/etc/http.toml"]
        self.assertIn('["authclient"]', resource)
        self.assertIn('PluginPath = "authclient/authclient.so"', resource)
        self.assertIn("EnableHttp = false", http)
        self.assertNotIn("backend.internal", resource)
        self.assertNotIn("backend.internal", http)


if __name__ == "__main__":
    unittest.main()
