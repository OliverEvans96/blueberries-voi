# 0014. SCN-B-state: Perfect state oracle
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SCN-B-state
GROUP: SCN
PROVENANCE: notes-agree
TIER: 2

## Context

**What it is.**

True age vector and true kernels known; **demand still stochastic**. The ceiling on what information
*about inventory* can buy. Full Sunrise should approach it.

**Why it is not optional.**

Without an upper bound, a VOI number has no scale. "Lot scanning is worth $3,400 per store-year" is
unreadable; "lot scanning captures 61% of the value of knowing the shelf exactly" is not.

It is also the cheapest possible arm — it is the simulator's own state handed straight to the
controller, with no filter in between. Perhaps twenty lines.

**The distinction that must be preserved.**

This is **not** the same as perfect foresight (SCN-B-clair), and conflating them is a common and
embarrassing error. This one knows the *shelf*; that one knows the *future*.

> **Recommended: In.** Near-zero cost, and it is what makes every other number interpretable.

## Decision

We will adopt **A — In**.

**A — In.** Chosen on the board.

## Alternatives considered

- **B — Out** — not chosen on the board.

## Consequences

**Revisit if:** Membership of the knowledge ladder changes.
