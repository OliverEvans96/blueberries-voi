"""Smoke: rollout arm alpha grid search via Rust kernel when _core is built."""

from __future__ import annotations

import pytest

from blueberries_voi.backend import rust_available, rust_core
from blueberries_voi.sim.alpha_tune import DEFAULT_CI_ALPHAS, tune_alpha_grid
from blueberries_voi.sim.shipments import smoke_cool_shipments


@pytest.mark.skipif(
    not rust_available()
    or rust_core is None
    or not hasattr(rust_core, "evaluate_alpha_tune_episode_py"),
    reason="requires blueberries_voi._core with evaluate_alpha_tune_episode_py",
)
def test_tune_alpha_grid_rollout_returns_grid_member() -> None:
    ships = smoke_cool_shipments()
    best = tune_alpha_grid(
        "rollout",
        alphas=DEFAULT_CI_ALPHAS,
        root_seed=42,
        shipments=ships,
        n_burn=2,
        n_score=3,
    )
    assert best in DEFAULT_CI_ALPHAS


def test_tune_alpha_grid_rollout_not_placeholder() -> None:
    """Rollout must not raise NotImplementedError once wired."""
    if not rust_available() or rust_core is None:
        pytest.skip("rust kernel not built")
    if not hasattr(rust_core, "evaluate_alpha_tune_episode_py"):
        pytest.skip("evaluate_alpha_tune_episode_py missing")
    ships = smoke_cool_shipments()
    try:
        tune_alpha_grid(
            "rollout",
            alphas=(0.9,),
            root_seed=1,
            shipments=ships,
            n_burn=1,
            n_score=1,
        )
    except NotImplementedError as exc:
        pytest.fail(f"rollout should be tunable: {exc}")
