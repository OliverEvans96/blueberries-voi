# 0021. SCN-P1: Shrink gun
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SCN-P1
GROUP: SCN
PROVENANCE: notes-agree
TIER: 2

## Context

**What the store observes.**

P0, plus **daily item-level waste counts**. An ops discipline change, no new hardware — widely done
in fresh at disciplined chains.

The catch: **under-reporting**. Compliance κ ≈ 0.6–0.85, varying by store and day of week. A slammed
shift dumps the cull without scanning.

**Why in or out.**

**In:** this is the regime the existing Julia experiments live in, and it is where the κ·μ₀
multiplicative gauge problem bites — you cannot separate "few things died" from "nobody scanned
them". That confounding is a genuinely good result and it is cheap to demonstrate.

**Out:** if the arrival-age story is the whole post, P1 adds a compliance parameter that is orthogonal
to age and arguably a distraction.

> **Recommended: In.** It is the realistic present-day baseline, and the κ gauge is one of the more
> interesting things the project can say about present-day data.

## Decision

We will adopt **A — In**.

**A — In.** Chosen on the board.

## Alternatives considered

- **B — Out** — not chosen on the board.

## Consequences

**Revisit if:** Membership of the knowledge ladder changes.
