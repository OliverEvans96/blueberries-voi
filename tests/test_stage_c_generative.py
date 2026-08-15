"""T-012 Stage C generative check vs day_step (RED / acceptance).

ADR 0088: production Stage C must fail under injected wrong physics and pass
under the production MC LL — not M1 soft-LL ``tv_vs_exact`` self-consistency.
"""

from __future__ import annotations

import pytest

pytest.skip(
    "T-121 F3: particle_filter production path removed", allow_module_level=True
)

import ast
import inspect
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from blueberries_voi.viz.fil11 import StageCResult, run_fil11_stage_c

_ROOT = Path(__file__).resolve().parents[1]


def _fil11_source() -> str:
    import blueberries_voi.viz.fil11 as fil11

    return Path(fil11.__file__).read_text(encoding="utf-8")


def _ast_function(source: str, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            return node
    msg = f"function {name!r} not found in source"
    raise AssertionError(msg)


def _names_in_function(fn: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}


def _stage_c_kwargs(
    tmp_path: Path,
    *,
    inject_wrong_physics: bool,
    n_obs_samples: int = 80,
    tolerance: float = 0.05,
    L: int = 2,
    K: int = 4,
) -> dict[str, Any]:
    """Build kwargs for the generative Stage C API (spec T-012)."""
    sig = inspect.signature(run_fil11_stage_c)
    missing = [
        name
        for name in ("inject_wrong_physics", "n_obs_samples", "tolerance")
        if name not in sig.parameters
    ]
    assert missing == [], (
        "run_fil11_stage_c missing generative kwargs "
        f"{missing}; expected inject_wrong_physics / n_obs_samples / tolerance "
        "(ADR 0088 / T-012)"
    )
    kwargs: dict[str, Any] = {
        "L": L,
        "K": K,
        "n_obs_samples": n_obs_samples,
        "tolerance": tolerance,
        "inject_wrong_physics": inject_wrong_physics,
    }
    if "figures_dir" in sig.parameters:
        kwargs["figures_dir"] = tmp_path
    return kwargs


def test_stage_c_result_exposes_generative_contract_fields() -> None:
    """AC: StageCResult carries divergence / tolerance / mode generative_day_step."""
    names = {f.name for f in fields(StageCResult)}
    for required in ("divergence", "tolerance", "passed", "figure_path", "mode"):
        assert required in names, (
            f"StageCResult missing {required!r}; M1 fields tv/tvs are not the "
            "generative contract (T-012 / ADR 0088)"
        )


def test_run_fil11_stage_c_signature_supports_wrong_physics_injection() -> None:
    """AC: harness accepts inject_wrong_physics for falsifiable Stage C."""
    params = inspect.signature(run_fil11_stage_c).parameters
    assert "inject_wrong_physics" in params
    assert params["inject_wrong_physics"].default is False
    assert "n_obs_samples" in params
    assert "tolerance" in params


def test_stage_c_fails_when_wrong_physics_injected(tmp_path: Path) -> None:
    """AC: wrong-physics obs model → passed=False and divergence above tolerance."""
    result = run_fil11_stage_c(**_stage_c_kwargs(tmp_path, inject_wrong_physics=True))
    assert getattr(result, "mode", None) == "generative_day_step"
    assert result.passed is False
    divergence = getattr(result, "divergence", None)
    tolerance = getattr(result, "tolerance", None)
    assert isinstance(divergence, float)
    assert isinstance(tolerance, float)
    assert divergence > tolerance
    assert divergence > 0.0
    assert getattr(result, "n_support", 0) > 1
    assert result.figure_path.is_file()


def test_stage_c_passes_under_production_mc_ll(tmp_path: Path) -> None:
    """AC: production MC LL / shared day_step → passed=True within tolerance."""
    result = run_fil11_stage_c(**_stage_c_kwargs(tmp_path, inject_wrong_physics=False))
    assert getattr(result, "mode", None) == "generative_day_step"
    assert result.passed is True
    divergence = getattr(result, "divergence", None)
    tolerance = getattr(result, "tolerance", None)
    assert isinstance(divergence, float)
    assert isinstance(tolerance, float)
    assert divergence <= tolerance
    assert getattr(result, "n_support", 0) > 1
    assert result.figure_path.is_file()


def test_production_stage_c_does_not_gate_on_soft_tv_vs_exact() -> None:
    """AC: M1 soft-LL tv_vs_exact is not the production Stage C gate."""
    src = _fil11_source()
    fn = _ast_function(src, "run_fil11_stage_c")
    names = _names_in_function(fn)
    assert "tv_vs_exact" not in names, (
        "run_fil11_stage_c still calls tv_vs_exact (soft self-check); "
        "replace with generative agreement vs day_step (ADR 0088)"
    )


def test_stage_c_default_figures_dir_is_m15() -> None:
    """AC: Stage C figures land under figures/m1.5/ (not historical m1 soft gate)."""
    import blueberries_voi.viz.fil11 as fil11

    fig = Path(fil11.FIG)
    assert "m1.5" in fig.parts, (
        f"fil11.FIG default is {fig}; generative Stage C must write under "
        "figures/m1.5/ (T-012)"
    )


def test_stage_c_m15_entrypoint_documented() -> None:
    """AC: documented uv run entrypoint + result MD path under m1.5 or experiments."""
    readme = _ROOT / "figures" / "m1.5" / "README.md"
    assert readme.is_file(), (
        "figures/m1.5/README.md must document Stage C figure and result MD paths"
    )
    text = readme.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "uv run" in lowered, "README must document a uv run entrypoint"
    asserts_stage = (
        "stage c" in lowered
        or "stage_c" in lowered
        or "generative" in lowered
        or "fil11" in lowered
    )
    assert asserts_stage, "README must mention Stage C / generative / FIL-11"
    # Result note path must be pointed at (figures/m1.5 or experiments/).
    mentions_result = (
        "result" in lowered or ".md" in lowered or "experiments/" in lowered
    )
    assert mentions_result, "README must point at the short result MD path"


def test_optional_auxiliary_does_not_restore_soft_self_check() -> None:
    """AC (if auxiliary present): RPF vs brute-force must not use soft tv_vs_exact.

    Optional per T-012; skips when no auxiliary helper exists yet.
    """
    import blueberries_voi.viz.fil11 as fil11

    def _looks_like_aux(name: str) -> bool:
        lower = name.lower()
        return any(tok in lower for tok in ("brute", "auxiliary", "exact"))

    aux_names = [
        name
        for name in dir(fil11)
        if name.startswith("run_")
        and _looks_like_aux(name)
        and name != "run_fil11_stage_c"
    ]
    if not aux_names:
        pytest.skip("optional particle filter-vs-brute auxiliary not implemented")
    src = _fil11_source()
    for name in aux_names:
        fn = _ast_function(src, name)
        names = _names_in_function(fn)
        # Soft self-check must not be the pass rule for any Stage C auxiliary.
        soft = "sales_pow" in names or "waste_pow" in names
        assert not soft, (
            f"{name} still references soft powers; "
            "auxiliary must share MC/closed-form LL"
        )
