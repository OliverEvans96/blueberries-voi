"""M1.5 B-state oracle ladder helpers and runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.filter.types import (
    ScenarioId,
    age_grid,
    mask_for,
    rich_obs_from_day_log,
)
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import ShipmentTrace, load_abdella_shipments
from blueberries_voi.sim import run_episode
from blueberries_voi.viz.m15_common import (
    _SMOKE_K,
    _SMOKE_L,
    _SMOKE_N,
    _SMOKE_N_BURN,
    _SMOKE_N_SCORE,
    _SMOKE_ORACLE_REPS,
    FIG_M15,
    ORACLE_GAP_F2_VS_P1_MAX_RATIO,
    ROOT,
    _validate_rungs,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


@dataclass
class OracleGapRow:
    """Shared-CRN age-error gap vs the B-state ceiling for one scenario."""

    scenario: ScenarioId
    mean_abs_age_error: float
    vs_b_state: float


@dataclass(frozen=True)
class OracleBelief:
    """Lot-level belief pinned to true ``(n, τ)`` (SCN-B-state harness)."""

    n: int
    tau: float

    @classmethod
    def from_true_state(cls, *, n: int, tau: float) -> OracleBelief:
        return cls(n=int(n), tau=float(tau))

    def mean_abs_age_error(
        self,
        true_n: int | None = None,
        true_tau: float | None = None,
    ) -> float:
        """Age error vs truth; zero when belief is the true state (default)."""
        tt = float(self.tau if true_tau is None else true_tau)
        _ = true_n  # count is carried for belief identity; age metric uses tau
        return abs(float(self.tau) - tt)


def b_state_mean_abs_age_error(*, true_n: int, true_tau: float) -> float:
    """SCN-B-state harness: belief ≡ true ``(n, τ)`` ⇒ age error is zero."""
    bel = OracleBelief.from_true_state(n=true_n, tau=true_tau)
    return float(bel.mean_abs_age_error())


def apply_b_state_belief(*, true_n: int, true_tau: float) -> OracleBelief:
    """Filter bypass: set belief to the true lot state."""
    return OracleBelief.from_true_state(n=true_n, tau=true_tau)


def mean_abs_age_error(
    belief: OracleBelief,
    *,
    true_n: int,
    true_tau: float,
) -> float:
    """Mean absolute age error of a belief vs true ``(n, τ)``."""
    return float(belief.mean_abs_age_error(true_n=true_n, true_tau=true_tau))


def oracle_gap_f2_much_less_than_p1(
    *,
    p1_vs_b_state: float,
    f2_vs_b_state: float,
) -> bool:
    """True when F2's gap to B-state is much smaller than P1's (plan §4.4)."""
    p1 = float(p1_vs_b_state)
    f2 = float(f2_vs_b_state)
    if p1 <= 0.0:
        return f2 <= p1
    return (f2 / p1) <= float(ORACLE_GAP_F2_VS_P1_MAX_RATIO)


def assert_oracle_gap_f2_ll_p1(rows: Sequence[OracleGapRow]) -> None:
    """Raise if published gap rows do not show F2 ≪ P1 vs B-state."""
    by_scen = {str(r.scenario): r for r in rows}
    if "P1" not in by_scen or "F2" not in by_scen:
        msg = "oracle gap table requires P1 and F2 rows"
        raise ValueError(msg)
    ok = oracle_gap_f2_much_less_than_p1(
        p1_vs_b_state=by_scen["P1"].vs_b_state,
        f2_vs_b_state=by_scen["F2"].vs_b_state,
    )
    if not ok:
        msg = (
            "F2 vs B-state must be << P1 vs B-state "
            f"(max ratio {ORACLE_GAP_F2_VS_P1_MAX_RATIO})"
        )
        raise AssertionError(msg)


def _mean_abs_age_error_for_scenario(
    *,
    scenario: ScenarioId,
    params: ModelParams,
    ships: list[ShipmentTrace],
    root_seed: int,
    n_reps: int,
    n_particles: int,
    K: int,
    L: int,
    n_burn: int,
    n_score: int,
) -> float:
    """Birth-lot age error under shared CRN (newest slot vs true arrival τ).

    Evaluated on delivery days after the filter applies the scenario birth
    prior — the information gap F2 (Dirac age-at-receipt) vs P1 (cold mix)
    is visible without requiring long post-birth tracking.
    """
    grid = age_grid(K)
    mask = mask_for(scenario)
    errs: list[float] = []
    for rep in range(n_reps):
        seed = int(root_seed) + rep
        ep = run_episode(
            params,
            root_seed=seed,
            run_id=f"m15_oracle_{scenario}_{rep}",
            n_burn=n_burn,
            n_score=n_score,
            shipments=ships,
        )
        particle_filter = ResearchParticleFilter(params=params, N=n_particles, K=K, L=L)
        particle_filter._root_seed = seed
        particle_filter._run_id = f"m15_oracle_{scenario}_{rep}"
        rng = np.random.default_rng(seed + 23)
        particle_filter.initialize(rng, L=L)

        for d in ep.scored:
            obs = rich_obs_from_day_log(d, mask)
            particle_filter.step(obs, rng)
            if d.arrivals <= 0 or not d.lots:
                continue
            post = particle_filter.age_posterior(L - 1)
            true_age = float(d.lots[-1].tau)
            post_mean = float(np.sum(grid * post))
            errs.append(abs(post_mean - true_age))

    return float(np.mean(errs)) if errs else 0.0


def _validate_oracle_compare(compare: Sequence[str]) -> tuple[ScenarioId, ...]:
    if len(compare) == 0:
        msg = "compare must be non-empty"
        raise ValueError(msg)
    return _validate_rungs([str(c) for c in compare])


def run_m15_oracle_ladder(
    *,
    root_seed: int,
    compare: Sequence[ScenarioId] = ("P1", "F2"),
    n_particles: int = _SMOKE_N,
    n_reps: int = _SMOKE_ORACLE_REPS,
    n_burn: int = _SMOKE_N_BURN,
    n_score: int = _SMOKE_N_SCORE,
    figures_dir: Path | None = None,
    write_figure: bool = True,
    write_md: bool = False,
) -> list[OracleGapRow]:
    """Shared-CRN age-error ladder vs B-state (belief ≡ true ``(n, τ)``).

    Default ``compare`` is P1 vs F2. B-state age error is zero by construction;
    each row's ``vs_b_state`` is the scenario error minus that ceiling.
    """
    msg = "research particle filter removed (T-TAU-RETIRE)"
    raise NotImplementedError(msg)

