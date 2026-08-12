"""T-017 Stage B per passing rung + oracle ladder — RED / acceptance contracts.

Locks library API + result schema + diagnostic / gap-table hooks without running
full Stage B calibration grids or expensive episode sweeps.
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

# Spec / plan §4.2: Stage B on rungs Stage A can evaluate (same six).
_STAGE_B_RUNGS: tuple[ScenarioId, ...] = ("P0", "P1", "F1", "F1s", "F2a", "F2")
# Spec / plan §4.4: shared-CRN oracle compare defaults.
_ORACLE_COMPARE_DEFAULT: tuple[ScenarioId, ...] = ("P1", "F2")
# Documented band around nominal 90% (M1 Stage B / fil11 precedent).
_COVERAGE_LO = 0.70
_COVERAGE_HI = 0.99

_API_MODULES = (
    "blueberries_voi.viz.m25",
    "blueberries_voi.viz.stage_b",
    "blueberries_voi.viz.oracle",
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
        f"{attr} must be exported for T-017 (see .team/specs/T-017.md); "
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


def _m25_surface_blobs() -> list[str]:
    """Source/docs for m25 / stage_b / oracle surfaces (not legacy fil11 alone)."""
    blobs: list[str] = []
    for name in _API_MODULES[:3]:
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
    return blobs


# ---------------------------------------------------------------------------
# Stage B calibration API (spec interfaces)
# ---------------------------------------------------------------------------


def test_stage_b_rung_result_schema_fields() -> None:
    """Per-rung Stage B reports scenario, coverage_90, diagnostic_only, figure_path."""
    cls = _resolve("StageBRungResult")
    fields = _field_names(cls)
    required = {"scenario", "coverage_90", "diagnostic_only", "figure_path"}
    missing = required - fields
    assert not missing, f"StageBRungResult missing fields: {sorted(missing)}"


def test_run_m25_stage_b_exported() -> None:
    fn = _resolve("run_m25_stage_b")
    assert callable(fn)


def test_run_m25_stage_b_accepts_rungs() -> None:
    fn = _resolve("run_m25_stage_b")
    sig = inspect.signature(fn)
    assert "rungs" in sig.parameters, "run_m25_stage_b must accept rungs="


def test_run_m25_stage_b_accepts_shared_root_seed() -> None:
    """Shared CRN across rungs (plan §4 / SIM-05); only mask differs."""
    fn = _resolve("run_m25_stage_b")
    sig = inspect.signature(fn)
    assert "root_seed" in sig.parameters
    assert sig.parameters["root_seed"].kind in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


def test_run_m25_stage_b_accepts_stage_a_pass_map() -> None:
    """Stage B must know which Stage A rungs passed (full vs diagnostic-only)."""
    fn = _resolve("run_m25_stage_b")
    sig = inspect.signature(fn)
    markers = {"stage_a_pass", "stage_a_passed", "a_pass", "passed_rungs"}
    assert markers & set(sig.parameters), (
        "run_m25_stage_b must accept a Stage A pass map "
        f"(one of {sorted(markers)}) so A-failing rungs can be diagnostic-only"
    )


def test_coverage_band_documented_around_90() -> None:
    """Pass language: coverage within a documented band around nominal 90%."""
    lo = _load_attr("STAGE_B_COVERAGE_LO")
    hi = _load_attr("STAGE_B_COVERAGE_HI")
    band = _load_attr("STAGE_B_COVERAGE_BAND")
    assert lo is not None or hi is not None or band is not None, (
        "Export STAGE_B_COVERAGE_LO/HI (or STAGE_B_COVERAGE_BAND) documenting "
        "the band around 90% (M1 precedent ≈ [0.70, 0.99])"
    )
    if lo is not None and hi is not None:
        assert float(lo) < 0.90 < float(hi)
        assert float(lo) == pytest.approx(_COVERAGE_LO) or float(lo) <= 0.90
        assert float(hi) == pytest.approx(_COVERAGE_HI) or float(hi) >= 0.90


def test_rank_histogram_pass_rule_documented() -> None:
    """Ranks must not be strongly U-shaped or dome-shaped (metric or doc rule)."""
    rule = _load_attr("STAGE_B_RANK_FLATNESS_RULE")
    narrative = _load_attr("STAGE_B_PASS_FAIL_NARRATIVE")
    blobs = [str(rule or ""), str(narrative or "")]
    blobs.extend(_m25_surface_blobs())
    joined = "\n".join(blobs).lower()
    shape_ok = "u-shaped" in joined or "u shaped" in joined or "dome" in joined
    assert (
        rule is not None or narrative is not None or ("rank" in joined and shape_ok)
    ), (
        "Export STAGE_B_RANK_FLATNESS_RULE and/or STAGE_B_PASS_FAIL_NARRATIVE "
        "describing non-U / non-dome rank histogram pass language (plan §4.2)"
    )


def test_diagnostic_only_labeling_for_a_failing_rungs() -> None:
    """A-failing rungs: Stage B skipped or labeled diagnostic only (M1 pattern)."""
    hook = _load_attr("STAGE_B_DIAGNOSTIC_ONLY_LABEL")
    narrative = _load_attr("STAGE_B_PASS_FAIL_NARRATIVE")
    assert hook is not None or narrative is not None, (
        "Export STAGE_B_DIAGNOSTIC_ONLY_LABEL and/or STAGE_B_PASS_FAIL_NARRATIVE "
        "so A-failing rungs are clearly diagnostic-only in MD"
    )
    text = str(hook if hook is not None else narrative).lower()
    assert "diagnostic" in text
    assert "only" in text or "fail" in text or "a-fail" in text or "stage a" in text


def test_stage_b_result_md_path_convention() -> None:
    """Result MD under experiments/m25_stage_b_*.md (spec)."""
    path_hook = _load_attr("STAGE_B_RESULT_MD_PATH")
    if path_hook is not None:
        path = Path(path_hook)
        if not path.is_absolute():
            path = _REPO_ROOT / path
    else:
        # Accept either a single aggregate or glob-style convention name.
        candidates = sorted(_EXPERIMENTS.glob("m25_stage_b_*.md"))
        path = candidates[0] if candidates else _EXPERIMENTS / "m25_stage_b_result.md"

    assert path.name.startswith("m25_stage_b"), (
        f"Stage B result MD must be named m25_stage_b_*.md, got {path.name!r}"
    )
    assert path.suffix == ".md"
    assert "experiments" in path.parts, (
        f"Result MD must live under experiments/: {path}"
    )

    if not path.is_file():
        assert path_hook is not None, (
            "Export STAGE_B_RESULT_MD_PATH pointing at experiments/m25_stage_b_*.md "
            "(or publish that file with diagnostic / coverage language)"
        )
        return

    body = path.read_text(encoding="utf-8").lower()
    assert "coverage" in body or "90%" in body or "0.9" in body
    # If any A-failing rung is discussed, diagnostic labeling must appear.
    if "p0" in body or "p1" in body:
        assert "diagnostic" in body, (
            "Published Stage B MD must label A-failing / P0-P1 runs as diagnostic "
            "when those rungs appear"
        )


def test_figures_readme_maps_stage_b_and_oracle() -> None:
    """Figures under figures/m2.5/ with README mapping Stage B / oracle artifacts."""
    assert _FIG_README.is_file(), f"missing {_FIG_README}"
    body = _FIG_README.read_text(encoding="utf-8").lower()
    assert "stage b" in body or "stage_b" in body, (
        "figures/m2.5/README.md must document Stage B multi-rung figures"
    )
    assert "rank" in body or "calibration" in body or "coverage" in body
    assert "oracle" in body or "b-state" in body or "b_state" in body, (
        "figures/m2.5/README.md must document oracle ladder / B-state gap figures"
    )
    assert "fil-11" in body or "fil11" in body


def test_no_voi_or_ctl_in_stage_b_oracle_surface() -> None:
    """No CTL / VOI sweep code on the Stage B + oracle surface (spec)."""
    blobs = _m25_surface_blobs()
    if not blobs:
        pytest.fail(
            "blueberries_voi.viz.m25 (or viz.stage_b / viz.oracle) must exist for "
            "T-017 Stage B + oracle surface; must not include CTL or VOI sweep code"
        )

    joined = "\n".join(blobs)
    assert not re.search(
        r"\bVOI\s*\$|\bvoi_dollars\b|\bvalue of information \(\$\)|\bvoi.?sweep\b",
        joined,
        re.I,
    )
    assert not re.search(r"\bCTL\b|causal.?tree|uplift.?tree|base.?stock", joined, re.I)
    assert not re.search(r"\bb-clair\b|\bb_clair\b|scn-b-clair", joined, re.I), (
        "B-clair must not be implemented on the M2.5 Stage B / oracle surface"
    )


# ---------------------------------------------------------------------------
# Oracle ladder (B-state + F2 ≪ P1 gap table)
# ---------------------------------------------------------------------------


def test_oracle_gap_row_schema_fields() -> None:
    """Gap table rows: scenario, mean_abs_age_error, vs_b_state."""
    cls = _resolve("OracleGapRow")
    fields = _field_names(cls)
    required = {"scenario", "mean_abs_age_error", "vs_b_state"}
    missing = required - fields
    assert not missing, f"OracleGapRow missing fields: {sorted(missing)}"


def test_run_m25_oracle_ladder_exported() -> None:
    fn = _resolve("run_m25_oracle_ladder")
    assert callable(fn)


def test_run_m25_oracle_ladder_shared_root_seed_and_compare_default() -> None:
    """Oracle ladder uses shared CRN; default compare is P1 vs F2 (spec)."""
    fn = _resolve("run_m25_oracle_ladder")
    sig = inspect.signature(fn)
    assert "root_seed" in sig.parameters
    assert sig.parameters["root_seed"].kind in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    assert "compare" in sig.parameters
    default = sig.parameters["compare"].default
    assert default is not inspect.Parameter.empty
    assert tuple(default) == _ORACLE_COMPARE_DEFAULT


def test_b_state_age_error_zero_by_construction() -> None:
    """B-state belief ≡ true (n, τ) / filter bypass → age error is zero in harness."""
    # Prefer an explicit harness helper; fall back to documented constant + API.
    harness = _load_attr("b_state_mean_abs_age_error")
    apply_fn = _load_attr("apply_b_state_belief")
    oracle_belief = _load_attr("OracleBelief")
    zero_hook = _load_attr("B_STATE_AGE_ERROR_IS_ZERO")

    if harness is not None:
        # Tiny synthetic true state — no episode grid.
        err = harness(true_n=3, true_tau=2.5)
        assert float(err) == pytest.approx(0.0)
        return

    if apply_fn is not None:
        # Identity belief: age error against the same truth must be zero.
        belief = apply_fn(true_n=3, true_tau=2.5)
        err_fn = _load_attr("mean_abs_age_error")
        assert err_fn is not None, (
            "With apply_b_state_belief, export mean_abs_age_error(belief, true_*) "
            "so harness can assert zero error"
        )
        assert float(err_fn(belief, true_n=3, true_tau=2.5)) == pytest.approx(0.0)
        return

    if oracle_belief is not None:
        # Construction from truth must yield zero age error via a documented method.
        assert hasattr(oracle_belief, "from_true_state") or callable(oracle_belief), (
            "OracleBelief must be constructible from true (n, τ)"
        )
        if hasattr(oracle_belief, "from_true_state"):
            bel = oracle_belief.from_true_state(n=3, tau=2.5)
        else:
            bel = oracle_belief(n=3, tau=2.5)
        age_err = getattr(bel, "mean_abs_age_error", None)
        if callable(age_err):
            assert float(age_err()) == pytest.approx(0.0)
        else:
            assert float(getattr(bel, "age_error", 0.0)) == pytest.approx(0.0)
        return

    assert zero_hook is True or str(zero_hook).lower() in {"true", "yes", "1"}, (
        "Export b_state_mean_abs_age_error / apply_b_state_belief / OracleBelief "
        "(preferred) or B_STATE_AGE_ERROR_IS_ZERO=True documenting zero age error "
        "by construction under SCN-B-state (plan §4.4)"
    )


def test_oracle_gap_table_f2_much_less_than_p1_vs_b_state() -> None:
    """Shared-CRN gap: F2 posterior age error ≪ P1 error vs B-state (ordering helper).

    Does not run the full ladder grid — locks a pure comparison helper (or
    documented assertion) that implementers use when publishing the MD table.
    """
    cmp_fn = _load_attr("assert_oracle_gap_f2_ll_p1")
    order_fn = _load_attr("oracle_gap_f2_much_less_than_p1")
    ratio_hook = _load_attr("ORACLE_GAP_F2_VS_P1_MAX_RATIO")

    if cmp_fn is not None:
        # Synthetic rows: F2 closer to B-state than P1 must pass; reverse must fail.
        row_cls = _resolve("OracleGapRow")
        good = [
            row_cls(scenario="P1", mean_abs_age_error=1.0, vs_b_state=1.0),
            row_cls(scenario="F2", mean_abs_age_error=0.1, vs_b_state=0.1),
        ]
        cmp_fn(good)  # must not raise
        bad = [
            row_cls(scenario="P1", mean_abs_age_error=0.1, vs_b_state=0.1),
            row_cls(scenario="F2", mean_abs_age_error=1.0, vs_b_state=1.0),
        ]
        with pytest.raises((AssertionError, ValueError)):
            cmp_fn(bad)
        return

    if order_fn is not None:
        assert order_fn(p1_vs_b_state=1.0, f2_vs_b_state=0.1) is True
        assert order_fn(p1_vs_b_state=0.1, f2_vs_b_state=1.0) is False
        return

    assert ratio_hook is not None, (
        "Export assert_oracle_gap_f2_ll_p1 / oracle_gap_f2_much_less_than_p1 "
        "or ORACLE_GAP_F2_VS_P1_MAX_RATIO so F2 ≪ P1 vs B-state is enforceable "
        "without re-deriving the rule in experiment scripts"
    )
    assert 0.0 < float(ratio_hook) < 1.0


def test_oracle_gap_md_path_convention() -> None:
    """Gap table in experiments/m25_stage_b_*.md (or dedicated oracle MD)."""
    path_hook = _load_attr("ORACLE_GAP_MD_PATH") or _load_attr("STAGE_B_RESULT_MD_PATH")
    if path_hook is not None:
        path = Path(path_hook)
        if not path.is_absolute():
            path = _REPO_ROOT / path
        assert "experiments" in path.parts
        assert path.name.startswith("m25_stage_b") or "oracle" in path.name
        return

    # Require an explicit path hook before expensive publish.
    pytest.fail(
        "Export ORACLE_GAP_MD_PATH or STAGE_B_RESULT_MD_PATH for the shared-CRN "
        "F2/P1 vs B-state gap table under experiments/"
    )


def test_b_clair_not_implemented() -> None:
    """SCN-B-clair remains out of M2.5 (spec out of scope)."""
    assert _load_attr("run_m25_b_clair") is None
    assert _load_attr("BClairResult") is None
    hook = _load_attr("B_CLAIR_IMPLEMENTED")
    if hook is not None:
        assert hook is False or str(hook).lower() in {"false", "no", "0", "out"}


# ---------------------------------------------------------------------------
# Unhappy paths (API contract)
# ---------------------------------------------------------------------------


def test_stage_b_empty_rungs_rejected() -> None:
    fn = _resolve("run_m25_stage_b")
    with pytest.raises((ValueError, TypeError)):
        fn(root_seed=0, rungs=())


def test_stage_b_unknown_rung_rejected() -> None:
    fn = _resolve("run_m25_stage_b")
    with pytest.raises((ValueError, KeyError, TypeError)):
        fn(root_seed=0, rungs=("NOT_A_RUNG",))


def test_oracle_ladder_empty_compare_rejected() -> None:
    fn = _resolve("run_m25_oracle_ladder")
    with pytest.raises((ValueError, TypeError)):
        fn(root_seed=0, compare=())


def test_oracle_ladder_rejects_b_clair_in_compare() -> None:
    """B-clair must not sneak in via compare= (out of scope)."""
    fn = _resolve("run_m25_oracle_ladder")
    with pytest.raises((ValueError, KeyError, TypeError)):
        fn(root_seed=0, compare=("P1", "B-clair"))


def test_stage_b_rungs_default_or_explicit_six() -> None:
    """Callable surface covers the six data-availability rungs (plan §4.2)."""
    fn = _resolve("run_m25_stage_b")
    sig = inspect.signature(fn)
    rungs_param = sig.parameters.get("rungs")
    has_default = (
        rungs_param is not None and rungs_param.default is not inspect.Parameter.empty
    )
    if has_default:
        assert rungs_param is not None
        assert tuple(rungs_param.default) == _STAGE_B_RUNGS
    else:
        # Explicit-only API is OK if documented constant lists the six.
        documented = _load_attr("STAGE_B_DEFAULT_RUNGS") or _load_attr(
            "M25_STAGE_B_RUNGS"
        )
        assert documented is not None, (
            "Either default rungs= on run_m25_stage_b or export "
            "STAGE_B_DEFAULT_RUNGS covering P0…F2"
        )
        assert tuple(documented) == _STAGE_B_RUNGS
