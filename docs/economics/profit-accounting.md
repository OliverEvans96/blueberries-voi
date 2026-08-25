---
title: Profit accounting
sources:
  code: [src/blueberries_voi/sim/profit.py, src/blueberries_voi/sim/types_log.py, crates/voi_core/src/rollout.rs]
---

# Profit accounting

Every simulated day distills down to one number: the profit that day's decisions produced. It's not just "money in minus money out" — it's built from three terms (margin earned, waste written off, and a penalty for turning a customer away empty-handed), and which terms are included is itself a modeling choice that shapes which ordering policies end up looking good in the experiment.

![Daily profit waterfall: margin, waste, stockout for a books-only day vs a lot ID + pack date day](/figures/profit-waterfall-daily.png)

## The idea

A day at the shelf breaks into three buckets. Some demand gets **sold** — that's margin in the till. Some units sit unsold until they spoil and get thrown out — that's **waste**, a pure loss on units that were paid for but never rang up. And on a day the shelf runs empty before demand stops, some customers leave without buying — that's a **stockout**, which costs at least the margin that would have been earned, plus a flat penalty per lost sale on top of the forgone margin.

A small example makes the arithmetic concrete. Suppose a day sells 40 units, wastes 5, and turns away 3 customers after the shelf empties, under the project's default (but uncalibrated — see below) costs of \$2 margin, \$1.50 waste cost, and \$3 stockout penalty per unit:

$$
\text{profit} = 2(40) - 1.5(5) - 3(3) = 80 - 7.5 - 9 = 63.5
$$

Holding inventory costs nothing in this accounting — a case of blueberries sitting on the shelf overnight, waiting to be sold tomorrow, is free. Only spoiled waste and turned-away customers cost money beyond the margin already reflected in sales.

Unmet demand is also **censored**: if a stockout happens, the model doesn't ask "how many more people would have bought if there'd been more stock" — the day's demand number is what it is, and whatever wasn't sold out of it is simply lost, for that day only. Nothing carries over as a backorder to tomorrow.

## The math

For one simulated day, let $\text{sales}$ be units sold, $\text{waste}$ be units discarded as spoiled, and $\text{demand}$ be that day's total demand realization. Define lost sales as the shortfall between demand and what was actually sold:

$$
\text{lost} = \max(0,\ \text{demand} - \text{sales})
$$

Day profit is then a weighted sum of three terms, using per-unit cost parameters $\text{unit\_margin}$, $\text{waste\_cost}$, and $\text{stockout\_penalty}$:

$$
\text{day\_profit} = \text{unit\_margin} \cdot \text{sales} - \text{waste\_cost} \cdot \text{waste} - \text{stockout\_penalty} \cdot \text{lost}
$$

An episode's profit is the sum of $\text{day\_profit}$ over the **scored** days — the days after a burn-in window, so the ordering pipeline has had time to stabilize before any day counts toward the reported number.

## Why it's modelled this way

The accounting uses three terms — margin, waste cost, and an *explicit* stockout penalty beyond forgone margin — rather than two simpler alternatives: margin-and-waste-only (simplest, but silently rewards running lean) or a full P&L that also charges a holding cost on on-hand inventory (unnecessary complexity for a fast-turning perishable, where holding cost is usually small).

The stockout penalty is the load-bearing choice. Unmet demand is lost and censored, with no backorder, so a stockout already costs *at minimum* the margin not earned that day. Without an *additional* penalty on top of that, a policy that runs deliberately lean and occasionally empties the shelf would look artificially good in the experiment: the only visible cost of running out would be the one sale not made that day, with no goodwill or switching-cost consequence modeled. That would bias the whole comparison against the case for freshness information, because information-aware policies earn part of their edge specifically by avoiding stockouts, not just by avoiding waste — under-penalizing stockouts would understate exactly the advantage the project is trying to measure.

**Caveat.** The default dollar values — \$2 unit margin, \$1.50 waste cost, \$3 stockout penalty — are an explicitly **uncalibrated scaffold**, not fitted blueberry-store numbers. They're centralized as a single named `DEFAULT_PROFIT_COSTS` constant so that different call sites don't each carry their own private, undocumented guess — but centralizing the constant doesn't calibrate it. Every profit number, and by extension every VOI number built on top of it (see [the VOI metric](/economics/voi-metric)), inherits this caveat unless a caller passes in real economics.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Day-profit formula (Python) | `day_profit` | `src/blueberries_voi/sim/profit.py:37` |
| Lost sales, censored (no backorder) | `lost` | `src/blueberries_voi/sim/profit.py:44` |
| Episode profit, summed over scored days | `episode_profit` | `src/blueberries_voi/sim/profit.py:52` |
| Cost parameters container | `ProfitCosts` | `src/blueberries_voi/sim/profit.py:20` |
| Uncalibrated default costs (\$2 / \$1.50 / \$3) | `DEFAULT_PROFIT_COSTS` | `src/blueberries_voi/sim/profit.py:30` |
| Which days are "scored" (post burn-in) | `EpisodeLog.scored` | `src/blueberries_voi/sim/types_log.py:45` |
| Day-profit formula (Rust, rollout's inner loop) | `day_profit` | `crates/voi_core/src/rollout.rs:107` |
| Same \$2 / \$1.50 / \$3 scaffold, Rust side | `RolloutCosts::default` | `crates/voi_core/src/rollout.rs:32` |

## Caveats

- Holding / on-hand inventory carries no cost at all — capital tied up in shelf stock, or the labor to face and rotate it, is not represented anywhere in this accounting.
- Unmet demand is censored with no backorder: a stockout only costs that one day's forgone margin plus the flat penalty, never a downstream effect on future days' demand.
- The stockout penalty is a single flat dollar figure, not a model of actual customer behavior (switching stores, buying less next time, and so on) — it stands in for those effects without simulating any of them.
- The default cost parameters are an uncalibrated scaffold: unless a caller supplies real store economics, every dollar figure downstream of `day_profit` — including the VOI headline — is denominated in these placeholder numbers, not fitted blueberry-store margins.
