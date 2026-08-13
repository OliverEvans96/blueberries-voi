# 0106. ShelfBelief ages are arrival-prior exports

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: CTL / ENG-01 (belief surface)
GROUP: CTL / FIL
PROVENANCE: Cascade from ADR 0105 (Oliver lock 2026-08-13)
TIER: 1
MILESTONE: Arrival-only count filter

## Context

ADR 0092 defined `ShelfBelief` with `age_marginals` filled from production RBPF
mean-field `age_post` rows — sales-updated MF posteriors. ADR 0100 / ENG-01 flatten that
`(L,K)` structure to a length-`L·K` buffer on the wire. ADR 0105 removes production
in-store age learning: particle ages are birth priors clocked forward, not MF posteriors.

Controllers, VOI, and the browser export still need a stable belief shape. Changing the
wire schema would break ENG-01 and CTL for no product gain.

## Decision

We will:

1. Keep the **`ShelfBelief` wire shape**: `lot_counts`, `age_marginals` as `(L, K)` (or
   list-of-lists), `tau_grid`, plus existing export helpers (`to_export`,
   `flatten_shelf_belief` → flat `L·K`).
2. Fill **`age_marginals` from arrival-derived belief only**: Dirac / birth histogram /
   F2a prior / cold Abdella prior as carried (and clocked) by the filter — **not** from
   `mean_field_update` or other in-store LL age posteriors.
3. Keep **`shelf_belief_from_oracle`** as the B-state / true-`(n,τ)` constructor with the
   same shape.
4. **Supersede the production reading** of ADR **0092** that age marginals are MF
   posteriors, and the **age_marginals semantics** of ADR **0100** insofar as they implied
   filtered MF ages. Schema / flatten contract remains.
5. Add **no new runtime dependencies** and **no new export field names** for this settle.

## Alternatives considered

- **Remove age_marginals from ShelfBelief** — rejected: F2a/F2 arrival information and
  survival-weighted inventory still need age rows; ENG-01 flat export depends on `L·K`.
- **New field `arrival_age_marginals` beside MF rows** — rejected: dual semantics invite
  the same silent mismatch this redesign removes; one meaning per wire field.
- **Change flat export to a different layout** — rejected: ENG-01 / schema already ship;
  semantics change under the same shape (ADR 0105 cascade).

## Consequences

- CTL and ENG-01 keep working without a schema migration; only the meaning of age rows
  changes (arrival prior, not sales-updated MF).
- Docs, Stage A harness notes, and changelog must say age rows are arrival priors
  (T-069).
- Cost: readers who assumed `age_marginals` were learned from sales will be wrong; that
  is intentional and must be stated in plain English.
