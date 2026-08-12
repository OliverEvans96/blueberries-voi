# 0002. X-02: Objective denomination
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: X-02
GROUP: X
PROVENANCE: notes-agree
TIER: 1

## Context

**The question.**

VOI is a difference of expected costs, so the units of the headline number are decided here. The
notes assert profit without argument ([X-01](X-01%20What%20the%20post%20must%20demonstrate.md) framing C makes this consequential — the whole payoff
is a single number).

## Decision

We will adopt **A — Profit**.

**A — Profit.** Margin x sales − waste cost − stockout penalty − disposal cost.

## Alternatives considered

- **B — Waste and service level, reported as a pair** — not chosen. No exchange rate asserted; the reader picks their own.
- **C — Profit, subject to a service-level constraint** — not chosen. Retail practice: service is a floor, not a term you trade against.

## Consequences

margin x sales − waste cost − stockout penalty − disposal cost

**What this gates:** CTL fractile tuning · VOI reporting · whether a service constraint enters the controller at
all.

**Revisit if:** The stockout penalty turns out to dominate the VOI number, in which case B's honesty starts to look
better than A's crispness.

**Depends on:** `X-01`
