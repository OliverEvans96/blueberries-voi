"""T-155 Modal batch map: job extraction, merge, and grid tests (no live Modal)."""

from __future__ import annotations

import json

import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.experiments.channel_joint import (
    all_obs_channels_product,
    channel_joint_job_grid,
    merge_channel_joint_rows,
)
from blueberries_voi.experiments.controller_bakeoff import (
    BAKEOFF_ARMS,
    DEFAULT_CONTROLLER_SEEDS,
    arms_for_belief_world,
    controller_bakeoff_job_grid,
    merge_controller_bakeoff_rows,
    resolve_arm_rho,
)
from blueberries_voi.experiments.filter_accuracy import (
    DEFAULT_SEEDS,
    all_channel_combos,
    channel_from_factorial,
    merge_channel_rows,
    nb13_job_grid,
    run_seed_channel,
)
from blueberries_voi.experiments.gsin_upc import (
    N_REGIMES,
    N_SEEDS,
    REGIME_TITLES,
    gsin_job_grid,
    merge_gsin_diag_rows,
)
from blueberries_voi.experiments.rollout_bakeoff import (
    DEFAULT_ROLLOUT_SEEDS,
    best_alpha_per_arm,
    rollout_eval_job_grid,
)
from blueberries_voi.experiments.voi_profit import (
    DEFAULT_PROFIT_SEEDS,
    merge_voi_profit_rows,
    run_seed_channel_profit,
    voi_profit_job_grid,
)
from blueberries_voi.filter.types import channels_for_preset

_RUST = pytest.mark.skipif(
    _maybe_core is None,
    reason="blueberries_voi._core not built",
)


def test_all_obs_channels_product_count() -> None:
    combos = all_obs_channels_product()
    assert len(combos) == 12


def test_channel_joint_job_grid_size() -> None:
    grid = channel_joint_job_grid((42, 7))
    assert len(grid) == 2 * 12


def test_merge_channel_joint_rows_schema() -> None:
    shard = {
        "seed": 42,
        "key": "code=upc|waste=0|hist=none",
        "profit": 1.0,
        "waste_total": 0,
        "stockout": 0,
        "mae_f": 0.1,
        "mae_dist": 0.2,
        "code_type": "upc",
        "waste": "off",
        "delivery": "none",
        "preset": "P0",
    }
    rows = merge_channel_joint_rows([shard])
    assert rows[0]["mae_dist"] == 0.2


def test_modal_channel_joint_grid_dry_run() -> None:
    pytest.importorskip("modal")
    grid = channel_joint_job_grid((42,))
    args = [(seed, ch.__dict__, {"n_burn": 2, "n_score": 10}) for seed, ch in grid]
    assert len(args) == 12


def test_all_channel_combos_count() -> None:
    combos = all_channel_combos()
    assert len(combos) == 12
    keys = {c.code_type for c in combos}
    assert keys == {"upc", "gsin"}


def test_channel_from_factorial_matches_preset_p0() -> None:
    from blueberries_voi.filter.types import channels_for_preset

    ch = channel_from_factorial("upc_only", "none", "quantity_only")
    assert ch == channels_for_preset("P0")


def test_nb13_job_grid_size() -> None:
    grid = nb13_job_grid()
    assert len(grid) == len(DEFAULT_SEEDS) * 12


def test_nb13_job_grid_with_f3_adds_named_ladder_rung() -> None:
    from blueberries_voi.experiments.filter_accuracy import nb13_job_grid_with_f3
    from blueberries_voi.filter.types import channels_for_preset

    grid = nb13_job_grid_with_f3()
    assert len(grid) == len(DEFAULT_SEEDS) * 12 + len(DEFAULT_SEEDS)
    f3 = channels_for_preset("F3")
    extras = [ch for _seed, ch in grid[len(DEFAULT_SEEDS) * 12 :]]
    assert extras == [f3] * len(DEFAULT_SEEDS)


def test_merge_channel_rows_schema() -> None:
    shards = [
        {
            "seed": 42,
            "key": "code=upc|waste=0|hist=none",
            "pos": "upc_only",
            "waste": "none",
            "deliveries": "quantity_only",
            "preset": "P0",
            "mae_f": 0.1,
            "mean_spread": 0.2,
        },
        {
            "seed": 42,
            "key": "code=upc|waste=0|hist=none",
            "pos": "upc_only",
            "waste": "none",
            "deliveries": "quantity_only",
            "preset": "P0",
            "mae_f": 0.1,
            "mean_spread": 0.2,
        },
    ]
    rows = merge_channel_rows(shards)
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {
        "seed",
        "key",
        "pos",
        "waste",
        "deliveries",
        "preset",
        "mae_f",
        "mean_spread",
    }


def test_gsin_job_grid_size() -> None:
    assert len(gsin_job_grid()) == N_REGIMES * N_SEEDS


def test_merge_gsin_diag_rows_shape() -> None:
    series = {
        "day": [10, 11],
        "truth_on_hand": [1.0, 2.0],
        "belief_on_hand": [1.1, 2.1],
        "truth_mean_f": [0.5, 0.6],
        "belief_mean_f": [0.51, 0.61],
        "ess": [100.0, 100.0],
    }
    shard_a = {
        "regime": REGIME_TITLES[0],
        "seed_index": 0,
        "channels": [
            {
                "channel": "P0",
                "metrics": {
                    "n": 2.0,
                    "lot_n": 4.0,
                    "count_mae": 0.2,
                    "count_bias": 0.02,
                    "store_meanf_mae": 0.04,
                    "lot_meanf_mae": 0.08,
                    "lot_count_mae": 0.16,
                    "tv_sum": 0.3,
                    "ess_sum": 200.0,
                    "eff_inv_mae": 0.5,
                    "ms": 10.0,
                },
                "series": series,
            }
        ],
    }
    shard_b = {
        "regime": REGIME_TITLES[0],
        "seed_index": 1,
        "channels": [
            {
                "channel": "P0",
                "metrics": {
                    "n": 2.0,
                    "lot_n": 4.0,
                    "count_mae": 0.4,
                    "count_bias": 0.04,
                    "store_meanf_mae": 0.08,
                    "lot_meanf_mae": 0.16,
                    "lot_count_mae": 0.32,
                    "tv_sum": 0.6,
                    "ess_sum": 180.0,
                    "eff_inv_mae": 1.0,
                    "ms": 12.0,
                },
                "series": series,
            }
        ],
    }
    rows = merge_gsin_diag_rows([shard_a, shard_b])
    assert len(rows) == 1
    row = rows[0]
    assert row["regime"] == REGIME_TITLES[0]
    assert row["channel"] == "P0"
    assert row["count_mae"] == pytest.approx(0.15)
    assert row["series"] == series


def test_modal_app_grid_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Construct starmap args without importing modal at collection time."""
    pytest.importorskip("modal")
    from blueberries_voi.experiments.filter_accuracy import nb13_job_grid

    grid = nb13_job_grid()
    args = [(seed, ch.__dict__, 3) for seed, ch in grid]
    assert len(args) == len(DEFAULT_SEEDS) * 12
    assert all(len(a) == 3 for a in args)


@_RUST
def test_run_seed_channel_tiny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    ch = channel_from_factorial("upc_only", "none", "quantity_only")
    out = run_seed_channel(seed=42, channel=ch, n_days=3)
    assert out["seed"] == 42
    assert out["preset"] == "P0"
    assert out["n_days"] == 3
    assert "mae_f" in out
    json.dumps(out)


def test_voi_profit_job_grid_size() -> None:
    channels = [channels_for_preset(s) for s in ("P0", "P1", "F2")]
    grid = voi_profit_job_grid(DEFAULT_PROFIT_SEEDS, channels)
    assert len(grid) == len(DEFAULT_PROFIT_SEEDS) * len(channels)


def test_merge_voi_profit_rows_dedup() -> None:
    shards = [
        {
            "seed": 42,
            "key": "code=upc|waste=0|hist=none",
            "profit": 10.0,
            "waste": 1,
            "stockout": 0,
            "preset": "P0",
        },
        {
            "seed": 42,
            "key": "code=upc|waste=0|hist=none",
            "profit": 10.0,
            "waste": 1,
            "stockout": 0,
            "preset": "P0",
        },
        {
            "seed": 7,
            "key": "code=gsin|waste=1|hist=none",
            "profit": 12.0,
            "waste": 2,
            "stockout": 1,
            "preset": "F1",
        },
    ]
    rows = merge_voi_profit_rows(shards)
    assert len(rows) == 2
    keys = {(r["seed"], r["key"]) for r in rows}
    assert keys == {
        (42, "code=upc|waste=0|hist=none"),
        (7, "code=gsin|waste=1|hist=none"),
    }


def test_rollout_eval_job_grid_size() -> None:
    alphas = (0.8, 0.9)
    grid = rollout_eval_job_grid(
        DEFAULT_ROLLOUT_SEEDS[:2], ("sw", "rollout"), alphas, 0.8
    )
    assert len(grid) == 2 * 2 * 2


def test_best_alpha_per_arm_picks_highest_mean() -> None:
    rows = [
        {"arm_id": "sw", "alpha": 0.8, "seed": 1, "profit": 10.0},
        {"arm_id": "sw", "alpha": 0.8, "seed": 2, "profit": 12.0},
        {"arm_id": "sw", "alpha": 0.9, "seed": 1, "profit": 9.0},
        {"arm_id": "sw", "alpha": 0.9, "seed": 2, "profit": 11.0},
    ]
    assert best_alpha_per_arm(rows, "sw") == pytest.approx(0.8)


def test_controller_bakeoff_job_grid_size() -> None:
    grid = controller_bakeoff_job_grid(DEFAULT_CONTROLLER_SEEDS[:2], BAKEOFF_ARMS, 0.8)
    assert len(grid) == 2 * len(BAKEOFF_ARMS)


def test_controller_bakeoff_filtered_arms_exclude_rung0() -> None:
    filtered = arms_for_belief_world("filtered")
    assert "rung0" not in filtered
    assert "rollout" not in filtered
    assert len(arms_for_belief_world("oracle")) == 4


def test_resolve_arm_rho_sla_pb_uses_bo_tuned_rho() -> None:
    assert resolve_arm_rho("sla_pb") == pytest.approx(0.5)
    assert resolve_arm_rho("sw") == pytest.approx(0.8)


def test_controller_bakeoff_job_grid_per_arm_rho() -> None:
    grid = controller_bakeoff_job_grid((42,), ("sw", "sla_pb"), 0.8)
    rhos = {arm: rho for _, arm, rho in grid}
    assert rhos["sw"] == pytest.approx(0.8)
    assert rhos["sla_pb"] == pytest.approx(0.5)


def test_merge_controller_bakeoff_rows_dedup() -> None:
    shards = [
        {
            "seed": 42,
            "arm_id": "sw",
            "belief_world": "oracle",
            "alpha": 0.9,
            "rho": 0.8,
            "profit": 10.0,
            "waste": 1,
            "stockout": 0,
            "elapsed_s": 0.5,
        },
        {
            "seed": 42,
            "arm_id": "sw",
            "belief_world": "oracle",
            "alpha": 0.9,
            "rho": 0.8,
            "profit": 10.0,
            "waste": 1,
            "stockout": 0,
            "elapsed_s": 0.5,
        },
        {
            "seed": 7,
            "arm_id": "sla_pb",
            "belief_world": "oracle",
            "alpha": 0.95,
            "rho": 0.8,
            "profit": 12.0,
            "waste": 2,
            "stockout": 1,
            "elapsed_s": 0.02,
        },
    ]
    rows = merge_controller_bakeoff_rows(shards)
    assert len(rows) == 2
    sw_row = next(r for r in rows if r["arm_id"] == "sw")
    assert sw_row["elapsed_s"] == pytest.approx(0.5)


def test_modal_controller_bakeoff_grid_dry_run() -> None:
    pytest.importorskip("modal")
    grid = controller_bakeoff_job_grid((42,), arms_for_belief_world("oracle"), 0.8)
    args = [
        (seed, arm, rho, {"n_burn": 2, "n_score": 14, "belief_world": "oracle"})
        for seed, arm, rho in grid
    ]
    assert len(args) == len(BAKEOFF_ARMS)


def test_gsin_cells_subset_grid() -> None:
    cells = [(2, 0), (3, 1)]
    assert len(cells) == 2
    assert all(0 <= r < N_REGIMES and 0 <= s < N_SEEDS for r, s in cells)


@_RUST
@pytest.mark.slow
def test_gsin_shard_cli_smoke() -> None:
    from blueberries_voi.experiments.gsin_upc import run_regime_seed

    shard = run_regime_seed(0, 0)
    assert shard["seed_index"] == 0
    assert len(shard["channels"]) == 6


@_RUST
def test_run_seed_channel_profit_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    from blueberries_voi.filter.types import channels_cache_key

    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    ch = channels_for_preset("P0")
    out = run_seed_channel_profit(42, ch, n_burn=1, n_score=2)
    assert out["seed"] == 42
    assert out["key"] == channels_cache_key(ch)
    assert "profit" in out
    assert "waste" in out
    assert "stockout" in out
    json.dumps(out)


def test_modal_app_wheel_path_relative_to_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("modal")
    import importlib
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    import experiments.modal.app as app_mod

    wheel_dir = repo / "dist" / "wheel"
    if not wheel_dir.is_dir():
        pytest.skip("dist/wheel not built")

    notebooks_cwd = repo / "notebooks"
    notebooks_cwd.mkdir(exist_ok=True)
    monkeypatch.chdir(notebooks_cwd)
    monkeypatch.setenv("BLUEBERRIES_VOI_WHEEL", "dist/wheel")
    importlib.reload(app_mod)

    assert app_mod.WHEEL_PATH.is_file()
    assert app_mod.WHEEL_PATH.parent == wheel_dir.resolve()
    assert app_mod._TUNED_ALPHA.is_file()
    assert app_mod._REMOTE_TUNED_ALPHA == "/experiments/tuned_alpha.json"
