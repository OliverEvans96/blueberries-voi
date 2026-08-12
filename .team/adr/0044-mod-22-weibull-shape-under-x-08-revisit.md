# 0044. MOD-22: Weibull shape under X-08 revisit
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-22
GROUP: MOD
PROVENANCE: newly-raised
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1. Triggers the revisit clause in [X-08](X-08%20Data%20provenance.md).*

**The question.**

[X-08](X-08%20Data%20provenance.md)=B promised synthetic priors calibrated from published shelf-life
studies. Its own revisit clause fires if the literature does not report Weibull shape for berries.
That is the situation: **no published blueberry *spoilage / marketability* Weibull** turned up.
Food Weibull fits exist for quality attributes (e.g. Odriozola-Serrano et al. 2009 anthocyanins in
fresh-cut strawberry) — wrong endpoint, wrong product form. AI-note β=2.5 is a placeholder, not a
citation.

## Decision

We will adopt **A — Accept β as unverified / sweep-only for M1**.

**A — Accept β as unverified / sweep-only for M1.** No published blueberry *spoilage / marketability*
Weibull turned up; quality-attribute fits are the wrong endpoint. Fix one β for the FIL-11 age-recovery
go/no-go; keep β∈[1,4] as the VOI sweep. η and Q₁₀ stay literature-anchored; shape does not — honest
partial collapse of [X-08](X-08%20Data%20provenance.md)=B for shape only.

## Alternatives considered

- **B — Attempt a decay-curve literature fit before M1** — not chosen. Force a β from quality-attribute kinetics. Wrong endpoint risk (Odriozola-Serrano etc.).

## Consequences

Honest — no published blueberry spoilage Weibull found. Fix one β for FIL-11; sweep β∈[1,4] for VOI.

**What this gates:** Whether X-08=B is claimable for the full Weibull · wording of the calibration appendix · whether M1
is blocked on a literature rabbit-hole.

**Revisit if:** A genuine blueberry *unit spoilage / marketability* Weibull (or comparable parametric hazard) appears
in the postharvest literature — then B becomes a real option rather than a category error.

**Depends on:** `X-08`, `MOD-04`, `MOD-06`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
