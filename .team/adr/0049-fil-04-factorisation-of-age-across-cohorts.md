# 0049. FIL-04: Factorisation of age across cohorts
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-04
GROUP: FIL
PROVENANCE: contested
TIER: 1
MILESTONE: M2 — controller and multi-scenario
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M2. This is the one approximation that could quietly corrupt every downstream number.*

**The question.**

The allocation step couples cohorts through the picking normaliser, so the exact within-particle age
posterior is **joint** over (grid)^(cohorts), not a product of per-cohort marginals. Assuming it
factorises is a mean-field approximation.

**Why it will probably be fine.**

The coupling runs through a normaliser over three to five terms, and below the lot-scanning rung the
allocation is not observed per cohort anyway, so there is little information to induce dependence.

**Why "probably" is not good enough.**

Every VOI number in the project is a small difference between two expected profits. An approximation
that biases the posterior slightly, in a way that varies across rungs, would shift those differences
without producing any visible symptom. There would be no error, no warning, and no way to notice.

**The check.**

Brute-force the full joint lattice at two and three cohorts and compare against the factorised
posterior. That is an hour of work, and it either **validates the whole filter design or reveals the
one thing that would quietly corrupt every downstream number.** [FIL-03](FIL-03%20Arrival-age%20discretisation.md) decides whether it is
runnable.

**Why this card is flagged contested.**

The factorisation was introduced by the notes and immediately flagged there as unverified. It is
exactly the sort of assumption that gets made once for tractability and never revisited.

> **Recommended: C.** A without the check is the highest-risk item on the board; B is unnecessary if
> the check passes.

## Decision

We will adopt **B — Joint age posterior across cohorts**. Chosen against the card recommendation of **C — Mean-field, validated by brute force at small cohort counts**.

**B — Joint age posterior across cohorts.** ⚑ Against the card's recommendation (C).

## Alternatives considered

- **A — Mean-field — a separate age posterior per cohort** — not chosen on the board.
- **C — Mean-field, validated by brute force at small cohort counts** _(card recommendation; not chosen)_ — not chosen on the board.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `FIL-02`

**Milestone:** M2 — controller and multi-scenario
