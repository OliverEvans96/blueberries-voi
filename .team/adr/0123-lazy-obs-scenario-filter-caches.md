# 0123. Observation scenario is live via lazy per-rung filter catch-up

STATUS: ACCEPTED
DATE: 2026-08-14
RELATED: ADR 0110 (ladder and masks; apply-on-reset superseded here), ADR 0122 (90-day episode), ADR 0065 (CRN shared physics)

## Context

ADR 0110 applied studio `obs_scenario` only on init/reset because a sequential counts-only
filter’s weights already include the previous mask. Hot-swapping the live particle cloud would
mix likelihoods. The revisit condition was a mid-episode filter restart that is bit-stable
under CRN.

T-112 now keeps a full episode (cap 90). The scientific comparison (beliefs under P1 vs F2
given the same lots, sales, waste, and **past orders**) is valid if we replay the richest
observation log. Future Autopilot orders may fork after a chip change; that is the intended demo.

## Decision

We will:

1. Keep **one physics trajectory and one order sequence**. Persist a **richest** day log for
   the episode (totals, lot maps, receipt meta). Do not store 90 particle clouds.
2. Keep a lazy map per `ScenarioId`: `ResearchParticleFilter | None` and `last_synced_day`. First select at day
   t initializes and steps `0…t-1` with `mask_for(id)` on the log. Advance steps **only the
   active** filter. Switch-back steps only the gap.
3. Expose `EngineSession.set_obs_scenario(id)` that performs that catch-up and returns a
   Snapshot. Hosts (HTTP, Pyodide RPC) forward that one method. Studio chips call it and do
   **not** mark `obs_scenario` as dirty-until-Reset.
4. Selecting a chip retargets Autopilot’s next `act` to that rung’s `ShelfBelief`. Past days
   stay the shared trajectory; future orders may change.
5. Reset / seed / physics knobs still wipe log and all caches. Other SimConfig remains
   reset-gated.
6. **Still forbidden:** retarget `_obs_scenario` on the current particles without replay.
7. Keep the type name `ResearchParticleFilter`. Do not rename in this decision.

The six-rung ladder, default P1, and SCN-P2 Out from ADR 0110 remain.

## Alternatives considered

- **Keep reset-only apply (ADR 0110 as-is)** — rejected: operators cannot compare knowledge
  on the episode they just played.
- **Naive hot-swap of the live cloud** — rejected: mixed sequential weights are not a scenario.
- **Six live filters every Advance** — rejected: ~6× the expensive filter cost in the browser
  demo; lazy catch-up is enough.
- **Replay physics from seed with stored orders** — rejected as the primary path: a richest
  log is smaller and avoids a second physics pass; CRN already keys filter RNG by day.

## Consequences

**Easy:** chips toggle beliefs on the current run; Autopilot follows the selected knowledge.

**Hard / cost:** first click on a cold rung at late day is one filter pass (seconds on Pyodide);
UI must disable chips and show progress. Memory up to one demo `N=200` cloud per opened rung.

**Locked in:** catch-up protocol; `set_obs_scenario`; Autopilot follows the chip; no in-place
mask swap.

**Revisit if:** a rename of `ResearchParticleFilter`. Rust/wasm method: ADR [0124](./0124-rust-wasm-set-obs-scenario.md).
