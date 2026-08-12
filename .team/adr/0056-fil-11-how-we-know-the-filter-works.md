# 0056. FIL-11: How we know the filter works
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-11
GROUP: FIL
PROVENANCE: newly-raised
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1. This is the gate that decides whether the project has a technical core.*

**The question.**

"The filter runs" is not "the filter works". What is the falsifiable test?

**The go/no-go, and it comes first.**

**Does the posterior actually move?** Under [MOD-02](MOD-02%20Effective%20age%20dynamics.md)=A, in-store ageing adds the same amount to
every cohort and cannot help you tell them apart, so **all** identification comes from cohorts
arriving at different ages. If the arrival spread is tight and the cadence rigid, the age posterior
stays at the prior, the filter is decoration, and the low-rung VOI is entirely a statement about
where the prior came from.

This is a **two-hour experiment** and it should be the first thing built after the simulator. Plot
the posterior spread over a cohort's life against the prior, swept over arrival spread. If it does
not contract, the honest move is to publish that.

**The three tests.**

**A — Contraction.** As above. Necessary, not sufficient: a filter can be confidently wrong.

**B — Calibration.** Simulate many worlds, filter each, and check that the truth falls inside the 90%
credible interval about 90% of the time; rank histograms should be flat, not U-shaped (overconfident)
or dome-shaped (underconfident). This is the test that catches a *wrong* filter, and it is the one
most often skipped.

**C — Exact comparison.** At two or three cohorts with a small age grid, run the exact forward
algorithm and compare posteriors directly. Definitive where it applies, and it doubles as the
[FIL-04](FIL-04%20Factorisation%20of%20age%20across%20cohorts.md) factorisation check.

**Two free bug-catchers worth building at the same time.**

- **The degeneracy check.** At Weibull shape 1 the survival weight is constant in age, so an
  age-aware policy and an age-blind one must produce **identical** decisions. Falsifiable by its own
  mechanism, catches a large class of implementation bugs, and validates the filter and the
  controller simultaneously.
- **Simulator/filter model agreement.** Assert that the transition ordering ([MOD-12](MOD-12%20Within-day%20order%20of%20operations.md)) and the
  survival-ratio form ([MOD-04](MOD-04%20Spoilage%20law.md)) are literally shared code between the two, so misspecification is
  something you *switch on* deliberately rather than something you have by accident.

> **Recommended: D**, staged: contraction first as the go/no-go, then calibration, then exact
> comparison. Contraction is cheap and decides whether the rest is worth building.

## Decision

We will adopt **D — All three, as a staged gate**.

**D — All three, as a staged gate.** Chosen on the board.

## Alternatives considered

- **A — Posterior contraction against the prior** — not chosen. As above. Necessary, not sufficient: a filter can be confidently wrong.
- **B — Calibration — rank histograms and credible-interval coverage** — not chosen. Simulate many worlds, filter each, and check that the truth falls inside the 90% credible interval about 90% of the time; rank histograms should be flat, not U-shaped (overconfident) or dome-shaped (underconfident). This is the test that catches a *wrong* filter, and it is the one most often skipped.
- **C — Exact comparison at toy scale** — not chosen. At two or three cohorts with a small age grid, run the exact forward algorithm and compare posteriors directly. Definitive where it applies, and it doubles as the [FIL-04](FIL-04%20Factorisation%20of%20age%20across%20cohorts.md) factorisation check.

## Consequences

**Milestone:** M1 — filter recovers truth from synthetic P1 data
