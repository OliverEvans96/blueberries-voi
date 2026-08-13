#!/usr/bin/env python3
"""Smoke-check slim wheel METADATA for heavy hard deps (T-046 / ADR 0099).

Fails if any built ``blueberries_voi`` wheel under ``dist/`` (or packaging
dist) hard-requires ``pyarrow`` or ``matplotlib``.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HEAVY = frozenset({"pyarrow", "matplotlib"})


def _wheels() -> list[Path]:
    found: list[Path] = []
    for folder in (
        _REPO_ROOT / "dist",
        _REPO_ROOT / "packaging" / "dist",
        _REPO_ROOT / "artifacts" / "wheels",
    ):
        if folder.is_dir():
            found.extend(sorted(folder.glob("blueberries_voi-*.whl")))
            found.extend(sorted(folder.glob("*slim*.whl")))
            found.extend(sorted(folder.glob("*browser*.whl")))
    # Deduplicate while preserving order.
    seen: set[Path] = set()
    out: list[Path] = []
    for path in found:
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


def _requires_dist(wheel: Path) -> set[str]:
    names: set[str] = set()
    with zipfile.ZipFile(wheel) as zf:
        meta_names = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
        if not meta_names:
            raise SystemExit(f"no METADATA in {wheel.name}")
        meta = zf.read(meta_names[0]).decode("utf-8")
    for line in meta.splitlines():
        if not line.startswith("Requires-Dist:"):
            continue
        spec = line.split(":", 1)[1].strip()
        if ";" in spec:
            before, _, marker = spec.partition(";")
            if "extra ==" in marker.lower():
                continue
            spec = before.strip()
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        if name:
            names.add(name)
    return names


def main() -> int:
    wheels = _wheels()
    if not wheels:
        print(
            "error: no slim wheel under dist/; run scripts/build_slim_wheel.py first",
            file=sys.stderr,
        )
        return 1
    failed = False
    for wheel in wheels:
        reqs = _requires_dist(wheel)
        leaking = sorted(reqs & _HEAVY)
        if leaking:
            print(
                f"FAIL {wheel.name}: hard Requires-Dist includes {leaking}",
                file=sys.stderr,
            )
            failed = True
        else:
            print(f"OK {wheel.name}: hard Requires-Dist={sorted(reqs)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
