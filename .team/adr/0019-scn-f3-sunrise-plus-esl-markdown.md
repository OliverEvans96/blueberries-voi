# 0019. SCN-F3: Sunrise plus ESL markdown
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SCN-F3
GROUP: SCN
PROVENANCE: contested
TIER: 2

## Context

**What changes.**

F2, plus **price at age becomes a decision** rather than a constant. Electronic shelf labels make
dynamic markdown actuable per lot.

This is the **only rung where information changes the action space** rather than just the belief.

**Why it probably conflicts with a decision you already made.**

[X-04](X-04%20Controller%20action%20space.md) settled the controller's action space as **order quantity only**. F3 requires a second
control (price), a demand–price elasticity model, and — the trap — a picking kernel that responds to
price, since a marked-down old punnet is chosen differently from a full-price one.

So F3 as a *modelled* rung is out of scope by construction. It can still appear in the post as the
named next step, which is where your bullets originally put it ("dynamic discounts based on this
information, and the value that might provide").

**Why in or out.**

**In:** it is where the money actually is, and your own outline predicts VOI concentrates in
markdown and cull sequencing rather than in ordering.

**Out:** consistent with [X-04](X-04%20Controller%20action%20space.md), and it is a whole second project.

> **Recommended: Out**, as a modelled rung — named as future work in the post's closing section.

## Decision

We will adopt **B — Out**.

**B — Out.** Chosen on the board.

## Alternatives considered

- **A — In** — not chosen on the board.

## Consequences

**Revisit if:** Membership of the knowledge ladder changes.

**Depends on:** `X-04`
