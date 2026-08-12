# 0009. X-09: Language and stack
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: X-09
GROUP: X
PROVENANCE: newly-raised
TIER: 2
AGAINST-RECOMMENDATION: true

## Context

**The question.**

The repo currently contains **both** a `pyproject.toml` with no code and a Julia project in
`si-picking-expiry/` with a working Turing.jl recovery study. Nobody has decided which one this is.
It affects nothing conceptual and everything practical, and it gets more expensive to change every
day.

## Decision

We will adopt **B — Python throughout, JS for the browser sim**. Chosen against the card recommendation of **A — Julia throughout, JS for the browser sim**.

**B — Python throughout, JS for the browser sim.** ⚑ Against the card's recommendation (A). Pyproject.toml already exists; wider reader familiarity.

## Alternatives considered

- **A — Julia throughout, JS for the browser sim** _(card recommendation; not chosen)_ — not chosen. Matches si-picking-expiry/ and the controller pseudocode.
- **C — Julia core, Python for plotting and analysis** — not chosen. Two languages, each where it is strongest.

## Consequences

pyproject.toml already exists; wider reader familiarity.

**What this gates:** ENG repo layout · reproducibility manifest · how the browser simulator gets its pre-computed inputs.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** The browser visualisation ends up needing to share model code with the backend, which would argue for
whichever language transpiles or ports most cleanly.
