"""FreshNet-derived calendar demand profile (ADR 0110 / 0112 / T-082).

Runtime loads committed ``data/freshnet/demand_profile.json`` via stdlib JSON only.
No Hugging Face / ``datasets`` imports.

μ(day) = scale_target_mu * dow_factors[day % 7] * week_factors[min(day // 7, W-1)]
with ``dow_index`` monday0 (as recorded in the product notes).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DemandProfile:
    """Day-indexed NB mean factors from the FreshNet derived product."""

    scale_target_mu: float
    dow_factors: tuple[float, ...]
    week_factors: tuple[float, ...]
    demand_vm: float = 2.0

    def __post_init__(self) -> None:
        if len(self.dow_factors) != 7:
            msg = "dow_factors must have length 7 (monday0)"
            raise ValueError(msg)
        if len(self.week_factors) < 1:
            msg = "week_factors must be non-empty"
            raise ValueError(msg)
        if self.scale_target_mu <= 0.0:
            msg = "scale_target_mu must be positive"
            raise ValueError(msg)

    def mu(self, day: int) -> float:
        """Calendar NB mean for episode day (monday0 DOW; week clamped)."""
        dow = int(day) % 7
        week = min(int(day) // 7, len(self.week_factors) - 1)
        return float(
            self.scale_target_mu * self.dow_factors[dow] * self.week_factors[week]
        )


def load_demand_profile(path: Path | str) -> DemandProfile:
    """Load a committed demand_profile.json (JSON only; no HF)."""
    raw: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = "demand_profile.json root must be a JSON object"
        raise ValueError(msg)
    dow = raw.get("dow_factors")
    week = raw.get("week_factors")
    if not isinstance(dow, list) or not isinstance(week, list):
        msg = "demand_profile.json must include dow_factors and week_factors lists"
        raise ValueError(msg)
    scale = float(raw["scale_target_mu"])
    vm = float(raw.get("demand_vm", 2.0))
    return DemandProfile(
        scale_target_mu=scale,
        dow_factors=tuple(float(x) for x in dow),
        week_factors=tuple(float(x) for x in week),
        demand_vm=vm,
    )
