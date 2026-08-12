"""Exercise M1.5 Stage A/B/oracle runners under tiny smoke budgets (coverage).

Contract tests in ``test_stage_a_multirung`` / ``test_stage_b_oracle`` lock the
API without running episodes. This module calls the real runners with
cheap ``n_particles`` / horizon / ``n_reps`` so ``viz.m15`` paths stay under
the ≥80% coverage gate without huge grids. Behaviour of T-016/T-017 is
unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from blueberries_voi.viz import m15

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def fig_dir(tmp_path: Path) -> Path:
    d = tmp_path / "figures"
    d.mkdir()
    return d


def test_apply_b_state_and_mean_abs_age_error_helpers() -> None:
    bel = m15.apply_b_state_belief(true_n=2, true_tau=1.5)
    assert bel.n == 2
    assert bel.tau == pytest.approx(1.5)
    assert m15.mean_abs_age_error(bel, true_n=2, true_tau=1.5) == pytest.approx(0.0)
    assert m15.mean_abs_age_error(bel, true_n=2, true_tau=2.5) == pytest.approx(1.0)
    assert m15.oracle_gap_f2_much_less_than_p1(p1_vs_b_state=1.0, f2_vs_b_state=0.1)
    assert not m15.oracle_gap_f2_much_less_than_p1(p1_vs_b_state=0.1, f2_vs_b_state=1.0)
    # Degenerate P1 gap ≤ 0: only pass when F2 is no worse.
    assert m15.oracle_gap_f2_much_less_than_p1(p1_vs_b_state=0.0, f2_vs_b_state=0.0)
    assert not m15.oracle_gap_f2_much_less_than_p1(p1_vs_b_state=0.0, f2_vs_b_state=0.1)


def test_assert_oracle_gap_requires_p1_and_f2_rows() -> None:
    row = m15.OracleGapRow(scenario="P1", mean_abs_age_error=1.0, vs_b_state=1.0)
    with pytest.raises(ValueError, match="P1 and F2"):
        m15.assert_oracle_gap_f2_ll_p1([row])


def test_run_m15_stage_a_smoke_exercises_filter_and_figure(fig_dir: Path) -> None:
    """One shared episode, two rungs — covers ``_filter_rung`` + figure write."""
    result = m15.run_m15_stage_a(
        root_seed=0,
        rungs=("P1", "F2"),
        contraction_margin=0.05,
        figures_dir=fig_dir,
        n_particles=4,
        n_burn=1,
        n_score=2,
        write_figure=True,
    )
    assert result.root_seed == 0
    assert result.figure_dir == fig_dir
    assert len(result.rows) == 2
    assert {r.scenario for r in result.rows} == {"P1", "F2"}
    assert (fig_dir / "m15_stage_a_rung_map.png").is_file()
    for row in result.rows:
        assert row.prior_sd >= 0.0
        assert row.posterior_sd >= 0.0


def test_run_m15_stage_b_smoke_diagnostic_and_pass_labels(fig_dir: Path) -> None:
    """Tiny Stage B: A-fail → diagnostic_only; A-pass → not diagnostic."""
    rows = m15.run_m15_stage_b(
        root_seed=0,
        rungs=("P1", "F2"),
        stage_a_pass={"P1": False, "F2": True},
        figures_dir=fig_dir,
        n_particles=4,
        n_reps=1,
        n_burn=1,
        n_score=2,
        write_figure=True,
        write_md=False,
    )
    assert len(rows) == 2
    by = {r.scenario: r for r in rows}
    assert by["P1"].diagnostic_only is True
    assert by["F2"].diagnostic_only is False
    assert 0.0 <= by["P1"].coverage_90 <= 1.0
    assert by["P1"].figure_path.is_file()
    assert by["F2"].figure_path.is_file()


def test_run_m15_stage_b_unmarked_stage_a_is_diagnostic(fig_dir: Path) -> None:
    """``stage_a_pass=None`` → conservative diagnostic-only for all rungs."""
    rows = m15.run_m15_stage_b(
        root_seed=1,
        rungs=("P0",),
        stage_a_pass=None,
        figures_dir=fig_dir,
        n_particles=4,
        n_reps=1,
        n_burn=1,
        n_score=2,
        write_figure=False,
        write_md=False,
    )
    assert len(rows) == 1
    assert rows[0].diagnostic_only is True


def test_run_m15_oracle_ladder_smoke_writes_figure(fig_dir: Path) -> None:
    rows = m15.run_m15_oracle_ladder(
        root_seed=0,
        compare=("P1", "F2"),
        figures_dir=fig_dir,
        n_particles=4,
        n_reps=1,
        n_burn=1,
        n_score=2,
        write_figure=True,
        write_md=False,
    )
    assert len(rows) == 2
    by = {r.scenario: r for r in rows}
    assert by["P1"].mean_abs_age_error >= 0.0
    assert by["F2"].mean_abs_age_error >= 0.0
    assert (fig_dir / "m15_oracle_ladder_gap.png").is_file()


def test_run_m15_stage_b_write_md_embeds_oracle_gap(
    fig_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``write_md=True`` covers Stage B MD + nested oracle ladder."""
    md_path = tmp_path / "m15_stage_b_smoke.md"
    monkeypatch.setattr(m15, "STAGE_B_RESULT_MD_PATH", md_path)
    rows = m15.run_m15_stage_b(
        root_seed=0,
        rungs=("F2",),
        stage_a_pass={"F2": True},
        figures_dir=fig_dir,
        n_particles=4,
        n_reps=1,
        n_burn=1,
        n_score=2,
        write_figure=False,
        write_md=True,
    )
    assert len(rows) == 1
    text = md_path.read_text(encoding="utf-8")
    assert "Stage B" in text
    assert "F2" in text
    assert "Oracle ladder" in text or "oracle" in text.lower()


def test_write_stage_b_md_gap_fail_and_empty_branches(tmp_path: Path) -> None:
    """Direct MD helper: missing gap table + failing F2≪P1 wording."""
    path_empty = tmp_path / "empty_gap.md"
    m15._write_stage_b_md(
        [
            m15.StageBRungResult(
                scenario="P1",
                coverage_90=0.9,
                diagnostic_only=True,
                figure_path=tmp_path / "p1.png",
            )
        ],
        None,
        root_seed=0,
        path=path_empty,
    )
    empty_text = path_empty.read_text(encoding="utf-8")
    assert "run_m15_oracle_ladder" in empty_text

    path_fail = tmp_path / "fail_gap.md"
    bad_gap = [
        m15.OracleGapRow(scenario="P1", mean_abs_age_error=0.1, vs_b_state=0.1),
        m15.OracleGapRow(scenario="F2", mean_abs_age_error=1.0, vs_b_state=1.0),
    ]
    m15._write_stage_b_md([], bad_gap, root_seed=0, path=path_fail)
    fail_text = path_fail.read_text(encoding="utf-8")
    assert "FAIL" in fail_text
