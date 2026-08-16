"""M1.5 Stage A multi-rung contraction runners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.filter.arrival_priors import cold_abdella_arrival_age_prior
from blueberries_voi.filter.types import (
    ScenarioId,
    age_grid,
    mask_for,
    rich_obs_from_day_log,
)
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import load_abdella_shipments
from blueberries_voi.sim import EpisodeLog, run_episode
from blueberries_voi.viz.fil11 import _arrival_prior, _spread
from blueberries_voi.viz.m15_common import (
    _SMOKE_K,
    _SMOKE_L,
    _SMOKE_N,
    _SMOKE_N_BURN,
    _SMOKE_N_SCORE,
    _TIGHT_SPREAD,
    DEFAULT_STAGE_A_RUNGS,
    FIG_M15,
    ROOT,
    _validate_margin,
    _validate_rungs,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


@dataclass
class StageARungResult:
    """One data-availability rung under shared CRN Stage A."""

    scenario: ScenarioId
    prior_sd: float
    posterior_sd: float
    contracted: bool
    tight_control_collapsed: bool


@dataclass
class StageAMultiResult:
    """Multi-rung Stage A aggregate (shared ``root_seed``)."""

    rows: list[StageARungResult]
    root_seed: int
    figure_dir: Path


def _filter_rung(
    ep: EpisodeLog,
    *,
    scenario: ScenarioId,
    params: ModelParams,
    prior: np.ndarray,
    root_seed: int,
    n_particles: int,
    K: int,
    L: int,
    reseeds_birth_with_prior: bool,
) -> np.ndarray:
    """Run particle filter on shared episode; observation mask differs by rung.

    Cohort-from-birth: track the first scored delivery's slot as arrivals shift
    the window left. Report that cohort's age marginal after it has lived at
    least one post-birth day (not the same-day birth prior alone, and not
    oldest-slot-only).
    """
    mask = mask_for(scenario)
    particle_filter = ResearchParticleFilter(params=params, N=n_particles, K=K, L=L)
    particle_filter._root_seed = root_seed
    particle_filter._run_id = f"m15_a_{scenario}"
    rng = np.random.default_rng(root_seed + 17)
    particle_filter.initialize(rng, L=L)
    assert particle_filter._state is not None
    particle_filter._state.age_post[:] = prior[None, None, :]

    tracked_slot: int | None = None
    last_post: np.ndarray | None = None
    for d in ep.scored:
        obs = rich_obs_from_day_log(d, mask)
        particle_filter.step(obs, rng)
        if d.arrivals > 0:
            if tracked_slot is None:
                tracked_slot = L - 1
            else:
                tracked_slot -= 1
            if reseeds_birth_with_prior and particle_filter._state is not None:
                # Tight-control path: keep birth belief collapsed (ignore F2/F2a).
                particle_filter._state.age_post[:, -1, :] = prior[None, :]
            if tracked_slot is not None and tracked_slot < 0:
                # Birth fell off the L-window; re-anchor to newest birth.
                tracked_slot = L - 1
        elif tracked_slot is not None:
            # Post-birth observation day: cohort-from-birth posterior is meaningful.
            last_post = particle_filter.age_posterior(tracked_slot)

    if last_post is not None:
        return last_post
    # Fallback: newest live slot (still not oldest-slot-only).
    idx = L - 1 if tracked_slot is None else max(tracked_slot, 0)
    return particle_filter.age_posterior(idx)


def _write_rung_map_figure(
    rows: list[StageARungResult],
    *,
    figure_dir: Path,
    margin: float,
) -> Path:
    import matplotlib.pyplot as plt

    figure_dir.mkdir(parents=True, exist_ok=True)
    labels = [r.scenario for r in rows]
    prior = [r.prior_sd for r in rows]
    post = [r.posterior_sd for r in rows]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    width = 0.35
    ax.bar(x - width / 2, prior, width, label="prior SD (cold)", color="#4a5568")
    ax.bar(x + width / 2, post, width, label="posterior SD (birth)", color="#2b6cb0")
    ax.axhline(0.0, color="k", lw=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Arrival-age SD (cohort-from-birth)")
    ax.set_title(f"FIL-11 Stage A multi-rung map (≥{100 * margin:.0f}% contraction)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = figure_dir / "m15_stage_a_rung_map.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def run_m15_stage_a(
    *,
    root_seed: int = 0,
    rungs: Sequence[ScenarioId] = DEFAULT_STAGE_A_RUNGS,
    contraction_margin: float = 0.05,
    figures_dir: Path | None = None,
    n_particles: int = _SMOKE_N,
    n_burn: int = _SMOKE_N_BURN,
    n_score: int = _SMOKE_N_SCORE,
    write_figure: bool = True,
) -> StageAMultiResult:
    """Multi-rung FIL-11 Stage A under shared CRN (SIM-05 ``root_seed``).

    One simulator episode is shared across rungs; only the observation mask
    changes. Spread uses the cohort-from-birth metric (tracked birth-lot slot
    after ≥1 post-birth day), avoiding oldest-slot-only comparisons when
    ``L_filter`` < empirical L.
    """
    msg = "research particle filter removed (T-TAU-RETIRE)"
    raise NotImplementedError(msg)

