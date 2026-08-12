# 0052. FIL-07: Where parameter inference lives
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-07
GROUP: FIL
PROVENANCE: notes-agree
TIER: 1
MILESTONE: M2 — controller and multi-scenario

## Context

*Milestone: M2. A for M1.*

**The question.**

The Weibull shape and scale, the picking parameter, and shrink compliance are persistent across the
whole time series. Do they get inferred, and if so, where?

**Why this is a real fork and not a detail.**

The Weibull shape is the **x-axis of the headline figure**. If it is also inferred, then the VOI
surface is being computed at estimated rather than known values, and the sweep stops being a sweep.
Keeping it assumed-known for the VOI experiment is not a shortcut — it is what makes the experiment
mean anything.

Separately, the identifiability question ("can you recover the kernels from ordinary store data?") is
a **different experiment** with a different answer, and it is the one the existing Julia work already
addresses.

**The specific trap to avoid.**

Do not let the filter estimate the Weibull shape jointly with arrival age from a single store-SKU at
a low rung and then report the result as a shape estimate. High arrival age with low shape mimics low
arrival age with high shape — only a power-law combination enters the cumulative hazard — so the
posterior has a ridge, not a peak.

> **Recommended: A** for the VOI line of work, with B as a separate, clearly-labelled identifiability
> experiment. Neural posterior estimation is worth naming as the production route and not building.

## Decision

We will adopt **A — Assume parameters known; filter the state only**.

**A — Assume parameters known; filter the state only.** Chosen on the board.

## Alternatives considered

- **B — Outer-level inference — PMMH or SMC-squared around the filter** — not chosen. Particle-marginal Metropolis–Hastings or SMC-squared wrapping the filter. Correct, expensive, and the honest way to ask the identifiability question. This is where the existing A=7 recovery study sits.
- **C — Joint — parameters inside the particle state** — not chosen. Do **not** do this. A static global parameter inside a particle filter degenerates exactly as [FIL-06](FIL-06%20Handling%20static-parameter%20degeneracy.md) describes, and unlike arrival age it is not rescued by cohort turnover, because it never dies. It produces confident, wrong posteriors.

## Consequences

**Depends on:** `FIL-06`

**Milestone:** M2 — controller and multi-scenario
