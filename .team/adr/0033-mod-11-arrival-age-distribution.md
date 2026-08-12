# 0033. MOD-11: Arrival age distribution
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-11
GROUP: MOD
PROVENANCE: contested
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M1. This distribution is where the entire project's uncertainty lives.*

**The question.**

Under [MOD-02](MOD-02%20Effective%20age%20dynamics.md)=A all freshness randomness is pushed to the inflow boundary, so this distribution
*is* the uncertainty. Its **spread** is the most important parameter in the model that nobody has
named yet.

**Why the spread is load-bearing.**

Constant in-store ageing adds the same amount to every cohort and therefore cannot help you tell
cohorts apart. **All identification of relative freshness comes from cohorts arriving at genuinely
different ages.** If the arrival prior is tight and cadence is rigid, cohorts become nearly
exchangeable, the composition posterior collapses to the prior, the filter is decoration, and the
low-rung VOI is entirely a statement about where you got your prior.

That is the go/no-go for the technical core, and it is a two-hour experiment. **It is also a result
worth being willing to publish.**

## Decision

We will adopt **C — Derived from an explicit transit temperature model**. Chosen against the card recommendation of **A — Parametric prior on arrival age, spread as a free knob**.

**C — Derived from an explicit transit temperature model.** ⚑ Against the card's recommendation (A). Sample a temperature path, integrate the Arrhenius factor.

## Alternatives considered

- **A — Parametric prior on arrival age, spread as a free knob** _(card recommendation; not chosen)_ — not chosen. (lognormal or gamma on arrival age). One location, one spread. The spread becomes the diagnostic knob for the experiment above. Cheapest and most controllable.
- **B — Two-point or discrete mixture** — not chosen. Directly encodes staggered vs uniform arrivals.

## Consequences

Sample a temperature path, integrate the Arrhenius factor.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `MOD-02`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
