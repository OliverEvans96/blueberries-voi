# 0025. MOD-03: In-store temperature treatment
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-03
GROUP: MOD
PROVENANCE: contested
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M1.*

**The question.**

Display-case cycling is real. Door openings and defrost cycles put a genuine ±2–4 °C swing on the
shelf. Because the Arrhenius factor is convex in temperature, **variance costs shelf life at fixed
mean** — the same Jensen argument the post already makes for transit (roughly ×1.04 at 3 °C spread).

Assuming it away biases the effective shelf life **optimistically**.

**Why this is flagged contested.**

The notes assume constant in-store conditions while making temperature variance *the whole story* in
transit. That is defensible — transit is the larger and more variable leg — but it is mildly in
tension with the post's own thesis, and a careful reader will notice. It needs to be a stated scope
call, not a slipped-in assumption.

## Decision

We will adopt **A — Constant, known**. Chosen against the card recommendation of **B — Constant, Jensen-inflated**.

**A — Constant, known.** ⚑ Against the card's recommendation (B). Dtau is a fixed number.

## Alternatives considered

- **B — Constant, Jensen-inflated** _(card recommendation; not chosen)_ — not chosen. Same, but dtau scaled up to account for cycling variance.
- **C — Common daily shock** — not chosen. One latent scalar per day, shared across lots.

## Consequences

dtau is a fixed number.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Depends on:** `MOD-02`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
