#!/usr/bin/env python3
"""Demo-budget RPC smoke for the Pyodide worker edge (T-047 / ADR 0099).

Exercises ``init`` + one ``step`` + ``step_n`` (≥2 orders) through
``session_rpc.handle_rpc`` under dialed ``DEMO_BUDGETS`` (n_particles ≤ 200;
not the full production particle count). Pass/fail via process exit code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from session_rpc import (  # noqa: E402
    DEMO_BUDGETS,
    handle_rpc,
    prepare_demo_config,
)

from blueberries_voi.model.abdella import ShipmentTrace  # noqa: E402


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    warm = np.asarray([5.0, 5.0, 5.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="SMOKE-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        ),
        ShipmentTrace(
            shipment_id="SMOKE-WARM",
            times_d=times,
            temps_c=warm,
            duration_d=2.0,
        ),
    ]


def _call(method: str, params: dict, *, req_id: str) -> object:
    raw = handle_rpc({"id": req_id, "method": method, "params": params})
    resp = json.loads(raw) if isinstance(raw, str) else raw
    if not resp.get("ok"):
        err = resp.get("error") or {}
        raise RuntimeError(f"{err.get('type')}: {err.get('message')}")
    return resp["result"]


def main() -> int:
    # Dialed demo budgets — DEMO_BUDGETS, never the full production particle count.
    wire_cfg = prepare_demo_config(
        {
            "n_particles": int(DEMO_BUDGETS["n_particles"]),
            "H": int(DEMO_BUDGETS["H"]),
            "n_rollout_paths": int(DEMO_BUDGETS["n_rollout_paths"]),
            "candidate_case_radius": int(DEMO_BUDGETS["candidate_case_radius"]),
            "L": 2,
            "K": 4,
            "enable_filter": True,
        },
        shipments=_fixture_shipments(),
    )
    assert int(wire_cfg["n_particles"]) <= 200

    snap = _call("init", {"config": wire_cfg, "seed": 47}, req_id="smoke-init")
    if not isinstance(snap, dict) or "belief" not in snap:
        raise RuntimeError("init did not return a Snapshot")

    delta = _call("step", {"order_qty": 1}, req_id="smoke-step")
    if not isinstance(delta, dict) or "day" not in delta:
        raise RuntimeError("step did not return a DayDelta")

    multi = _call("step_n", {"orders": [1, 0]}, req_id="smoke-stepn")
    if isinstance(multi, list):
        deltas = multi
    elif isinstance(multi, dict) and "deltas" in multi:
        deltas = list(multi["deltas"])
    else:
        raise RuntimeError("step_n must return list[DayDelta] or {deltas: [...]}")
    if len(deltas) < 2:
        raise RuntimeError("step_n smoke requires ≥2 orders")

    print("T-047 demo budget smoke OK: init + step + step_n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"T-047 demo budget smoke FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
