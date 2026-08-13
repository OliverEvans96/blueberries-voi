# 0094. VOI package layout and public API under `voi/`

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: VOI / M3 package surface
GROUP: VOI
PROVENANCE: M3 Wave 0 lock (post–M2)
TIER: 1
MILESTONE: M3 — VOI sweep, oracles, misspecification arms

## Context

M2 left `blueberries_voi.voi` as an empty stub (`__all__ == []`) so CTL could ship without
claiming dollar VOI. M3 must own aggregation of profits across knowledge scenarios and β without
putting sweep orchestration inside `controller/` (policies stay pure) or duplicating SIM-01
accounting already in `sim/profit.py`. A module boundary choice now prevents later tangle between
metric math, CRN cells, bootstrap, and the outer grid.

## Decision

We will:

1. Implement the VOI library under **`src/blueberries_voi/voi/`** with focused modules:
   - `metric.py` — VOI-01 absolute $ and percentage vs P0
   - `crn.py` — SIM-02 outer-loop cell: shared physical realization across scenarios for one
     `(beta, replication)`
   - `bootstrap.py` — VOI-03 paired bootstrap CI on per-replication differences
   - `sweep.py` — VOI-04 / X-06 orchestrator over scenario × β (and smoke entrypoint)
2. Re-export the stable public names from `voi/__init__.py` (metric helpers, sweep smoke / run,
   result types). Keep matplotlib / filesystem figure writers **out** of these core modules
   (ENG-03 figures call in from `viz/` or `experiments/`).
3. Depend on existing `sim.profit`, `sim` closed-loop / multi-scenario patterns, `filter` masks /
   `ShelfBelief`, and `controller` SW+rollout — without importing Abdella parquet or writing
   figures from `voi/` itself.
4. Treat JSON-/list-friendly result dicts as preferred for later handoff; not a Pyodide deliverable.

## Alternatives considered

- **Put sweep under `sim/` next to `m2_multi_scenario.py`** — rejected: M2 already reserved VOI
  aggregation for `voi/`; keeping sim as physics + episode driver avoids a god-module.
- **Put sweep under `controller/`** — rejected: violates pure-policy library shape (M2 brief) and
  couples ordering to experiment grids.
- **Single monolithic `voi/sweep.py` only** — rejected: metric and bootstrap are independently
  testable contracts (VOI-01 / VOI-03) and should not require running a full grid to unit-test.

## Consequences

**Easy:** T-036–T-040 map 1:1 onto modules; CTL remains untouched for VOI math.  
**Hard:** Outer CRN cell must carefully share physics across masks without leaking filter RNG into
demand streams.  
**Locked:** M3 ownership of dollar VOI lives in `voi/`; no silent move into controller.  
**Revisit if:** A future ENG-01 façade needs a thinner `init/step/act` export — add a façade module
without collapsing metric/bootstrap into it.
