"""CLI entry: ``python -m blueberries_voi`` or ``blueberries-voi``."""

from __future__ import annotations

import argparse
import sys

from blueberries_voi import __version__


def main(argv: list[str] | None = None) -> int:
    """Parse args and run the CLI. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        prog="blueberries-voi",
        description="Simulation, analysis, and visualization for blueberry VOI work",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
