# 0075. ENG-03: Figure and plot pipeline
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: ENG-03
GROUP: ENG
PROVENANCE: yours
TIER: 3
AGAINST-RECOMMENDATION: true

## Context

**The question.**

Your bullets ask for two kinds of figure: "some plots for each component (the filter, controller,
etc.) / explaining / evaluating the setup" and "plots comparing VOI for the different scenarios
(knowledge scenario × β)." [X-10](X-10%20Reproducibility%20standard.md) already requires figures be
committed and reproducible from the scripted pipeline; this card is about *what kind* of artifact
those figures are, distinct from [ENG-01](ENG-01%20Browser%20simulator%20scope.md)'s decision about
the interactive shelf simulator itself.

## Decision

We will adopt **A — Static images (matplotlib), committed as files per X-10**. Chosen against the card recommendation of **B — Interactive JS/Plotly embeds for the comparison plots, static images elsewhere**.

**A — Static images (matplotlib), committed as files per X-10.** ⚑ Against the card's recommendation (B). Simplest, matches X-10's "figures committed" literally, works in any blog platform.

## Alternatives considered

- **B — Interactive JS/Plotly embeds for the comparison plots, static images elsewhere** _(card recommendation; not chosen)_ — not chosen. Your bullets ask for VOI-comparison plots specifically; those are the ones worth making explorable.
- **C — Fully interactive throughout — every figure is a live embed** — not chosen. Most engineering, and overlaps with ENG-01's browser-sim risk if not scoped carefully.

## Consequences

Simplest, matches X-10's "figures committed" literally, works in any blog platform.

**What this gates:** If B or C: the VOI sweep's output format needs to be embed-friendly (e.g. a tidy JSON/CSV export
alongside whatever produces the static PNG), which should be decided once rather than bolted on after
the sweep code is written. Worth coordinating with [ENG-01](ENG-01%20Browser%20simulator%20scope.md)
if B is chosen there too, since both want a JSON export of VOI results and duplicating that pipeline
is pure waste.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** The VOI sweep's compute cost or output size makes an interactive embed impractical (e.g. the surface
is too fine-grained to ship client-side) — fall back to A for that figure specifically.

**Depends on:** `X-10`
