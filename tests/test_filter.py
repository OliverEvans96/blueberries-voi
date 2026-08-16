"""T-005/T-006 filter tests."""

from __future__ import annotations

import pytest

pytest.skip(
    "T-TAU-RETIRE: filter.backends / particle research modules deleted",
    allow_module_level=True,
)
from blueberries_voi.filter.types import P1Obs, guard_joint_memory
from blueberries_voi.model import ModelParams, death_prob_survival_ratio
from blueberries_voi.sim.rust_bridge import day_step


def test_filter_shares_day_step() -> None:
    assert day_step.__module__ == "blueberries_voi.sim.rust_bridge"


@pytest.mark.skip(
    reason=(
        "T-121 F3: ADR 0127 Wave F supersession — "
        "research backends use removed day_step"
    )
)
def test_all_backends_construct() -> None:
    assert set(BACKENDS) == {
        "sliding_window",
        "mean_field",
        "bound_L",
        "bootstrap_pf",
        "full_joint",
    }
    rng = np.random.default_rng(0)
    for name in BACKENDS:
        be = get_backend(name)
        if name == "full_joint":
            st = be.initialize(N=10, K=4, L=3, params=ModelParams(), rng=rng)
        else:
            st = be.initialize(N=20, K=6, L=4, params=ModelParams(), rng=rng)
        obs = P1Obs(10, 1, 8)
        st2 = be.predict_update(st, obs, ModelParams(), rng)
        assert st2.backend == name


def test_full_joint_memory_guard() -> None:
    with pytest.raises(MemoryError, match="budget exceeded"):
        guard_joint_memory(K=8, L=12, N=2000)


@pytest.mark.skip(reason="T-121 F3: production particle filter removed")
def test_particle_filter_step_and_posterior() -> None:
    particle_filter = ResearchParticleFilter(params=ModelParams(), N=50, K=6, L=3)
    rng = np.random.default_rng(3)
    particle_filter.initialize(rng)
    summary = particle_filter.step(P1Obs(12, 1, 8), rng)
    assert summary.ess > 0
    post = particle_filter.age_posterior(0)
    assert post.shape == (6,)
    assert abs(float(post.sum()) - 1.0) < 1e-6


def test_survival_ratio_via_filter_import() -> None:
    # Regression: filter path still uses shared model death kernel.
    assert day_step.__module__ == "blueberries_voi.sim.rust_bridge"
    p = death_prob_survival_ratio(3.0, 1.0, beta=2.0, eta=14.0)
    assert 0.0 < p < 1.0


def test_microbench_row() -> None:
    row = run_microbench("sliding_window", K=4, N=50, L=2, timeout_s=1.0)
    assert row.backend == "sliding_window"
    assert not row.oom


@pytest.mark.skip(reason="T-121 F3: production particle filter removed")
def test_particle_filter_requires_initialize() -> None:
    particle_filter = ResearchParticleFilter(params=ModelParams(), N=20, K=4, L=2)
    with pytest.raises(RuntimeError, match="initialize"):
        particle_filter.step(P1Obs(1, 0, 0))
    with pytest.raises(RuntimeError, match="initialize"):
        particle_filter.age_posterior()


@pytest.mark.skip(reason="T-121 F3: production particle filter removed")
def test_production_backend_is_not_age_mean_field() -> None:
    """T-068 / ADR 0105: production identity is not the age mean-field settle."""
    assert filter_pkg.PRODUCTION_BACKEND != "mean_field"
    particle_filter = ResearchParticleFilter(params=ModelParams(), N=20, K=4, L=2)
    assert particle_filter.backend_choice.backend == filter_pkg.PRODUCTION_BACKEND
    assert particle_filter.backend_choice.backend not in {
        "mean_field",
        "sliding_window",
        "full_joint",
    }
    assert (
        getattr(particle_filter._backend, "name", None) == filter_pkg.PRODUCTION_BACKEND
    )
