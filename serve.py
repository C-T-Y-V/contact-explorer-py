"""Run the optional local HTTP backend."""

from __future__ import annotations

import argparse
from pathlib import Path

from contact_explorer.api import run_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Contact Explorer backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()
    run_server(args.host, args.port, args.db)


if __name__ == "__main__":
    main()
