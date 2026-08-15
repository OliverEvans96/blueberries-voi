# 0124. Rust/wasm hosts implement the same `set_obs_scenario` catch-up

STATUS: ACCEPTED
DATE: 2026-08-14
RELATED: ADR 0123 (Python lazy rungs), ADR 0120 (wasm adapter), ADR 0122 (90-day cap)

## Context

ADR 0123 locked live observation chips via lazy per-rung catch-up on the Python
session. Its revisit clause named Rust/wasm. The wasm worker still only speaks
init/step/step_n/reset/act, so chips cannot retarget a wasm or PyO3 session.

## Decision

We will:

1. Implement `EngineSession.set_obs_scenario` in `voi_core` with the same
   protocol as Python: richest totals log, lazy `ParticleBank` per scenario,
   gap-only catch-up, CRN keyed by seed and day.
2. Forward RPC method `set_obs_scenario` through wasm-bindgen `handle_rpc`,
   the wasm worker, `WasmAdapter`, and PyO3 `PyEngineSession`.
3. Keep class name `RBPF` on the Python side. Rust keeps `ParticleBank`.
4. Apply the 90-day refuse on the mock adapter so all studio hosts share the
   T-112 horizon.

## Alternatives considered

- **Leave wasm on reset-only chips** — rejected: studio already calls
  `set_obs_scenario`; wasm would silently fall back or fail.
- **Replay full physics from seed** — rejected in 0123; same for Rust.
- **Port full RichObs/lot masks into Rust now** — rejected at T-114: interactive
  wasm filter was totals-only; P0 vs P1 was the distinguishable mask. **Superseded
  for FilterObs richness by [0126](./0126-wasm-rich-filterobs-particle-belief.md).**

## Consequences

**Easy:** chips work on wasm the same way as Pyodide/HTTP.

**Hard / cost:** three hosts must keep the catch-up protocol in sync; until 0126,
Rust beliefs did not match Python F1/F2 lot-resolved filters.

**Locked in:** RPC name `set_obs_scenario`; lazy rungs in `voi_core`.

**Revisit if:** Rust grows lot-resolved observations — done in 0126.
