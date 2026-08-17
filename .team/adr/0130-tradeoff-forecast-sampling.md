# ADR 0130: Particle-bank sampling for tradeoff display forecasts

## Status

Accepted (T-127)

## Context

The studio Run pane will show Options A+B tradeoff charts (`tradeoff_forecast` RPC):
expected waste and missed sales vs. order quantity over the **protection window**
(2–4 days from `OrderSchedule.protection_days`, not the full H=28 rollout horizon).

The existing order-decision rollout (`rollout_order` in `rollout.rs`) seeds each path
from belief via `unit_state_from_f_belief`, which **collapses** each lot's marginal
freshness to its expected `f`. That mean-collapse is appropriate for choosing an
order: the decision policy should not inject extra shelf-state noise beyond what the
filter already encodes in the belief mean.

For a **display** forecast, band width should reflect both demand/spoilage randomness
**and** today's shelf-state uncertainty (especially at low-observability rungs P0/P1).
Mean-collapse would understate uncertainty at those rungs.

`tradeoff_forecast` runs on `EngineSession`, which holds `self.bank: UnitParticleBank`
with per-unit particle freshness — more accurate than reconstructing a categorical
sampler from binned `f_grid`/`f_marginals` on the wire.

## Decision

1. **`tradeoff_forecast` paths** resample starting unit freshness from the session
   particle bank (e.g. `systematic_resample`) at the start of each Monte Carlo path.
2. **`rollout_order` / Autopilot `act`** remain on **mean-collapse** via
   `unit_state_from_f_belief`. This feature must not change the order Autopilot places.
3. **CRN across the q-sweep** is preserved: RNG keyed on `seed`/`path`/`day`, not `q`.
4. **No terminal salvage** in the tradeoff forecast (profit-objective only).
5. **Protection window** uses `OrderSchedule.protection_days(day)` already used in
   `damped_sw_order_f_belief` (`policy.rs`).

## Consequences

- Option A p10–p90 bands honestly widen at low-observability rungs.
- Autopilot behavior is unchanged.
- `tradeoff_forecast` must read `EngineSession.bank`, not only flattened belief wire.
- ADR must land before `impl-rust` implements `tradeoff.rs`.

## Alternatives rejected

- **Mean-collapse for display:** simpler but misleads at P0/P1 (bands too narrow).
- **Sample from binned `f_marginals`:** duplicates bank state; more code, less accurate.
- **Change `rollout_order` to sample:** would alter Autopilot orders — out of scope.
