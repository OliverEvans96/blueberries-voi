# 0152. Studio opening inventory at 95% service level

STATUS: ACCEPTED
DATE: 2026-08-28
RELATED: [0136](./0136-zero-init-phantom-belief-remediation.md), [0114](./0114-order-schedule-api.md)

## Context

ADR 0136 removed phantom filter pre-fill and the `starting_inv` studio slider, leaving
episodes at an empty shelf until the first order delivery. For teaching and demo UX the
studio should open with realistic on-hand stock.

## Decision

1. **Studio RPC `init` / `reset` only:** after configure, call
   `EngineSession::seed_initial_stock()` — not `init()` used by bakeoffs / PyO3 direct
   sessions.
2. **Quantity:** `case_round(protection_demand_quantile(0.95, params,
   schedule.protection_days(0), 0))` using the committed calendar demand profile.
3. **Freshness:** standard corridor draw via `draw_truth_multilot_delivery_biased` (same
   path as scheduled deliveries).
4. **Filter:** birth from synthetic day-0 arrival observation; `bank_init` synced so
   rung replay starts from the stocked shelf.
5. **Mock path:** `createInitialState` mirrors sizing (homogeneous NB quantile) and
   prior-mean birth spread.

`INITIAL_STOCK_ALPHA = 0.95` is fixed and independent of the controller α slider
(default 0.9).

## Consequences

- Partially supersedes ADR 0136 item 1 for studio RPC init only; direct `init()` and
  PyO3 sessions remain empty-shelf unless they call `seed_initial_stock` explicitly.
- Snapshot `applied_config` exposes `initial_stock_qty` and `initial_stock_alpha`.
- Publishable studio paths changed → patch bump `web/package.json`.
