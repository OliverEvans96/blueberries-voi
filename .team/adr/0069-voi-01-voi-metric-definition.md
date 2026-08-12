# 0069. VOI-01: VOI metric definition
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: VOI-01
GROUP: VOI
PROVENANCE: newly-raised
TIER: 1
MILESTONE: M3 — VOI sweep, oracles, misspecification arms

## Context

*Milestone: M3.*

**The question.**

[X-06](X-06%20VOI%20sweep%20axes.md) settled that the sweep is over (knowledge scenario × β), and
[X-02](X-02%20Objective%20denomination.md) settled that the objective is profit, not waste. Neither
settles what the reported *number* actually is — a raw dollar delta doesn't mean anything without a
scale, and a bare percentage doesn't convey the real stakes. This is the number that goes in the
post's headline, so it's worth choosing deliberately rather than defaulting to whatever the sweep code
happens to print first.

## Decision

We will adopt **C — Both -- percentage as the headline, absolute dollar figure as supporting detail**.

**C — Both -- percentage as the headline, absolute dollar figure as supporting detail.** Costs nothing extra once both numbers exist; lets the reader translate to their own scale.

## Alternatives considered

- **A — Absolute profit difference between adjacent knowledge rungs, per store-day** — not chosen. profit(F2) - profit(P0), in dollars. Concrete, but needs a store-size caveat to generalise.
- **B — Percentage improvement relative to the least-informed rung (P0)** — not chosen. (profit(rung) - profit(P0)) / profit(P0). Scale-free, generalises across store sizes, but obscures the absolute stakes.

## Consequences

Costs nothing extra once both numbers exist; lets the reader translate to their own scale.

**What this gates:** The structure of the VOI-comparison figure ([ENG-03](ENG-03%20Figure%20and%20plot%20pipeline.md)) —
whether it's a percentage axis, a dollar axis, or both — and what
[VOI-03](VOI-03%20Statistical%20reporting%20standard.md)'s confidence intervals are computed on
(percentage or absolute, since these don't transform linearly through a bootstrap in general).

**Revisit if:** The percentage metric behaves oddly near P0 where profit could be small or noisy (a percentage off a
near-zero or noisy denominator is unstable) — if that happens in practice, anchor the percentage to a
more stable reference (e.g. the constant-order floor) instead of P0 specifically.

**Depends on:** `X-02`, `X-06`, `SIM-01`

**Milestone:** M3 — VOI sweep, oracles, misspecification arms
