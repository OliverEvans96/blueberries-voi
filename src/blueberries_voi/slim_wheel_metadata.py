"""Rewrite slim-wheel METADATA numpy floors for Pyodide vs native (ADR 0099).

Native ``pyproject.toml`` keeps ``numpy>=2.4.6``. The slim wheel's METADATA
splits hard Requires-Dist so emscripten accepts Pyodide 314.0.4 bundled
numpy 2.4.3.
"""

from __future__ import annotations

import re

# Pyodide 314.0.4 full index ships numpy 2.4.3 (pyemscripten wasm32).
PYODIDE_BUNDLED_NUMPY = "2.4.3"
NATIVE_NUMPY_FLOOR = "2.4.6"
NUMPY_EMSCRIPTEN = f'numpy>={PYODIDE_BUNDLED_NUMPY}; sys_platform == "emscripten"'
NUMPY_NATIVE = f'numpy>={NATIVE_NUMPY_FLOOR}; sys_platform != "emscripten"'


def rewrite_hard_numpy_requires(meta: str) -> str:
    """Split native vs emscripten numpy floors; extras are left untouched."""
    lines = meta.splitlines(keepends=True)
    out: list[str] = []
    replaced = False
    for line in lines:
        if not line.startswith("Requires-Dist:"):
            out.append(line)
            continue
        raw = line.split(":", 1)[1].strip()
        nl = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
        spec = raw
        marker = ""
        if ";" in raw:
            spec, _, marker = raw.partition(";")
            spec, marker = spec.strip(), marker.strip()
        name = re.split(r"[<>=!~\s]", spec, maxsplit=1)[0].strip().lower()
        if name == "numpy" and "extra ==" not in marker.lower():
            if not replaced:
                out.append(f"Requires-Dist: {NUMPY_EMSCRIPTEN}{nl}")
                out.append(f"Requires-Dist: {NUMPY_NATIVE}{nl}")
                replaced = True
            continue
        out.append(line)
    if not replaced:
        raise RuntimeError(
            "slim wheel METADATA had no hard numpy Requires-Dist to retarget "
            f"for Pyodide bundled numpy {PYODIDE_BUNDLED_NUMPY}"
        )
    return "".join(out)
