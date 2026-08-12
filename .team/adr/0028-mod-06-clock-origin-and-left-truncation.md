# 0028. MOD-06: Clock origin and left-truncation
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-06
GROUP: MOD
PROVENANCE: notes-agree
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1.*

**The question.**

The units that arrive at the store are the **survivors of transit**. So arrival age is a
left-truncation point on a single clock, not a fresh start.

**Why it matters.**

Reset the clock at arrival (option B) and you lose the transit selection: a cohort that rode warm
should arrive both *older* and *already thinned of its frailest units*. B keeps the first effect and
discards the second, which biases the surviving population's robustness downward and makes warm
cohorts look worse than they are.

Under A everything is exact provided the one-day death probability is written as a conditional
survival ratio (see [MOD-04](MOD-04%20Spoilage%20law.md)) — the ratio handles the truncation automatically. And under gamma
frailty ([MOD-05](MOD-05%20Within-lot%20heterogeneity.md)) the selection is closed form and costs nothing.

## Decision

We will adopt **A — Run the hazard from harvest; arrival age is a truncation point**.

**A — Run the hazard from harvest; arrival age is a truncation point.** Chosen on the board.

## Alternatives considered

- **B — Reset the clock at arrival** — not chosen on the board.

## Consequences

**Depends on:** `MOD-04`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
