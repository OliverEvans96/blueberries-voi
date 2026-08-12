# 0046. FIL-01: Filter family
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-01
GROUP: FIL
PROVENANCE: contested
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M1. The technical core of the project.*

**The question.**

Your bullets say "particle filter". The notes upgraded that to Rao–Blackwellised without asking. Both
work; they differ in variance, in code complexity, and in how much you have to explain in the post.

**First, the framing that dissolves a lot of confusion.**

*Hidden Markov model* and *particle filter* are **not alternatives**. HMM is a model **class**; the
forward algorithm, the Kalman filter, and the particle filter are three **solvers** for the identical
recursion, differing only in what makes the integral tractable. Asking "is it an HMM or do I need a
PF?" is like asking whether something is a differential equation or Runge–Kutta.

So: yes, this is a state-space model. Yes, it can be made finite and discrete. And no, that does not
mean you can solve it exactly at the low rungs.

**Why C fails, and why it is still worth stating.**

Because effective age advances at a known rate ([MOD-02](MOD-02%20Effective%20age%20dynamics.md)=A), the only unknown in the age direction
is the static arrival value. Discretise it and the transition kernel on that coordinate is the
**identity matrix** — the grid never moves, never needs refining, never smears. The state is then
finite and the forward algorithm is exact.

But the joint lattice is roughly (compositions) × (age grid)^(cohorts) ≈ 10^12 for a realistic SKU.
So C is a **conceptual** win, not a computational one. It is still worth having, for three reasons:
it lets the post say accurately *this is an HMM; the only reason we don't solve it exactly is state
space size, not a structural obstruction*; it makes the full-telemetry collapse exact rather than
approximate; and it is what makes A possible at all.

**A versus B.**

**B — bootstrap.** Sample the whole state. Simplest possible code, roughly twenty lines, and it needs
**no density for the allocation law** — only the ability to simulate it ([MOD-08](MOD-08%20Allocation%20law.md)). Its weakness is
that the arrival-age coordinate has no process noise, so **resampling can never regenerate diversity
along it**: every resample strictly reduces the number of distinct age values in the cloud until all
particles agree on something possibly wrong.

**A — Rao–Blackwellised.** Each particle carries a count vector and, per cohort, a small discrete
posterior over arrival age updated **in closed form**. Sample the counts; never sample age. Variance
is strictly lower, and the degeneracy above cannot occur along age *by construction*. Costs a
mean-field assumption ([FIL-04](FIL-04%20Factorisation%20of%20age%20across%20cohorts.md)) and noticeably more code.

**The degeneracy is self-limiting here, which is why B is viable.**

Static-parameter impoverishment kills particle filters in long time series. Here **cohorts die**. A
cohort lives 7–14 days and is gone. You never need its arrival age to survive 500 resampling steps —
only about ten. Fresh cohorts arrive carrying fresh prior draws. The impoverishment horizon is
bounded by shelf life.

> **Recommended: B for M1, A as the upgrade.** Your instruction is to start small and iterate. B is
> the smallest thing that can be correct, it validates the simulator and the observation model, and
> it gives A something to be checked against. Building A first means debugging a mean-field
> approximation and a filter at the same time.

**Consequence of [MOD-13](MOD-13%20Bounding%20the%20number%20of%20live%20cohorts.md), added after MOD settled.**

[MOD-13](MOD-13%20Bounding%20the%20number%20of%20live%20cohorts.md)=C means **nothing bounds the live cohort count** — cohorts run until they sell out or die
out. That is not fatal (a cohort does reach zero eventually, so the count is bounded stochastically
even though it is not bounded by construction), but it changes the arithmetic between A and B:

- **B (bootstrap) costs linearly in the cohort count.** No lattice, no exponential term.
- **A (Rao-Blackwellised) costs (grid points) × (cohorts) per particle**, and the *exact* forward
  algorithm it is checked against costs grid^cohorts — which is what makes the [FIL-04](FIL-04%20Factorisation%20of%20age%20across%20cohorts.md) validation
  runnable or not.

Under LIFO-ish picking, old cohorts do not sell; they linger and slowly die, so the tail is longer
than intuition suggests. **This strengthens the case for B at M1** and means that choosing A later
would put [MOD-13](MOD-13%20Bounding%20the%20number%20of%20live%20cohorts.md) back on the table.

## Decision

We will adopt **A — Rao-Blackwellised particle filter — sample counts, marginalise age**. Chosen against the card recommendation of **B — Plain bootstrap particle filter over the joint state**.

**A — Rao-Blackwellised particle filter — sample counts, marginalise age.** ⚑ Against the card's recommendation (B).

## Alternatives considered

- **B — Plain bootstrap particle filter over the joint state** _(card recommendation; not chosen)_ — not chosen. Sample the whole state. Simplest possible code, roughly twenty lines, and it needs **no density for the allocation law** — only the ability to simulate it ([MOD-08](MOD-08%20Allocation%20law.md)). Its weakness is that the arrival-age coordinate has no process noise, so **resampling can never regenerate diversity along it**: every resample strictly reduces the number of distinct age values in the cloud until all particles agree on something possibly wrong.
- **C — Exact forward algorithm on a discretised joint lattice** — not chosen on the board.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `MOD-02`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
