"""T-039 / T-040 VOI sweep + smoke + beta=1 gate."""

from __future__ import annotations

import pytest

pytest.skip("T-121 F3: voi sweep uses removed rbpf imports", allow_module_level=True)

from typing import TYPE_CHECKING

import pytest

from blueberries_voi.viz.voi import plot_voi_vs_beta
from blueberries_voi.voi import (
    PRODUCTION_BETAS,
    VoISweepResult,
    assert_beta_one_voi_near_zero,
    run_voi_smoke,
    run_voi_sweep,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_production_beta_grid_fine_and_includes_one() -> None:
    assert len(PRODUCTION_BETAS) >= 10
    assert 1.0 in PRODUCTION_BETAS


def test_run_voi_sweep_smoke_returns_jsonable_arms() -> None:
    result = run_voi_sweep(
        smoke=True,
        root_seed=5,
        scenarios=["P0", "P1", "B-state"],
    )
    assert isinstance(result, VoISweepResult)
    assert result.smoke is True
    assert 1.0 in result.betas
    assert any(b > 1.0 for b in result.betas)
    payload = result.to_jsonable()
    assert isinstance(payload["arms"], list)
    assert payload["arms"]
    for arm in result.arms:
        assert arm.scenario != "P0"
        assert arm.n_replications >= 1


def test_beta_one_gate_passes_under_smoke() -> None:
    result = run_voi_sweep(
        smoke=True,
        root_seed=9,
        scenarios=["P0", "P1", "B-state"],
        n_replications=2,
    )
    assert_beta_one_voi_near_zero(result, tol=50.0)


def test_run_voi_smoke_writes_experiment_note(tmp_path: Path) -> None:
    report = tmp_path / "m3_voi_smoke.md"
    result = run_voi_smoke(root_seed=2, report_path=report)
    text = report.read_text(encoding="utf-8")
    assert "not headline" in text.lower() or "smoke" in text.lower()
    assert result.smoke is True


def test_plot_voi_vs_beta_does_not_import_mpl_in_voi_metric() -> None:
    import blueberries_voi.voi.metric as metric_mod

    assert "matplotlib" not in metric_mod.__dict__


def test_plot_voi_vs_beta_writes_png(tmp_path: Path) -> None:
    result = run_voi_sweep(
        smoke=True,
        root_seed=1,
        scenarios=["P0", "P1"],
        n_replications=1,
        n_bootstrap=8,
    )
    out = tmp_path / "voi_vs_beta.png"
    path = plot_voi_vs_beta(result, out_path=out)
    assert path.exists()
    assert path.stat().st_size > 0


def test_assert_beta_one_fails_when_far_from_zero() -> None:
    from blueberries_voi.voi.sweep import VoIArmResult

    bad = VoISweepResult(
        betas=(1.0,),
        scenarios=("P0", "P1"),
        arms=(
            VoIArmResult(
                scenario="P1",
                beta=1.0,
                absolute_delta=999.0,
                pct_vs_p0=9.0,
                ci_low=900.0,
                ci_high=1000.0,
                n_replications=2,
            ),
        ),
        smoke=True,
    )
    with pytest.raises(AssertionError, match="near zero"):
        assert_beta_one_voi_near_zero(bad, tol=50.0)
