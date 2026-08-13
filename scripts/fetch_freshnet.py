#!/usr/bin/env python3
"""Download / refresh FreshRetailNet-50K into a local gitignored cache.

Requires the optional ``[freshnet]`` extra (Hugging Face ``datasets``)::

    uv sync --extra freshnet
    uv run python scripts/fetch_freshnet.py          # deps check only
    uv run python scripts/fetch_freshnet.py --fetch  # download/refresh

Raw parquet lands under ``.data/freshnet/`` (gitignored). See
``data/freshnet/PROVENANCE.md`` for dataset id, license, and SKU rule.
Does not fit ``demand_profile.json`` (T-080).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CACHE = _REPO_ROOT / ".data" / "freshnet"
_DATASET_ID = "Dingdong-Inc/FreshRetailNet-50K"


def _require_freshnet_deps() -> None:
    """Exit with a clear message if the ``[freshnet]`` extra is missing."""
    try:
        import datasets  # noqa: F401
    except ImportError as exc:
        print(
            "error: optional [freshnet] dependency 'datasets' is not installed.\n"
            "Install with: uv sync --extra freshnet\n"
            f"(import failed: {exc})",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def fetch(*, cache_dir: Path, revision: str | None) -> Path:
    """Load FreshRetailNet-50K via Hugging Face ``datasets`` into ``cache_dir``."""
    _require_freshnet_deps()
    from datasets import load_dataset

    cache_dir.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, object] = {
        "path": _DATASET_ID,
        "cache_dir": str(cache_dir),
    }
    if revision is not None:
        kwargs["revision"] = revision
    dataset = load_dataset(**kwargs)
    splits = list(dataset.keys()) if hasattr(dataset, "keys") else ["_"]
    print(
        f"FreshNet ingest OK: {_DATASET_ID} → {cache_dir} (splits={splits})",
        file=sys.stderr,
    )
    return cache_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download or refresh FreshRetailNet-50K (requires [freshnet] extra)."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=_DEFAULT_CACHE,
        help=f"gitignored raw cache directory (default: {_DEFAULT_CACHE})",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="optional Hugging Face dataset revision / commit",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="actually download/refresh into the cache (default: deps check only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="alias for default: check [freshnet] deps and print cache path",
    )
    args = parser.parse_args(argv)

    _require_freshnet_deps()
    cache_dir = args.cache_dir.resolve()
    if not args.fetch or args.dry_run:
        print(
            f"deps OK: [freshnet] present; would write {_DATASET_ID} to {cache_dir}\n"
            "pass --fetch to download/refresh (multi-GB; gitignored cache)",
            file=sys.stderr,
        )
        return 0

    fetch(cache_dir=cache_dir, revision=args.revision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
