---
title: One day, in order
sources:
  code: [crates/voi_core/src/day_step.rs]
---

# One day, in order

Every simulated day runs through the same four events in the same fixed order: freshness loss, then spoil, then sell, then deliver. That order isn't an implementation detail — swapping any two of these steps changes the store's numbers, because it changes what's actually available to sell or to spoil at each moment. This page walks through the sequence and why it's fixed the way it is.

## The idea

Think through one day from the shelf's point of view. Whatever survived to this morning has spent another day (or transit leg) losing freshness overnight — so the first thing that happens is **freshness loss**: every alive unit's freshness ticks down by its own random amount. Some of those units, having just lost that freshness, cross zero — they're now spoiled, and they get pulled off the shelf as **waste** before a single customer walks in. Only after that culling happens do today's **sales** get resolved: a day's worth of demand is drawn, and units are sold one at a time out of whatever's left alive, using the freshness-weighted lottery described on [the picking page](/store/picking). Last, after the registers have rung up today's sales, today's **delivery** — if one is scheduled — gets unloaded onto the shelf. A fresh truck's units are not in play for today's sales at all: they can't be bought same-day, and they don't pad out today's picking pool, because they aren't added to the shelf state until after the sales step has already finished with it.

The ordering has a real consequence at the edges. A unit that would have spoiled today never gets a chance to be sold today, no matter how attractive its freshness looked yesterday. And a shipment that lands today can't undercut yesterday's older stock in today's picking lottery, because it isn't part of the pool the lottery draws from.

## The math

Writing $f_i$ for unit $i$'s freshness and $\ell$ for a lot index, one simulated day runs:

1. **Freshness loss.** For every alive unit ($f_i > 0$), draw an independent decrement and apply it: $f_i \leftarrow \max(f_i - \Delta_i,\ 0)$, with $\Delta_i \sim \mathrm{Gamma}(k\bar\phi, \theta)$ (see [how fruit loses freshness](/store/gamma-aging)).
2. **Spoil.** Comparing freshness before and after step 1, any unit with $f_i^{\text{before}} > 0$ and $f_i^{\text{after}} \le 0$ is recorded as waste for its lot and removed from the eligible-to-sell set (see [spoilage and waste](/store/spoilage-waste)).
3. **Sell.** A day's demand $X$ is drawn (see [demand: a calendar, not a coin](/store/demand-calendar)); $\text{to\_sell} = \min(X,\ \#\{i : f_i > 0\})$ units are drawn one at a time from the *post-step-2* alive set, using the freshness-weighted picking rule.
4. **Deliver.** If a delivery is scheduled today, its units — each with its own birth freshness from the cold-chain arrival model — are appended to the shelf state as a new lot, *after* step 3 has already resolved which units could be sold.

Steps 1–2 only ever remove units from the shelf (spoilage); step 3 only removes units by selling them, and only from what step 2 left behind; step 4 only ever adds units, and only after step 3 is done. Nothing added in step 4 is visible to steps 1–3 of the same day.

## Why it's modelled this way

When spoilage risk is high, the difference between spoiling before selling and selling before spoiling produces a systematic shift in both waste and sales. It doesn't flip the sign of a headline result, but it changes the magnitude. If the simulator and the belief-tracking filter ever used different orders, the filter would end up quietly wrong in a way that's hard to spot from the outside. So the simulator and the filter's transition model use the identical sequence.

Independent per-unit freshness loss, modeled with a Gamma process (see [spoilage and waste](/store/spoilage-waste)), makes spoilage a direct, structural consequence of a unit's own freshness-loss draw crossing zero, rather than a separate lottery applied afterward to whichever units happen to survive a sales draw. Once spoilage is defined that way, there's no separate spoilage lottery to place before or after sales — a unit that hits zero during freshness loss simply isn't eligible for the picking lottery in step 3, by construction (see [who buys which punnet](/store/picking)). What the ordering has to preserve is that the simulator's step order and the filter's transition model agree: the filter's own transition step runs on freshness that has already had that day's loss applied, matching the alive set the simulator hands to sales.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Full day-step function (calls all four steps in order) | — | `crates/voi_core/src/day_step.rs:254` ([`unit_day_step_with_birth`](/api/rust/voi_core/day_step/fn.unit_day_step_with_birth.html)) |
| Step 1 — freshness loss (independent per-unit decrement) | $f_i \leftarrow \max(f_i - \Delta_i, 0)$ | `crates/voi_core/src/day_step.rs:269` (calls `apply_gamma_step`) |
| Step 2 — detect and record spoiled units | `waste_by`, `UnitExitCause::Spoiled` | `crates/voi_core/src/day_step.rs:275` (`count_spoil_by_lot`), `:276` (`spoil_unit_exits`) |
| Step 3 — sell from the post-spoilage alive set | `sales_total`, `sales_by` | `crates/voi_core/src/day_step.rs:283` (calls `pick_units_f`) |
| Step 4 — append today's delivery after sales | `lot_offsets.push(...)` | `crates/voi_core/src/day_step.rs:287` (`if input.deliver { ... }`) |
| Filter's transition step assumes the same post-freshness-loss, post-spoilage alive set | — | `crates/voi_core/src/unit_pf.rs:427` (doc comment on the filter step) |

## Caveats

- The step order is fixed for every observation scenario and every policy in the model; there is no case where, say, delivery happens before sales.
- Everything within a step happens at day granularity — the model doesn't resolve *when during the day* freshness loss, a sale, or a delivery occurred, only their fixed relative order.
- Demand for the day is drawn as a single aggregate number (see the demand-calendar page), not as individual customers arriving at distinct times that could interleave with a same-day delivery — same-day delivery exclusion is enforced structurally (step ordering), not by modeling time-of-day.
