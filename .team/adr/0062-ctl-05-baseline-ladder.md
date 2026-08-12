# 0062. CTL-05: Baseline ladder
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: CTL-05
GROUP: CTL
PROVENANCE: notes-agree
TIER: 1
MILESTONE: M2 — controller and multi-scenario

## Context

*Milestone: M2.*

**The question.**

The rollout policy has to be compared against something, or the VOI numbers are meaningless — a
number that's only ever been checked against itself proves nothing. What has to actually get built.

**Why "naive age-blind base-stock" is not on this list at all.**

It's tempting to make the zero baseline "counts on-hand, ignores age" — but Nahmias (1976) built
exactly that policy's honest competitor: one that observes **only total on-hand** yet lands within
~1% of the age-aware optimum, by *modelling* expected outdating from the known demand distribution
and shelf life rather than by naive counting. Comparing the age-aware policy against a strawman that
doesn't do this manufactures VOI out of a baseline nobody competent would ship. This is the "corrected
age-blind" / Rung 0 baseline, and it's only well-posed under [X-11](X-11%20Delivery%20cadence%20for%20the%20base%20case.md)'s daily-delivery,
i.i.d.-demand setting — a stationary age distribution has to exist for $\bar w$ to be a single number.

## Decision

We will adopt **A — Full ladder — constant order, corrected age-blind (Rung 0), survival-weighted, +rollout, toy-scale exact DP**.

**A — Full ladder — constant order, corrected age-blind (Rung 0), survival-weighted, +rollout, toy-scale exact DP.** Five points. The DP certificate is CTL-06's concern but its existence is decided here.

## Alternatives considered

- **B — Minimal — corrected age-blind (Rung 0) and survival-weighted+rollout only** — not chosen. Answers the headline VOI question; skips the sanity floor and the optimality certificate.
- **C — Full ladder minus the exact-DP certificate** — not chosen. Four points; defer CTL-06 as future work.

## Consequences

Five points. The DP certificate is CTL-06's concern but its existence is decided here.

**What this gates:** The β=1 degeneracy check (age-aware and age-blind policies must coincide when $w$ is constant) is a
free correctness test that falls out of building the survival-weighted and constant-order arms
together. The exact-DP certificate, if built, directly gates whether
[CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md) needs revisiting.

**Revisit if:** Toy-scale exact DP turns out to be substantially harder to build than a backward induction over a
small state space suggests — then fall back to C and flag the missing certificate explicitly in the
writeup rather than silently omitting it.

**Depends on:** `CTL-01`, `CTL-02`, `X-02`

**Milestone:** M2 — controller and multi-scenario
