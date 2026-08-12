# 0043. MOD-21: Abdella transit sampling frame
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-21
GROUP: MOD
PROVENANCE: newly-raised
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1. Directly sets arrival-age spread and the "transit dominates" claim.*

**The question.**

[MOD-18](MOD-18%20Transit%20model%20parameterisation.md)=A and [MOD-11](MOD-11%20Arrival%20age%20distribution.md)=C
derive arrival age from published cold-chain temperature paths. The named open dataset is Abdella,
Brecht & Uysal 2021 (*J. Food Eng.* 298:110477 / arXiv:2103.12895) — six US strawberry shipments with
harvest-started multi-position loggers. Which shipments enter the bootstrap?

Empirical durations (harvest→end of instrumented chain): roughly **2.0, 4.2, 5.5, 6.4, 6.4, 6.6**
days. That mix is FL short-haul plus CA→East long-haul.

## Decision

We will adopt **A — Bootstrap all six Abdella shipments**.

**A — Bootstrap all six Abdella shipments.** Keeps the full FL short-haul + CA→East long-haul mix
(~2–6.6 d calendar exposure). That spread is the identification signal for FIL-11; dropping either
corridor would either stack the deck for transit-dominance (B) or put the base case in the
near-exchangeable failure regime (C).

## Alternatives considered

- **B — Long-haul only (CA→East)** — not chosen. Drops the short FL corridor; older mean arrival age, less bimodality.
- **C — Short-haul only (FL)** — not chosen. Tight arrivals — the FIL-11 failure regime as a stress test, not a base case.

## Consequences

FL short-haul (~2 d) plus CA→East long-haul (~4–6.6 d). Max arrival-age spread.

**What this gates:** Arrival-age pushforward · FIL-11 go/no-go realism · strength of the SCN-F2a transit-dominance claim.

**Revisit if:** The blueberry virtual-chain ([MOD-23](MOD-23%20Strawberry-logger%20to%20blueberry%20substitution.md)=B)
replaces Abdella bootstrap entirely — then this card becomes moot.

**Depends on:** `MOD-11`, `MOD-18`, `MOD-23`, `X-08`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
