"""SIM-02 outer-loop CRN cell: shared physics across knowledge scenarios.

Wave F (T-121 / ADR 0127): Abdella/alpha orchestration then ``run_voi_crn_cell_py``
only — no Python episode loop body.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from blueberries_voi.sim.alpha_tune import require_tuned_alpha_table
from blueberries_voi.sim.shipments import default_shipments, smoke_cool_shipments

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from blueberries_voi.model.abdella import ShipmentTrace
    from blueberries_voi.sim.profit import ProfitCosts

PHYSICS_RUN_ID: str = "voi-physics"

VOI_SCENARIOS: tuple[str, ...] = (
    "P0",
    "P1",
    "F1",
    "F1s",
    "F2a",
    "F2",
    "B-state",
)

_SMOKE_ALPHA: float = 0.9

__all__ = [
    "PHYSICS_RUN_ID",
    "VOI_SCENARIOS",
    "default_shipments",
    "run_voi_crn_cell",
    "smoke_cool_shipments",
]


def run_voi_crn_cell(
    *,
    beta: float,
    root_seed: int,
    scenarios: Sequence[str] | None = None,
    n_burn: int = 1,
    n_score: int = 2,
    costs: ProfitCosts | None = None,
    shipments: Sequence[ShipmentTrace] | None = None,
    params: Any | None = None,
    lead_time: int = 1,
    filter_n: int = 32,
    alpha: float = _SMOKE_ALPHA,
    alpha_table_path: str | Path | None = None,
    H: int = 2,
    n_rollout_paths: int = 1,
    policy: Any | None = None,
) -> dict[str, float]:
    """Per-scenario scored episode profit under shared physics CRN (SIM-02=C).

    Loads Abdella shipments when ``shipments=None``, resolves alpha table when
    provided, then delegates episode execution to ``run_voi_crn_cell_py``.
    """
    del costs, policy  # profit/costs and custom policies are Rust-owned post-Wave F
    from blueberries_voi.backend import rust_available, rust_core, warn_fallback_once

    warn_fallback_once()
    if not rust_available() or rust_core is None:
        msg = (
            "run_voi_crn_cell requires BLUEBERRIES_VOI_BACKEND=rust and "
            "blueberries_voi._core (T-121 Wave F)"
        )
        raise RuntimeError(msg)

    names = list(scenarios) if scenarios is not None else list(VOI_SCENARIOS)
    for name in names:
        if name not in VOI_SCENARIOS:
            msg = f"unknown VOI scenario {name!r}; expected one of {VOI_SCENARIOS}"
            raise ValueError(msg)

    if alpha_table_path is not None:
        alphas = require_tuned_alpha_table(alpha_table_path)
        if "sw" not in alphas:
            msg = (
                "tuned alpha table incomplete for VOI: missing arm 'sw' "
                f"(path={alpha_table_path!s})"
            )
            raise ValueError(msg)
        _ = float(alphas["sw"])
    else:
        _ = float(alpha)

    ships = list(shipments) if shipments is not None else default_shipments()
    times = [list(map(float, getattr(s, "times_d", []))) for s in ships]
    temps = [list(map(float, getattr(s, "temps_c", []))) for s in ships]

    p = params
    beta_val = float(beta if p is None else replace(p, beta=float(beta)).beta)

    rows = rust_core.run_voi_crn_cell_py(
        beta_val,
        int(root_seed),
        int(n_burn),
        int(n_score),
        int(filter_n),
        int(H),
        int(n_rollout_paths),
        int(lead_time),
        times,
        temps,
    )
    table = {str(k): float(v) for k, v in rows}
    return {n: table[n] for n in names if n in table}
