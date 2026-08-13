"""Toy-scale exact DP optimality certificate (CTL-06 / ADR 0063).

Backward induction on a frozen small grid (demand support {0,1,2}, truncated
τ bins, ~2 lots, short horizon). ``gap_vs_rollout`` reports the optimality
gap between the DP optimum and a base (myopic protection) policy value on the
**same identical** toy instance. When one-step rollout (T-030) is not yet
available, the base policy stands in for the comparison arm — the gap still
adjudicates distance from optimal on this certificate instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import TYPE_CHECKING

from blueberries_voi.model import ModelParams, q10_age_increment

if TYPE_CHECKING:
    from collections.abc import Sequence

# Frozen CI grid (T-031 open question: keep under a few seconds).
DEMAND_SUPPORT: tuple[int, ...] = (0, 1, 2)
TAU_BINS: tuple[float, ...] = (0.0, 1.0, 2.0, 3.0)
MAX_LOTS: int = 2
MAX_INVENTORY: int = 4
HORIZON: int = 3
LEAD_TIME_DAYS: int = 1
PROTECTION_DEMAND_DAYS: int = 2

_HOLDING_COST: float = 0.1
_WASTE_COST: float = 1.0
_STOCKOUT_COST: float = 5.0
_UNIT_REVENUE: float = 1.0

_params_for_delta = ModelParams()
DELTA_TAU_L: float = float(
    q10_age_increment(
        float(LEAD_TIME_DAYS),
        t_store_c=_params_for_delta.t_store_c,
        t_ref_c=_params_for_delta.t_ref_c,
        q10=_params_for_delta.q10,
    )
)
delta_tau_L: float = DELTA_TAU_L
TOY_DELTA_TAU_L: float = DELTA_TAU_L

# Inventory state: counts per age bin (youngest → oldest), length = n_bins.
InvState = tuple[int, ...]
# Full pre-decision state: (inventory_by_age, pipeline arriving this period).
DpState = tuple[InvState, int]


@dataclass(frozen=True)
class ToyDpResult:
    """Optimal value / policy tables for the locked toy DP instance."""

    value_table: dict[tuple[int, DpState], float]
    policy_table: dict[tuple[int, DpState], int]
    demand_support: tuple[int, ...]
    tau_bins: tuple[float, ...]
    max_lots: int
    max_inventory: int
    horizon: int
    delta_tau_L: float
    base_value_table: dict[tuple[int, DpState], float]
    initial_state: DpState


def _demand_probs(support: Sequence[int]) -> dict[int, float]:
    n = len(support)
    p = 1.0 / float(n)
    return {int(d): p for d in support}


def _enumerate_inventories(
    *,
    n_bins: int,
    max_inventory: int,
    max_lots: int,
) -> list[InvState]:
    """Age-bin count vectors with total ≤ max_inventory and ≤ max_lots live lots."""
    out: list[InvState] = []
    for counts in product(range(max_inventory + 1), repeat=n_bins):
        total = sum(counts)
        if total > max_inventory:
            continue
        live_lots = sum(1 for c in counts if c > 0)
        if live_lots > max_lots:
            continue
        out.append(tuple(int(c) for c in counts))
    return out


def _total(inv: InvState) -> int:
    return int(sum(inv))


def _sell_fefo(inv: InvState, demand: int) -> tuple[InvState, int, int]:
    """Sell from oldest bins first; return (leftover, sales, unmet)."""
    bins = list(inv)
    remaining = int(demand)
    sales = 0
    for i in range(len(bins) - 1, -1, -1):
        take = min(bins[i], remaining)
        bins[i] -= take
        sales += take
        remaining -= take
        if remaining == 0:
            break
    return tuple(bins), sales, remaining


def _age_and_waste(inv: InvState) -> tuple[InvState, int]:
    """Shift inventory one age bin older; oldest bin exits as waste."""
    if not inv:
        return inv, 0
    waste = int(inv[-1])
    aged = (0, *inv[:-1])
    return aged, waste


def _deliver(inv: InvState, pipeline: int) -> InvState:
    """Receive pipeline into the youngest age bin."""
    if not inv:
        return inv
    bins = list(inv)
    bins[0] += int(pipeline)
    return tuple(bins)


def _transition(
    inv: InvState,
    pipeline: int,
    order: int,
    demand: int,
    *,
    max_inventory: int,
) -> tuple[DpState, float]:
    """One period: sell → age/waste → deliver pipeline → order becomes pipeline."""
    after_sale, sales, unmet = _sell_fefo(inv, demand)
    aged, waste = _age_and_waste(after_sale)
    next_inv = _deliver(aged, pipeline)
    # Cap for finite state; excess treated as immediate waste.
    overflow = max(0, _total(next_inv) - max_inventory)
    if overflow:
        bins = list(next_inv)
        left = overflow
        for i in range(len(bins) - 1, -1, -1):
            take = min(bins[i], left)
            bins[i] -= take
            left -= take
            if left == 0:
                break
        next_inv = tuple(bins)
        waste += overflow
    next_pipe = int(order)
    reward = (
        _UNIT_REVENUE * float(sales)
        - _HOLDING_COST * float(_total(after_sale))
        - _WASTE_COST * float(waste)
        - _STOCKOUT_COST * float(unmet)
    )
    return (next_inv, next_pipe), reward


def _base_order(
    inv: InvState,
    pipeline: int,
    *,
    max_inventory: int,
    mean_demand: float,
    protection_demand_days: int,
) -> int:
    """Myopic protection base-stock (stand-in for rollout when T-030 absent)."""
    target = min(
        max_inventory,
        round(mean_demand * float(protection_demand_days)),
    )
    position = _total(inv) + int(pipeline)
    return max(0, min(max_inventory, target - position))


def solve_toy_dp(
    *,
    demand_support: Sequence[int] = DEMAND_SUPPORT,
    tau_bins: Sequence[float] = TAU_BINS,
    max_lots: int = MAX_LOTS,
    max_inventory: int = MAX_INVENTORY,
    horizon: int = HORIZON,
    lead_time_days: int = LEAD_TIME_DAYS,
    protection_demand_days: int = PROTECTION_DEMAND_DAYS,
) -> ToyDpResult:
    """Run backward induction on the locked toy state space.

    ``lead_time_days`` is fixed at 1 for this certificate (pipeline lag);
    ``protection_demand_days`` documents the shared R+L window with SW / Rung 0.
    """
    del lead_time_days  # LT=1 is baked into the one-period pipeline lag
    support = tuple(int(d) for d in demand_support)
    bins = tuple(float(t) for t in tau_bins)
    n_bins = len(bins)
    if n_bins < 2:
        msg = "tau_bins must have length >= 2"
        raise ValueError(msg)
    h = int(horizon)
    m_inv = int(max_inventory)
    m_lots = int(max_lots)
    prot = int(protection_demand_days)

    inventories = _enumerate_inventories(
        n_bins=n_bins, max_inventory=m_inv, max_lots=m_lots
    )
    inv_set = set(inventories)
    pipelines = range(m_inv + 1)
    actions = range(m_inv + 1)
    probs = _demand_probs(support)
    mean_d = sum(d * probs[d] for d in support)

    # Terminal value 0 at t = horizon.
    value: dict[tuple[int, DpState], float] = {}
    policy: dict[tuple[int, DpState], int] = {}
    base_value: dict[tuple[int, DpState], float] = {}

    for inv, pipe in product(inventories, pipelines):
        value[(h, (inv, pipe))] = 0.0
        base_value[(h, (inv, pipe))] = 0.0
        policy[(h, (inv, pipe))] = 0

    for t in range(h - 1, -1, -1):
        for inv, pipe in product(inventories, pipelines):
            state: DpState = (inv, pipe)
            best_q = 0
            best_v = float("-inf")
            for q in actions:
                exp_v = 0.0
                for d, p_d in probs.items():
                    nxt, reward = _transition(inv, pipe, q, d, max_inventory=m_inv)
                    if nxt[0] not in inv_set:
                        nxt = (_project_inv(nxt[0], m_inv, m_lots), nxt[1])
                    exp_v += p_d * (reward + value[(t + 1, nxt)])
                if exp_v > best_v:
                    best_v = exp_v
                    best_q = int(q)
            value[(t, state)] = best_v
            policy[(t, state)] = best_q

            q_base = _base_order(
                inv,
                pipe,
                max_inventory=m_inv,
                mean_demand=mean_d,
                protection_demand_days=prot,
            )
            exp_base = 0.0
            for d, p_d in probs.items():
                nxt, reward = _transition(inv, pipe, q_base, d, max_inventory=m_inv)
                if nxt[0] not in inv_set:
                    nxt = (_project_inv(nxt[0], m_inv, m_lots), nxt[1])
                exp_base += p_d * (reward + base_value[(t + 1, nxt)])
            base_value[(t, state)] = exp_base

    initial: DpState = (tuple(0 for _ in range(n_bins)), 0)
    return ToyDpResult(
        value_table=value,
        policy_table=policy,
        demand_support=support,
        tau_bins=bins,
        max_lots=m_lots,
        max_inventory=m_inv,
        horizon=h,
        delta_tau_L=float(DELTA_TAU_L),
        base_value_table=base_value,
        initial_state=initial,
    )


def _project_inv(inv: InvState, max_inventory: int, max_lots: int) -> InvState:
    """Clip / merge so the vector respects max_inventory and max_lots."""
    bins = list(inv)
    # Drop youngest excess lots if too many live lots.
    while sum(1 for c in bins if c > 0) > max_lots:
        for i, c in enumerate(bins):
            if c > 0:
                bins[i] = 0
                break
    total = sum(bins)
    if total > max_inventory:
        left = total - max_inventory
        for i in range(len(bins) - 1, -1, -1):
            take = min(bins[i], left)
            bins[i] -= take
            left -= take
            if left == 0:
                break
    return tuple(bins)


def gap_vs_rollout(result: ToyDpResult) -> float:
    """Optimality gap J* - J_base on the **same identical** toy instance.

    Compares the exact-DP optimum to the base (myopic protection) policy value
    evaluated under the same dynamics and initial state. This is the CTL-06
    certificate vs rollout/base; rollout improvement (T-030) can replace the
    base arm later without changing the DP side.
    """
    key = (0, result.initial_state)
    j_star = float(result.value_table[key])
    j_base = float(result.base_value_table[key])
    gap = j_star - j_base
    # Numerical noise: clamp tiny negatives from float ties to 0.
    if gap < 0.0 and abs(gap) < 1e-12:
        return 0.0
    return float(gap)


__all__ = [
    "DELTA_TAU_L",
    "DEMAND_SUPPORT",
    "HORIZON",
    "LEAD_TIME_DAYS",
    "MAX_INVENTORY",
    "MAX_LOTS",
    "PROTECTION_DEMAND_DAYS",
    "TAU_BINS",
    "TOY_DELTA_TAU_L",
    "ToyDpResult",
    "delta_tau_L",
    "gap_vs_rollout",
    "solve_toy_dp",
]
