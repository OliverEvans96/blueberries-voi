#!/usr/bin/env python3
"""Build the slim / browser-oriented wheel (T-046 / ADR 0099).

Produces a setuptools wheel under ``dist/`` whose hard Requires-Dist matches
core ``project.dependencies`` (numpy + scipy only; no pyarrow / matplotlib).

Native ``pyproject.toml`` / ``uv.lock`` keep ``numpy>=2.4.6``. After the
setuptools build, this script rewrites the slim wheel's hard numpy
Requires-Dist so Pyodide 314.0.4 can reuse ``loadPackage`` numpy **2.4.3**
(emscripten) instead of micropip reinstalling a CPython numpy.
"""

from __future__ import annotations

import base64
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile

from blueberries_voi.slim_wheel_metadata import (
    NATIVE_NUMPY_FLOOR,
    PYODIDE_BUNDLED_NUMPY,
    rewrite_hard_numpy_requires,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DIST = _REPO_ROOT / "dist"


def _record_sha256(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _rewrite_numpy_requires_for_pyodide(wheel: Path) -> None:
    """Patch METADATA + RECORD so micropip accepts loadPackage numpy 2.4.3."""
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        meta_name = next(n for n in names if n.endswith(".dist-info/METADATA"))
        record_name = next(n for n in names if n.endswith(".dist-info/RECORD"))
        meta = rewrite_hard_numpy_requires(zf.read(meta_name).decode("utf-8"))
        meta_bytes = meta.encode("utf-8")
        record_lines: list[str] = []
        for line in zf.read(record_name).decode("utf-8").splitlines():
            if not line.strip():
                continue
            path, _, rest = line.partition(",")
            if path == meta_name:
                record_lines.append(
                    f"{meta_name},{_record_sha256(meta_bytes)},{len(meta_bytes)}"
                )
            else:
                record_lines.append(line if rest else path)
        record_bytes = ("\n".join(record_lines) + "\n").encode("utf-8")
        replacements = {meta_name: meta_bytes, record_name: record_bytes}
        members: list[tuple[zipfile.ZipInfo, bytes]] = []
        for info in zf.infolist():
            payload = replacements.get(info.filename, zf.read(info.filename))
            members.append((info, payload))

    with NamedTemporaryFile(dir=wheel.parent, suffix=".whl", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "w") as out:
            for info, payload in members:
                new_info = zipfile.ZipInfo(
                    filename=info.filename, date_time=info.date_time
                )
                new_info.compress_type = info.compress_type
                new_info.external_attr = info.external_attr
                out.writestr(new_info, payload)
        tmp_path.replace(wheel)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    print(
        "Retargeted slim numpy Requires-Dist for Pyodide "
        f"{PYODIDE_BUNDLED_NUMPY} (native floor {NATIVE_NUMPY_FLOOR} kept)",
        flush=True,
    )


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
    wheel = wheels[-1]
    _rewrite_numpy_requires_for_pyodide(wheel)
    print(f"Built slim wheel: {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
