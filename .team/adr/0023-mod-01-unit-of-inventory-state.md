# 0023. MOD-01: Unit of inventory state
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-01
GROUP: MOD
PROVENANCE: notes-agree
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M1. Blocks everything.*

**The question.**

What is one atom of the state? Your bullets say "items remaining per lot (lots known from delivery
records)", which quietly assumes one delivery equals one lot.

**What is actually true about produce logistics.**

- A **case** is certainly one lot — clamshells are filled and coded together at the packhouse.
- A **truckload** from one grower is typically one lot; split across 30 stores, each store's delivery
  is then genuinely single-lot.
- A **DC-picked order** may mix receipts. For fast-turning berries the DC runs tight FIFO and turns
  in 1–3 days, so mixing is usually mild but not zero.
- Failure cases are specific: growing-region transitions (Chile → Mexico → California), promotional
  volume pulled from several receipts, and slow movers.

Honest position: **one to three lots per delivery, usually dominated by one.**

**Where A breaks.**

If the mixture is wide — a Chilean lot and a Mexican lot five effective days apart in one delivery —
the cohort is genuinely **bimodal**, and the unimodal spread model of [MOD-05](MOD-05%20Within-lot%20heterogeneity.md) cannot represent it.
Keep as a named unmodelled uncertainty and test by simulating bimodal truth against a fitted model.

**A small VOI result hiding here.**

Pre-Sunrise you cannot tell a single-lot delivery from a mixed one. Post-Sunrise you can, trivially.
So lot scanning does not only tell you *which* lot you sold — it tells you **how many lots you have**.
The "deconvolution with known support" framing quietly assumes the support is known. Sometimes it
isn't, and that is a channel of value nothing has counted yet.

## Decision

We will adopt **B — GS1 lot — split cohorts when the delivery mixes lots**. Chosen against the card recommendation of **A — Receipt cohort — everything that arrived on one delivery**.

**B — GS1 lot — split cohorts when the delivery mixes lots.** ⚑ Against the card's recommendation (A).

## Alternatives considered

- **A — Receipt cohort — everything that arrived on one delivery** _(card recommendation; not chosen)_ — not chosen. Define the atom as "everything that arrived on delivery t". It is exactly what the delivery record gives you, exactly what the filter can resolve, and exactly what the state should be indexed by. Mild lot mixing is then absorbed by the within-cohort spread parameter you need anyway (see [MOD-05](MOD-05%20Within-lot%20heterogeneity.md)).
- **C — Individual unit** — not chosen. Exact, and hopeless — the state space explodes and nothing is identifiable. > **Recommended: A.** But **say this explicitly in the post**: the post is *about* GS1 lot codes, and > a reader who works in traceability will otherwise assume you have conflated cohort with lot.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Milestone:** M1 — filter recovers truth from synthetic P1 data
