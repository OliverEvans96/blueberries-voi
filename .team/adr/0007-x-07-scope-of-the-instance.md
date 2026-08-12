# 0007. X-07: Scope of the instance
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: X-07
GROUP: X
PROVENANCE: newly-raised
TIER: 2

## Context

**The question.**

Nothing in your bullets or the notes states this explicitly, but it decides the shape of every array
in the codebase and whether hierarchical structure exists at all. Worth settling before any code.

## Decision

We will adopt **A — One SKU, one store**.

**A — One SKU, one store.** Blueberries. Everything else is a sweep axis.

## Alternatives considered

- **B — One SKU, several stores** — not chosen. Enables partial pooling of kernel parameters across stores.
- **C — Two contrasting SKUs** — not chosen. One fragile (berries, high beta), one robust (apples, beta near 1).

## Consequences

Blueberries. Everything else is a sweep axis.

**What this gates:** Array shapes throughout · whether parameter inference is hierarchical · calibration effort.

**Revisit if:** Single-store event counts turn out to be too thin to identify anything, which would make B a
necessity rather than an enhancement.

**Depends on:** `X-01`
