# 0034. MOD-12: Within-day order of operations
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-12
GROUP: MOD
PROVENANCE: newly-raised
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1.*

**The question.**

Nobody has written this down, and it changes the numbers. The daily recursion has five events and
their order determines things like whether a unit can be sold on the same day it would have spoiled,
and whether today's delivery is available to today's shoppers.

**Why it is not pedantry.**

At high hazard — the fragile end of the beta sweep, which is where the headline effect lives — the
difference between "spoil then sell" and "sell then spoil" is a systematic shift in both waste and
sales. It will not change the sign of any result, but it will change the magnitude, and if the
simulator and the filter disagree about the ordering the filter is misspecified in a way that is very
hard to see.

**Whatever is chosen, the simulator and the filter's transition model must use the identical
ordering, and there should be a test that asserts it.**

**Note on the recursion as your bullets state it.**

The bullets say `sales = min(demand, inventory)` and `next = inventory + orders - sales`. The second
line omits spoilage, which is the channel the entire post is about. The corrected sequence:

1. **Age** — deterministic
2. **Demand** — negative binomial draw
3. **Sales** — the minimum of demand and total on hand; lost sales censored
4. **Allocation** — split sales across cohorts by picking weight
5. **Spoilage** — Binomial on the *survivors of step 4*, using the conditional survival ratio
6. **Delivery** — new cohort arrives with its own arrival age

## Decision

We will adopt **A — Age, demand, allocate sales, spoil survivors, deliver**.

**A — Age, demand, allocate sales, spoil survivors, deliver.** Chosen on the board.

## Alternatives considered

- **B — Age, spoil, then sell survivors** — not chosen on the board.
- **C — Deliver first, then sell** — not chosen on the board.

## Consequences

**Depends on:** `MOD-04`, `MOD-08`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
