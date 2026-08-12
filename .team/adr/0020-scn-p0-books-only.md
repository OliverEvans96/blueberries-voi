# 0020. SCN-P0: Books only
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SCN-P0
GROUP: SCN
PROVENANCE: notes-agree
TIER: 2

## Context

**What the store observes.**

Everything in a grocer's data lake today, with zero new instrumentation.

- Receipts in cases, with receiving error
- POS units by UPC by day — **censored**: a zero can mean no demand or no stock
- Perpetual book inventory, drifting, reset by physical count every 7–30 days
- Waste **not observed daily** — a periodic shrink accrual conflating spoilage, theft, damage and
  scan error
- Nothing at all about age

**Why in or out.**

**In:** this is the floor of the VOI ladder and therefore the baseline every other number is measured
against. Without it there is no "value of" anything.

**Out:** only if you would rather anchor at P1, on the argument that book-inventory drift and accrual
shrink are a separate modelling problem (they are) and that including them makes the floor about
*data hygiene* rather than about *age*.

> **Recommended: In**, but consider anchoring the headline at P1 and reporting P0 separately, so that
> the number you quote is not dominated by shrink-accrual noise.

## Decision

We will adopt **A — In**.

**A — In.** Chosen on the board.

## Alternatives considered

- **B — Out** — not chosen on the board.

## Consequences

**Revisit if:** Membership of the knowledge ladder changes.
