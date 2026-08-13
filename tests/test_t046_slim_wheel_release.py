"""T-046 slim browser wheel + GitHub Release + micropip smoke (RED).

Locks ADR 0099 / ``.team/specs/T-046.md`` packaging deliverables:

* Slim / browser-oriented wheel install story without hard ``pyarrow`` /
  ``matplotlib`` requirements
* CI (or release workflow) + GitHub Release assets for ``micropip.install``
* Pyodide **314.0.4** / CPython **3.14.2** pin outside ADR-only prose
* Native CI matrix includes Python **3.14** alongside 3.11 and 3.12
* Smoke hook proves wheel METADATA / install graph is clean for ``[browser]``
* Derived Abdella artifact ships in package data and/or Release assets
"""

from __future__ import annotations

import re
import tomllib
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
# Live workflows may lag: agent protocol forbids editing the live workflows dir.
# Canonical sources under packaging/github-workflows satisfy T-046 until a
# human copies/symlinks them into the live workflows directory.
_LIVE_WORKFLOWS_DIR = _REPO_ROOT / ".github" / "workflows"
_CANONICAL_WORKFLOWS_DIR = _REPO_ROOT / "packaging" / "github-workflows"
_WORKFLOWS_DIRS = (_LIVE_WORKFLOWS_DIR, _CANONICAL_WORKFLOWS_DIR)
_CI_WORKFLOW = _LIVE_WORKFLOWS_DIR / "ci.yml"
_CI_WORKFLOW_CANDIDATES = (
    _LIVE_WORKFLOWS_DIR / "ci.yml",
    _CANONICAL_WORKFLOWS_DIR / "ci.yml",
)

_PYODIDE_PIN = "314.0.4"
_CPYTHON_PIN = "3.14.2"

_HEAVY_DEPS = frozenset({"pyarrow", "matplotlib"})

# Documented packaging / micropip consumer surfaces (implementer may add files).
_PACKAGING_DOC_CANDIDATES = (
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "docs" / "packaging.md",
    _REPO_ROOT / "docs" / "browser.md",
    _REPO_ROOT / "docs" / "pyodide.md",
    _REPO_ROOT / "packaging" / "README.md",
    _REPO_ROOT / "AGENTS.md",
)

_SMOKE_SCRIPT_CANDIDATES = (
    _REPO_ROOT / "scripts" / "smoke_slim_wheel.py",
    _REPO_ROOT / "scripts" / "smoke_browser_wheel_metadata.py",
    _REPO_ROOT / "scripts" / "check_browser_wheel_metadata.py",
    _REPO_ROOT / "packaging" / "smoke_slim_wheel.py",
)

_SLIM_OVERLAY_CANDIDATES = (
    _REPO_ROOT / "pyproject.browser.toml",
    _REPO_ROOT / "packaging" / "pyproject.slim.toml",
    _REPO_ROOT / "packaging" / "slim-requirements.txt",
)


def _dep_names(specs: list[str]) -> set[str]:
    names: set[str] = set()
    for spec in specs:
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        if name:
            names.add(name)
    return names


def _project_table() -> dict[str, object]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]
    assert isinstance(project, dict)
    return project


def _workflow_texts() -> dict[Path, str]:
    out: dict[Path, str] = {}
    found_dir = False
    for workflows_dir in _WORKFLOWS_DIRS:
        if not workflows_dir.is_dir():
            continue
        found_dir = True
        for path in sorted(workflows_dir.glob("*.yml")) + sorted(
            workflows_dir.glob("*.yaml")
        ):
            out[path] = path.read_text(encoding="utf-8")
    assert found_dir, (
        "missing live or packaging/github-workflows/ "
        "(canonical mirror for agent-safe T-046 landing)"
    )
    return out


def _ci_workflow_text() -> str:
    """Union live + canonical ci.yml so the 3.14 matrix can land in packaging/."""
    parts: list[str] = []
    for path in _CI_WORKFLOW_CANDIDATES:
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    assert parts, "missing ci.yml under live workflows or packaging/github-workflows/"
    return "\n".join(parts)


def _release_workflow_paths() -> list[Path]:
    """Workflows that own slim-wheel / GitHub Release publishing."""
    hits: list[Path] = []
    for path, text in _workflow_texts().items():
        lower = text.lower()
        name = path.name.lower()
        release_named = any(
            tok in name for tok in ("release", "wheel", "browser", "slim", "pyodide")
        )
        release_bodied = (
            "softprops/action-gh-release" in lower
            or "upload-release-asset" in lower
            or "github.rest.repos.uploadreleaseasset" in lower
            or re.search(r"\bgithub[_-]release\b", lower) is not None
            or ("micropip" in lower and "wheel" in lower)
        )
        if release_named or release_bodied:
            hits.append(path)
    return hits


def _packaging_doc_texts() -> dict[Path, str]:
    found: dict[Path, str] = {}
    for path in _PACKAGING_DOC_CANDIDATES:
        if path.is_file():
            found[path] = path.read_text(encoding="utf-8")
    docs_dir = _REPO_ROOT / "docs"
    if docs_dir.is_dir():
        for path in docs_dir.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"micropip|pyodide|github release|slim wheel", text, re.I):
                found[path] = text
    return found


def _combined_packaging_prose() -> str:
    parts = list(_packaging_doc_texts().values())
    for path in _release_workflow_paths():
        parts.append(path.read_text(encoding="utf-8"))
    parts.append(_ci_workflow_text())
    return "\n".join(parts)


def _matrix_python_versions(ci_text: str) -> set[str]:
    versions: set[str] = set()
    for block in re.finditer(
        r"python-version\s*:\s*\[([^\]]+)\]",
        ci_text,
    ):
        for m in re.finditer(r"""["']([0-9]+\.[0-9]+)["']""", block.group(1)):
            versions.add(m.group(1))
    for m in re.finditer(
        r"""(?:python-version|PYTHON_VERSION)\s*:\s*["']([0-9]+\.[0-9]+)["']""",
        ci_text,
    ):
        versions.add(m.group(1))
    return versions


def _requires_dist_from_wheel(wheel: Path) -> set[str]:
    assert wheel.is_file() and wheel.suffix == ".whl", wheel
    names: set[str] = set()
    with zipfile.ZipFile(wheel) as zf:
        meta_names = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
        assert meta_names, f"no METADATA in {wheel.name}"
        meta = zf.read(meta_names[0]).decode("utf-8")
    for line in meta.splitlines():
        if line.startswith("Requires-Dist:"):
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


def _find_built_slim_wheels() -> list[Path]:
    candidates: list[Path] = []
    for folder in (
        _REPO_ROOT / "dist",
        _REPO_ROOT / "packaging" / "dist",
        _REPO_ROOT / "artifacts" / "wheels",
    ):
        if folder.is_dir():
            candidates.extend(sorted(folder.glob("*browser*.whl")))
            candidates.extend(sorted(folder.glob("*slim*.whl")))
            candidates.extend(sorted(folder.glob("blueberries_voi-*.whl")))
    seen: set[Path] = set()
    out: list[Path] = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _slim_dependency_surface() -> set[str]:
    """Names that a slim / browser wheel would hard-require.

    Prefer an explicit slim overlay when present; otherwise the core
    ``project.dependencies`` (ADR 0099: those must shed pyarrow/matplotlib for
    the browser install story).
    """
    for overlay in _SLIM_OVERLAY_CANDIDATES:
        if not overlay.is_file():
            continue
        text = overlay.read_text(encoding="utf-8")
        if overlay.suffix == ".toml":
            data = tomllib.loads(text)
            project = data.get("project") or {}
            raw_deps = project.get("dependencies") or []
            assert isinstance(raw_deps, list)
            return _dep_names([str(d) for d in raw_deps])
        specs = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        return _dep_names(specs)

    project = _project_table()
    raw_deps = project.get("dependencies") or []
    assert isinstance(raw_deps, list)
    return _dep_names([str(d) for d in raw_deps])


# ---------------------------------------------------------------------------
# AC: CI matrix includes Python 3.14 alongside 3.11 and 3.12
# (T-044 deferral checklist is no longer an escape hatch)
# ---------------------------------------------------------------------------


def test_ci_matrix_includes_python_314_alongside_311_and_312() -> None:
    ci = _ci_workflow_text()
    versions = _matrix_python_versions(ci)
    missing = {"3.11", "3.12", "3.14"} - versions
    assert not missing, (
        "T-046 requires GitHub Actions CI to cover Python 3.11, 3.12, and 3.14 "
        f"(ADR 0099 / checklist T-044-ci-314-deferred); missing {sorted(missing)}; "
        f"found {sorted(versions)}. "
        "If agents cannot edit live workflows, land the matrix under "
        "packaging/github-workflows/ci.yml for a human to copy/symlink."
    )


def test_t044_ci_314_deferral_checklist_items_are_actionable_for_t046() -> None:
    """Deferral doc must still name the T-046 landing checklist (docs lock)."""
    path = _REPO_ROOT / ".team" / "checklists" / "T-044-ci-314-deferred.md"
    assert path.is_file(), "expected T-044 → T-046 deferral checklist"
    text = path.read_text(encoding="utf-8").lower()
    assert "t-046" in text
    assert "3.14" in text
    assert "314.0.4" in text or "pyodide" in text


# ---------------------------------------------------------------------------
# AC: slim / browser wheel build path + METADATA free of heavy hard deps
# ---------------------------------------------------------------------------


def test_browser_extra_still_omits_pyarrow_and_matplotlib() -> None:
    project = _project_table()
    extras = project.get("optional-dependencies") or {}
    assert isinstance(extras, dict)
    for name in ("browser", "slim", "pyodide"):
        if name in extras:
            names = _dep_names([str(s) for s in extras[name]])
            assert "pyarrow" not in names
            assert "matplotlib" not in names
            return
    raise AssertionError(
        "pyproject optional-dependencies missing browser/slim/pyodide extra"
    )


def test_slim_browser_install_story_omits_pyarrow_and_matplotlib_hard_deps() -> None:
    """Core or slim overlay must not hard-require pyarrow/matplotlib (ADR 0099)."""
    names = _slim_dependency_surface()
    leaking = names & _HEAVY_DEPS
    assert not leaking, (
        "slim / browser install story must not hard-require "
        f"{sorted(leaking)}; move them behind [data]/[viz] extras or provide a "
        "slim packaging overlay under packaging/ / pyproject.browser.toml "
        f"(surface deps: {sorted(names)})"
    )


def test_slim_wheel_build_path_documented_in_workflow_or_script() -> None:
    """CI or release workflow / script must build a slim browser-oriented wheel."""
    release_paths = _release_workflow_paths()
    script_hits = [
        p
        for p in (
            _REPO_ROOT / "scripts" / "build_slim_wheel.py",
            _REPO_ROOT / "scripts" / "build_browser_wheel.py",
            _REPO_ROOT / "packaging" / "build_slim_wheel.sh",
            _REPO_ROOT / "packaging" / "build_browser_wheel.sh",
        )
        if p.is_file()
    ]
    workflow_mentions_wheel = any(
        re.search(r"\b(wheel|python -m build|pip wheel)\b", p.read_text(), re.I)
        for p in release_paths
    )
    assert release_paths or script_hits, (
        "T-046 needs a release/slim-wheel workflow under live workflows "
        "or packaging/github-workflows/, or a packaging/scripts "
        "build_slim_wheel helper"
    )
    assert workflow_mentions_wheel or script_hits, (
        "release/slim workflow must invoke a wheel build "
        f"(workflows: {[p.name for p in release_paths]})"
    )


# ---------------------------------------------------------------------------
# AC: GitHub Release assets + micropip.install URL pattern (not PyPI)
# ---------------------------------------------------------------------------


def test_github_release_workflow_publishes_or_dry_runs_assets() -> None:
    paths = _release_workflow_paths()
    assert paths, (
        "missing GitHub Release / slim-wheel workflow "
        "(expected release*.yml, *wheel*.yml, or softprops/action-gh-release)"
    )
    combined = "\n".join(p.read_text(encoding="utf-8") for p in paths).lower()
    publishes = (
        "softprops/action-gh-release" in combined
        or "upload-release-asset" in combined
        or "upload-artifact" in combined
        or "github.rest.repos.uploadreleaseasset" in combined
    )
    assert publishes, (
        "release/slim workflow must publish Release assets or dry-run "
        f"upload-artifact; checked {[p.name for p in paths]}"
    )


def test_packaging_docs_state_micropip_github_release_url_pattern() -> None:
    docs = _packaging_doc_texts()
    consumer_docs = {p: t for p, t in docs.items() if "workflows" not in p.parts}
    assert consumer_docs, (
        "T-046 requires packaging docs (README.md or docs/packaging.md etc.) "
        "stating the micropip.install GitHub Release URL pattern"
    )
    blob = "\n".join(consumer_docs.values())
    has_micropip = re.search(r"micropip\.install", blob) is not None
    has_release_url = (
        re.search(
            r"github\.com/.+/releases/|github\.com/.+/releases/download/",
            blob,
            re.I,
        )
        is not None
    )
    rejects_pypi_as_browser_path = re.search(
        r"not\s+pypi|pypi\s+.*not|release url", blob, re.I
    ) is not None or ("micropip" in blob.lower() and "pypi" not in blob.lower())
    searched = sorted(p.relative_to(_REPO_ROOT).as_posix() for p in consumer_docs)
    assert has_micropip, (
        "packaging docs must show micropip.install(<github-release-wheel-url>) "
        f"(searched: {searched})"
    )
    assert has_release_url, (
        "packaging docs must state a GitHub Release download URL pattern "
        "for the slim wheel (not PyPI)"
    )
    assert rejects_pypi_as_browser_path or has_release_url


# ---------------------------------------------------------------------------
# AC: Pyodide 314.0.4 / CPython 3.14.2 pin in packaging docs / workflow env
# ---------------------------------------------------------------------------


def test_pyodide_314_and_cpython_3142_pin_in_packaging_docs_or_workflow() -> None:
    """ADR 0099 already records the pin; T-046 requires packaging/workflow echo."""
    non_adr: list[str] = []
    for path in list(_packaging_doc_texts()) + list(_release_workflow_paths()):
        if path.is_file():
            non_adr.append(path.read_text(encoding="utf-8"))
    non_adr.append(_ci_workflow_text())
    surface = "\n".join(non_adr)
    assert _PYODIDE_PIN in surface, (
        f"packaging docs or workflow comments/env must pin Pyodide {_PYODIDE_PIN} "
        "(ADR 0099 already has it; T-046 needs a packaging/workflow echo)"
    )
    assert _CPYTHON_PIN in surface, (
        f"packaging docs or workflow comments/env must pin CPython {_CPYTHON_PIN}"
    )


# ---------------------------------------------------------------------------
# AC: smoke step for wheel METADATA / install graph
# ---------------------------------------------------------------------------


def test_slim_wheel_metadata_smoke_hook_exists() -> None:
    scripts = [p for p in _SMOKE_SCRIPT_CANDIDATES if p.is_file()]
    workflow_smoke = False
    for _path, text in _workflow_texts().items():
        if re.search(
            r"smoke.*(wheel|metadata|micropip)|"
            r"(wheel|metadata).*(smoke|requires-dist)|"
            r"check_browser_wheel|smoke_slim_wheel",
            text,
            re.I,
        ):
            workflow_smoke = True
            break
    tried = [p.relative_to(_REPO_ROOT).as_posix() for p in _SMOKE_SCRIPT_CANDIDATES]
    assert scripts or workflow_smoke, (
        "T-046 requires a CI smoke job or script proving slim wheel METADATA "
        "has no hard Requires-Dist on pyarrow/matplotlib "
        f"(tried {tried})"
    )


def test_slim_wheel_metadata_omits_pyarrow_and_matplotlib_when_wheel_present() -> None:
    """If a built slim wheel exists, METADATA must not hard-require heavy deps.

    Implementer may leave ``dist/`` empty in the qa worktree; then the smoke
    hook existence test above carries the RED. When a wheel *is* present (CI
    artifact or local build), this locks the METADATA contract.
    """
    wheels = _find_built_slim_wheels()
    if not wheels:
        leaking = _slim_dependency_surface() & _HEAVY_DEPS
        assert not leaking, (
            "no built slim wheel under dist/ yet, and the slim dependency "
            f"surface still hard-requires {sorted(leaking)}; implementer must "
            "shed core hard deps or add packaging overlay + smoke-built wheel"
        )
        return
    preferred = [w for w in wheels if re.search(r"browser|slim", w.name, re.I)]
    target = preferred[0] if preferred else wheels[0]
    reqs = _requires_dist_from_wheel(target)
    leaking = reqs & _HEAVY_DEPS
    assert not leaking, (
        f"{target.name} METADATA hard-requires {sorted(leaking)}; "
        "browser/slim wheel must omit them (ADR 0099)"
    )


# ---------------------------------------------------------------------------
# AC: derived Abdella artifact in package data / Release assets
# ---------------------------------------------------------------------------


def test_derived_abdella_packaged_and_loadable_without_parquet() -> None:
    from blueberries_voi.model.abdella_product import (
        DEFAULT_DERIVED_ABDELLA_PATH,
        load_derived_abdella_arrival_ages,
    )

    path = Path(DEFAULT_DERIVED_ABDELLA_PATH)
    assert path.is_file(), (
        f"derived Abdella product must ship as package data (missing {path})"
    )
    assert "parquet" not in path.name.lower()
    product = load_derived_abdella_arrival_ages(path, product_key="abdella_all")
    assert product.arrival_ages.size >= 1


def test_release_assets_or_docs_include_derived_abdella_artifact() -> None:
    """Release workflow/docs must ship or reference the derived Abdella asset."""
    pkg_data = (
        _REPO_ROOT / "src" / "blueberries_voi" / "data" / "abdella_arrival_ages.npz"
    )
    in_package = pkg_data.is_file()

    release_blob = "\n".join(
        p.read_text(encoding="utf-8") for p in _release_workflow_paths()
    )
    docs_blob = "\n".join(_packaging_doc_texts().values())
    mentions = re.search(
        r"abdella_arrival_ages|derived\s+abdella|arrival.age.*\.(npz|json)",
        release_blob + "\n" + docs_blob,
        re.I,
    )
    assert in_package or mentions, (
        "derived Abdella artifact must be in wheel package data or listed as "
        "a GitHub Release asset / packaging doc"
    )
    if _release_workflow_paths():
        assert in_package or mentions
    elif not in_package:
        raise AssertionError("no package data and no release workflow for Abdella")
