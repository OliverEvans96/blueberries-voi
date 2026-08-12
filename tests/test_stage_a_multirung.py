"""T-016 Multi-rung Stage A (shared CRN) — RED / acceptance contracts.

Locks library API + result schema + documentation hooks without running full
Stage A grids (no expensive episode sweeps in this module).
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_type_hints

import pytest

if TYPE_CHECKING:
    from blueberries_voi.filter.types import ScenarioId

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXPERIMENTS = _REPO_ROOT / "experiments"
_FIG_M25 = _REPO_ROOT / "figures" / "m2.5"
_FIG_README = _FIG_M25 / "README.md"
_RESULT_MD = _EXPERIMENTS / "m25_stage_a_result.md"

# Spec / plan §4.1: six data-availability rungs under shared CRN.
_EXPECTED_RUNGS: tuple[ScenarioId, ...] = ("P0", "P1", "F1", "F1s", "F2a", "F2")
_DEFAULT_MARGIN = 0.05

# Module candidates for the indicative interface in .team/specs/T-016.md.
_API_MODULES = (
    "blueberries_voi.viz.m25",
    "blueberries_voi.viz.stage_a",
    "blueberries_voi.viz.fil11",
    "blueberries_voi.viz",
)


def _load_attr(attr: str) -> Any | None:
    for name in _API_MODULES:
        try:
            mod = importlib.import_module(name)
        except ImportError:
            continue
        found = getattr(mod, attr, None)
        if found is not None:
            return found
    return None


def _resolve(attr: str) -> Any:
    found = _load_attr(attr)
    assert found is not None, (
        f"{attr} must be exported for T-016 (see .team/specs/T-016.md); "
        f"tried modules {_API_MODULES}"
    )
    return found


def _field_names(cls: Any) -> set[str]:
    hints = getattr(cls, "__annotations__", None)
    if isinstance(hints, dict) and hints:
        return set(hints)
    try:
        return set(get_type_hints(cls))
    except Exception:  # pragma: no cover - defensive for incomplete stubs
        return set()


def test_stage_a_rung_result_schema_fields() -> None:
    """Each rung reports prior/posterior SD, contracted flag, tight-control flag."""
    cls = _resolve("StageARungResult")
    fields = _field_names(cls)
    required = {
        "scenario",
        "prior_sd",
        "posterior_sd",
        "contracted",
        "tight_control_collapsed",
    }
    missing = required - fields
    assert not missing, f"StageARungResult missing fields: {sorted(missing)}"


def test_stage_a_multi_result_schema_fields() -> None:
    """Aggregate result carries rows, shared root_seed, and figure_dir."""
    cls = _resolve("StageAMultiResult")
    fields = _field_names(cls)
    required = {"rows", "root_seed", "figure_dir"}
    missing = required - fields
    assert not missing, f"StageAMultiResult missing fields: {sorted(missing)}"


def test_run_m25_stage_a_exported() -> None:
    fn = _resolve("run_m25_stage_a")
    assert callable(fn)


def test_run_m25_stage_a_default_rungs_cover_six_scenarios() -> None:
    """Runnable experiment covers {P0, P1, F1, F1s, F2a, F2} by default."""
    fn = _resolve("run_m25_stage_a")
    sig = inspect.signature(fn)
    assert "rungs" in sig.parameters, "run_m25_stage_a must accept rungs="
    default = sig.parameters["rungs"].default
    assert default is not inspect.Parameter.empty, "rungs must have a default"
    assert tuple(default) == _EXPECTED_RUNGS


def test_run_m25_stage_a_default_contraction_margin() -> None:
    """Documented margin e.g. ≥5% SD contraction (plan §4.1 / spec)."""
    fn = _resolve("run_m25_stage_a")
    sig = inspect.signature(fn)
    assert "contraction_margin" in sig.parameters
    default = sig.parameters["contraction_margin"].default
    assert default is not inspect.Parameter.empty
    assert float(default) == pytest.approx(_DEFAULT_MARGIN)


def test_run_m25_stage_a_accepts_shared_root_seed() -> None:
    """Shared CRN: same root_seed / SIM-05 streams; only observation mask differs."""
    fn = _resolve("run_m25_stage_a")
    sig = inspect.signature(fn)
    assert "root_seed" in sig.parameters
    assert sig.parameters["root_seed"].kind in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


def test_cohort_from_birth_metric_documented() -> None:
    """Cohort-from-birth metric must be named/documented (not oldest-slot-only)."""
    # Prefer an explicit export; fall back to module docstring / constant text.
    metric = _load_attr("COHORT_FROM_BIRTH_METRIC")
    doc_hook = _load_attr("STAGE_A_METRIC_DOC")
    mod = None
    for name in _API_MODULES:
        try:
            mod = importlib.import_module(name)
            break
        except ImportError:
            continue

    text_blobs: list[str] = []
    if metric is not None:
        text_blobs.append(str(metric))
    if doc_hook is not None:
        text_blobs.append(str(doc_hook))
    if mod is not None:
        text_blobs.append(inspect.getdoc(mod) or "")
        for attr in ("run_m25_stage_a", "StageARungResult", "StageAMultiResult"):
            obj = getattr(mod, attr, None)
            if obj is not None:
                text_blobs.append(inspect.getdoc(obj) or "")

    joined = "\n".join(text_blobs).lower()
    has_metric_doc = (
        metric is not None
        or doc_hook is not None
        or "cohort-from-birth" in joined
        or "cohort from birth" in joined
    )
    assert has_metric_doc, (
        "T-016 requires a documented cohort-from-birth Stage A metric "
        "(export COHORT_FROM_BIRTH_METRIC / STAGE_A_METRIC_DOC or document in viz.m25)"
    )
    assert "oldest-slot" not in joined or "not oldest" in joined or "avoid" in joined, (
        "cohort-from-birth docs must not endorse oldest-slot-only as the Stage A metric"
    )


def test_p0_p1_fail_allowed_documentation_hook() -> None:
    """P0/P1 FAIL is allowed if documented; must not be papered over as a gate."""
    hook = _load_attr("STAGE_A_P0_P1_FAIL_ALLOWED")
    narrative = _load_attr("STAGE_A_PASS_FAIL_NARRATIVE")
    assert hook is not None or narrative is not None, (
        "Export STAGE_A_P0_P1_FAIL_ALLOWED and/or STAGE_A_PASS_FAIL_NARRATIVE "
        "(T-016 / plan §4.5: P0/P1 fail OK if documented)"
    )
    if hook is not None:
        assert hook is True or str(hook).lower() in {"true", "allowed", "yes"}
    if narrative is not None:
        text = str(narrative).lower()
        assert "p0" in text and "p1" in text
        assert "fail" in text and (
            "allow" in text or "ok" in text or "optional" in text
        )
        # Higher-rung honesty: F2a/F2 should PASS language present when narrated.
        assert "f2" in text


def test_higher_rung_expectations_documented() -> None:
    """F2a/F2 should PASS; failures need-human, not papered over (plan §4.5)."""
    narrative = _resolve("STAGE_A_PASS_FAIL_NARRATIVE")
    text = str(narrative).lower()
    assert "f2a" in text or "f2" in text
    assert "pass" in text
    assert any(
        token in text for token in ("needs-human", "need-human", "honest", "document")
    ), "Higher-rung fail narrative must require honest / needs-human handling"


def test_result_md_convention_and_p0_p1_fail_language() -> None:
    """Result MD path convention + P0/P1 fail-allowed language when published.

    Library may expose RESULT_MD_PATH before the experiment is run; if the MD
    exists, it must state P0/P1 FAIL is allowed.
    """
    path_hook = _load_attr("STAGE_A_RESULT_MD_PATH")
    if path_hook is not None:
        path = Path(path_hook)
        if not path.is_absolute():
            path = _REPO_ROOT / path
    else:
        path = _RESULT_MD

    # Contract: documented default path is experiments/m25_stage_a_result.md
    assert path.name == "m25_stage_a_result.md", (
        f"Stage A result MD must be named m25_stage_a_result.md, got {path.name!r}"
    )
    assert "experiments" in path.parts, (
        f"Result MD must live under experiments/: {path}"
    )

    if not path.is_file():
        # RED is OK until the experiment publishes; require the path hook so
        # implementers lock the convention before running grids.
        assert path_hook is not None, (
            "Export STAGE_A_RESULT_MD_PATH pointing at "
            "experiments/m25_stage_a_result.md "
            "(or publish that file with P0/P1 fail-allowed language)"
        )
        return

    body = path.read_text(encoding="utf-8").lower()
    assert re.search(r"\|.*p0.*\|", body) or "p0" in body
    assert "p1" in body
    assert "fail" in body and (
        "allow" in body or "allowed" in body or "optional" in body or "ok" in body
    ), "Published Stage A result MD must document that P0/P1 FAIL is allowed"


def test_figures_readme_maps_stage_a_rungs() -> None:
    """Figures land under figures/m2.5/ with README mapping figure → rung / FIL-11."""
    assert _FIG_README.is_file(), f"missing {_FIG_README}"
    body = _FIG_README.read_text(encoding="utf-8").lower()
    assert "stage a" in body or "stage_a" in body, (
        "figures/m2.5/README.md must document Stage A multi-rung figures"
    )
    for rung in _EXPECTED_RUNGS:
        assert rung.lower() in body, (
            f"figures/m2.5/README.md must map figures to rung {rung}"
        )
    assert "fil-11" in body or "fil11" in body


def test_no_voi_dollars_or_ctl_in_stage_a_surface() -> None:
    """Does not claim VOI dollars; no CTL code on the Stage A surface."""
    blobs: list[str] = []
    for name in _API_MODULES[:2]:  # m25 / stage_a only (fil11 predates T-016)
        try:
            mod = importlib.import_module(name)
        except ImportError:
            continue
        blobs.append(inspect.getdoc(mod) or "")
        try:
            src_path = Path(inspect.getsourcefile(mod) or "")
        except TypeError:
            src_path = Path()
        if src_path.is_file():
            blobs.append(src_path.read_text(encoding="utf-8"))

    # If the module does not exist yet, require export so green phase creates it
    # without VOI/CTL claims — fail for missing surface first.
    if not blobs:
        pytest.fail(
            "blueberries_voi.viz.m25 (or viz.stage_a) must exist for T-016 Stage A "
            "surface; must not claim VOI dollars or include CTL code"
        )

    joined = "\n".join(blobs)
    voi_pat = r"\bVOI\s*\$|\bvoi_dollars\b|\bvalue of information \(\$\)"
    assert not re.search(voi_pat, joined, re.I)
    assert not re.search(r"\bCTL\b|causal.?tree|uplift.?tree", joined, re.I)


def test_empty_rungs_rejected() -> None:
    fn = _resolve("run_m25_stage_a")
    with pytest.raises((ValueError, TypeError)):
        fn(root_seed=0, rungs=())


def test_unknown_rung_rejected() -> None:
    fn = _resolve("run_m25_stage_a")
    with pytest.raises((ValueError, KeyError, TypeError)):
        fn(root_seed=0, rungs=("NOT_A_RUNG",))


def test_contraction_margin_boundaries() -> None:
    """Margin must be in (0, 1); reject non-positive and ≥1."""
    fn = _resolve("run_m25_stage_a")
    with pytest.raises((ValueError, AssertionError)):
        fn(root_seed=0, rungs=("P0",), contraction_margin=0.0)
    with pytest.raises((ValueError, AssertionError)):
        fn(root_seed=0, rungs=("P0",), contraction_margin=1.0)
    with pytest.raises((ValueError, AssertionError)):
        fn(root_seed=0, rungs=("P0",), contraction_margin=-0.05)
