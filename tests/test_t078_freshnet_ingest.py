"""T-078 CAL-B1 — FreshNet ingest + PROVENANCE (RED).

Locks ADR 0115 / ``.team/specs/T-078.md`` before the ingest script and
``[freshnet]`` extra land:

* optional ``[freshnet]`` extra (HF / ``datasets``) — not core or ``[browser]``
* documented ``scripts/`` ingest entry that fails clearly without the extra
* ``data/freshnet/PROVENANCE.md`` with dataset id, CC BY 4.0, access method,
  SKU selection rule text (IDs may be placeholders until T-080)
* importing ``blueberries_voi`` must not pull ``datasets`` / HF hub clients
* no ``demand_profile.json`` fit required here (T-080); raw cache gitignored

Offline assertions only — no Hugging Face network download in tests.
"""

from __future__ import annotations

import ast
import importlib
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_GITIGNORE = _REPO_ROOT / ".gitignore"
_PROVENANCE = _REPO_ROOT / "data" / "freshnet" / "PROVENANCE.md"
_DEMAND_PROFILE = _REPO_ROOT / "data" / "freshnet" / "demand_profile.json"
_SCRIPTS = _REPO_ROOT / "scripts"
_SRC = _REPO_ROOT / "src" / "blueberries_voi"

_SCRIPT_NAME_CANDIDATES = (
    "fetch_freshnet.py",
    "freshnet_ingest.py",
    "ingest_freshnet.py",
    "download_freshnet.py",
)

_HF_DEP_MARKERS = frozenset(
    {
        "datasets",
        "huggingface-hub",
        "huggingface_hub",
    }
)

_FORBIDDEN_RUNTIME_IMPORT_ROOTS = frozenset(
    {
        "datasets",
        "huggingface_hub",
        "huggingface_hub.hf_api",
        "huggingface",
    }
)

_DATASET_ID = "Dingdong-Inc/FreshRetailNet-50K"
_LICENSE_MARKERS = ("CC BY 4.0", "CC-BY-4.0", "Creative Commons Attribution 4.0")


def _optional_extras() -> dict[str, list[str]]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    extras = data["project"].get("optional-dependencies") or {}
    assert isinstance(extras, dict)
    return {str(k): list(v) for k, v in extras.items()}


def _dep_names(specs: list[str]) -> set[str]:
    names: set[str] = set()
    for spec in specs:
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        if name:
            names.add(name)
    return names


def _core_dep_names() -> set[str]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    deps = data["project"].get("dependencies") or []
    assert isinstance(deps, list)
    return _dep_names([str(d) for d in deps])


def _find_freshnet_script() -> Path:
    """Resolve the documented FreshNet ingest script under ``scripts/``."""
    for name in _SCRIPT_NAME_CANDIDATES:
        path = _SCRIPTS / name
        if path.is_file():
            return path

    # Allow a differently named script if docstring/PROVENANCE names FreshNet.
    if _SCRIPTS.is_dir():
        for path in sorted(_SCRIPTS.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            if re.search(r"FreshRetailNet|FreshNet|freshnet", text, re.I):
                return path

    msg = (
        "T-078 FreshNet ingest script missing under scripts/; expected one of "
        f"{_SCRIPT_NAME_CANDIDATES} (or a *.py whose docstring mentions FreshNet)"
    )
    raise AssertionError(msg)


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
                roots.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
            roots.add(node.module)
    return roots


def _gitignore_matches(rel_path: str) -> bool:
    """Best-effort: path is covered by a committed .gitignore pattern."""
    text = _GITIGNORE.read_text(encoding="utf-8")
    patterns: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped.rstrip("/"))

    normalized = rel_path.strip("/").replace("\\", "/")
    parts = normalized.split("/")
    for pattern in patterns:
        pat = pattern.strip("/")
        if not pat:
            continue
        if normalized == pat or normalized.startswith(pat + "/"):
            return True
        # Directory patterns like ``.data/`` or ``data/raw/``
        if pat in parts:
            return True
        # Simple basename match (e.g. ``*.parquet`` not used here)
        if "/" not in pat and parts[-1] == pat:
            return True
    return False


def _cache_paths_mentioned(provenance: str) -> list[str]:
    """Extract likely cache/raw path tokens from PROVENANCE.md."""
    paths: list[str] = []
    # Explicit path-like tokens under data/, .data/, or cache dirs.
    for match in re.finditer(
        r"(?:\.?data/[A-Za-z0-9_./\-]+|cache/[A-Za-z0-9_./\-]+|"
        r"data/freshnet/[A-Za-z0-9_./\-]+)",
        provenance,
    ):
        token = match.group(0).rstrip(".,);:`'\"")
        if token not in paths:
            paths.append(token)
    return paths


# ---------------------------------------------------------------------------
# AC: optional [freshnet] extra; not core / [browser]
# ---------------------------------------------------------------------------


def test_pyproject_declares_freshnet_optional_extra_with_hf_deps() -> None:
    extras = _optional_extras()
    assert "freshnet" in extras, (
        "pyproject.toml must declare optional-dependencies.freshnet "
        f"(ADR 0115 / T-078); have {sorted(extras)}"
    )
    names = _dep_names(extras["freshnet"])
    assert names & _HF_DEP_MARKERS, (
        "[freshnet] must list HF/datasets (or huggingface-hub) deps; "
        f"got {sorted(names)}"
    )


def test_core_and_browser_extras_do_not_require_freshnet_hf_deps() -> None:
    core = _core_dep_names()
    leaking_core = core & _HF_DEP_MARKERS
    assert not leaking_core, (
        f"core dependencies must not require HF/datasets; found {sorted(leaking_core)}"
    )

    extras = _optional_extras()
    assert "browser" in extras or "slim" in extras or "pyodide" in extras
    for key in ("browser", "slim", "pyodide"):
        if key not in extras:
            continue
        names = _dep_names(extras[key])
        leaking = names & _HF_DEP_MARKERS
        assert not leaking, (
            f"[{key}] must not require HF/datasets; found {sorted(leaking)}"
        )


# ---------------------------------------------------------------------------
# AC: scripts/ ingest entry documented; missing deps → non-zero + clear msg
# ---------------------------------------------------------------------------


def test_freshnet_ingest_script_exists_under_scripts() -> None:
    path = _find_freshnet_script()
    assert path.is_file()
    assert path.parent == _SCRIPTS


def test_freshnet_ingest_script_is_documented() -> None:
    path = _find_freshnet_script()
    script_text = path.read_text(encoding="utf-8")
    documented_in_script = bool(
        re.search(r"FreshRetailNet|FreshNet|\[freshnet\]", script_text, re.I)
    )
    provenance_ok = False
    if _PROVENANCE.is_file():
        prov = _PROVENANCE.read_text(encoding="utf-8")
        provenance_ok = path.name in prov or "scripts/" in prov
    assert documented_in_script or provenance_ok, (
        f"{path.name} must document FreshNet / [freshnet] in its docstring "
        "or be referenced from data/freshnet/PROVENANCE.md"
    )


def test_freshnet_script_exits_nonzero_when_freshnet_deps_missing(
    tmp_path: Path,
) -> None:
    """Subprocess with blocked HF modules — no network download."""
    path = _find_freshnet_script()
    # Sitecustomize / -c prelude that blocks datasets / huggingface_hub before
    # the script runs. Offline only.
    blocker = tmp_path / "_block_hf.py"
    blocker.write_text(
        """\
import sys

class _Blocker:
    def find_spec(self, fullname, path=None, target=None):
        roots = ("datasets", "huggingface_hub", "huggingface")
        for root in roots:
            if fullname == root or fullname.startswith(root + "."):
                raise ImportError(f"blocked optional dependency: {fullname}")
        return None

sys.meta_path.insert(0, _Blocker())
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    # Ensure blocker loads first without requiring a site-packages install.
    env["PYTHONPATH"] = str(tmp_path) + os.pathsep + env.get("PYTHONPATH", "")
    # Point sitecustomize at our blocker by naming the file sitecustomize.py
    blocker.rename(tmp_path / "sitecustomize.py")

    proc = subprocess.run(
        [sys.executable, str(path)],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        env=env,
        timeout=30,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, (
        f"{path.name} must exit non-zero when [freshnet] deps are missing; "
        f"got rc=0 output={combined!r}"
    )
    assert re.search(
        r"freshnet|datasets|huggingface|optional|install|extra",
        combined,
        re.I,
    ), f"{path.name} must print a clear missing-deps message; got {combined!r}"


# ---------------------------------------------------------------------------
# AC: data/freshnet/PROVENANCE.md required fields
# ---------------------------------------------------------------------------


def test_freshnet_provenance_md_exists() -> None:
    assert _PROVENANCE.is_file(), (
        "data/freshnet/PROVENANCE.md must exist (ADR 0115 / T-078)"
    )


def test_freshnet_provenance_records_dataset_id_license_access_sku_rule() -> None:
    assert _PROVENANCE.is_file(), "PROVENANCE.md missing"
    text = _PROVENANCE.read_text(encoding="utf-8")

    assert _DATASET_ID in text, f"PROVENANCE.md must record dataset id {_DATASET_ID!r}"
    assert any(marker in text for marker in _LICENSE_MARKERS), (
        "PROVENANCE.md must record license CC BY 4.0 (or equivalent spelling)"
    )
    assert re.search(
        r"access|download|huggingface\.co|datasets\.load|hf://|hub",
        text,
        re.I,
    ), "PROVENANCE.md must record an access method"

    assert re.search(
        r"(download\s*date|fetched|revision|commit)",
        text,
        re.I,
    ), "PROVENANCE.md must include placeholder or filled download date / revision"

    assert re.search(
        r"SKU|management_group|selection\s+rule|selected\s+ID",
        text,
        re.I,
    ), "PROVENANCE.md must include SKU selection rule text (IDs may be TBD)"


# ---------------------------------------------------------------------------
# AC: import graph — blueberries_voi must not import datasets / HF
# ---------------------------------------------------------------------------


def test_package_init_source_has_no_datasets_or_huggingface_imports() -> None:
    init = _SRC / "__init__.py"
    assert init.is_file()
    forbidden = _imported_roots(init) & _FORBIDDEN_RUNTIME_IMPORT_ROOTS
    assert not forbidden, (
        f"blueberries_voi/__init__.py must not import {sorted(forbidden)} "
        "(ADR 0115 / T-078)"
    )


def test_importing_blueberries_voi_does_not_load_datasets_or_huggingface() -> None:
    # Drop any prior loads so we observe this import only.
    doomed = [
        key
        for key in list(sys.modules)
        if key == "blueberries_voi" or key.startswith("blueberries_voi.")
    ]
    for key in doomed:
        del sys.modules[key]

    before = {
        key
        for key in sys.modules
        if key == "datasets"
        or key.startswith("datasets.")
        or key == "huggingface_hub"
        or key.startswith("huggingface_hub.")
        or key == "huggingface"
        or key.startswith("huggingface.")
    }

    importlib.import_module("blueberries_voi")

    after = {
        key
        for key in sys.modules
        if key == "datasets"
        or key.startswith("datasets.")
        or key == "huggingface_hub"
        or key.startswith("huggingface_hub.")
        or key == "huggingface"
        or key.startswith("huggingface.")
    }
    newly = after - before
    assert not newly, (
        "importing blueberries_voi must not load datasets/huggingface hub "
        f"modules; newly loaded {sorted(newly)}"
    )


def test_src_package_tree_has_no_eager_hf_imports() -> None:
    """Static scan of installable package sources (not scripts/)."""
    offenders: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        hit = _imported_roots(path) & _FORBIDDEN_RUNTIME_IMPORT_ROOTS
        if hit:
            offenders.append(f"{path.relative_to(_REPO_ROOT)}:{sorted(hit)}")
    assert not offenders, (
        "installable blueberries_voi sources must not import HF/datasets; "
        f"found {offenders}"
    )


# ---------------------------------------------------------------------------
# AC: no demand_profile.json required (fit is T-080)
# ---------------------------------------------------------------------------


def test_demand_profile_json_not_required_for_t078_ingest() -> None:
    """T-078 ships ingest + PROVENANCE; fit artifact is T-080."""
    # Presence is allowed if someone lands early, but must not be required.
    if not _DEMAND_PROFILE.is_file():
        assert not _DEMAND_PROFILE.exists()
        return
    # If present, PROVENANCE / ticket scope still treats fit as separate.
    assert _PROVENANCE.is_file()
    text = _PROVENANCE.read_text(encoding="utf-8")
    # Soft honesty: do not treat demand_profile as the only T-078 deliverable.
    assert "PROVENANCE" in text or _DATASET_ID in text


# ---------------------------------------------------------------------------
# AC: raw cache path gitignored / documented
# ---------------------------------------------------------------------------


def test_freshnet_raw_cache_path_documented_and_gitignore_covered() -> None:
    assert _PROVENANCE.is_file(), "PROVENANCE.md missing"
    text = _PROVENANCE.read_text(encoding="utf-8")
    assert re.search(r"cache|raw|gitignor", text, re.I), (
        "PROVENANCE.md must document the raw/cache path (and that it is gitignored)"
    )
    candidates = _cache_paths_mentioned(text)
    # Prefer explicit paths; fall back to known boring defaults if named in prose.
    boring_defaults = (
        ".data/freshnet",
        "data/raw/freshnet",
        "data/freshnet/cache",
        "data/freshnet/raw",
        ".data/freshnet/cache",
    )
    mentioned_defaults = [p for p in boring_defaults if p in text]
    paths = candidates or mentioned_defaults
    assert paths, (
        "PROVENANCE.md must name a concrete raw/cache directory "
        "(e.g. .data/freshnet or data/freshnet/cache)"
    )
    covered = [p for p in paths if _gitignore_matches(p)]
    assert covered, (
        f"documented FreshNet cache path(s) {paths} must be covered by "
        ".gitignore (do not commit multi-GB raw dumps)"
    )
