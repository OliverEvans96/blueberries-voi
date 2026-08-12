# 0048. FIL-03: Arrival-age discretisation
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-03
GROUP: FIL
PROVENANCE: newly-raised
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M1.*

**The question.**

How many grid points for arrival age, and placed where. Nobody has specified this and it directly
sets the filter's cost and its resolution.

**Why the grid is unusually well-behaved here.**

Under [MOD-02](MOD-02%20Effective%20age%20dynamics.md)=A the transition on this coordinate is the identity. So unlike almost every other
discretised filter, **the grid never needs to move or refine** — there is no diffusion to smear it and
no drift to chase. Choose it once.

**The tension.**

Grid points cost linearly in the Rao–Blackwellised filter but **exponentially in the joint lattice**
(as grid^cohorts), which is what makes the exact forward algorithm infeasible at low rungs and
feasible at high ones. So the grid size is also what decides whether the brute-force validation in
[FIL-04](FIL-04%20Factorisation%20of%20age%20across%20cohorts.md) is runnable.

## Decision

We will adopt **A — Fixed uniform grid over a truncated age range**. Chosen against the card recommendation of **B — Quantile grid from the arrival prior**.

**A — Fixed uniform grid over a truncated age range.** ⚑ Against the card's recommendation (B).

## Alternatives considered

- **B — Quantile grid from the arrival prior** _(card recommendation; not chosen)_ — not chosen. Points where the mass is. Same accuracy for fewer points, and it adapts automatically when the arrival spread is swept — which matters, because that spread is the key diagnostic knob ([MOD-11](MOD-11%20Arrival%20age%20distribution.md)).
- **C — Continuous — no discretisation** — not chosen. Only available if [FIL-01](FIL-01%20Filter%20family.md) takes the plain bootstrap route, in which case there is no grid at all and this card is moot. > **Recommended: B**, with the truncation stated explicitly (e.g. the point where survival falls to > 1%) since [X-03](X-03%20Date%20pull%20in%20or%20out.md) removed the maximum age that the date pull used to supply.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `MOD-11`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
