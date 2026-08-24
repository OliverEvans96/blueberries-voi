---
title: Does the money follow?
sources:
  code:
    - crates/voi_core/src/policy.rs
    - crates/voi_core/src/session.rs
---

# Does the money follow a sharper belief?

[Sharper beliefs are real](./does-belief-sharpen) — a pack date alone cuts arrival-belief
error roughly 3×. The natural next question is whether that sharper belief actually earns
the store more money once it's plugged into the ordering decision. The honest current
answer: at today's experiment budgets, mostly not, or at least not in a way that's been
measured cleanly yet.

> **Figure (coming soon):** a box/strip plot of closed-loop profit per rung, replicated
> across many seeds, with the spread *within* a rung (across seeds) shown next to the
> spread *across* rungs at a fixed seed — making the "seed variance dominates rung
> variance" claim checkable at a glance.

## The idea

Belief accuracy isn't what the store actually cares about — profit is. So take the same
30-day replay used to measure belief accuracy, but now let each rung actually *drive* its
own ordering decisions (not just observe a shared, pre-recorded order sequence), under
the same damped survival-weighted policy, and score the resulting profit. If sharper
beliefs are worth anything operationally, richer rungs should produce higher — or at
least more consistent — profit than poorer ones.

They don't, reliably, yet. Run the same rung on two different random seeds (two different
draws of demand and delivery noise, everything else held fixed) and the profit swings
more than it does between running two *different* rungs on the same seed. Right now,
which random seed you happen to get matters more to the bottom line than whether the
store used a pack-date feed or a temperature logger.

## The math

Let $\pi(r, s)$ be closed-loop profit for rung $r$ under seed $s$, all else (policy,
horizon, demand process) held fixed. The finding is a variance comparison:

$$
\mathrm{Var}_s\big[\pi(r, s)\big] \Big|_{r \text{ fixed}} \;\gtrsim\; \mathrm{Var}_r\big[\pi(r, s)\big] \Big|_{s \text{ fixed}}
$$

— the spread in profit *across seeds, at one rung* is comparable to or larger than the
spread *across rungs, at one seed*. That's the opposite of what you'd want if you were
trying to use rung-to-rung profit differences as evidence that a richer channel pays for
itself: the signal (the rung effect) is smaller than the noise floor it's competing
against (the seed effect), at the number of seeds and days currently run.

## Why it's modelled this way

This is a direct, reported result, not a hypothesis about how the model should behave, so
there's no alternative modeling choice to defend here. What's worth being explicit about
is *why* this might be true, since "sharper beliefs don't help" is a strong claim that
could mean several things. These are candidate explanations, listed as **hypotheses**,
not established facts — none has been isolated and confirmed as the cause:

1. **The profit-cost scaffold is uncalibrated.** `DEFAULT_PROFIT_COSTS` (unit margin,
   waste cost, stockout penalty) is a shared scaffold, explicitly flagged as still
   uncalibrated — not fitted to any real economics. If the true dollar gaps between rungs
   are small relative to these arbitrarily-set cost coefficients, the profit signal a
   sharper belief could produce may simply be smaller than what this scaffold can resolve.
   See [Profit accounting](/economics/profit-accounting) for the cost model itself.
2. **The ordering policy only consumes a single scalar from the belief.** The damped
   survival-weighted policy computes an order from `effective_inventory_f_belief` — a
   single $E[f]$-weighted on-hand number distilled from the full per-lot freshness
   distribution — not the shape of that distribution. A richer rung can produce a belief
   that is a materially narrower *distribution* over freshness without moving its *mean*
   much, and the current policy has no way to act on that narrowing; it only ever sees the
   one scalar. See [Effective inventory](/control/effective-inventory).
3. **The experiment horizon/replicate budget may be too small to resolve a real but
   modest effect.** Three seeds over 30 days is enough to establish the belief-accuracy
   ordering cleanly (see [Does belief actually sharpen?](./does-belief-sharpen)), but a
   profit effect genuinely smaller than the seed-to-seed demand noise would need more
   seeds, more days, or variance-reduction (common random numbers across more of the
   pipeline) to separate from that noise — not necessarily zero effect, just an unresolved
   one at this budget.
4. **The ladder mostly sharpens *arrival* freshness belief, not in-store state.** The
   accuracy gains measured in [Does belief actually sharpen?](./does-belief-sharpen) are
   about how well the filter knows a *delivery's* freshness the moment it arrives. Once
   units are on the shelf, in-store aging and picking dynamics are the same regardless of
   which rung produced the arrival belief — so a sharper arrival belief may just be a
   small lever on what is, in the end, one scalar ordering decision per day.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Damped survival-weighted order from belief | `damped_sw_order_f_belief(...)` | `crates/voi_core/src/policy.rs:201` |
| Single-scalar reduction of the freshness belief consumed by the policy | `effective_inventory_f_belief(...)` | `crates/voi_core/src/policy.rs:179` |
| Uncalibrated shared profit-cost scaffold | `DEFAULT_PROFIT_COSTS` | see [Profit accounting](/economics/profit-accounting) for the Rust/Python cost model |

## Caveats

- This is a **negative or inconclusive result, stated plainly**: closed-loop profit under
  the same damped policy moves more with the random seed than with the observation rung,
  at current experiment budgets. It is not evidence that richer observation channels are
  worthless — it is evidence that this experiment, as currently sized and scaffolded,
  can't yet show they're worth it in dollars.
- The four candidate explanations above are hypotheses for future investigation, not
  findings — none has been isolated experimentally (e.g. by re-running with a calibrated
  cost model, a distribution-aware policy, or a much larger seed budget) to confirm it as
  *the* cause rather than a contributing one.
- This uses the same fixed damped survival-weighted policy across all rungs. A policy
  designed to exploit belief shape (rather than just its mean) might show a different
  result — that's hypothesis 2 above, not something this page's data can confirm or rule
  out.
