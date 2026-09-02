---
title: Does the money follow?
sources:
  code:
    - crates/voi_core/src/policy.rs
    - crates/voi_core/src/session.rs
---

# Does the money follow a sharper belief?

[Sharper beliefs are real](./does-belief-sharpen) — adding pack date alone cuts belief
error by more than half, the single biggest jump on the observation ladder. The natural
next question is whether that sharper belief actually earns the store more money once
it's plugged into the ordering decision. The answer, measured cleanly across a real
experiment: **no, not in this setup.** Profit stays essentially flat no matter how much
richer the observation channel gets.

## The idea

Belief accuracy isn't what the store actually cares about — profit is. So we take the
same 30-day replay used to measure belief accuracy, but this time let each observation
scenario actually *drive* its own ordering decisions, instead of just watching a shared,
pre-recorded order sequence. This is the difference between a "closed-loop" replay
(the controller places real orders, so we can compare profit) and the "open-loop" replay
used on the belief-accuracy page (every scenario sees the identical sequence of events, so
we can compare belief sharpness alone). Each scenario runs under the same ordering
policy, and we score the resulting profit, averaged over 30 random seeds with a 95%
confidence interval (CI) — a range that's very likely to contain the true average.

If sharper beliefs were worth anything operationally, richer scenarios should produce
higher profit than poorer ones. They don't. Profit for every scenario on the ladder comes
out within about 1% of the plain "books only" baseline — how many units were delivered
and how many were sold, which is what nearly every store already tracks. This isn't a
noisy, unresolved question; it's a precisely bounded result.

## The math

For each observation scenario, we compute the average closed-loop profit across 30
seeds and express it as a ratio to the books-only baseline:

$$
\text{profit ratio}(r) = \frac{\bar{\pi}(r)}{\bar{\pi}(\text{books only})}
$$

where $\bar{\pi}(r)$ is the average profit earned under observation scenario $r$. A ratio
of 1.000 means no change from the baseline; a ratio above 1 means more profit.

| Observation scenario | Profit ratio vs. books-only (95% CI) |
| --- | --- |
| Books only | 1.000 (baseline) |
| + scan waste | 1.009 ± 0.008 |
| + pack date | 1.003 ± 0.015 |
| + LGTIN | 1.004 ± 0.014 |
| + temp. history | 1.006 ± 0.014 |

Every scenario lands within about 1% of the baseline, and every confidence interval
comfortably overlaps 1.000. Compare this to the belief-accuracy page, where the same
ladder produces a steady, large improvement — richer information clearly sharpens the
store's belief about freshness, it just doesn't show up as more money in this
experiment.

## Why it's modelled this way

This is a direct, reported result, not a modeling choice — so there's nothing to defend
here in terms of "why build it this way." What's worth explaining is *why* a much sharper
belief fails to produce more profit. Here's our best current explanation, based on what
we've tried so far:

**The ordering policy is short-sighted.** It decides how much to order by looking at
current average freshness and expected demand only until the next delivery arrives — a
few days out — not the berries' full shelf life of around 10 days. A sharper belief about
a delivery's freshness the moment it arrives doesn't help much if the policy making the
decision only ever looks a few days ahead.

**The costs already favor over-ordering, regardless of belief.** Missing a sale costs
about $5.20 — the $2.50 stockout penalty plus the $2.70 in margin you forgo by not
having a unit to sell — versus $1.20 to waste one spoiled unit. That's roughly 4.3 times
more expensive to run out than to over-order. A policy that already leans toward keeping
extra stock on hand is close to profit-maximizing even when its belief about freshness is
coarse, so there's less room for a sharper belief to move the needle.

**The fitted policy confirms this pattern.** The ordering rule is a base-stock policy: it
targets a certain inventory level. Two tuned numbers control it — alpha (a demand
quantile: how far into the demand distribution to aim) and rho (a multiplier on the gap
between that target and the store's current effective inventory, meaning on-hand units
weighted by expected freshness, plus incoming units at their expected arrival freshness).
When we tuned alpha and rho separately for each of the 12 possible observation
combinations, rho landed between 1.25 and 1.63 in every single one — always overshooting
the target gap rather than damping toward it. (The model's untuned default for rho, used
elsewhere on this site, is 0.8; the tuned range of 1.25–1.63 is a different number, from
this specific experiment.)

**Two alternative policies didn't help either.** We also tried a finite-horizon
rollout-based policy (one that simulates several days of possible outcomes before
choosing an order) and a service-level policy (one that targets a probability of no
stockouts across a window, adjusted for how fast freshness decays). Neither produced a
meaningful profit improvement — both turned out to be short-sighted in a similar way.

Taken together, this points to the ordering policy itself being the bottleneck, not to
richer information being worthless. We haven't built and tested a policy that plans over
the full shelf life and can fully exploit the shape of the freshness belief, so that
remains an open possibility rather than a ruled-out one.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| The survival-weighted ordering policy | `damped_sw_order_f_belief(...)` | `crates/voi_core/src/policy.rs:246` |
| Effective inventory: on-hand units weighted by expected freshness, plus incoming units at assumed arrival freshness | `effective_inventory_f_belief(...)` | `crates/voi_core/src/policy.rs:217` |
| Default profit/cost parameters (sell price, purchase cost, waste cost, stockout penalty) | `DEFAULT_PROFIT_COSTS` | see [Profit accounting](/economics/profit-accounting) for the full cost model |

## Caveats

- This is a **negative result, stated plainly**: closed-loop profit under this ordering
  policy stays within about 1% of the books-only baseline across the entire observation
  ladder, with tight confidence intervals. It is not a noise problem or an open question
  — it is a settled result at this experiment's scale.
- It is also not evidence that richer observation channels are worthless. Our best
  explanation is that the ordering policy itself is short-sighted — it only plans a few
  days ahead, not the berries' full shelf life — and that the cost structure already
  favors over-ordering enough that a coarser belief barely matters. Two other policy
  designs were tried and neither closed the gap, but a longer-horizon policy that can
  fully exploit the shape (not just the mean) of the freshness belief hasn't been built
  and tested yet.
- The profit numbers ($4.50 sell price, $1.80 purchase cost, $1.20 waste cost, $2.50
  stockout penalty) are a deliberate, reasoned synthetic design — chosen so a stockout
  costs meaningfully more than a spoilage — not a bug or an unresolved miscalibration.
  They are still illustrative, though: they haven't been validated against a real store's
  actual economics.
