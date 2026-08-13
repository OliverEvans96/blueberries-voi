# 0011. X-11: Delivery cadence for the base case
STATUS: SUPERSEDED BY 0109
DATE: 2026-08-12
BOARD-ID: X-11
GROUP: X
PROVENANCE: newly-raised
TIER: 1
AGAINST-RECOMMENDATION: true

## Context

**Why this card exists.**

It was not a decision until [X-06](X-06%20VOI%20sweep%20axes.md) settled as "scenario × β only". Cadence had been an axis of the
VOI surface; now that the surface is two-dimensional, cadence is a **fixed parameter** — and the
value it is fixed at materially changes the headline number.

**The problem with daily.**

[The Controller — Survival-Weighted Base-Stock with Rollout](../../The%20Controller%20%E2%80%94%20Survival-Weighted%20Base-Stock%20with%20Rollout.md) §2.0 assumes daily delivery, then
concedes the point in its own words:

> Daily delivery is the regime where age information matters **least** — stock turns fast and never
> gets old.

Realistic berry cadence is 3–5×/week. At 3×/week the Friday order carries a protection interval of 4
rather than 2, which on the note's own worked example takes effective inventory from 60 units to 49
and **roughly doubles** the gap against the age-blind policy.

**The compounding worry.**

Three settled decisions all push the headline number in the same direction:

| Decision | Chosen | Effect on the VOI number |
| --- | --- | --- |
| [X-01](X-01%20What%20the%20post%20must%20demonstrate.md) | Value of age information | fine — this is the point |
| [X-04](X-04%20Controller%20action%20space.md) | Order quantity only | measures VOI in the channel the outline predicts is **smallest** |
| [X-06](X-06%20VOI%20sweep%20axes.md) | scenario × β only | drops the cadence and staggering axes |
| this card, if A | Daily delivery | the regime where age information matters **least** |

Each is individually defensible and conservative. Stacked, they risk a headline VOI that is
indistinguishable from zero — at which point the post has a method and no result. This is the one
place where the conservative choices interact multiplicatively rather than additively, and cadence is
the cheapest of the four to reverse.

**What B costs.**

Non-daily cadence breaks time-homogeneity, and three things must be re-derived:

1. The protection interval becomes day-indexed.
2. The stationary age distribution becomes only **periodic**, so the corrected age-blind baseline
   needs a day-indexed survival weight. Leave it a scalar and that baseline silently reverts to the
   strawman it exists to prevent.
3. The rollout horizon sweep must move in multiples of 7.

None is hard; all are easy to forget.

## Decision

We will adopt **A — Daily delivery, lead time 1 day**. Chosen against the card recommendation of **C — Daily base case, one 3x/week sensitivity point**.

**A — Daily delivery, lead time 1 day.** ⚑ Against the card's recommendation (C). The controller note's assumption. Time-homogeneous, simplest everything.

## Alternatives considered

- **B — 3x/week, realistic berry cadence** — not chosen. Where age information actually bites. Breaks time-homogeneity.
- **C — Daily base case, one 3x/week sensitivity point** _(card recommendation; not chosen)_ — not chosen. Build on A, report B as a single additional cell.

## Consequences

The controller note's assumption. Time-homogeneous, simplest everything.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** The daily-cadence VOI comes out near zero — then B stops being an enhancement and becomes the only
way the post has a result.

**Depends on:** `X-06`
