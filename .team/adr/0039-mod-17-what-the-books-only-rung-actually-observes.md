# 0039. MOD-17: What the books-only rung actually observes
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-17
GROUP: MOD
PROVENANCE: contested
TIER: 1
MILESTONE: M2 — controller and multi-scenario
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M2.*

**The contradiction.**

Two settled decisions disagree.

[MOD-14](MOD-14%20Are%20arrival%20counts%20observed%20exactly.md)=A says arrival counts are **observed exactly** — delivery records are ground truth.
[SCN-P0](SCN-P0%20Books%20only.md)=In brings in a rung whose definition begins: *"receipts in cases, **with receiving error**
— mis-keyed, short-shipped, unrecorded."*

Both cannot hold. As it stands, P0 has lost its defining feature.

**Why it is not cosmetic.**

Exact arrival counts are a **strong observability anchor**. If deliveries are known exactly and shrink
is reported, total on-hand is near-known, and the latent object collapses from "how much do I have and
how old is it" to just the **composition** plus the arrival ages. That is what makes the inverse
problem a deconvolution with *known support* rather than blind source separation — and it is a large
part of why the filter is tractable at all.

Turn receiving error on and the total drifts, the support is no longer known, and the filter must
track an extra poorly-informed scalar. That is a real difference in difficulty, and it is most of what
distinguishes P0 from P1.

**The other half of the same problem.**

Book drift has three sources: receiving error, theft, and unreported shrink. [MOD-15](MOD-15%20Shrink%20reporting%20compliance.md)=B switched off
the third. With the first also off, **P0 and P1 differ only in whether daily waste is observed** —
which is a legitimate rung distinction, but a much narrower one than the scenario definitions claim,
and the post should not describe P0 as "books only, everything drifts" if it doesn't.

## Decision

We will adopt **A — Drop receiving error — P0 becomes P1 without the shrink gun**. Chosen against the card recommendation of **B — Re-open MOD-14 and add the receiving-error switch for P0 only**.

**A — Drop receiving error — P0 becomes P1 without the shrink gun.** ⚑ Against the card's recommendation (B).

## Alternatives considered

- **B — Re-open MOD-14 and add the receiving-error switch for P0 only** _(card recommendation; not chosen)_ — not chosen on the board.
- **C — Drop P0 entirely and anchor the ladder at P1** — not chosen on the board.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `MOD-14`, `SCN-P0`

**Milestone:** M2 — controller and multi-scenario
