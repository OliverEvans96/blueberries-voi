"""CTL-02/04 one-step rollout with survival-weighted terminal salvage.

ADR 0059 (CTL-02=B): single-step policy improvement over a base policy.
ADR 0061 (CTL-04=B): horizon H ~ 2x shelf life with terminal salvage

    V_T = m * sum_l w_long(tau_l) * n_l

where ``w_long`` is computed from queue position under oldest-first allocation
(exported as ``w_long_oldest_first``). Forward sims call shared ``model.day_step``
(no shadow dynamics). Rollouts are sequential only (single-threaded paths).

ADR 0112 / T-083: production rollout horizon presets step in **multiples of 7**
calendar days so weekly / MWF periodicity is preserved (H ∈ {7, 14, 21, 28, …}).

Helpers live in ``crn_desync``, ``salvage``, and ``rollout_paths``; this module
keeps the public ``rollout_order`` / ``RolloutPolicy`` surface and re-exports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from blueberries_voi.controller.crn_desync import CrnDesyncResult as CrnDesyncResult
from blueberries_voi.controller.crn_desync import detect_crn_desync as detect_crn_desync
from blueberries_voi.controller.rollout_paths import _EMPTY_TAU_GRID
from blueberries_voi.controller.rollout_paths import (
    _mean_candidate_value as _mean_candidate_value,
)
from blueberries_voi.controller.salvage import (
    terminal_salvage_value as terminal_salvage_value,
)
from blueberries_voi.controller.salvage import (
    w_long_oldest_first as w_long_oldest_first,
)
from blueberries_voi.filter.belief import ShelfBelief, empty_shelf_belief
from blueberries_voi.model import ModelParams
from blueberries_voi.model import day_step as day_step

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# Production presets: multiples of 7 (weekly MWF cadence; ADR 0112 re-derive #3).
DEFAULT_ROLLOUT_HORIZONS: tuple[int, ...] = (7, 14, 21, 28)
# CTL-04=B desktop default: H = 2 * eta_ref (ModelParams.eta_ref=14 → 28).
DEFAULT_ROLLOUT_H: int = 28
DEFAULT_N_ROLLOUT_PATHS: int = 8
DEFAULT_CANDIDATE_CASE_RADIUS: int = 2
DEFAULT_N_PARTICLES: int = 64
DEFAULT_LEAD_TIME: int = 1
_DEFAULT_MARGIN: float = 2.0
_DEFAULT_WASTE_COST: float = 1.5
_DEFAULT_STOCKOUT_PENALTY: float = 3.0


class _BaseOrderPolicy(Protocol):
    def order(
        self,
        belief: ShelfBelief,
        *,
        day: int = 0,
        pending_orders: Mapping[int, int] | None = None,
    ) -> int: ...


def candidate_orders(
    base_q: int,
    *,
    case_size: int,
    radius: int = DEFAULT_CANDIDATE_CASE_RADIUS,
) -> list[int]:
    """Case multiples within ±``radius`` cases of ``base_q`` (non-negative)."""
    if case_size <= 0:
        msg = f"case_size must be positive, got {case_size}"
        raise ValueError(msg)
    if radius < 0:
        msg = f"radius must be non-negative, got {radius}"
        raise ValueError(msg)
    base_cases = int(base_q) // int(case_size)
    out: list[int] = []
    for dc in range(-int(radius), int(radius) + 1):
        q = (base_cases + dc) * int(case_size)
        if q >= 0:
            out.append(q)
    if not out:
        msg = "candidate neighbourhood is empty"
        raise ValueError(msg)
    return out


def rollout_order(
    belief: ShelfBelief,
    *,
    base_policy: _BaseOrderPolicy,
    params: ModelParams,
    rng_address: Mapping[str, Any],
    H: int = DEFAULT_ROLLOUT_H,
    n_rollout_paths: int = DEFAULT_N_ROLLOUT_PATHS,
    candidate_case_radius: int = DEFAULT_CANDIDATE_CASE_RADIUS,
    n_particles: int = DEFAULT_N_PARTICLES,
    candidates: Sequence[int] | None = None,
    pending_orders: Mapping[int, int] | None = None,
    day: int = 0,
    lead_time: int = DEFAULT_LEAD_TIME,
    margin: float = _DEFAULT_MARGIN,
    waste_cost: float = _DEFAULT_WASTE_COST,
    stockout_penalty: float = _DEFAULT_STOCKOUT_PENALTY,
) -> int:
    """One-step rollout: pick the case order with highest CRN-paired path value.

    Evaluates a neighbourhood of candidates around the base policy order for
    one improvement step. Each candidate is scored by ``n_rollout_paths``
    sequential forward sims of horizon ``H`` using shared ``day_step``, then
    terminal salvage ``V_T = m * sum_l w_long(tau_l) * n_l``.

    ``n_particles`` is reserved as a desktop compute-budget knob (sample / MF
    cap); the current mean-field rollout path does not resample particles.
    """
    del n_particles  # budget surface; MF rollout does not consume particles yet
    if int(H) <= 0:
        msg = f"H must be positive, got {H}"
        raise ValueError(msg)
    if int(n_rollout_paths) <= 0:
        msg = f"n_rollout_paths must be positive, got {n_rollout_paths}"
        raise ValueError(msg)

    pending0: dict[int, int] = (
        {int(k): int(v) for k, v in pending_orders.items()}
        if pending_orders is not None
        else {}
    )
    base_q = int(base_policy.order(belief, day=int(day), pending_orders=dict(pending0)))
    if candidates is None:
        cand_list = candidate_orders(
            base_q,
            case_size=int(params.case_size),
            radius=int(candidate_case_radius),
        )
    else:
        cand_list = [int(q) for q in candidates]
    if not cand_list:
        msg = "candidates must be non-empty"
        raise ValueError(msg)

    # Prefer base on ties: score base first, only switch on strict improvement.
    ordered = [base_q] + [q for q in cand_list if q != base_q]
    # Deduplicate while preserving order
    seen: set[int] = set()
    unique: list[int] = []
    for q in ordered:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    root_seed = int(rng_address["root_seed"])
    run_id = rng_address["run_id"]
    best_q = unique[0]
    best_score = float("-inf")
    for q in unique:
        score = _mean_candidate_value(
            belief,
            first_order=q,
            base_policy=base_policy,
            params=params,
            root_seed=root_seed,
            run_id=run_id,
            day0=int(day),
            H=int(H),
            n_paths=int(n_rollout_paths),
            pending0=pending0,
            lead_time=int(lead_time),
            margin=float(margin),
            waste_cost=float(waste_cost),
            stockout_penalty=float(stockout_penalty),
        )
        if score > best_score:
            best_score = score
            best_q = q
    return int(best_q)


class RolloutPolicy:
    """Closed-loop wrapper: day-first Protocol calling ``rollout_order``."""

    def __init__(
        self,
        *,
        base_policy: _BaseOrderPolicy,
        params: ModelParams,
        root_seed: int = 0,
        run_id: str = "rollout",
        H: int = DEFAULT_ROLLOUT_H,
        n_rollout_paths: int = DEFAULT_N_ROLLOUT_PATHS,
        candidate_case_radius: int = DEFAULT_CANDIDATE_CASE_RADIUS,
        n_particles: int = DEFAULT_N_PARTICLES,
        lead_time: int = DEFAULT_LEAD_TIME,
    ) -> None:
        self.base_policy = base_policy
        self.params = params
        self.root_seed = int(root_seed)
        self.run_id = run_id
        self.H = int(H)
        self.n_rollout_paths = int(n_rollout_paths)
        self.candidate_case_radius = int(candidate_case_radius)
        self.n_particles = int(n_particles)
        self.lead_time = int(lead_time)

    def order(
        self,
        day: int,
        belief: object | None = None,
        *,
        pending_orders: Mapping[int, int] | None = None,
    ) -> int:
        shelf = (
            belief
            if isinstance(belief, ShelfBelief)
            else empty_shelf_belief(tau_grid=_EMPTY_TAU_GRID)
        )
        pending = {} if pending_orders is None else pending_orders
        # Without on-hand lots, closed-loop currently has no shelf signal; matching
        # the base order preserves the CTL-02 improvement guarantee (tie).
        if not any(float(n) > 0.0 for n in shelf.lot_counts):
            return int(
                self.base_policy.order(shelf, day=int(day), pending_orders=pending)
            )
        return rollout_order(
            shelf,
            base_policy=self.base_policy,
            params=self.params,
            rng_address={
                "root_seed": self.root_seed,
                "run_id": f"{self.run_id}-d{int(day)}",
            },
            H=self.H,
            n_rollout_paths=self.n_rollout_paths,
            candidate_case_radius=self.candidate_case_radius,
            n_particles=self.n_particles,
            pending_orders=pending,
            day=int(day),
            lead_time=self.lead_time,
        )


__all__ = [
    "DEFAULT_CANDIDATE_CASE_RADIUS",
    "DEFAULT_N_PARTICLES",
    "DEFAULT_N_ROLLOUT_PATHS",
    "DEFAULT_ROLLOUT_H",
    "DEFAULT_ROLLOUT_HORIZONS",
    "CrnDesyncResult",
    "RolloutPolicy",
    "candidate_orders",
    "day_step",
    "detect_crn_desync",
    "rollout_order",
    "terminal_salvage_value",
    "w_long_oldest_first",
]
