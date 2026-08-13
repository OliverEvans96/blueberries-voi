# 0031. MOD-09: Demand model
STATUS: SUPERSEDED BY 0110
DATE: 2026-08-12
BOARD-ID: MOD-09
GROUP: MOD
PROVENANCE: contested
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1.*

**The question.**

Your bullets say "learn negative binomial distribution from FreshNet; assume known distribution,
stochastic realization." The notes turn that into strict i.i.d. with no seasonality of any kind,
which is a stronger claim than your bullet made.

**Why "known distribution" is the point, not a shortcut.**

The project's thesis is that **forecasting is not ordering**. Granting every policy — including every
baseline — a *perfect* demand forecast and still measuring a large ordering gap is a far stronger
claim than one that confounds the two. Policies then differ **only** in what they know about age.

A useful side effect: since demand is not being estimated, the censoring in `min(demand, inventory)`
costs nothing. A stockout becomes a **lossless** event — an exact observation that on-hand reached
zero, which is strongly informative for the count filter.

**What i.i.d. plus daily delivery buys.**

Time-homogeneity: a constant protection interval, a genuinely **stationary** age distribution (which
the corrected age-blind baseline depends on being well-defined), no calendar in the rollout.

**What it costs, and it is the same worry as [X-11](X-11%20Delivery%20cadence%20for%20the%20base%20case.md).**

If day-of-week demand returns, three things break and must be re-derived: the protection interval
becomes day-indexed, the age distribution becomes only *periodic* so the age-blind baseline's weight
must be day-indexed too — leave it a scalar and that baseline silently reverts to the strawman it
exists to prevent — and the rollout horizon sweep must move in multiples of 7.

## Decision

We will adopt **A — Negative binomial, i.i.d., distribution known to every policy**.

**A — Negative binomial, i.i.d., distribution known to every policy.** Chosen on the board.

## Alternatives considered

- **B — Negative binomial with day-of-week and seasonal structure** — not chosen on the board.
- **C — Demand inferred jointly with the state** — not chosen on the board.

## Consequences

**Milestone:** M1 — filter recovers truth from synthetic P1 data
