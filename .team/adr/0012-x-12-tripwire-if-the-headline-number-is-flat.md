# 0012. X-12: Tripwire if the headline number is flat
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: X-12
GROUP: X
PROVENANCE: newly-raised
TIER: 1
MILESTONE: M2 — controller and multi-scenario
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M2 — but C runs before any controller code exists.*

**The risk, stated once and then left alone.**

Four settled decisions each push the headline number in the same direction:

| Decision | Chosen | Effect |
| --- | --- | --- |
| [X-01](X-01%20What%20the%20post%20must%20demonstrate.md) | Value of age information | the point of the project |
| [X-04](X-04%20Controller%20action%20space.md) | Order quantity only | VOI measured in the channel the outline predicts is **smallest** |
| [X-06](X-06%20VOI%20sweep%20axes.md) | scenario × β only | no cadence or staggering axis |
| [X-11](X-11%20Delivery%20cadence%20for%20the%20base%20case.md) | Daily delivery | the regime where age information matters **least** |

Every one is individually defensible and conservative. Stacked, they compose multiplicatively, and
the failure mode is a VOI indistinguishable from zero — a method with no result, discovered after the
controller, the rollout, and the sweep have all been built.

This card is not an argument to reverse any of them. It is about **finding out early and cheaply**.

**Why C is worth more than it costs.**

You do not need a controller to bound the effect. The base policy's order quantity differs from the
age-blind one only through **effective inventory**: survival-weighted on-hand versus total on-hand
deflated by the expected survival under the stationary age distribution. That difference is a few
lines of arithmetic given the model parameters.

If, at realistic parameters, that gap is **reliably smaller than one case**, then `caseRound` swallows
it, the two policies order identically almost every day, and no amount of rollout or filtering will
produce a measurable VOI. That is knowable in an afternoon, before any controller exists.

It is also the same object as the β = 1 degeneracy check — at β = 1 the gap is exactly zero by
construction — so building it doubles as a correctness test.

**The escalation order, if the pre-check comes out thin.**

Cheapest to most expensive:

1. **Cadence** — [X-11](X-11%20Delivery%20cadence%20for%20the%20base%20case.md) to 3×/week. Roughly doubles the gap on the notes' own worked example.
2. **Case size** — a smaller case rounds less of the signal away. Purely a parameter.
3. **Sweep range** — push β further from 1.
4. **Action space** — [X-04](X-04%20Controller%20action%20space.md) to include cull or markdown sequencing. Expensive, and where the
   outline predicts the effect actually lives.

## Decision

We will adopt **A — No tripwire — report whatever comes out**. Chosen against the card recommendation of **C — Cheap analytic pre-check before the controller is built**.

**A — No tripwire — report whatever comes out.** ⚑ Against the card's recommendation (C).

## Alternatives considered

- **B — Pre-register a threshold and an escalation order** — not chosen on the board.
- **C — Cheap analytic pre-check before the controller is built** _(card recommendation; not chosen)_ — not chosen on the board.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `X-04`, `X-06`, `X-11`

**Milestone:** M2 — controller and multi-scenario
