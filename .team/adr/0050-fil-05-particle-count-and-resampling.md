# 0050. FIL-05: Particle count and resampling
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-05
GROUP: FIL
PROVENANCE: newly-raised
TIER: 3
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1.*

**The question.**

Standard particle filter hygiene, on the board because the defaults matter more than usual here.

**Why resampling discipline matters more in this problem.**

The arrival-age coordinate has **no process noise**, so every resample strictly and irreversibly
reduces diversity along it ([FIL-01](FIL-01%20Filter%20family.md)). Resampling every step therefore burns the one coordinate you
care about faster than necessary. Triggering on an effective-sample-size threshold resamples only
when the weights actually demand it.

**Systematic** resampling over multinomial for the usual reason: lower variance, same cost, three
lines.

**What to watch.**

The daily waste count is highly informative relative to the prior, so weights may concentrate hard,
which pushes toward frequent resampling and back into the degeneracy problem. If effective sample
size collapses routinely, that is the signal to move to a better proposal ([FIL-10](FIL-10%20Proposal%20distribution.md)) rather than
simply adding particles.

> **Recommended: A**, with the particle count set by a convergence check rather than by taste —
> re-run one filtering pass at several counts and plot a posterior summary against count until it
> flattens. Cheap, and it belongs in the appendix.

## Decision

We will adopt **A — Fixed particle count, systematic resampling on an ESS threshold**.

**A — Fixed particle count, systematic resampling on an ESS threshold.** Chosen on the board.

## Alternatives considered

- **B — Fixed count, resample every step** — not chosen on the board.
- **C — Adaptive particle count** — not chosen on the board.

## Consequences

**Depends on:** `FIL-01`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
