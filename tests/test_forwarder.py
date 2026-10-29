"""The forwarder listens on each public port and dials the backend."""

import socket
import threading
import unittest

from opennhp_router.forwarder import serve_forwards


def _echo_server(host, port, ready, token):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(1)
    ready.set()
    conn, _ = sock.accept()
    with conn, sock:
        data = conn.recv(64)
        conn.sendall(token + data)


def _free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class ForwarderTest(unittest.TestCase):
    def test_listens_on_each_public_port_and_dials_backend(self):
        backend_ports = [_free_port(), _free_port()]
        tokens = [b"one:", b"two:"]
        readies = []
        for port, token in zip(backend_ports, tokens):
            ready = threading.Event()
            readies.append(ready)
            threading.Thread(
                target=_echo_server,
                args=("127.0.0.1", port, ready, token),
                daemon=True,
            ).start()
        for ready in readies:
            self.assertTrue(ready.wait(2))

        forwards = [
            {
                "public_port": 0,
                "backend_host": "127.0.0.1",
                "backend_port": backend_ports[0],
                "protocol": "tcp",
            },
            {
                "public_port": 0,
                "backend_host": "127.0.0.1",
                "backend_port": backend_ports[1],
                "protocol": "tcp",
            },
        ]
        bound = []
        stop = threading.Event()
        server = threading.Thread(
            target=serve_forwards,
            args=(forwards, "127.0.0.1", bound, stop),
            daemon=True,
        )
        server.start()
        for _ in range(50):
            if len(bound) == 2:
                break
            stop.wait(0.05)
        self.assertEqual(len(bound), 2)
        self.assertEqual(len(set(bound)), 2)

        for public_port, token in zip(bound, tokens):
            with socket.create_connection(("127.0.0.1", public_port), timeout=2) as client:
                client.sendall(b"ping")
                self.assertEqual(client.recv(64), token + b"ping")
        stop.set()
        server.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
