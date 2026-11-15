"""Run the Discord bridge for a Headlong identity.

Usage: headlong-discord-bridge [ROOT]

ROOT is the directory the web server serves (contains .identities/);
defaults to the current directory. Configuration comes from the
environment; see config.py and discord/README.md.
"""

import argparse
import logging
from pathlib import Path

from . import config
from .bridge import Bridge


def main() -> None:
    parser = argparse.ArgumentParser(prog="headlong-discord-bridge", description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Serve root (contains .identities/)")
    parser.add_argument("--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    serve_root = Path(args.root).resolve()
    if not serve_root.is_dir():
        raise SystemExit(f"Not a directory: {serve_root}")
    cfg = config.load(serve_root)
    Bridge(cfg).run(cfg.token, log_handler=None)


if __name__ == "__main__":
    main()
