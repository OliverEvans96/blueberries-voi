# 0049. FIL-04: Factorisation of age across cohorts
STATUS: SUPERSEDED BY 0091
DATE: 2026-08-12
BOARD-ID: FIL-04
GROUP: FIL
PROVENANCE: contested → reopened to C (2026-08-12)
TIER: 1
MILESTONE: M2 — controller and multi-scenario
AGAINST-RECOMMENDATION: false

## Context

**Reopened 2026-08-12:** FIL-04 settles to **C — Mean-field, validated by brute force at small
cohort counts** via ADR [0091](./0091-fil13-production-mean-field.md) after FIL-11 Stage C PASS
(ADR 0090 / `.team/reports/FIL-11-stage-c-mf-findings.md` §6). The historical B (joint) override
below is retained for provenance only.

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

**Historical (pre-0091):** We adopted **B — Joint age posterior across cohorts** against the card
recommendation of **C**.

**Active (ADR 0091):** **C — Mean-field, validated by brute force at small cohort counts.**
Stage C evidence passed; production wires `mean_field_update`. See ADR 0091.

## Alternatives considered

- **A — Mean-field — a separate age posterior per cohort** — not chosen (unvalidated).
- **B — Joint age posterior across cohorts** — original ⚑ board pick; superseded for production by
  ADR 0091 after Stage C validation of C.
- **C — Mean-field, validated by brute force at small cohort counts** _(card recommendation)_ —
  **accepted** via ADR 0091 reopen.

## Consequences

Production age factorisation is mean-field (C). Joint (B) remains available only as bakeoff /
historical analysis, not the production default. Further reopen requires a new ADR (belief-sensitive
VOI failure or new Stage C fail).

**Depends on:** `FIL-02`, ADR 0090 (evidence), ADR 0091 (settle)

**Milestone:** M2 — controller and multi-scenario
