# 0116. CAL-01 track ownership and day_step demand signature

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: CAL-01
GROUP: CAL
PROVENANCE: CAL-01 Wave 0 — concurrency / file-ownership lock
TIER: 1
MILESTONE: CAL-01 — calendar realism

## Context

CAL-01 fans out parallel tracks. Without ownership rules, Wave 2–3 tips will fight over
`day_step` / `draw_demand` signatures and `controller/` vs `model/` files. ENG-01 used the same
pattern: Wave 0 assigns owners so A and B can land independently.

Track A can gate orders before day-varying μ exists; Track B owns the demand signature change.

## Decision

We will assign **file / API ownership** and a **compatibility shim** as follows:

| Track | Owns | Must not edit without coordination |
|-------|------|-------------------------------------|
| **A** (schedule / controllers) | `OrderSchedule`; `sim/episode.py`, `simulator/day_driver.py`, session open-loop gates; `controller/*` protection / SW / Rung0 / rollout / toy_dp; M2 ladder/gates / α inputs | `model/demand*` product loaders; `data/freshnet/` |
| **B** (demand / FreshNet) | `data/freshnet/`; ingest/fit scripts; `[freshnet]` extra; `ModelParams` profile fields; **`draw_demand(..., *, day=)`** and physics wiring of profile μ(day) | `web/` UI; OrderSchedule definition |
| **C** (web) | `web/` Snapshot consumers, next-order-day chrome, demand charts / mock adapter | Library physics kernels except via exported Snapshot fields |
| **D** (closeout) | VOI smoke under new base; changelog; milestone DoD; FIL-13 remotesure note | New feature work outside closeout |

**Signature ownership (binding):**

1. **CAL-B3 (T-082)** owns landing `draw_demand(rng, params, *, day: int | None = None)` and any
   `day_step` / `ModelParams` changes required to read the profile.
2. **CAL-A2 (T-079)** may land **before** B3 with a thin shim: call sites pass `day=` when known;
   if the keyword is absent or `day is None`, behaviour remains pre-CAL i.i.d. μ (or constant
   `demand_mu`) so A2 tests stay green.
3. Controllers in **CAL-A3** may use **day-varying protection length** with homogeneous μ until B3
   lands heterogeneous μ; **CAL-B4** upgrades protection quantiles / CRN cells to day-indexed μ.
4. CRN identity: demand stream remains `(root_seed, PHYSICS_RUN_ID, day, :demand)` — never
   scenario-keyed ([SIM-02](./0065-sim-02-outer-loop-crn-scope.md) / [SIM-05](./0068-sim-05-seed-and-experiment-addressing-scheme.md)).

## Alternatives considered

- **Serialize all tracks behind one tip** — rejected: destroys the ENG-01-style concurrency CAL-01
  was planned for.
- **A3 owns `draw_demand(day=)`** — rejected: demand product and ModelParams belong to Track B;
  dual owners of the same signature invite merge conflicts.
- **Require B3 before any A2 merge** — rejected: order gating is independent of μ(day); shim is
  cheaper than blocking Track A.
- **Scenario-keyed demand RNGs for calendar μ** — rejected: would break VOI CRN pairing.

## Consequences

**Easy:** Wave 1–2 parallel fan-out; A2 green without FreshNet fit; clear conflict resolution.

**Hard / cost:** temporary shim / dual-path μ until B3; reviewers must check ownership boundaries;
integrate merges must respect track tips.

**Locked in:** B3 owns `day=` on `draw_demand`; A2 may precede with shim; CRN day addressing
unchanged; track file map above.

**Revisit if:** a single-package refactor moves schedule into `model/` (would need a new ADR).
