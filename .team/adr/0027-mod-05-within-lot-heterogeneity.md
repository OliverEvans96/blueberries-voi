# 0027. MOD-05: Within-lot heterogeneity
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-05
GROUP: MOD
PROVENANCE: contested
TIER: 1
MILESTONE: M2 — controller and multi-scenario
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M2 — can be switched off (theta = 0) for M1.*

**The question.**

Units in a cohort do **not** share an effective age. The strawberry pallet studies use nine logger
positions precisely because they don't — position determines exposure. So a cohort's age is a
*distribution*, and applying the hazard at the cohort mean is wrong.

This is entirely AI-introduced; nothing in your bullets mentions it. It is flagged contested for that
reason, not because the notes disagree.

**Why it matters more than bookkeeping — it biases the number the post is about.**

Under gamma frailty, unit i has hazard Z_i · h0(tau) with Z gamma-distributed, mean 1, variance
theta. Physically natural: a hotter pallet position just runs the clock faster. Lot-level survival is
then closed form, and the lot hazard is the individual hazard **deflated by a factor that grows with
age**, because frail units die first and the survivors are selected.

    d log h_lot / d log tau  =  (beta - 1) - theta*beta*H0 / (1 + theta*H0)

which starts at beta−1 and decreases. In words:

> **Unmodelled within-lot heterogeneity makes the observed aggregate hazard flatter than the true
> per-unit hazard. A fit that ignores it recovers a beta smaller than the truth.**

That is the classical frailty result, and it lands directly on the central claim, because **VOI is
zero at beta = 1 and increasing in beta**. Ignoring within-cohort spread therefore systematically
**understates the value of the information the post is trying to price.**

The bias runs conservative, which is lucky. But it is an attractive result to include: *heterogeneity
you didn't model makes your data look like the degenerate case* is a satisfying trap to spring.

**Why gamma specifically.**

It is **self-similar under selection**: among survivors, the frailty mean deflates but the
coefficient of variation stays exactly constant. So the spread parameter is a constant you never have
to propagate, and the left-truncation of [MOD-06](MOD-06%20Clock%20origin%20and%20left-truncation.md) becomes exact and free. That is the reason to
prefer A over B.

## Decision

We will adopt **C — Ignore it — units in a cohort share one age**. Chosen against the card recommendation of **A — Gamma frailty on the clock**.

**C — Ignore it — units in a cohort share one age.** ⚑ Against the card's recommendation (A).

## Alternatives considered

- **A — Gamma frailty on the clock** _(card recommendation; not chosen)_ — not chosen. Closed-form lot survival, one scalar per cohort.
- **B — Carry a variance and Jensen-correct** — not chosen. As in the outline; correction sign flips at beta = 2.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `MOD-01`

**Milestone:** M2 — controller and multi-scenario
