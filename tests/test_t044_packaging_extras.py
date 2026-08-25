"""T-044 packaging extras + T-125 WASM-only studio cleanup (RED).

Locks ADR 0101 optional-dependency split after T-125 retires Pyodide/browser and
HTTP API extras (ADR 0129):

* ``[data]`` retains pyarrow for desktop Gate 0 / Parquet
* ``[viz]`` owns matplotlib
* no ``[browser]``, ``[api]``, or Pyodide alias extras
* Python 3.14 CI matrix job landed **or** explicitly deferred to T-046
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"

_RETIRED_EXTRAS = frozenset({"browser", "api", "slim", "pyodide"})


def _dep_names(specs: list[str]) -> set[str]:
    names: set[str] = set()
    for spec in specs:
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        if name:
            names.add(name)
    return names


def _optional_extras() -> dict[str, list[str]]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    extras = data["project"].get("optional-dependencies") or {}
    assert isinstance(extras, dict)
    return {str(k): list(v) for k, v in extras.items()}


def _find_extra(*candidates: str) -> tuple[str, list[str]]:
    extras = _optional_extras()
    for name in candidates:
        if name in extras:
            return name, extras[name]
    msg = (
        f"pyproject optional-dependencies missing one of {candidates}; "
        f"have {sorted(extras)}"
    )
    raise AssertionError(msg)


def test_retired_browser_and_api_extras_absent() -> None:
    extras = _optional_extras()
    present = sorted(_RETIRED_EXTRAS & set(extras))
    assert not present, (
        "T-125 requires retiring browser/api/pyodide extras; still present: "
        + ", ".join(present)
    )


def test_data_extra_retains_pyarrow_for_desktop_parquet() -> None:
    name, specs = _find_extra("data", "parquet", "abdella")
    names = _dep_names(specs)
    assert "pyarrow" in names, (
        f"[{name}] must retain pyarrow for desktop Gate 0 / Parquet (ADR 0085/0101)"
    )


def test_viz_extra_owns_matplotlib() -> None:
    name, specs = _find_extra("viz", "plot")
    assert "matplotlib" in _dep_names(specs), (
        f"[{name}] must own matplotlib for static figures (ADR 0084)"
    )


def test_eng01_extras_are_data_and_viz_only() -> None:
    """After T-125, ENG-01 packaging extras are data + viz (no browser/api)."""
    extras = _optional_extras()
    eng_keys = {
        k
        for k in extras
        if k
        not in {
            "all",
            "dev",
            "notebooks",
            "test",
            "tests",
            "typing",
            "types",
            "rust",
            "freshnet",
            "modal",
        }
    }
    assert eng_keys == {"data", "viz"}, (
        f"T-125 locks ENG-01 extras to data + viz only; have {sorted(eng_keys)}"
    )


def test_python_314_ci_matrix_or_explicit_deferral_to_t046() -> None:
    ci = _CI_WORKFLOW.read_text(encoding="utf-8")
    has_314 = bool(re.search(r"""["']3\.14["']""", ci))
    if has_314:
        return

    deferral_candidates = [
        _REPO_ROOT / ".team" / "checklists" / "T-044-ci-314-deferred.md",
        _REPO_ROOT / ".team" / "qa" / "T-044-ci-314-deferred.md",
        _REPO_ROOT / ".team" / "specs" / "T-044-ci-314-deferred.md",
    ]
    found = [p for p in deferral_candidates if p.is_file()]
    assert found, (
        "CI matrix lacks Python 3.14 and no explicit deferral checklist "
        "pointing at T-046 was found; land a 3.14 job stub or add one of "
        + ", ".join(str(p.relative_to(_REPO_ROOT)) for p in deferral_candidates)
    )
    text = found[0].read_text(encoding="utf-8").lower()
    assert "t-046" in text, f"{found[0].name} must point at T-046"
    assert "3.14" in text, f"{found[0].name} must mention Python 3.14"
