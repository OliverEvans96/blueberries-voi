# 0015. SCN-F1: Sunrise partial — lot ID at POS
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SCN-F1
GROUP: SCN
PROVENANCE: contested
TIER: 2

## Context

**What the store observes.**

P2, plus **age-resolved sales for a fraction ρ of units** — those whose suppliers have converted to
GS1 Digital Link 2D. ρ ramps roughly 0.1 → 0.6 over 2027–2029.

**Coverage is not random.** Early adopters are large branded suppliers whose product has different
handling, cold chain and transit time than the local grower's. So tagged units are a **biased sample**
of the age distribution, not a thinned one — a real selection problem.

**Why this rung matters structurally.**

Observing which lot each sale came from **severs the coupling between lots**. Below this rung the
allocation normaliser makes the lot marginals dependent and nothing factorises, so you need a joint
filter. At this rung the lots become conditionally independent and an exact per-lot forward algorithm
becomes available. **This is the rung where the filter gets simpler as you climb.**

It also identifies the **picking kernel** φ.

**Why in or out.**

**In:** this is the Sunrise rung, and the post is about Sunrise.

**Out:** hard to justify — but note that modelling ρ-selection honestly is real work, and a
simplified "ρ = 1, unbiased" version is a different and much cheaper card.

> **Recommended: In.** Consider whether biased-ρ is in scope or whether you take ρ = 1 and name the
> selection problem as future work.

## Decision

We will adopt **A — In**.

**A — In.** Chosen on the board.

## Alternatives considered

- **B — Out** — not chosen on the board.

## Consequences

**Revisit if:** Membership of the knowledge ladder changes.
