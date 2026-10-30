"""Listen on each public port and dial the backend. Not a client-facing address."""

import socket
import threading


def serve_forwards(forwards, host="0.0.0.0", bound=None, stop=None):
    """Bind one TCP listener per forward. `bound` receives the actual ports."""
    listeners = []
    for forward in forwards:
        protocol = (forward.get("protocol") or "tcp").lower()
        if protocol not in ("tcp", "any"):
            continue
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, int(forward["public_port"])))
        sock.listen(32)
        sock.settimeout(0.2)
        if bound is not None:
            bound.append(sock.getsockname()[1])
        listeners.append((sock, forward))
    threads = [
        threading.Thread(target=_accept_loop, args=(sock, forward, stop), daemon=True)
        for sock, forward in listeners
    ]
    for thread in threads:
        thread.start()
    if stop is None:
        return listeners
    stop.wait()
    for sock, _forward in listeners:
        sock.close()
    for thread in threads:
        thread.join(timeout=2)
    return listeners


def _accept_loop(sock, forward, stop):
    while stop is None or not stop.is_set():
        try:
            client, _addr = sock.accept()
        except socket.timeout:
            continue
        except OSError:
            return
        threading.Thread(target=_proxy, args=(client, forward), daemon=True).start()


def _proxy(client, forward):
    remote = None
    try:
        remote = socket.create_connection(
            (forward["backend_host"], int(forward["backend_port"])),
            timeout=5,
        )
        left = threading.Thread(target=_copy, args=(client, remote), daemon=True)
        right = threading.Thread(target=_copy, args=(remote, client), daemon=True)
        left.start()
        right.start()
        left.join()
        right.join()
    except OSError:
        pass
    finally:
        client.close()
        if remote is not None:
            remote.close()


def _copy(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass
