"""Modal CPU / wall budget planning for channel-joint shards (nb19)."""

from __future__ import annotations

import math
from dataclasses import dataclass

WALL_LIMIT_S = 20 * 60
CPU_HR_LIMIT = 2.0
BUDGET_SAFETY = 0.90
DEFAULT_N_CHANNELS = 12
DEFAULT_N_BURN = 2
DEFAULT_MAX_PARALLEL = 32

__all__ = [
    "BUDGET_SAFETY",
    "CPU_HR_LIMIT",
    "DEFAULT_MAX_PARALLEL",
    "DEFAULT_N_BURN",
    "DEFAULT_N_CHANNELS",
    "WALL_LIMIT_S",
    "ChannelJointBudgetPlan",
    "assert_within_budget",
    "plan_channel_joint_budget",
]


@dataclass(frozen=True)
class ChannelJointBudgetPlan:
    """Feasible nb19 shard grid under wall and CPU-hour ceilings."""

    n_seeds: int
    n_score: int
    n_burn: int
    n_channels: int
    shard_count: int
    t_shard_s: float
    est_wall_s: float
    est_cpu_hr: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "n_seeds": self.n_seeds,
            "n_score": self.n_score,
            "n_burn": self.n_burn,
            "n_channels": self.n_channels,
            "shard_count": self.shard_count,
            "t_shard_s": self.t_shard_s,
            "est_wall_s": self.est_wall_s,
            "est_cpu_hr": self.est_cpu_hr,
        }


def _estimates(
    *,
    n_seeds: int,
    n_score: int,
    n_burn: int,
    n_channels: int,
    t_shard_s: float,
    max_parallel: int,
) -> tuple[float, float, int]:
    shards = n_seeds * n_channels
    wall_s = math.ceil(shards / max(max_parallel, 1)) * t_shard_s
    cpu_hr = (shards * t_shard_s) / 3600.0
    return wall_s, cpu_hr, shards


def plan_channel_joint_budget(
    t_shard_s: float,
    *,
    n_channels: int = DEFAULT_N_CHANNELS,
    n_burn: int = DEFAULT_N_BURN,
    n_score_min: int = 10,
    n_score_max: int = 30,
    max_seeds: int = 12,
    max_parallel: int = DEFAULT_MAX_PARALLEL,
) -> ChannelJointBudgetPlan:
    """Greedy: maximize seeds at ``n_score_min``, then bump ``n_score`` if room."""
    if t_shard_s <= 0:
        msg = "t_shard_s must be positive"
        raise ValueError(msg)

    wall_cap = WALL_LIMIT_S * BUDGET_SAFETY
    cpu_cap = CPU_HR_LIMIT * BUDGET_SAFETY

    best: ChannelJointBudgetPlan | None = None

    for n_score in range(n_score_min, n_score_max + 1):
        for n_seeds in range(max_seeds, 0, -1):
            wall_s, cpu_hr, shards = _estimates(
                n_seeds=n_seeds,
                n_score=n_score,
                n_burn=n_burn,
                n_channels=n_channels,
                t_shard_s=t_shard_s,
                max_parallel=max_parallel,
            )
            if wall_s <= wall_cap and cpu_hr <= cpu_cap:
                candidate = ChannelJointBudgetPlan(
                    n_seeds=n_seeds,
                    n_score=n_score,
                    n_burn=n_burn,
                    n_channels=n_channels,
                    shard_count=shards,
                    t_shard_s=t_shard_s,
                    est_wall_s=wall_s,
                    est_cpu_hr=cpu_hr,
                )
                if best is None or (
                    candidate.n_seeds > best.n_seeds
                    or (
                        candidate.n_seeds == best.n_seeds
                        and candidate.n_score > best.n_score
                    )
                ):
                    best = candidate
                break

    if best is None:
        msg = (
            f"no feasible plan for t_shard_s={t_shard_s:.1f}s within "
            f"wall={wall_cap:.0f}s cpu_hr={cpu_cap:.2f}"
        )
        raise RuntimeError(msg)
    return best


def assert_within_budget(plan: ChannelJointBudgetPlan) -> None:
    """Raise when a plan exceeds safety-adjusted Modal ceilings."""
    wall_cap = WALL_LIMIT_S * BUDGET_SAFETY
    cpu_cap = CPU_HR_LIMIT * BUDGET_SAFETY
    if plan.est_wall_s > wall_cap:
        msg = f"planned wall {plan.est_wall_s:.1f}s exceeds cap {wall_cap:.1f}s"
        raise RuntimeError(msg)
    if plan.est_cpu_hr > cpu_cap:
        msg = f"planned CPU-hr {plan.est_cpu_hr:.3f} exceeds cap {cpu_cap:.3f}"
        raise RuntimeError(msg)
