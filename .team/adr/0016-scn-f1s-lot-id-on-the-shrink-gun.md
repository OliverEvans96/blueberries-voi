# 0016. SCN-F1s: Lot ID on the shrink gun
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SCN-F1s
GROUP: SCN
PROVENANCE: contested
TIER: 2

## Context

**What the store observes.**

Scanning the 2D code when culling, so **deaths are age-resolved** rather than sales.

Not a rung in the original ladder — it comes from your own 2026-08-10 plan bullets, and it is a
better idea than the ladder it was added to.

**Why it is its own card.**

Sales observations tell you *which lot a customer chose*; death observations tell you *when units
die*. The first identifies the **picking kernel φ**, the second identifies the **spoilage kernel μ**.
Both arrive with Sunrise, but they are **different purchases with different business cases** — one is
a checkout integration, the other is an ops procedure with a handheld.

This is the clean answer to the φ/μ confounding that stopped the A=7 recovery study: it breaks the
identifiability problem **by measurement design** rather than by prior. That is a stronger result than
anything a better prior could give you.

**Why in or out.**

**In:** it is arguably the single highest-value card on this board relative to its cost, because it
converts a known negative result of yours into a positive one.

**Out:** only if the post cannot afford a second Sunrise rung.

> **Recommended: In.** If only one Sunrise rung survives, there is a real case that it should be this
> one rather than F1.

## Decision

We will adopt **A — In**.

**A — In.** Chosen on the board.

## Alternatives considered

- **B — Out** — not chosen on the board.

## Consequences

**Revisit if:** Membership of the knowledge ladder changes.
