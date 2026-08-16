"""M1.5 B-state oracle ladder helpers and runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from blueberries_voi.viz.m15_common import ORACLE_GAP_F2_VS_P1_MAX_RATIO

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from blueberries_voi.filter.types import ScenarioId


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


def run_m15_oracle_ladder(
    *,
    root_seed: int,
    compare: Sequence[ScenarioId] = ("P1", "F2"),
    n_particles: int = 32,
    n_reps: int = 2,
    n_burn: int = 1,
    n_score: int = 2,
    figures_dir: Path | None = None,
    write_figure: bool = True,
    write_md: bool = False,
) -> list[OracleGapRow]:
    """Shared-CRN age-error ladder vs B-state (belief ≡ true ``(n, τ)``).

    Retired with τ research particle filter (T-TAU-RETIRE).
    """
    _ = (
        root_seed,
        compare,
        n_particles,
        n_reps,
        n_burn,
        n_score,
        figures_dir,
        write_figure,
        write_md,
    )
    msg = "research particle filter removed (T-TAU-RETIRE)"
    raise NotImplementedError(msg)
