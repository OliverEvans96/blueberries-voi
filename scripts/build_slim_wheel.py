#!/usr/bin/env python3
"""Build the slim / browser-oriented wheel (T-046 / ADR 0099).

Produces a setuptools wheel under ``dist/`` whose hard Requires-Dist matches
core ``project.dependencies`` (numpy + scipy only; no pyarrow / matplotlib).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DIST = _REPO_ROOT / "dist"


def main() -> int:
    _DIST.mkdir(parents=True, exist_ok=True)
    # Clear prior wheels so smoke scripts see a fresh slim build.
    for stale in _DIST.glob("*.whl"):
        stale.unlink()
    cmd = [
        sys.executable,
        "-m",
        "build",
        "--wheel",
        "--outdir",
        str(_DIST),
        str(_REPO_ROOT),
    ]
    print("Running:", " ".join(cmd), flush=True)
    try:
        subprocess.run(cmd, check=True, cwd=_REPO_ROOT)
    except FileNotFoundError:
        # Fallback when the ``build`` package is not installed yet.
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(_DIST), "."],
            check=True,
            cwd=_REPO_ROOT,
        )
    wheels = sorted(_DIST.glob("blueberries_voi-*.whl"))
    if not wheels:
        print("error: no blueberries_voi-*.whl written to dist/", file=sys.stderr)
        return 1
    print(f"Built slim wheel: {wheels[-1].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
