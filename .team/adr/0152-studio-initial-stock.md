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
2. **Opening protection window** (calendar-derived, no ambiguity on first manual order):
   - `first_order_day` = first `schedule.can_order(day)` for `day >= 0`
   - `first_order_arrival_day` = `first_order_day + lead_time`
   - `opening_protection_days` = `first_order_arrival_day` — covers demand on episode
     days `0 .. first_order_arrival_day` (exclusive of the arrival day). Example: default
     MWF with `LT=1`, Monday episode start → first order Tuesday (day 1), arrival
     Wednesday (day 2) → cover Mon–Tue (2 days).
3. **Quantity:** `initial_stock_sla_pb` — the SLA_PB Poisson-binomial window model
   (`OpeningStockPbModel`) at `INITIAL_STOCK_ALPHA = 0.95`, with units on shelf at
   corridor prior freshness (`f_pipeline = 1.0`) from episode day 0. Not the plain
   `protection_demand_quantile` (which ignores freshness spoilage over the window).
4. **Freshness:** standard corridor draw via `draw_truth_multilot_delivery_biased` (same
   path as scheduled deliveries).
5. **Filter:** birth from synthetic day-0 arrival observation; `bank_init` synced so
   rung replay starts from the stocked shelf.
6. **Mock path:** `createInitialState` mirrors the **opening protection window**
   (`first_order_arrival_day`); quantity remains a homogeneous NB quantile approximation
   (full SLA_PB is Rust-only).

`INITIAL_STOCK_ALPHA = 0.95` is fixed and independent of the controller α slider
(default 0.9).

## Consequences

- Partially supersedes ADR 0136 item 1 for studio RPC init only; direct `init()` and
  PyO3 sessions remain empty-shelf unless they call `seed_initial_stock` explicitly.
- Snapshot `applied_config` exposes `initial_stock_qty` and `initial_stock_alpha`;
  `episode_day` is `0` before the first `step()`.
- Publishable studio paths changed → patch bump `web/package.json`.
