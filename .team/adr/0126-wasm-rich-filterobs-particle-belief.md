# 0126. Wasm FilterObs is RichObs-shaped; Snapshot.belief is the particle posterior

STATUS: ACCEPTED
DATE: 2026-08-14
RELATED: ADR 0086 (masks), ADR 0105 (arrival-only ages), ADR 0106 (belief export), ADR 0123–0124 (catch-up)

## Context

ADR 0124 shipped lazy `set_obs_scenario` on `voi_core` with totals-only `FilterObs` and
explicitly deferred lot-resolved rungs. Interactive Snapshot `belief` still serializes
physics lots (`oracle_flat_belief`), so chip clicks retarget `applied_config` and catch-up
a `ParticleBank` the UI never sees. F1–F2 therefore equal P1, and births ignore F2/F2a
receipt information.

Python `mask_for` / `RichObs` / arrival-only birth (ADR 0105–0106) already define the
contract. Wasm must match that contract without Abdella parquet.

## Decision

We will:

1. Add a public Rust observation module with `mask_for`, `ObsMask`, richest `RichDay`, and
   `FilterObs` fields aligned to Python `RichObs` (totals, lot maps, `pack_date_days`,
   `age_at_receipt`, `lot_ids_live`). Absent fields are `None`, never invented zeros.
2. Build each day’s `RichDay` from `DayStepOut` (lot vectors + ids) plus receipt meta:
   `age_at_receipt = delivery_tau`; `pack_date_days = day - round(tau)` when a delivery
   exists. Catch-up and live `filter_step` apply `mask_for(obs_scenario)` to that log.
3. Birth τ from the masked observation: shipments mix when no receipt age/pack date;
   F2a Gaussian (mean = calendar transit, SD = 0.75); F2 Dirac on observed age. Ages then
   advance only with the shared clock. No B-state mask; P2 rejected.
4. Export Snapshot `belief` by flattening the **active** `ParticleBank` onto the existing
   `L×K` wire (weighted lot counts and age histograms). Keep `live_lots` as the physics
   truth overlay only.
5. Studio Belief heatmap density is a function of `snapshot.belief`, not of `live_lots`
   ages/counts (truth may still extend the count axis).

## Alternatives considered

- **Keep totals-only FilterObs (ADR 0124 clause)** — rejected: F1/F1s/F2a/F2 chips cannot
  change the posterior; the studio ladder would remain a lie on wasm.
- **Keep oracle_flat_belief and only change weights internally** — rejected: the Belief tab
  reads Snapshot.belief; physics overlay must stay on `live_lots`.
- **Load Abdella parquet in wasm for P0 mix** — rejected: no filesystem; session
  `shipments` traces already supply a cold mix.

## Consequences

**Easy:** mid-episode chips change the heatmap under wasm the same way Python masks change
ShelfBelief; catch-up CRN stays day-keyed.

**Hard / cost:** `filter_step` must score lot maps when present; particle slots must stay
aligned with logged `lot_ids` / `sales_by` order. Flattening a variable-length bank onto
fixed `L` can truncate or pad.

**Locked in:** belief wire = particle posterior; live_lots = truth; wasm birth without
parquet; RichDay stored for catch-up.

**Revisit if:** particle `L` must match Python sliding-window semantics bit-for-bit, or
wasm gains a real Abdella mix.
