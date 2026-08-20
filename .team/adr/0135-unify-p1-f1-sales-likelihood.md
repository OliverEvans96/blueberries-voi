# 0135. Unify P1/F1 sales likelihood: closed-form allocation + unscored state-transition removal

STATUS: PROPOSED
DATE: 2026-08-20
BOARD-ID: FIL
GROUP: FIL
PROVENANCE: T-136 — sales-likelihood unification (intake 2026-08-20)
TIER: 1
RELATED: [0130](./0130-f-native-c2-a-unit-pf.md) (f-native unit-PF router and particle bank — unchanged),
[0105](./0105-arrival-only-age-counts-only-exact-wor.md) (exact WOR production policy lineage),
[0090](./0090-fil11-stage-c-sequential-wor-pmf-exact-vs-mf.md) (sequential WOR vs soft likelihood precedent)

## Context

Production `unit_pf` (ADR 0130) routes P1 totals through `p1_totals_loglik` and F1 lot-resolved
observations through `loglik_sales_by_units`. Both functions today call
`sequential_kernel_path_logprob` — a **single-sample Monte Carlo draw** of one weighted-WOR path —
and sum that path's log-probability into the particle importance weight. F1 calls this once **per
lot** (`L` independent draws); P1 calls it once (pooled). Estimator variance compounds with lot
count, making F1 posteriors **more diffuse than P1** despite richer observations — a pure
implementation artifact.

Additionally, `score_particle` takes `freshness: &[f64]` immutably: sold units are scored but
**never removed** from particle state, unlike truth (`day_step::pick_units_f`). Sales evidence is
only a soft re-weighting signal, not a state mutation — a shared bug on both channels.

The cross-lot information in `sales_by` (how pooled demand split across lots given picking-weight
mass) is **never scored**: per-lot factorization treats each lot as an isolated sub-population.

This is a quiet reversal of principles locked in ADR 0105 ("Monte Carlo observation likelihood is
diagnostic / legacy only; default weights = exact sequential WOR, one evaluation per particle-day")
and ADR 0090 (avoid tautological soft scoring). ADR 0130 moved to continuous per-unit freshness
and fell back to MC-scored paths without re-litigating that stance — the exact Wallenius PMF at
unit granularity is genuinely intractable, but the departure was never documented.

Investigation and architectural review: `.team/reports/sales-likelihood-unification-review.md`.

## Decision

We will split the conflated "sample a path and score it" into two independent pieces:

**(a) Deterministic, closed-form likelihood — no RNG in importance weights:**

- `p1_totals_loglik(freshness, sales_tot, waste_tot, params) -> f64`: drop `rng`; drop internal
  `sequential_kernel_path_logprob` from the weight; keep feasibility gate and exact binomial waste
  term unchanged.
- `loglik_sales_by_units(freshness, sales_by, offsets, params) -> f64`: drop `rng`; drop per-lot
  `sequential_kernel_path_logprob` loop; keep per-lot feasibility gates; **add**
  `Multinomial(sales_by; n = sales_tot, p = lot_share)` where `lot_share[ℓ]` is the normalized
  sum of pooled `picking_weights_f` over lot `ℓ` (pre-mutation freshness). Guard
  `lot_share[ℓ] == 0 && sales_by[ℓ] > 0 => -∞`; `sales_tot == 0 => 0.0`.
- P1 is the `n_lots = 1` degenerate case (trivial multinomial), not a separately maintained path.
- Waste scoring runs on **pre-removal** freshness (ordering invariant preserved).

**(b) Unscored state-transition removal — stochastic, not in the weight:**

- `sequential_kernel_path_logprob(freshness: &mut [f64], ...)` zeroes picked slots as it goes
  (mirroring `pick_units_f`), returning path log-prob as diagnostic only.
- Called from `score_particle` **after** a finite likelihood, never before:
  - P1: one pooled WOR draw across the whole store.
  - F1: independent per-lot WOR draws conditional on known `sales_by[ℓ]`.
- `score_particle` takes `&mut [f64]`; `filter_step_unit` scoring loop passes `&mut bank.freshness[p]`.

This unscored removal is a **forward application** of known picking dynamics (matching truth), not
**backward inference** of freshness from sales — consistent with ADR 0105's "no in-store age
learning from sales" principle.

The Stage-2 multinomial term approximates **Wallenius' weighted noncentral hypergeometric**
distribution over the cross-lot split — not the plain multivariate hypergeometric ADR 0105
rejected for the counts model (which was tractable exactly there). At unit granularity the exact
Wallenius PMF is intractable; multinomial with fixed lot shares is a deliberate first-order
approximation, validated before merge (exact-path enumeration at small `L`, Monte Carlo comparison
at realistic `L`).

## Alternatives considered

- **Increase particle count `N` alone** — reduces overall noise but does not remove L-scaling
  asymmetry, does not score cross-lot allocation, does not fix missing state mutation. Rejected as
  a substitute; not precluded as an orthogonal tuning knob.
- **Average `m` independent within-day MC path draws per lot (log-mean-exp), optionally CRN across
  lots** — reduces variance of problem 1 but converges to a still mis-specified quantity; does not
  fix problem 2 or 3. Rejected as insufficient.
- **Exact enumeration over individual units** — combinatorially intractable at continuous per-unit
  weights. Rejected.
- **Revert to cohort/binned representation for sales pathway** — pre-0130 architecture; ADR 0130
  rejected cohort abstraction for good physical reasons. Rejected again.
- **Deferred (not rejected): binned-freshness DP** — recursive DP over `f_grid` K-bins for a
  bin-exact Wallenius-style cross-lot split; strictly more faithful than plain multinomial. Named
  for revisit if validation shows multinomial error too large in realistic regimes.

## Consequences

- F1 (`sales_by`) will no longer look less informative than P1 (`sales_tot`) due to MC noise;
  richer observations can tighten posteriors when lots are heterogeneous.
- Sold units are removed from particle belief state, aligning filter dynamics with truth picking.
- Importance-weight formula changes → posterior beliefs and downstream policy decisions shift;
  **previously published VOI sweep profit deltas are stale** and require a separate regeneration
  decision (out of scope for T-136).
- `experiments/c2_a_totals_study.md` headline figures (mean_f MAE, timing, hist_tv) will shift;
  **must be regenerated in T-136** since ADR 0130 cites them as decision provenance.
- ADR 0130 `STATUS` and architectural decisions (unit-f truth, router, wire) remain unchanged;
  this ADR owns likelihood/state-transition internals only.
- Multinomial approximation error is accepted for now; binned-freshness DP is the documented
  upgrade path if validation fails in production regimes.
