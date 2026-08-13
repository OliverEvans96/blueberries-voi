"""T-080 CAL-B2 - Fit demand_profile.json (RED).

Locks ADR 0112 / ``.team/specs/T-080.md`` before the fit script and committed
derived product land:

* committed ``data/freshnet/demand_profile.json`` (versioned schema, DOWxweek,
  ``scale_target_mu`` ~ 30, ``demand_vm``)
* fit report beside the profile (SKU IDs, censoring, V/M, Mar-Jun honesty)
* ``PROVENANCE.md`` updated with final SKU list + pointers to profile + report
* ``scripts/fit_freshnet_demand.py`` (or equivalent) requiring ``[freshnet]``
* pytest asserts the committed JSON only - no live Hugging Face download
* no HF import from installable package runtime modules

Offline assertions only. Do not run the fit or pull HF in these tests.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROVENANCE = _REPO_ROOT / "data" / "freshnet" / "PROVENANCE.md"
_DEMAND_PROFILE = _REPO_ROOT / "data" / "freshnet" / "demand_profile.json"
_SCRIPTS = _REPO_ROOT / "scripts"
_SRC = _REPO_ROOT / "src" / "blueberries_voi"
_FRESHNET_DIR = _REPO_ROOT / "data" / "freshnet"

# Spec illustrative target; AC: pick one tol and test it - absolute +/-1.
_SCALE_TARGET_MU = 30.0
_SCALE_ABS_TOL = 1.0

# Committed derived product must stay git-friendly (not a raw HF dump).
_MAX_PROFILE_BYTES = 512 * 1024  # 512 KiB

_FIT_SCRIPT_CANDIDATES = (
    "fit_freshnet_demand.py",
    "fit_freshnet.py",
    "fit_demand_profile.py",
)

_FIT_REPORT_CANDIDATES = (
    "fit_report.md",
    "fit_report.json",
    "demand_fit_report.md",
    "demand_fit_report.json",
)

_FORBIDDEN_RUNTIME_IMPORT_ROOTS = frozenset(
    {
        "datasets",
        "huggingface_hub",
        "huggingface_hub.hf_api",
        "huggingface",
    }
)

# Keys that signal DOW structure / week (or month) structure.
_DOW_KEY_MARKERS = (
    "dow_factors",
    "dow",
    "day_of_week",
    "weekday",
    "dow_means",
    "dow_multipliers",
)
_WEEK_KEY_MARKERS = (
    "week_factors",
    "week",
    "week_index",
    "week_of_year",
    "month_factors",
    "month",
    "week_means",
    "week_multipliers",
)
_TABLE_KEY_MARKERS = (
    "dow_week",
    "mu_table",
    "mean_table",
    "demand_table",
    "factors_table",
    "calendar_means",
)


def _find_fit_script() -> Path:
    for name in _FIT_SCRIPT_CANDIDATES:
        path = _SCRIPTS / name
        if path.is_file():
            return path

    # Fallback: a differently named script that clearly owns the *fit*, not
    # ingest/fetch (fetch_freshnet.py mentions demand_profile.json as OOS).
    _ingest_names = {
        "fetch_freshnet.py",
        "freshnet_ingest.py",
        "ingest_freshnet.py",
        "download_freshnet.py",
    }
    if _SCRIPTS.is_dir():
        for path in sorted(_SCRIPTS.glob("*.py")):
            if path.name in _ingest_names:
                continue
            text = path.read_text(encoding="utf-8")
            produces_fit = bool(
                re.search(
                    r"(writes?|produces?|fit(?:s|ting)?)\s+.*demand_profile\.json"
                    r"|demand_profile\.json.*(?:fit|write|output)",
                    text,
                    re.I,
                )
            )
            mentions_freshnet = bool(
                re.search(r"FreshNet|FreshRetailNet|freshnet", text, re.I)
            )
            # Reject scripts that only say fit is out of scope / separate ticket.
            defers_fit = bool(
                re.search(
                    r"does\s+not\s+fit|out\s+of\s+scope|separate\s+ticket\s*\(?T-080",
                    text,
                    re.I,
                )
            )
            if produces_fit and mentions_freshnet and not defers_fit:
                return path

    msg = (
        "T-080 FreshNet fit script missing under scripts/; expected one of "
        f"{_FIT_SCRIPT_CANDIDATES} (or a *.py that documents fitting "
        "demand_profile.json)"
    )
    raise AssertionError(msg)


def _find_fit_report() -> Path:
    for name in _FIT_REPORT_CANDIDATES:
        path = _FRESHNET_DIR / name
        if path.is_file():
            return path

    # Allow a differently named report if it mentions fit / SKU / censoring.
    if _FRESHNET_DIR.is_dir():
        for path in sorted(_FRESHNET_DIR.iterdir()):
            if path.suffix.lower() not in {".md", ".json"}:
                continue
            if path.name in {"PROVENANCE.md", "demand_profile.json"}:
                continue
            text = path.read_text(encoding="utf-8")
            if re.search(r"SKU|censor|Mar.?Jun|demand_vm|V/?M", text, re.I):
                return path

    msg = (
        "T-080 fit report missing beside the profile; expected one of "
        f"{[str(_FRESHNET_DIR / n) for n in _FIT_REPORT_CANDIDATES]}"
    )
    raise AssertionError(msg)


def _load_profile() -> dict[str, Any]:
    assert _DEMAND_PROFILE.is_file(), (
        "data/freshnet/demand_profile.json must exist and be committed "
        "(ADR 0112 / T-080); pytest reads this artifact - no HF download"
    )
    raw = _DEMAND_PROFILE.read_bytes()
    assert len(raw) <= _MAX_PROFILE_BYTES, (
        f"demand_profile.json is {len(raw)} bytes; must stay small for git "
        f"(≤{_MAX_PROFILE_BYTES}), not a raw HF dump"
    )
    data = json.loads(raw.decode("utf-8"))
    assert isinstance(data, dict), "demand_profile.json root must be a JSON object"
    return data


def _profile_keys_lower(profile: dict[str, Any]) -> dict[str, Any]:
    return {str(k).lower(): v for k, v in profile.items()}


def _has_marker_key(keys: set[str], markers: tuple[str, ...]) -> bool:
    for key in keys:
        for marker in markers:
            if marker in key:
                return True
    return False


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


def _extract_sku_ids(text: str) -> list[str]:
    """Pull concrete SKU / product id tokens (not TBD placeholders)."""
    ids: list[str] = []
    # Bullet / comma lists of numeric or alphanumeric opaque IDs.
    for match in re.finditer(
        r"(?:SKU|product|item)[_\s-]*(?:ID|id)?s?\s*[:：]\s*([^\n]+)",
        text,
        re.I,
    ):
        chunk = match.group(1)
        if re.search(r"\bTBD\b|_TBD|placeholder", chunk, re.I):
            continue
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-]{1,}", chunk):
            if token.lower() in {"sku", "id", "ids", "selected", "list", "and"}:
                continue
            if token not in ids:
                ids.append(token)
    # Bracket / backtick lists: [`123`, `456`] or [123, 456]
    for match in re.finditer(
        r"selected\s+SKU[^\n]*?(?:\[[^\]]+\]|`[^`]+`(?:,\s*`[^`]+`)+)",
        text,
        re.I,
    ):
        for token in re.findall(r"[A-Za-z0-9_\-]{2,}", match.group(0)):
            if token.lower() in {"selected", "sku", "ids", "id"}:
                continue
            if token not in ids:
                ids.append(token)
    return ids


# ---------------------------------------------------------------------------
# AC: committed demand_profile.json - versioned schema, DOWxweek, μ~30, V/M
# ---------------------------------------------------------------------------


def test_demand_profile_json_exists_and_is_git_sized() -> None:
    assert _DEMAND_PROFILE.is_file(), (
        "committed data/freshnet/demand_profile.json is required (T-080)"
    )
    size = _DEMAND_PROFILE.stat().st_size
    assert 0 < size <= _MAX_PROFILE_BYTES, (
        f"demand_profile.json size {size} must be non-empty and ≤ "
        f"{_MAX_PROFILE_BYTES} bytes (git-suitable derived product)"
    )


def test_demand_profile_schema_is_versioned() -> None:
    profile = _load_profile()
    keys = _profile_keys_lower(profile)
    version = None
    for candidate in ("schema_version", "schema", "version"):
        if candidate in keys:
            version = keys[candidate]
            break
    assert version is not None, (
        "demand_profile.json must include a versioned schema field "
        "(e.g. schema_version) so T-082 can validate"
    )
    if isinstance(version, str):
        assert version.strip(), "schema version string must be non-empty"
    else:
        assert isinstance(version, (int, float)), (
            f"schema_version must be int/float/str; got {type(version).__name__}"
        )
        assert int(version) >= 1


def test_demand_profile_encodes_dow_by_week_structure() -> None:
    profile = _load_profile()
    keys = {str(k).lower() for k in profile}
    has_dow = _has_marker_key(keys, _DOW_KEY_MARKERS)
    has_week = _has_marker_key(keys, _WEEK_KEY_MARKERS)
    has_table = _has_marker_key(keys, _TABLE_KEY_MARKERS)
    assert has_table or (has_dow and has_week), (
        "demand_profile.json must encode day-of-week x week-index (or month) "
        "structure via dow_factors/week_factors (or equivalent) or a DOWxweek "
        f"table; keys present: {sorted(keys)}"
    )

    # At least one factor / table value must be a non-empty sequence or mapping.
    lowered = _profile_keys_lower(profile)
    structural_values = [
        v
        for k, v in lowered.items()
        if _has_marker_key(
            {k}, _DOW_KEY_MARKERS + _WEEK_KEY_MARKERS + _TABLE_KEY_MARKERS
        )
    ]
    assert structural_values, "DOW/week keys present but no structural values"
    nonempty = False
    for value in structural_values:
        if (isinstance(value, (list, tuple)) and len(value) > 0) or (
            isinstance(value, dict) and len(value) > 0
        ):
            nonempty = True
    assert nonempty, "DOWxweek factors / table must be non-empty sequences or mappings"


def test_demand_profile_scale_target_mu_near_30() -> None:
    """Operational scale target ~ 30; absolute +/-1 (documented in fit report)."""
    profile = _load_profile()
    keys = _profile_keys_lower(profile)
    assert "scale_target_mu" in keys, (
        "demand_profile.json must record scale_target_mu (operational μ~30)"
    )
    mu = float(keys["scale_target_mu"])
    assert abs(mu - _SCALE_TARGET_MU) <= _SCALE_ABS_TOL, (
        f"scale_target_mu={mu} must be within +/-{_SCALE_ABS_TOL} of "
        f"{_SCALE_TARGET_MU} (T-080 / ADR 0112)"
    )


def test_demand_profile_records_demand_vm() -> None:
    profile = _load_profile()
    keys = _profile_keys_lower(profile)
    vm_key = None
    for candidate in ("demand_vm", "vm", "variance_to_mean", "v_over_m"):
        if candidate in keys:
            vm_key = candidate
            break
    assert vm_key is not None, (
        "demand_profile.json must record demand_vm (V/M; refit or keep 2.0)"
    )
    vm = float(keys[vm_key])
    assert vm > 0.0, f"demand_vm must be positive; got {vm}"


def test_fit_report_documents_scale_tolerance_matching_tests() -> None:
    """AC: pick one tol (+/-1 or +/-5%) and document it - we lock absolute +/-1."""
    report = _find_fit_report()
    text = report.read_text(encoding="utf-8")
    assert re.search(
        r"(+/-\s*1|within\s*1|abs(?:olute)?\s*tol(?:erance)?\s*[:=]?\s*1|"
        r"tolerance[^\n]{0,40}+/-?\s*1)",
        text,
        re.I,
    ), (
        f"{report.name} must document the operational-μ tolerance used for "
        f"scale_target_mu~30 (tests lock absolute +/-{_SCALE_ABS_TOL})"
    )


# ---------------------------------------------------------------------------
# AC: fit report - SKUs, censoring, V/M, Mar-Jun honesty
# ---------------------------------------------------------------------------


def test_fit_report_artifact_exists_beside_profile() -> None:
    report = _find_fit_report()
    assert report.is_file()
    assert report.parent == _FRESHNET_DIR


def test_fit_report_records_sku_ids_censoring_vm_and_mar_jun_honesty() -> None:
    report = _find_fit_report()
    text = report.read_text(encoding="utf-8")

    sku_ids = _extract_sku_ids(text)
    assert sku_ids or re.search(
        r"selected\s+SKU|SKU\s+ID\s*list|product_id",
        text,
        re.I,
    ), f"{report.name} must record selected SKU IDs"
    # Reject pure TBD placeholders when an ID list section exists.
    assert not re.search(
        r"Selected\s+SKU\s+IDs?\s*:\s*_?TBD\b",
        text,
        re.I,
    ), f"{report.name} must list concrete SKU IDs (not TBD placeholders)"

    assert re.search(
        r"censor|stock_hour6_22_cnt|stockout",
        text,
        re.I,
    ), f"{report.name} must record the censoring rule applied"

    assert re.search(
        r"\bV/?M\b|demand_vm|variance[\s_-]*to[\s_-]*mean|refit|keep\s*2\.0",
        text,
        re.I,
    ), f"{report.name} must record V/M choice (refit or keep 2.0)"

    assert re.search(
        r"Mar\s*[---/]\s*Jun|March\s*[---/]\s*June|Mar.?Jun",
        text,
        re.I,
    ), (
        f"{report.name} must record Mar-Jun seasonality honesty "
        "(window-only; not full annual)"
    )


# ---------------------------------------------------------------------------
# AC: PROVENANCE updated with SKU list + pointers
# ---------------------------------------------------------------------------


def test_provenance_lists_final_sku_ids() -> None:
    assert _PROVENANCE.is_file(), "data/freshnet/PROVENANCE.md must exist"
    text = _PROVENANCE.read_text(encoding="utf-8")
    assert not re.search(
        r"Selected\s+SKU\s+IDs?\s*:\s*_?TBD\b",
        text,
        re.I,
    ), (
        "PROVENANCE.md must replace TBD SKU placeholders with the final "
        "selected ID list (T-080)"
    )
    sku_ids = _extract_sku_ids(text)
    assert sku_ids or re.search(
        r"(?:selected\s+)?SKU\s+IDs?\s*:\s*[`\[]?\s*\d",
        text,
        re.I,
    ), "PROVENANCE.md must record a concrete final SKU ID list"


def test_provenance_points_to_profile_and_fit_report() -> None:
    assert _PROVENANCE.is_file(), "data/freshnet/PROVENANCE.md must exist"
    text = _PROVENANCE.read_text(encoding="utf-8")
    assert "demand_profile.json" in text, (
        "PROVENANCE.md must point to demand_profile.json"
    )
    report = _find_fit_report()
    assert report.name in text or "fit_report" in text.lower(), (
        f"PROVENANCE.md must point to the fit report ({report.name})"
    )


# ---------------------------------------------------------------------------
# AC: fit script under scripts/ requiring [freshnet]
# ---------------------------------------------------------------------------


def test_fit_freshnet_demand_script_exists_under_scripts() -> None:
    path = _find_fit_script()
    assert path.is_file()
    assert path.parent == _SCRIPTS


def test_fit_script_documents_freshnet_extra_requirement() -> None:
    path = _find_fit_script()
    text = path.read_text(encoding="utf-8")
    assert re.search(r"\[freshnet\]|freshnet", text, re.I), (
        f"{path.name} must document that it requires the [freshnet] extra"
    )
    assert re.search(r"demand_profile\.json", text), (
        f"{path.name} must mention producing demand_profile.json"
    )


def test_fit_script_exits_nonzero_when_freshnet_deps_missing(
    tmp_path: Path,
) -> None:
    """Subprocess with blocked HF modules - no network download."""
    path = _find_fit_script()
    blocker = tmp_path / "sitecustomize.py"
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
    env["PYTHONPATH"] = str(tmp_path) + os.pathsep + env.get("PYTHONPATH", "")

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
# AC: pytest does not require live HF download; committed JSON is SoT
# ---------------------------------------------------------------------------


def test_this_module_does_not_import_huggingface_or_datasets() -> None:
    """CI pytest path must not pull HF - only assert committed artifacts."""
    this_file = Path(__file__).resolve()
    roots = _imported_roots(this_file)
    forbidden = roots & _FORBIDDEN_RUNTIME_IMPORT_ROOTS
    assert not forbidden, (
        "test_t080 must not import HF/datasets; tests assert committed JSON "
        f"only; found {sorted(forbidden)}"
    )


def test_demand_profile_loads_without_network_or_freshnet_extra() -> None:
    """Committed JSON is the source of truth - no hub I/O to exercise it."""
    profile = _load_profile()
    keys = _profile_keys_lower(profile)
    assert "schema_version" in keys or "schema" in keys or "version" in keys
    assert "scale_target_mu" in keys
    assert any(k in keys for k in ("demand_vm", "vm", "variance_to_mean", "v_over_m"))


# ---------------------------------------------------------------------------
# AC: no HF import from package runtime modules
# ---------------------------------------------------------------------------


def test_src_package_tree_has_no_hf_imports() -> None:
    offenders: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        hit = _imported_roots(path) & _FORBIDDEN_RUNTIME_IMPORT_ROOTS
        if hit:
            offenders.append(f"{path.relative_to(_REPO_ROOT)}:{sorted(hit)}")
    assert not offenders, (
        "installable blueberries_voi sources must not import HF/datasets; "
        f"found {offenders}"
    )
