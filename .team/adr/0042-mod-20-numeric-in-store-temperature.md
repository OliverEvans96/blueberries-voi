# 0042. MOD-20: Numeric in-store temperature
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-20
GROUP: MOD
PROVENANCE: newly-raised
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M1. [MOD-03](MOD-03%20In-store%20temperature%20treatment.md)=A settled constant-and-known; this picks the number.*

**The question.**

Under [MOD-03](MOD-03%20In-store%20temperature%20treatment.md)=A the in-store temperature is a fixed
known constant — but the literature does **not** pick a retail display setpoint. Optimum storage,
"good display," and typical case temperatures are different numbers, and which one you use changes
AF_store (under [MOD-19](MOD-19%20T_ref%20convention.md)=A) and remaining shelf life.

## Decision

We will adopt **C — ~4 °C (typical retail case)**. Chosen against the card recommendation of **D — Declare one constant and sensitivity-sweep**.

**C — ~4 °C (typical retail case).** ⚑ Against the card's recommendation (D with base B). Fixes a
single round "grocery display case" setpoint rather than a literature-cited blueberry "good display"
number or an appendix sweep. Under [MOD-19](MOD-19%20T_ref%20convention.md)=A this raises AF_store
above 1 and shortens remaining in-store life relative to optimum storage — realistic for retail, less
tightly cited than 2 °C.

## Alternatives considered

- **A — 0–1 °C (UC Davis optimum storage)** — not chosen. Best-case cold chain on the shelf; maximises remaining life, minimises AF_store under T_ref=0.
- **B — ~2 °C (Ktenioudaki "good display")** — not chosen. Published blueberry virtual-chain "good store" setpoint.
- **D — Declare one constant and sensitivity-sweep** _(card recommendation; not chosen)_ — not chosen. Pick a base (e.g. B or C) and show the VOI / FIL-11 numbers move with store T.

## Consequences

Closer to many grocery display cases; warmer AF_store under T_ref=0.

**What this gates:** Numeric AF_store · remaining in-store life vs arrival age · part of the SCN-F2a dominance check.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** A store-instrumentation arm (SCN-P2) ever supplies a measured case temperature for the instance.

**Depends on:** `MOD-03`, `MOD-19`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
