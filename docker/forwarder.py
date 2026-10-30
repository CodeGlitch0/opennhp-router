#!/usr/bin/env python3
"""Listen on each public port from the gateway forward table and dial the backend."""

import sys
import tomllib
from pathlib import Path

from opennhp_router.forwarder import serve_forwards


def load_forwards(path):
    data = tomllib.loads(Path(path).read_text())
    return data.get("forwards", [])


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    path = argv[0] if argv else "/etc/opennhp/forwards.toml"
    serve_forwards(load_forwards(path))


if __name__ == "__main__":
    main()
