#!/usr/bin/env -S uv run --python 3.11
# /// script
# requires-python = ">=3.11"
# ///
"""One-way sync of blog post figures to personal-website.

Usage (from repo root)::

    ./scripts/sync_blog_figures.py
    ./scripts/sync_blog_figures.py --dry-run
    ./scripts/sync_blog_figures.py --dest /path/to/public/images/blog/blueberries-voi
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from blog_figures_manifest import (  # noqa: E402
    ARTICLE_FIGURES_DIR,
    BLOG_FIG_STUDIO_MANUAL,
    DEFAULT_WEB_DEST,
    SYNC_SOURCES,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy article_figures PNGs into personal-website public images.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_WEB_DEST,
        help=f"Destination directory (default: {DEFAULT_WEB_DEST})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print copies without writing files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    dest: Path = args.dest.expanduser().resolve()
    missing: list[Path] = []

    if not args.dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    for rel_src, dest_name in SYNC_SOURCES:
        src = ARTICLE_FIGURES_DIR / rel_src
        out = dest / dest_name
        if not src.is_file():
            missing.append(src)
            continue
        if args.dry_run:
            print(f"would copy {src} -> {out}")
        else:
            shutil.copy2(src, out)
            print(f"copied {dest_name}")

    if missing:
        print(
            "\nMissing sources (re-run notebook / barcode generator first):",
            file=sys.stderr,
        )
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 1

    studio = dest / BLOG_FIG_STUDIO_MANUAL
    if not studio.is_file():
        print(
            f"\nNote: {BLOG_FIG_STUDIO_MANUAL} is not synced "
            f"(manual screenshot; keep it in {dest}).",
            file=sys.stderr,
        )

    if args.dry_run:
        print(f"\nDry run OK — would sync {len(SYNC_SOURCES)} files to {dest}")
    else:
        print(f"\nSynced {len(SYNC_SOURCES)} files to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
