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
    BARCODE_DIR,
    BARCODE_WEB_SUBDIR,
    BLOG_FIG_STUDIO_MANUAL,
    DEFAULT_WEB_DEST,
    SYNC_ARTICLE_FIGURES,
    SYNC_BARCODE_BLOG,
    SyncCopy,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy article figures and barcodes into personal-website public images."
        ),
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


def _copy_one(copy: SyncCopy, dest: Path, *, dry_run: bool) -> Path | None:
    src = copy.source_dir / copy.rel_path
    out = dest / copy.dest_rel
    if not src.is_file():
        return src
    if dry_run:
        print(f"would copy {src} -> {out}")
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
        print(f"copied {copy.dest_rel}")
    return None


def _sync_barcode_bundle(dest: Path, *, dry_run: bool) -> list[Path]:
    missing: list[Path] = []
    barcode_dest = dest / BARCODE_WEB_SUBDIR
    if not BARCODE_DIR.is_dir():
        missing.append(BARCODE_DIR)
        return missing

    for src in sorted(BARCODE_DIR.glob("*.png")):
        out = barcode_dest / src.name
        if dry_run:
            print(f"would copy {src} -> {out}")
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
            print(f"copied {BARCODE_WEB_SUBDIR}/{src.name}")

    if not missing and not any(BARCODE_DIR.glob("*.png")):
        missing.append(BARCODE_DIR / "*.png")
    return missing


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    dest: Path = args.dest.expanduser().resolve()
    missing: list[Path] = []

    if not args.dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    for copy in (*SYNC_ARTICLE_FIGURES, SYNC_BARCODE_BLOG):
        if (src := _copy_one(copy, dest, dry_run=args.dry_run)) is not None:
            missing.append(src)

    for path in _sync_barcode_bundle(dest, dry_run=args.dry_run):
        missing.append(path)

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

    n_article = len(SYNC_ARTICLE_FIGURES) + 1
    n_barcode = len(list(BARCODE_DIR.glob("*.png"))) if BARCODE_DIR.is_dir() else 0
    total = n_article + n_barcode
    if args.dry_run:
        print(f"\nDry run OK — would sync {total} files to {dest}")
    else:
        print(f"\nSynced {total} files to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
