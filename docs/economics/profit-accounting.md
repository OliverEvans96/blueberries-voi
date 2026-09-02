---
title: Profit accounting
sources:
  code: [src/blueberries_voi/sim/profit.py, src/blueberries_voi/sim/types_log.py, crates/voi_core/src/rollout.rs]
---

# Profit accounting

Every simulated day boils down to one number: the profit that day's decisions produced. It isn't just "money in minus money out." It's built from three pieces — margin earned, waste written off, and a penalty for turning a customer away empty-handed — and which pieces are counted is itself a modeling choice. That choice shapes which ordering policies end up looking good in the experiment.

## The idea

A day at the shelf breaks into three buckets. Some demand gets **sold** — that's margin in the till. Some units sit unsold until they spoil and get thrown out — that's **waste**, a pure loss on units that were paid for but never rang up. And on a day the shelf runs empty before demand stops, some customers leave without buying — that's a **stockout**, which costs at least the margin that would have been earned, plus a flat penalty per lost sale on top of the forgone margin.

A small example makes the arithmetic concrete. Suppose a day sells 40 units, wastes 5, and turns away 3 customers after the shelf empties. Using the project's cost figures — a $2.70 margin per unit sold, a $1.20 cost per unit wasted, and a $2.50 penalty per lost sale — the day's profit is:

$$
\text{profit} = 2.70(40) - 1.20(5) - 2.50(3) = 108 - 6 - 7.5 = 94.5
$$

Holding inventory costs nothing in this accounting — a case of blueberries sitting on the shelf overnight, waiting to be sold tomorrow, is free. Only spoiled waste and turned-away customers cost money beyond the margin already reflected in sales.

Unmet demand is also **censored**: if a stockout happens, the model doesn't ask "how many more people would have bought if there'd been more stock." The day's demand number is what it is, and whatever wasn't sold out of it is simply lost, for that day only. Nothing carries over as a backorder to tomorrow.

## The math

For one simulated day, let $\text{sales}$ be units sold, $\text{waste}$ be units discarded as spoiled, and $\text{demand}$ be that day's total demand realization. Define lost sales as the shortfall between demand and what was actually sold:

$$
\text{lost} = \max(0,\ \text{demand} - \text{sales})
$$

Day profit is then a weighted sum of three terms. $\text{unit\_margin}$ is the dollars earned per unit sold, $\text{waste\_cost}$ is the dollars lost per unit thrown out, and $\text{stockout\_penalty}$ is the extra dollars charged per lost sale, on top of the margin that sale would have earned:

$$
\text{day\_profit} = \text{unit\_margin} \cdot \text{sales} - \text{waste\_cost} \cdot \text{waste} - \text{stockout\_penalty} \cdot \text{lost}
$$

An episode's profit is the sum of $\text{day\_profit}$ over the **scored** days — the days after a burn-in window, so the ordering pipeline has had time to stabilize before any day counts toward the reported number.

## Why it's modelled this way

The accounting uses three terms — margin, waste cost, and an *explicit* stockout penalty beyond forgone margin. Two simpler alternatives were considered and rejected. Margin-and-waste-only is the simplest option, but it silently rewards running lean on inventory. A full profit and loss (P&L) statement that also charges a holding cost on on-hand inventory adds complexity that isn't needed for a fast-turning perishable, where the cost of holding stock for a day or two is usually small.

The stockout penalty is the load-bearing choice. Unmet demand is lost and censored, with no backorder, so a stockout already costs *at minimum* the margin not earned that day. Without an *additional* penalty on top of that, a policy that runs deliberately lean and occasionally empties the shelf would look artificially good in the experiment. The only visible cost of running out would be the one sale not made that day, with no goodwill or switching-cost consequence modeled. That would bias the whole comparison against the case for freshness information. Information-aware policies earn part of their edge specifically by avoiding stockouts, not just by avoiding waste, so under-penalizing stockouts would understate exactly the advantage the project is trying to measure.

**Caveat.** The cost figures — $2.70 margin, $1.20 waste cost, $2.50 stockout penalty — are a deliberate synthetic design, not a bug or an arbitrary guess. They're set up so that a stockout costs roughly 4.3 times as much as a wasted unit once the forgone margin is folded in ($2.50 penalty + $2.70 forgone margin ≈ $5.20, versus $1.20 to waste a unit), reflecting that a real grocer typically cares more about keeping the shelf stocked than about a bit of silent waste. They are centralized in one place so that different parts of the code don't each carry their own private, undocumented guess. That said, they haven't been validated against a real store's books, so every profit number — and by extension every Value of Information (VOI) number built on top of it (see [the VOI metric](/economics/voi-metric)) — should be read as relative comparisons under this synthetic economics, not as dollar figures a real store would see.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Day-profit formula (Python) | `day_profit` | `src/blueberries_voi/sim/profit.py:42` |
| Lost sales, censored (no backorder) | `lost` | `src/blueberries_voi/sim/profit.py:49` |
| Episode profit, summed over scored days | `episode_profit` | `src/blueberries_voi/sim/profit.py:57` |
| Cost parameters container | `ProfitCosts` | `src/blueberries_voi/sim/profit.py:25` |
| Default synthetic costs ($2.70 margin / $1.20 waste / $2.50 stockout) | `DEFAULT_PROFIT_COSTS` | `src/blueberries_voi/sim/profit.py:35` |
| Which days are "scored" (post burn-in) | `EpisodeLog.scored` | `src/blueberries_voi/sim/types_log.py:45` |
| Day-profit formula (Rust, rollout's inner loop) | `day_profit` | `crates/voi_core/src/rollout.rs:129` |
| Same default costs, Rust side | `RolloutCosts::default` | `crates/voi_core/src/rollout.rs:37` |

## Caveats

- Holding / on-hand inventory carries no cost at all — capital tied up in shelf stock, or the labor to face and rotate it, is not represented anywhere in this accounting.
- Unmet demand is censored with no backorder: a stockout only costs that one day's forgone margin plus the flat penalty, never a downstream effect on future days' demand.
- The stockout penalty is a single flat dollar figure, not a model of actual customer behavior (switching stores, buying less next time, and so on) — it stands in for those effects without simulating any of them.
- The cost parameters are a deliberately chosen synthetic economics, not numbers pulled from a real store's books. Every dollar figure downstream of `day_profit` — including the VOI headline — should be read as a comparison under this synthetic economics rather than as a real store's margins.
