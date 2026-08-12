# 0036. MOD-14: Are arrival counts observed exactly
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-14
GROUP: MOD
PROVENANCE: contested
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M1.*

**The question.**

Your bullets say "lots known from delivery records", which implies arrival counts are known exactly.
The scenario definitions say the opposite for the lowest rung: P0 has "receipts in cases, with
receiving error (mis-keyed, short-shipped, unrecorded)".

Both cannot be true, and the difference is large.

**Why it matters more than it looks.**

Exact arrival counts are a **strong observability anchor**. If deliveries are known and shrink is
reported, total on-hand is near-known, and the latent object collapses from "how much do I have and
how old is it" to just the **composition** — a point on a simplex — plus the arrival ages. That is
what makes the inverse problem a deconvolution *with known support* rather than blind source
separation, and it is a large part of why the filter is tractable at all.

Introduce receiving error and the total starts to drift, the support is no longer known, and the
filter has to track an extra scalar with almost no information about it.

## Decision

We will adopt **A — Yes, exactly — delivery records are ground truth**. Chosen against the card recommendation of **B — Exact by default, with a receiving-error switch for the P0 rung**.

**A — Yes, exactly — delivery records are ground truth.** ⚑ Against the card's recommendation (B).

## Alternatives considered

- **B — Exact by default, with a receiving-error switch for the P0 rung** _(card recommendation; not chosen)_ — not chosen on the board.
- **C — Always noisy** — not chosen on the board.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Milestone:** M1 — filter recovers truth from synthetic P1 data
