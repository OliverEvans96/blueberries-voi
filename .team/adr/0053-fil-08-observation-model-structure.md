# 0053. FIL-08: Observation model structure
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-08
GROUP: FIL
PROVENANCE: newly-raised
TIER: 1
MILESTONE: M2 — controller and multi-scenario
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M2 — M1 needs only the shrink-gun rung.*

**The question.**

Each knowledge scenario differs **only** in what the store observes. How that is expressed in code
decides whether the rung comparison is fair.

**Why it is the fairness of the whole experiment.**

The pipeline is identical in every scenario — observation, belief, policy, dollars — and **only the
first arrow changes.** Keeping everything else literally the same code is what makes the comparison a
measurement rather than an accident of two implementations. If the low rung and the high rung run
different filters, any difference between them is partly an artefact of the two codebases.

**The complication.**

The rungs are not all the same algorithm. Below lot-scanning you need Monte Carlo; at lot-scanning and
above, cohorts decouple and a per-cohort forward algorithm is **exact** and runs in microseconds.
That is a genuine and desirable asymmetry — "the filter gets simpler as you climb the ladder" is one
of the project's better results — but it means A cannot be literally one algorithm.

The resolution: one *interface* (a log-likelihood of observations given a proposed transition), with
the solver chosen per rung behind it, and the exact solver checked against the Monte Carlo one where
both are valid. That cross-check is nearly free and validates both.

**Two structural details that bite here.**

**Observations depend on the transition, not the state.** Waste is a function of the *change* in
state, so strictly this is a pairwise Markov model, not a textbook HMM. Trivial to fix — augment with
the last increments — but it changes how the likelihood is written.

**Waste is logged late.** A shrink event on day t may hit the books on day t+2. That breaks
conditional independence at the recorded timestamp and is the single most common quiet bug in this
class of model. Handle it with a short reporting-lag buffer in the state.

> **Recommended: A.**

## Decision

We will adopt **C — One filter with the richest observation model, others by masking**. Chosen against the card recommendation of **A — One filter, a pluggable observation function per rung**.

**C — One filter with the richest observation model, others by masking.** ⚑ Against the card's recommendation (A).

## Alternatives considered

- **A — One filter, a pluggable observation function per rung** _(card recommendation; not chosen)_ — not chosen on the board.
- **B — A separate filter implementation per rung** — not chosen on the board.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Milestone:** M2 — controller and multi-scenario
