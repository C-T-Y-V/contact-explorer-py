"""Launch the Contact Explorer Tkinter application."""

from __future__ import annotations

import argparse
from pathlib import Path

from contact_explorer.ui import launch


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Contact Explorer")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite database path (defaults to data/contact_explorer.db)",
    )
    args = parser.parse_args()
    launch(args.db)


if __name__ == "__main__":
    main()
