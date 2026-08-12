# 0055. FIL-10: Proposal distribution
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-10
GROUP: FIL
PROVENANCE: notes-agree
TIER: 3
MILESTONE: M2 — controller and multi-scenario

## Context

*Milestone: M2. Only revisit if effective sample size demands it.*

**The question.**

What distribution particles are propagated from before weighting.

**Why bootstrap is not just the lazy choice here.**

The exact allocation law ([MOD-08](MOD-08%20Allocation%20law.md)) is Wallenius' noncentral multivariate hypergeometric, whose
density involves a one-dimensional integral and is genuinely unpleasant to evaluate. **A bootstrap
filter never needs the density — only the ability to simulate it.** B and C both need it.

So this is not a performance trade-off, it is a "do you have to implement an awkward special function"
trade-off. That is also a good argument to make in the post, because you can show the reader the
simulation loop.

**When to revisit.**

The daily waste count is highly informative relative to the prior, which is exactly the condition
under which bootstrap proposals degenerate — particles are proposed blind to the observation and then
mostly thrown away. If effective sample size collapses ([FIL-05](FIL-05%20Particle%20count%20and%20resampling.md)), this is the card to reopen.

> **Recommended: A**, with the effective sample size logged so the decision to revisit is
> evidence-driven.

## Decision

We will adopt **A — Bootstrap — propose from the transition prior**.

**A — Bootstrap — propose from the transition prior.** Chosen on the board.

## Alternatives considered

- **B — Auxiliary particle filter** — not chosen on the board.
- **C — Locally optimal proposal** — not chosen on the board.

## Consequences

**Depends on:** `FIL-01`

**Milestone:** M2 — controller and multi-scenario
