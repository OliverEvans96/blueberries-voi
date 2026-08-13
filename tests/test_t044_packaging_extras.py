"""T-044 packaging extras + CI 3.14 deferral (RED).

Locks ADR 0099 optional-dependency split and the T-044 CI checklist item:

* ``[browser]`` (or equivalent) free of pyarrow / matplotlib
* ``[data]`` (or equivalent) retains pyarrow for desktop Gate 0 / Parquet
* ``[viz]`` (or equivalent) may own matplotlib
* Python 3.14 CI matrix job landed **or** explicitly deferred to T-046
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"


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
    # Allow rename aliases documented in the extra's own list comments — still
    # require one of the ADR 0099 / T-044 names to exist as a table key.
    msg = (
        f"pyproject optional-dependencies missing one of {candidates}; "
        f"have {sorted(extras)}"
    )
    raise AssertionError(msg)


def test_browser_extra_exists_and_omits_pyarrow_and_matplotlib() -> None:
    name, specs = _find_extra("browser", "slim", "pyodide")
    names = _dep_names(specs)
    assert "pyarrow" not in names, f"[{name}] must omit pyarrow (ADR 0099)"
    assert "matplotlib" not in names, f"[{name}] must omit matplotlib (ADR 0099)"


def test_data_extra_retains_pyarrow_for_desktop_parquet() -> None:
    name, specs = _find_extra("data", "parquet", "abdella")
    names = _dep_names(specs)
    assert "pyarrow" in names, (
        f"[{name}] must retain pyarrow for desktop Gate 0 / Parquet (ADR 0085/0099)"
    )


def test_viz_extra_owns_matplotlib_or_browser_core_omits_it() -> None:
    extras = _optional_extras()
    if "viz" in extras or "plot" in extras:
        name, specs = _find_extra("viz", "plot")
        assert "matplotlib" in _dep_names(specs), (
            f"[{name}] should own matplotlib when present"
        )
        return
    # If no viz extra yet, hard runtime deps must not be the only story —
    # browser extra must exist (previous test) and core should be on a path
    # toward shedding matplotlib (assert browser extra key exists).
    assert "browser" in extras or "slim" in extras or "pyodide" in extras


def test_core_runtime_dependencies_document_split_or_shed_heavy_deps() -> None:
    """Core install must not be the only place pyarrow+matplotlib live forever.

    After T-044, either they move behind extras, or core stays temporarily
    while ``[browser]`` documents the slim graph — but ``[browser]`` / ``[data]``
    keys must exist (see sibling tests). This test locks that the extras table
    is non-empty beyond legacy ``dev`` / ``notebooks``.
    """
    extras = _optional_extras()
    eng_keys = {
        k
        for k in extras
        if k
        not in {
            "dev",
            "notebooks",
            "test",
            "tests",
            "typing",
            "types",
        }
    }
    assert eng_keys, (
        "T-044 requires ENG-01 extras (browser/data/viz or equivalents) in "
        "pyproject optional-dependencies"
    )
    assert eng_keys & {"browser", "slim", "pyodide", "data", "parquet", "abdella", "viz", "plot"}, (
        f"ENG-01 extras missing expected names; have {sorted(eng_keys)}"
    )


def test_python_314_ci_matrix_or_explicit_deferral_to_t046() -> None:
    ci = _CI_WORKFLOW.read_text(encoding="utf-8")
    has_314 = bool(re.search(r"""["']3\.14["']""", ci))
    if has_314:
        return

    # Explicit deferral checklist pointing at T-046 (spec allows this).
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
