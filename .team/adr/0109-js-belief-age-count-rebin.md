# 0109. JS-only FlatBelief → age×count BeliefGrid rebin + merged age marginal

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: T-054 review debt (lot-index-as-age heatmap); Ticket A belief charts
TIER: 1
MILESTONE: ENG-01 — studio belief visualization

## Context

ADR 0100 (wire still FlatBelief `L×K` after 0106 age semantics) keeps nested heatmap
density **JS-only**, derived from `lot_counts × age_marginals`. T-054 implemented
`beliefGridFromFlat` by treating **lot index** as the age axis (`tau_edges = 0..L`) and
placing `tau_grid` on the count axis. The Belief chart still labels Age×Count and draws
truth markers at `(tau, n)`, so cells and overlays disagree — called out as non-blocking
debt in the T-054 review.

The Python wire must stay flat `L×K` (no particle age×count joint on the boundary). The
studio needs a true age×count surface plus a merged age marginal that shares the heatmap
age axis.

## Decision

We will:

1. **Rebin in JS only** (projector): for each lot `l` with count `n_l`, form
   `mass[k] = lot_counts[l] * age_marginals[l*K+k]` and deposit that mass into the
   **count bin** for `n_l`. The presentation `BeliefGrid.density` becomes **`K × C`**
   (age bins × count bins), not `L × K`.
2. Set **`tau_edges = centersToEdges(tau_grid)`** and **integer-friendly `count_edges`**
   spanning `0 .. max(lot counts, truth lot n, 1)` (inclusive upper extent for binning).
3. Expose a **merged age marginal**
   `m[k] = Σ_l lot_counts[l] * age_marginals[l*K+k]` (length `K`) on the view-model /
   chart inputs for a **top** histogram that shares the heatmap age (`tau`) domain.
4. Leave the **Python / wire `FlatBelief` shape unchanged** (`L`, `K`, `lot_counts`,
   `age_marginals` length `L*K`, `tau_grid` length `K`).

## Alternatives considered

- **Expand Python export to an age×count joint** — rejected: enlarges FFI/HTTP payloads,
  contradicts ADR 0100 flat-belief ownership, and is unnecessary when lot-level
  marginals × counts already determine the deposited mass.
- **Keep lot-index axes (status quo)** — rejected: axes and truth `(tau, n)` remain
  inconsistent with chart labels; the T-054 review debt stays open.
- **Transpose only (swap axes) without count binning** — rejected: yields age×lot or
  similar; still not age×count, so truth `n` has no matching count bin axis.

## Consequences

**Easy:** Belief heatmap and truth overlay share a coherent age×count geometry; age
marginal sits as a top strip on the same `tau` domain; Mock / Http / Pyodide adapters
need no wire change.

**Hard / cost:** Projector tests that asserted `L×K` density must be rewritten; count
binning of non-integer `lot_counts` needs a fixed rule (round to nearest integer bin);
axis extent depends on both belief counts and live truth lots.

**Locked in:** Presentation density is age×count (`K×C`); wire remains `L×K` FlatBelief;
age marginal is a JS-derived length-`K` vector.

**Revisit if:** product wants a true particle joint age×count posterior on the wire
(then a new ADR superseding the flat-marginal ownership split).
