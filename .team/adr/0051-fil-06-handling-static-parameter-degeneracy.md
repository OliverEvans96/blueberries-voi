# 0051. FIL-06: Handling static-parameter degeneracy
STATUS: SUPERSEDED BY 0105
DATE: 2026-08-12
BOARD-ID: FIL-06
GROUP: FIL
PROVENANCE: notes-agree
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M1.*

**The question.**

Arrival age is a static latent parameter inside the filter, and static parameters are the classic
particle filter failure mode: resampling cannot regenerate diversity along a coordinate with no
process noise, so the cloud collapses monotonically onto a value that may be wrong.

**Why it is bounded here, and this is a genuinely nice property.**

**Cohorts die.** A cohort lives 7–14 days and is then gone, so its arrival age needs to survive about
ten resampling steps, not five hundred. Fresh cohorts arrive carrying fresh draws from the prior. The
impoverishment horizon is bounded by shelf life, and the degeneracy that kills static-parameter
filters in long time series never gets going.

Worth stating in the post: it is a case where a modelling feature that looks like a problem is
disarmed by the physics of the application.

**The distinction that must not be blurred.**

Genuinely persistent parameters — the Weibull shape and scale, the picking parameter, shrink
compliance — are a **different matter entirely** and belong at the outer level ([FIL-07](FIL-07%20Where%20parameter%20inference%20lives.md)), not
inside the filter. Conflating the two is how people end up with mysteriously overconfident posteriors.

## Decision

We will adopt **C — Marginalise it away**. Chosen against the card recommendation of **A — Rely on cohort turnover — no intervention**.

**C — Marginalise it away.** ⚑ Against the card's recommendation (A). I.e. take the Rao-Blackwellised route.

## Alternatives considered

- **A — Rely on cohort turnover — no intervention** _(card recommendation; not chosen)_ — not chosen on the board.
- **B — Jitter arrival age on resampling** — not chosen on the board.

## Consequences

i.e. take the Rao-Blackwellised route.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `FIL-01`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
