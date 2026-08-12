# 0081. FIL-14: Cohort extinct when n = 0 exactly

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-14
GROUP: FIL
PROVENANCE: newly-raised
TIER: 3
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

MOD-13=C says cohorts run to extinction with no prune threshold. With integer counts a cohort
eventually hits n = 0, so extinction is well defined — but under a fresh-biased picking kernel the
expected time is long, and both simulator and filter need a single rule for when a cohort leaves the
live set (and therefore what L is).

This is bookkeeping, but L is the exponent in FIL-13's tractability arithmetic, so the rule is on
the M1 path.

## Decision

We will adopt **A — Extinct when n = 0 exactly.** A cohort leaves the state only when the last unit
is sold or dies. No count threshold, no posterior-mass ε prune in the production process model.

## Alternatives considered

- **B — n = 0, or posterior mass below ε** — rejected for M1 production truth: a numerical filter
  truncation is not the same as the process model; if needed later for filter representation only,
  it must be documented separately and must not silently change ground-truth L.
- **C — n below a count threshold, remainder booked as waste** — rejected because that is MOD-13=A
  by another name; choosing it means reopening MOD-13 (⚑), which we will not do without Oliver.

## Consequences

- Simulator and shared `day_step` drop cohorts only at n = 0; live L is maximised relative to prune
  rules.
- FIL-13 bakeoff must measure empirical L under this exact rule (and under MOD-25 σ cells).
- Cost: longer tails and larger L than a prune-threshold world; may force FIL-13 away from full
  joint. Honesty to MOD-13=C is preserved.

**Depends on:** `MOD-13`, `FIL-13`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
