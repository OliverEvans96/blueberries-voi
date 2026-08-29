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
   - `opening_protection_days` = `first_order_arrival_day + 1` — covers demand on
     episode days `0 ..= first_order_arrival_day` inclusive. The arrival day is
     included because `unit_day_step` sells before it delivers, so a truck due that
     morning cannot satisfy that day's customers. Example: default MWF with `LT=1`,
     Monday episode start → first order Tuesday (day 1), arrival Wednesday (day 2)
     → cover Mon–Wed (3 days).
3. **Quantity:** `initial_stock_sla_mc` — Monte Carlo window SLA over
   [`simulate_protection_path`] / `unit_day_step` at `INITIAL_STOCK_ALPHA = 0.95`, with
   units on shelf at corridor prior freshness (`f_pipeline = 1.0`) from episode day 0.
   The fast `OpeningStockPbModel` path remains for tests and benchmarks but is not used
   for studio RPC sizing because its Poisson-binomial approximation materially
   undersizes relative to the truth day step (sell-before-deliver + gamma spoilage).
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
