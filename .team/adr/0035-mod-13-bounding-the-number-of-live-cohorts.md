# 0035. MOD-13: Bounding the number of live cohorts
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-13
GROUP: MOD
PROVENANCE: contested
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M1.*

**Why this card exists.**

It did not exist until [X-03](X-03%20Date%20pull%20in%20or%20out.md) settled as "drop the date pull". The printed-date pull was the
mechanism that kept the live cohort count at three to five. Without it, cohorts linger — and **worse
under LIFO-ish picking**, because a fresh-biased kernel means old cohorts don't sell, they just
slowly die.

With a plausible fragile-berry hazard, a cohort is only ~1% surviving at around 25 effective days, so
on a 2-day cadence the live cohort count could reach 8–10. That is a real filter cost, because the
joint age lattice grows as K^L ([FIL-03](FIL-03%20Arrival-age%20discretisation.md)).

**The honest framing.**

Whatever is chosen here is a **modelling artefact with no physical referent** — which the date pull
was not. That is the price of [X-03](X-03%20Date%20pull%20in%20or%20out.md)=B, and it should be stated in the post rather than buried in a
config file.

## Decision

We will adopt **C — No bound — let cohorts run to extinction**. Chosen against the card recommendation of **A — Prune a cohort when its count drops below a threshold, book the remainder as waste**.

**C — No bound — let cohorts run to extinction.** ⚑ Against the card's recommendation (A).

## Alternatives considered

- **A — Prune a cohort when its count drops below a threshold, book the remainder as waste** _(card recommendation; not chosen)_ — not chosen. Cheap, honest, restores the bound. Document the threshold and sweep it once to show it doesn't matter. Note it now also affects the exact-DP baseline, so it is not purely a filter convenience.
- **B — Hard cap on live cohorts; merge the oldest** — not chosen. Bounds the lattice exactly, but merging two cohorts of different ages into one destroys precisely the age spread the filter exists to track.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `MOD-07`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
