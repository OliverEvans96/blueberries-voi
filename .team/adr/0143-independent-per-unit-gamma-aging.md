# 0143. Independent per-unit gamma aging and Poisson-binomial spoilage

STATUS: ACCEPTED
DATE: 2026-08-21
BOARD-ID: FIL
GROUP: FIL
TIER: 1
RELATED: [0130](./0130-f-native-c2-a-unit-pf.md) (f-native unit PF),
[0137](./0137-observed-lot-segmentation-and-exact-spoilage-likelihood.md) (shared δ interval — **superseded**),
[0133](./0133-observation-channel-toggles.md) (orthogonal observation channels)

## Context

ADR 0137 replaced binomial waste with an exact interval constraint on **one shared** daily
gamma decrement `δ`. That matched a generative model where every live unit received the same
aging draw, which forced lot-homogeneous freshness within segments and made LGTIN `waste_by`
a pure **contrast falsifier** — it could reject mis-ordered particles but never sharpen the
posterior over freshness **level** relative to pooled UPC waste.

Empirical LGTIN/UPC diagnostics (notebook 14, `lgtin_upc_diag`) showed the structural ceiling:
level gains came from pack-date / delivery-history channels, not lot-resolved spoilage. The
investigation hypothesis: independent unit aging unlocks lot-resolved spoilage as a **level**
informative channel because units within a lot can diverge before spoiling.

## Decision

### 1. Independent decrements in ground truth

`unit_day_step` draws **one gamma decrement per live unit per day** when aging stochastically.
`gamma_decrement: Some(d)` on `UnitDayStepIn` remains a deterministic shared cap for tests.

### 2. Poisson-binomial spoilage likelihood

For a cohort with pre-aging freshness vector `f` and spoil probabilities
`p_i = P(δ_i ≥ f_i)` from the gamma decrement law, observing `w` spoils yields the
Poisson-binomial PMF. We score **`log PMF(w)`** exactly via a DP (`pb_log_pmf`,
`pb_loglik_by_lot` for LGTIN segments, pooled alive set for UPC).

### 3. Fully adapted proposal

Stage 1 of `filter_step_unit`:

1. Compute per-unit spoil probabilities from freshness (via table).
2. **Backward-sample** the death count and which units died from the PB DP
   (`pb_sample_deaths`) — proposal `q(deaths | f, w)`.
3. Apply **truncated gamma** decrements to survivors; weight = exact PMF / proposal mass.

This is fully adapted: weights are deterministic given the draw; no interval truncation on a
shared `δ`.

### 4. GammaDecrementTable (mandatory, explicit)

`physics::GammaDecrementTable` precomputes a **4096-point** grid on freshness bits for the
current `(gamma_shape, gamma_scale, store temp factor)`. It provides `cdf`, `quantile`, and
`spoil_prob`. Callers pass `&mut GammaDecrementTable`; **`for_params` rebuilds on change**.
No `thread_local` cache — session, VOI, and diagnostics own one table each (or rebuild per
call in thin wrappers).

### 5. Delete shared-δ interval primitives

The following are **removed from the codebase** (not feature-gated):

- `spoil_delta_interval`, `spoil_delta_interval_by_lot`
- `delta_interval_loglik`, `DeltaInterval`, `DELTA_ANY`
- `contrast_spoilage_weight`
- `draw_gamma_decrement_truncated` on the filter hot path (may remain in physics for research
  if unused — prefer delete if no callers)

Guard tests forbid reintroduction. ADR 0137 interval semantics are historical only.

### 6. LGTIN waste_by always scored when aligned

Remove the T-139 guard that disabled lot-resolved waste when segments lacked spread — with
independent aging, per-lot counts are always meaningful when `sales_by` alignment holds.

## Consequences

- **Level information from spoilage:** UPC and LGTIN waste observations constrain per-unit
  death probabilities, not just order statistics of a shared decrement.
- **LGTIN ≤ UPC guard:** Richer channel remains at least as informative on comparable metrics
  (AC-G4 non-regression); strict improvement is measured, not assumed.
- **count_bias == 0:** With adapted PB spoilage + observed arrivals/sales, store count
  conservation is exact on scored rungs (hard gate in diagnostics).
- **Runtime:** Table lookup replaces per-step incomplete-gamma calls; PB DP is O(n·w) per
  lot segment — acceptable at N=200, U=15×L.
- **Supersedes ADR 0137** spoilage mechanism; lot segmentation and sales path from 0137 remain.
