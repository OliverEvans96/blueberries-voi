# 0037. MOD-15: Shrink reporting compliance
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-15
GROUP: MOD
PROVENANCE: contested
TIER: 2
MILESTONE: M2 — controller and multi-scenario
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M2 — set to perfect reporting for M1.*

**The question.**

At the shrink-gun rung, waste is scanned by associates. Realistically, a compliance fraction of
0.6–0.85, varying by store and by day of week — a slammed shift dumps the cull without scanning.

**The confounding, which is the interesting part.**

Compliance and the spoilage rate enter the observed waste count **multiplicatively**. Few observed
deaths can mean few deaths, or poor scanning. That is a gauge problem: only the product is
identified, and it is the same shape of problem that appears on the state side, where a cohort dying
fast can mean it arrived old, or the category is fragile, or reporting is spotty.

With the Weibull shape also uncertain there is a fourth: **high arrival age with low shape mimics low
arrival age with high shape**, because only a power-law combination enters the cumulative hazard.
Expect a ridge in that posterior. Plot it — it is an honest and informative figure, and it is the
mechanism behind "don't claim to know the shape parameter below full telemetry."

What breaks the ridge: **arrival staggering** ([MOD-11](MOD-11%20Arrival%20age%20distribution.md)) and **cross-cohort contrast**. Cohorts that
arrived at genuinely different ages trace out the hazard's *shape*; cohorts that all arrived alike
trace out only its *level*.

## Decision

We will adopt **B — Perfect reporting**. Chosen against the card recommendation of **A — In scope — compliance below 1 and unknown**.

**B — Perfect reporting.** ⚑ Against the card's recommendation (A).

## Alternatives considered

- **A — In scope — compliance below 1 and unknown** _(card recommendation; not chosen)_ — not chosen on the board.
- **C — Below 1 but known** — not chosen on the board.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `MOD-14`

**Milestone:** M2 — controller and multi-scenario
