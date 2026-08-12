# 0067. SIM-04: Ground-truth instrumentation contract
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SIM-04
GROUP: SIM
PROVENANCE: newly-raised
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1. This is what [FIL-11](FIL-11%20How%20we%20know%20the%20filter%20works.md)'s calibration
stage actually consumes — worth fixing before the simulator is built rather than reverse-engineering
from a filter that's already running.*

**The question.**

"The simulator knows the true state" (per [A.6](../../Updated%20Plan%20%E2%80%94%20Filter%2C%20Controller%2C%20and%20Where%20the%20Weibull%20Sits.md))
is the plan's whole mechanism for validating the filter — but *knowing* the truth internally and
*logging* it in a form the calibration pipeline can consume are different engineering commitments.
[FIL-11](FIL-11%20How%20we%20know%20the%20filter%20works.md)'s staged gate (does the posterior move off
the prior; credible-interval coverage and rank histograms; exact comparison at two or three cohorts)
and [FIL-12](FIL-12%20Making%20the%20joint%20age%20posterior%20tractable.md)'s brute-force
joint-vs-mean-field check both need the *true* $(n_\ell, \tau_\ell)$ per lot, per day, to compare
against the filter's posterior. If the simulator only logs aggregates, that comparison is impossible
after the fact.

## Decision

We will adopt **A — Full per-lot ground truth logged every day -- n_l and tau_l for every live lot**.

**A — Full per-lot ground truth logged every day -- n_l and tau_l for every live lot.** What FIL-11's coverage and rank-histogram calibration, and FIL-12's brute-force joint-vs-mean-field check, actually need.

## Alternatives considered

- **B — Aggregate ground truth only -- total on-hand, total waste, total sales** — not chosen. Cheaper, but insufficient to score the filter's per-cohort posterior against anything.
- **C — Full per-lot state plus the full particle cloud snapshot at each day** — not chosen. Everything in A, plus the filter's entire belief, not just its summary -- heavier storage, enables post-hoc diagnostics not anticipated up front.

## Consequences

What FIL-11's coverage and rank-histogram calibration, and FIL-12's brute-force joint-vs-mean-field check, actually need.

**What this gates:** Directly determines whether [FIL-11](FIL-11%20How%20we%20know%20the%20filter%20works.md)'s calibration
stages and [FIL-12](FIL-12%20Making%20the%20joint%20age%20posterior%20tractable.md)'s brute-force check
are even possible to run. This is on the M1 critical path, not just SIM's usual M3 territory — the
go/no-go experiment ([FIL-11](FIL-11%20How%20we%20know%20the%20filter%20works.md)) needs this logging
contract to exist before it can be run at all.

**Revisit if:** A specific debugging need arises during M1 that A's logging contract doesn't cover (e.g. needing the
full particle cloud to diagnose a specific filter failure) — upgrade to C at that point rather than
building it speculatively now.

**Depends on:** `FIL-11`, `FIL-12`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
