# 0137. Observed lot segmentation and exact spoilage likelihood

STATUS: PROPOSED
DATE: 2026-08-20
BOARD-ID: FIL
GROUP: FIL
PROVENANCE: GSIN/UPC accuracy investigation (branch `investigation/gsin-upc-accuracy`)
TIER: 1
RELATED: [0130](./0130-f-native-c2-a-unit-pf.md) (f-native unit PF),
[0135](./0135-unify-p1-f1-sales-likelihood.md) (deterministic sales weights, unscored WOR removal),
[0136](./0136-zero-init-phantom-belief-remediation.md) (zero-init, birth = arrival qty),
[0133](./0133-observation-channel-toggles.md) (orthogonal observation channels)

## Context

ADR 0135 set out to make the GSIN (lot-resolved) filter at least as accurate as the UPC
(aggregate) filter. Measured end to end it was dramatically **worse**: on a 60-day episode
with overlapping lots, GSIN carried **+24 units** of phantom belief mass against truth
where UPC carried under 1, and its closed-loop CRN profit was roughly **a third** of the
UPC rungs'.

Three defects compounded:

1. **The filter guessed its own lot boundaries.** `unit_pf` partitioned each particle row
   into fixed `units_per_lot` chunks (`lot_offsets_for_len`), while ground truth appends
   one variable-width segment per delivery and never removes it. The two partitions were
   unrelated: by day 12 of a typical episode truth held 4 lots and the particle row
   resolved to 2. A third, different partition (`row.len() / L`) lived in `belief_flat`.

2. **Misalignment silently disabled the GSIN likelihood.** `loglik_waste_by_units` returns
   `-∞` when `waste_by.len() != n_lots`, which after (1) was almost every day. Every
   particle scored `-1e300`, the weights normalized to uniform, and the "richer" channel
   ran as a blind bootstrap filter. `align_lot_map` masked the rest by truncating the
   observed map to its last `n_lots` entries — discarding real sales rather than failing.

3. **Row length drifted.** On each arrival the bank drained a fixed `units_per_lot` from
   the front and appended `obs.arrivals`, so any case size above `units_per_lot` inflated
   the row by the difference every delivery. That is the mechanical source of the phantom
   mass; nothing in the likelihood could remove it.

Separately, the waste term itself was indefensible. Both channels scored spoilage as
`Binomial(waste; alive - sales, dead/units)` — treating the fraction of already-dead slots
as a per-unit death probability. Spoilage in this model is not a per-unit coin flip: the
whole store ages by **one shared gamma decrement** per day
(`physics::apply_gamma_aging`), so spoilage is its deterministic consequence.

## Decision

### 1. The bank carries an observed lot segmentation

`UnitParticleBank` gains `lot_offsets: Vec<usize>` and `lot_ids: Vec<i64>`, shared by every
particle. Arrival quantity is present on **every** mask, so all particles agree on how many
units arrived and when; they differ only in the freshness those units carry. A delivery
appends exactly one segment, exactly as wide as the delivery.

Under GSIN, `arrival_lot_ids` supplies real identities and `sales_by` / `waste_by` are
matched to segments **by id** (`project_lot_map`), not by position. An observation that
attributes a nonzero count to a lot the bank does not hold degrades that day to aggregate
scoring rather than killing every particle. Under UPC the ids are internal and monotone.

Leading segments that hold no live unit in **any** particle are retired
(`prune_dead_prefix`); `lot_summary_aligned` gives callers the newest-`n` view padded with
zeros, which is the alignment truth's lot list uses. `belief_flat_from_unit_bank` reads the
bank's segmentation instead of re-deriving one.

### 2. Spoilage is an interval constraint on the shared decrement

A unit with pre-aging freshness `f > 0` spoils iff `f ≤ δ`. Observing `w` spoiled units in
a group whose sorted positive freshness values are `g_1 ≤ … ≤ g_m` confines `δ` to
`[g_w, g_{w+1})` (`g_0 = 0`, `g_{m+1} = ∞`). So:

- **Likelihood** = the gamma mass of that interval (`delta_interval_loglik`), exact and
  deterministic.
- **State update** = draw `δ` from the gamma **truncated to the interval**
  (`draw_gamma_decrement_truncated`) — the fully adapted proposal, `q(δ|x,y) = p(δ|x,y)`
  with weight `p(y|x)`.

UPC observes the store total and gets the pooled interval. GSIN observes `w_ℓ` per lot and
gets `⋂_ℓ I_ℓ`. Every `δ` consistent with the per-lot counts is consistent with their sum,
so **`I_gsin ⊆ I_pooled` always**: the richer channel can never blur the posterior over `δ`.

**It also never sharpens it, in this model.** Births are lot-uniform and aging is one shared
decrement, so every live unit in a lot carries the same `f` and a lot spoils *all or
nothing*. Under that structure the store's order statistics **are** the lot values, so the
total already determines which lots died. Measured over 20 000 random cohort-consistent
shelves (`gsin_waste_never_narrows_the_pooled_interval`), `I_gsin` was **exactly**
`I_pooled` in 91% of cases and **empty** in the other 9% — a strictly tighter non-empty
interval never occurred.

So `waste_by` is a **falsification** channel, not a sharpening one: it kills particles whose
lots are ordered wrongly by freshness. That is real information, but it is information about
the *contrast* between lots, not about the freshness *level* — see the consequences below.

This is exact for this generative model, not an approximation: births assign one freshness
to a whole delivery and aging applies one decrement to the store, so a particle row holds
at most one distinct positive value per lot.

`gamma_p` / `gamma_q` (regularized incomplete gamma, series + continued fraction) and
`gamma_decrement_quantile` (monotone bisection) are added to `physics`. No new dependency.

### 3. One scoring path for both channels

`filter_step_unit` runs the same four stages for every channel; only the **resolution of
the evidence** changes:

| Stage | UPC | GSIN |
|-------|-----|------|
| Spoilage → `δ` interval | pooled `waste_tot` | intersection over per-lot `waste_by` |
| Sales feasibility | pooled `alive ≥ sales_tot` | per-lot `alive_ℓ ≥ sales_ℓ` |
| Cross-lot allocation | *(unobservable)* | `Multinomial(sales_by; lot_share)` |
| Sales removal | pooled WOR draw | per-lot WOR conditional on `sales_ℓ` |

Each GSIN term is a refinement of the corresponding UPC term on the same state.

### 4. Superseded primitives are removed, not muted

`p1_totals_loglik`, `loglik_waste_by_units`, and `loglik_waste_tot_after_sales_by` — together
with the `binom_pmf` and `iter_compositions` helpers they were the only callers of — are
**deleted** from `unit_ll`, not left exported as "research use only". A dead
`Binomial(waste; rem, dead/units)` on the public surface is a standing invitation to rewire
the filter back onto a waste model the shared-decrement physics does not support, and a
second definition of "the waste likelihood" defeats the unification this ADR is for.

`lib.rs` now re-exports the terms that replace them (`spoil_delta_interval`,
`spoil_delta_interval_by_lot`, `delta_interval_loglik`, `DeltaInterval`, `DELTA_ANY`).

The acceptance tests that pinned the old primitives (T-136's "P1 weight is deterministic",
"P1 takes no rng") pinned a *contract*, not a function name, so they were re-pointed at the
surviving terms rather than deleted:

| Retired test | Replacement | Contract preserved |
|--------------|-------------|--------------------|
| `p1_totals_loglik_impossible_sales_neg_inf` | `aggregate_totals_weight_rejects_infeasible_sales` | sales beyond the alive count rules out every particle |
| `p1_totals_loglik_signature_has_no_rng` | `production_likelihood_terms_take_no_rng` | no rng in any weight term |
| `p1_totals_loglik_deterministic_no_path_mc_in_body` | `production_likelihood_terms_have_no_path_mc_in_body` | no sampled sales path inside a weight |
| — | `superseded_binomial_waste_primitives_are_gone` | the removed names cannot come back |

`tests/test_age_likelihood.py` referenced the same model but is skipped at module level
(`T-TAU-RETIRE`), so nothing there depended on the removal.

## Consequences

- **Conservation becomes exact.** With zero-init plus observed arrivals, observed sales, and
  an adapted spoilage step, `alive_t = alive_{t-1} - waste_t - sales_t + arrivals_t` holds
  in every particle. Store count error is **0.000** for every rung with `scan_waste` on.
- **GSIN dominates UPC on every measured metric**, decisively on lot attribution (per-lot
  count MAE 0.000 vs 0.22–0.44) and marginally on freshness level and ESS.
- **The level gain is small for a structural reason, not a tuning one.** Both GSIN terms are
  *contrast* observations and are close to blind to the common freshness level:
  - `waste_by` never narrows the decrement interval (above); it only rejects mis-ordered
    particles.
  - `sales_by` is scored by `Multinomial(sales_by; lot_share)` with
    `lot_share_ℓ ∝ n_ℓ · f_ℓ^σ`. The `n_ℓ` are now known exactly under **every** mask, and
    the share vector is a ratio — **exactly** invariant to rescaling all `f` by a constant,
    and flattened further by `σ = 0.5` (a 3× freshness contrast yields only a 1.7× pick-rate
    contrast).

  The control experiment is in the data: on the *homogeneous* fleet, where lots arrive at
  near-identical freshness and there is no contrast to resolve, `P1 → F1` moves store
  mean-`f` MAE by **0.0000** (0.0848 → 0.0848). On the heterogeneous fleet it moves 0.1188 →
  0.1173. Compare the two *level* channels on the same rows: adding waste totals is
  `P0 → P1` = 0.1419 → 0.1188 (−16%), and adding pack date is `P1 → F2a` = 0.1188 → 0.0883
  (−26%). Level is bought on the `delivery_history` axis, which is exactly the orthogonality
  ADR 0133 intends — GSIN buys attribution.
- **P0 is the one rung whose count error is not pinned**, because it has no spoilage
  observation. Its bias moved from −8.4 (an artifact of the old fixed drain) to +10.1
  (unpenalized over-stocked particles: the sales feasibility gate is one-sided). The
  documented next upgrade is a demand-censoring term — scoring `P(D ≥ sales)` instead of
  `P(D = sales)` when a particle stocks out — which needs the calendar day on
  `filter_step_unit`.
- **Tests that asserted F1 ≠ P1 on single-lot fixtures were asserting the bug.** With one
  live lot the two channels observe identical evidence and must agree; the fixtures now
  drive to a genuine two-lot split, and a companion test pins the single-lot equality.
- **VOI rung separation needs a longer horizon than the old fixtures used.** Under ~12
  scored days every rung places identical case-rounded orders, so profits tie for reasons
  unrelated to the mask.
- **Closed-loop profit ordering is still not monotone in information** at some seeds — the
  `B-state` oracle also underperforms, which localizes the problem in the policy/cost
  tuning rather than the filter. Out of scope here; flagged for a controller ticket.
- Runtime is unchanged in order: 3–6 ms/day at N=200 for a 3–6 lot shelf. UPC got slightly
  faster (no `iter_compositions` over waste splits); GSIN got slower than its broken self
  only because it now does the work it was skipping.
