# 0057. FIL-12: Making the joint age posterior tractable
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-12
GROUP: FIL
PROVENANCE: newly-raised
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M1. **This is the one thing that blocks writing filter code.** Everything else in M1 is
settled and consistent.*

**The conflict.**

Four settled decisions are individually reasonable and jointly infeasible:

| Card                                         | Chosen   | Consequence                            |                                                             |
| -------------------------------------------- | -------- | -------------------------------------- | ----------------------------------------------------------- |
| [FIL-01](FIL-01%20Filter%20family.md) | Rao–Blackwellised PF                   | each particle carries an age posterior                      |
| [FIL-04](FIL-04%20Factorisation%20of%20age%20across%20cohorts.md) | **Joint** age posterior across cohorts | that posterior has grid^cohorts entries                     |
| [FIL-03](FIL-03%20Arrival-age%20discretisation.md) | Fixed uniform grid                     | the grid is not adaptive, so it cannot shrink to compensate |
| [MOD-13](MOD-13%20Bounding%20the%20number%20of%20live%20cohorts.md) | **No bound** on live cohorts           | the exponent is unbounded                                   |

A joint posterior over the age grid costs `K^L` **per particle, per day**. At a 50-point grid and
four cohorts that is 6.25 million entries per particle; at ten thousand particles it is not a filter,
it is a heat source. And [MOD-13](MOD-13%20Bounding%20the%20number%20of%20live%20cohorts.md)=C means `L` has no ceiling — under LIFO-ish picking old cohorts
do not sell, they linger and slowly die, so the tail is longer than intuition suggests.

The mean-field option ([FIL-04](FIL-04%20Factorisation%20of%20age%20across%20cohorts.md) A/C) exists precisely to avoid this. Choosing the joint posterior is
the *more correct* answer and it is the one that does not run.

**Why the coupling exists at all.**

The allocation step couples cohorts through the picking normaliser — the denominator sums over every
live cohort. So the exact within-particle age posterior genuinely is joint. Below the lot-scanning
rung you only observe the sales *total*, so the dependence is real but weak: there is little
per-cohort information to induce it.

## Decision

We will adopt **B — Coarse age grid, joint**. Chosen against the card recommendation of **C — Joint over a sliding window of the youngest few cohorts**.

**B — Coarse age grid, joint.** ⚑ Against the card's recommendation (C). Few grid points so grid^L stays small.

## Alternatives considered

- **A — Bound the cohort count** — not chosen. Reopen MOD-13; a hard cap makes grid^L finite.
- **C — Joint over a sliding window of the youngest few cohorts** _(card recommendation; not chosen)_ — not chosen. Exact where the coupling is strong, factorised in the tail.
- **D — Revert FIL-04 to mean-field with a brute-force check** — not chosen. The originally recommended option.

## Consequences

Few grid points so grid^L stays small.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `FIL-01`, `FIL-03`, `FIL-04`, `MOD-13`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
