# 0032. MOD-10: Unmet demand
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-10
GROUP: MOD
PROVENANCE: notes-agree
TIER: 3
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1.*

**The question.**

What happens to demand that arrives when the shelf is empty.

## Decision

We will adopt **A — Lost sales, censored**.

**A — Lost sales, censored.** A stockout day reveals no more demand information.

## Alternatives considered

- **B — Backordered** — not chosen. Analytically far more tractable and standard in the classical literature, and completely wrong for a self-service grocery shelf. > **Recommended: A.** Listed only because it is load-bearing and cheap to confirm — under [MOD-09](MOD-09%20Demand%20model.md)=A > the censoring costs nothing, since demand is not being estimated, and a stockout is an *exact* > observation that on-hand hit zero.

## Consequences

A stockout day reveals no more demand information.

**Depends on:** `MOD-09`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
