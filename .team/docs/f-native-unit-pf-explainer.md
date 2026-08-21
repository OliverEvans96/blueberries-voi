# F-native unit particle filter — explainer

Plain-language guide to how the **f-native** belief works in the C2 unit-level particle filter (ADR 0130). Terminology: **units** (individual clamshells on the display) and **lots** (delivery cohorts). The filter does not use “shelf” as a state variable.

---

## 1. Unit-level belief vs histogram on the wire

### Ground truth (simulator)

Each alive inventory item carries one scalar **freshness** `f ∈ [0, 1]`. A value of `0` means dead (sold or wasted). The simulator stores a flat vector of `f` values plus `lot_offsets` that segment that vector into variable-length **lots** as deliveries arrive.

### Filter (particles)

The particle filter keeps **N** hypotheses. Each particle is a full copy of the inventory grid:

- One **segment per observed delivery**, exactly as wide as that delivery (ADR 0137)
- So each particle holds one `f` per unit currently on the shelf, and every particle shares
  the same segmentation — arrival quantity is on the wire under every mask, so particles
  cannot disagree about *how many* units arrived, only about *how fresh* they were

Particles disagree about the exact `f` on every unit slot. That is the full belief; nothing coarser is stored inside the filter.

### Wire export (UI and policy)

Charts and the ordering policy do not consume raw particles. `belief_flat_from_unit_bank` **collapses** the particle bank onto a fixed **L×K** grid:

| Field | Meaning |
|-------|---------|
| `lot_counts[L]` | Expected alive units in each of the newest **L** lots (weighted over particles) |
| `f_marginals[L×K]` | Per-lot **histogram** over freshness bins |
| `f_grid[K]` | Bin centers in `[0, 1]` |

So: **unit-level inside the filter**, **histogram per lot on the wire**. The histogram is a projection for display and control, not the internal state.

---

## 2. Observations do not re-learn arrival cohort age

This follows the spirit of **FIL-11** and **ADR 0105** (arrival-only age), expressed in **f coordinates** instead of τ.

### Birth `f` is set once at delivery

When a delivery is observed (`arrivals > 0`), each particle appends a new cohort of exactly `arrivals` units, all sharing one birth freshness drawn from the knowledge scenario:

| Scenario | Birth rule |
|----------|------------|
| **F2** | Dirac from `age_at_receipt` → `f` via `age_to_f` |
| **F2a** | Gaussian on pack-date transit age → `f` |
| **P0** / default | Mixed shipment prior (no receipt age) |

That birth draw happens **once per delivery event**, not updated by later sales or waste observations.

### Daily observation update

On each day with observations:

1. **Predict + score spoilage together:** the day's waste observation pins the shared gamma decrement to an interval (§3); the particle is weighted by that interval's gamma mass and then aged by a decrement drawn *from within* it. This is the fully adapted proposal — the aging draw is conditioned on the observation rather than blind to it (ADR 0137).
2. **Reweight on sales:** score each particle with the sales likelihood (see §3), then remove the sold units by an unscored WOR draw (ADR 0135).
3. **Deliver (if any):** append one new segment, exactly as wide as the observed delivery (§4).
4. **Resample:** systematic resample copies **entire** particle freshness vectors from parents; there is no backward smoothing or per-unit Bayesian edit from the likelihood.
5. **Retire:** drop leading lots that hold no live unit in **any** particle.

So in-store sales and waste **inform which particles are plausible**, not **rewrite freshness at receipt**. The filter does not “learn” that an old cohort was younger than believed; it only kills or keeps whole-world hypotheses.

### P1 totals vs F1 per-lot

- **P1** (`sales_total` / `waste_total` only): one likelihood pools **all** alive units on the particle — “did this world produce these totals?”
- **F1** (`sales_by` present): the same unit grid is scored **per observed lot** — “did lot ℓ sell this many?”

Factorization is in the **likelihood routing**, not in separate filter banks.

---

## 3. Observation routing

`filter_step_unit` runs the **same four stages for every channel** (ADR 0137). Only the
*resolution* of the evidence changes:

| Stage | UPC (aggregate) | GSIN (lot-resolved) |
|-------|-----------------|---------------------|
| Spoilage → decrement interval | pooled `waste_tot` | intersection over per-lot `waste_by` |
| Sales feasibility | pooled `alive ≥ sales_tot` | per-lot `alive_ℓ ≥ sales_ℓ` |
| Cross-lot allocation | *(structurally unobservable)* | `Multinomial(sales_by; lot_share)` |
| Sales removal | one pooled WOR draw | per-lot WOR conditional on `sales_ℓ` |

### Why spoilage is an interval, not a coin flip

The whole store ages by **one** shared gamma decrement `δ` per day, so a unit with pre-aging
freshness `f > 0` spoils iff `f ≤ δ`. Observing that `w` units spoiled therefore does not
merely reweight the particle — it confines `δ` to `[g_w, g_{w+1})`, where `g_j` is the `j`-th
smallest live freshness in the observed group. The likelihood is that interval's gamma mass
(`delta_interval_loglik`); the state update draws `δ` from the gamma truncated to it.

Important details:

- **GSIN refines UPC; it never contradicts it.** UPC sees the store total and gets the pooled
  interval; GSIN sees `w_ℓ` per lot and gets `⋂_ℓ I_ℓ`. Every `δ` consistent with the per-lot
  counts is consistent with their sum, so `I_gsin ⊆ I_pooled` **always**.
- **Ties are informative.** A cohort born at one freshness spoils *together*, so some splits
  are unreachable rather than merely unlikely — a constraint only GSIN can see.
- **`sales_by` dominates.** If per-lot sales are observed, the pooled feasibility gate is not
  used, even when `sales_total` is also on the wire.
- **The weight is deterministic.** Randomness lives in the proposal (adapted aging, unscored
  WOR removal), never in the importance weight (ADR 0135).

The pre-0137 primitives (`p1_totals_loglik`, `loglik_waste_by_units`,
`loglik_waste_tot_after_sales_by`) scored waste as `Binomial(waste; rem, dead/units)`. That
had no derivation from the physics and has been **removed**, not merely bypassed.

Mixed **F1** scenarios (uneven `sales_by` with fixed totals) produce a **different** posterior
than **P1**, because the per-lot terms break exchangeability across lots. With only **one**
live lot the two channels observe identical evidence and correctly agree.

---

## 4. Lot segmentation

### Ground truth

Lots **grow** with each delivery. Each lot has a stable `lot_id` for logging and truth
overlays. `lot_offsets` is variable length.

### Filter

Since ADR 0137 the filter uses **the same shape**. `UnitParticleBank` carries
`lot_offsets` and `lot_ids` shared by every particle:

1. On delivery, append **one** segment of exactly `arrivals` units — no fixed-width eviction.
2. Under GSIN, `arrival_lot_ids` supplies real identities and `sales_by` / `waste_by` are
   matched to segments **by id** (`project_lot_map`), never by position. An observation that
   attributes a nonzero count to a lot the bank does not hold degrades that day to aggregate
   scoring rather than killing every particle. Under UPC the ids are internal and monotone.
3. Leading segments that hold no live unit in **any** particle are retired
   (`prune_dead_prefix`), so the row tracks the live window instead of growing forever.

Before ADR 0137 the filter guessed its own boundaries as fixed `units_per_lot` chunks and
drained one chunk per delivery. That partition was unrelated to truth's, which silently
returned `-inf` from the GSIN likelihood almost every day and inflated the row by
`arrivals − units_per_lot` per delivery.

`belief_flat_from_unit_bank` reads the bank's segmentation (newest **L** lots, oldest first,
zero-padded) rather than re-deriving one.

---

## 5. Picking is not FIFO

Two different “ordering” ideas:

| Mechanism | Rule |
|-----------|------|
| **Lot retirement** | **FIFO** — a leading lot is dropped once no particle believes any unit in it is alive |
| **Customer picking (sales)** | **Freshness-weighted sequential WOR** — each sale draws among alive units with weights from `f` (via τ), without replacement, one unit at a time |

Ground-truth `pick_units_f` and the unit likelihoods share that sequential WOR kernel. Old units can remain alive under fresh-biased picking; they are not forced out because they arrived first.

---

## 6. Forgetting old deliveries and choosing L

The filter itself keeps every lot that any particle still believes in, so nothing live is ever dropped. **L** now sizes only the **wire projection**: `belief_flat_from_unit_bank` exports the newest **L** lots, oldest first. Lots beyond that window are invisible to charts and the ordering policy — not merged, not smoothed backward.

### How to pick L

Choose **L** large enough that:

\[
L \geq \text{peak concurrent open cohorts with alive units}
\]

under your delivery cadence and spoilage dynamics (see MOD-13: without a date pull, 8–10 concurrent cohorts is plausible on a 2-day cadence). When the window is sized correctly, the oldest exported lot is already **dead** (all `f = 0`), so the projection loses nothing. If **L** is too small, the *wire* under-reports on-hand inventory even though the filter's own state is intact.

### Default `L = 10`

The production default was raised from `2` to **`10`** (`DEFAULT_L_DIM`) so typical MWF / 2-day episodes retain all materially alive cohorts without tuning. At default particle counts, unit-PF cost is on the order of **~3 ms per filter day** in Rust — well inside the studio **~500 ms** per-day interaction budget (physics + policy dominate at episode scale).

---

## 7. Distribution per lot

For one lot **ℓ** on one particle:

- One scalar freshness value per unit in that delivery (many zero if units are dead)

Across **N** particles:

- An **empirical distribution** over those values, weighted by particle weights

On the wire:

- **`f_marginals[ℓ, :]`** — histogram with **K** bins over `[0, 1]`, row-normalized  
- **`lot_counts[ℓ]`** — expected alive count (units with `f > 0`)

So “distribution per lot” means: **per-lot histogram across particles**, built by binning alive units’ `f` values, not a parametric family.

---

## 8. Effective inventory

Ordering policy (damped survival-weighted baseline, ADR 0058) needs a scalar **quality-weighted on-hand** \(\tilde I_t\), not raw case counts. Retiring τ / Weibull from production does **not** remove effective inventory — it replaces the old “integrate Weibull survival over τ bins” path with a **freshness-native** definition aligned to the same gamma aging used in truth and the filter.

### Quality weight \(w(f)\)

Per unit with freshness \(f\), define:

\[
w(f) = \frac{\mathbb{E}[T_{\mathrm{rem}} \mid f]}{T_{\mathrm{nom}}}
\]

- \(T_{\mathrm{rem}}(f)\): time until spoil (first day \(f \le 0\)) under production gamma aging (MOD-02 in freshness space).
- \(T_{\mathrm{nom}} = \mathbb{E}[T_{\mathrm{rem}} \mid f{=}1]\): pristine reference remaining life.

**Effective inventory** from the wire belief:

\[
\tilde I = \sum_{\ell=0}^{L-1} n_\ell \, \mathbb{E}[w(f) \mid \ell] + q_{\mathrm{pipeline}} \, f_{\mathrm{pipe}}
\]

Here \(n_\ell =\) `lot_counts[ℓ]` (expected alive units in lot ℓ) and the expectation over \(f\) uses row `f_marginals[ℓ, ·]` against `f_grid`. Pipeline units use default birth freshness \(f_{\mathrm{pipe}}\) (typically 1.0).

### Link to gamma aging

Production aging applies a gamma decrement each day (`apply_gamma_decrement` / `draw_gamma_decrement` in `physics.rs`):

\[
f_{t+1} = \max(f_t - \Delta_t, 0), \quad \Delta_t \sim \mathrm{Gamma}(\mathrm{shape}, \mathrm{scale} \times \mathrm{Q10})
\]

| Regime | \(w(f)\) | Intuition |
|--------|----------|-----------|
| **Deterministic** decrement \(\Delta \equiv \delta\) | \(w(f) = f\) | Remaining life \(T_{\mathrm{rem}} = f/\delta\); numerator and denominator both scale with \(1/\delta\) |
| **Stochastic gamma** | \(w(f) \approx f\) to first order; exact \(w(f_k)\) tabulatable | Jensen / first-passage effects mean \(\mathbb{E}[T_{\mathrm{rem}}\mid f] \neq f \cdot T_{\mathrm{nom}}\) in general |

When \(f\) is a **linear remaining-life fraction** (birth convention \(f = 1 - \tau/\eta_{\mathrm{ref}}\), with τ private inside shipment cache only), treating bin centers as \(w(f_k) = f_k\) counts **pristine-equivalent units** — the MVP shipped in ADR 0131.

### MVP on the wire (production)

The implementation uses **\(\mathbb{E}[f]\) weighting** — i.e. \(w(f_k) = f_k\) at bin centers:

\[
\tilde I = \sum_\ell n_\ell \sum_k p_{\ell k} f_k + q_{\mathrm{pipe}} f_{\mathrm{pipe}}
\]

| Layer | Function |
|-------|----------|
| Rust policy | `effective_inventory_f_belief` → input to `damped_sw_order_f_belief` |
| Python | `effective_inventory_f_belief(FreshShelfBelief, …)` |
| Web charts | `effectiveInventoryFromFlatBelief` |

Damped-SW compares \(\tilde I_t\) to protection demand; it does **not** re-integrate Weibull survival.

### Contrast with retired τ / Weibull path

| Retired (τ) | Kept (f-native MVP) |
|-------------|---------------------|
| `effective_inventory_belief` — Weibull × `tau_grid` / `age_marginals` | `effective_inventory_f_belief` — \(\mathbb{E}[f]\) × `f_marginals` |
| `damped_sw_order_belief` | `damped_sw_order_f_belief` |
| Mock `survivalWeightedInventory(lots, β)` on **belief** `effective_inv` | `effectiveInventoryFromFlatBelief` everywhere ordering / UI reads belief |
| Weibull survival chart + β slider in studio | Gamma / f spoilage story only |

Truth overlay `live_lots[].mean_f` is **not** \(\tilde I\); it is physics mean freshness per ground-truth lot for charts. Policy \(\tilde I\) always comes from **filter** `f_marginals`.

### Optional refinement (not MVP)

ADR 0131 documents a follow-up: precompute \(w(f_k)\) on `f_grid` from `(gamma_shape, gamma_scale, store Q10)` via Monte Carlo or first-passage approximation, and a horizon-aligned variant \(w_H(f)\) matched to damped-SW protection window \(H\). MVP \(w = f\) ships first because it matches deterministic-gamma physics and is already implemented.

---

## Related work (out of scope here)

Legacy **τ** / `age_marginals` wire fields belong to the pre–f-native count filter. Retiring τ from the production wire is **planned separately**; f-native exports `f_grid` / `f_marginals` only.

## References

- ADR 0105 — arrival-only age; no in-store age learning  
- ADR 0130 — f-native unit grid and unit particle filter  
- ADR 0135 — deterministic sales weight, unscored WOR removal  
- ADR 0137 — observed lot segmentation and exact spoilage likelihood  
- `crates/voi_core/src/unit_pf.rs` — `filter_step_unit`  
- `crates/voi_core/src/belief_flat.rs` — wire projection  
- `crates/voi_core/src/day_step.rs` — ground-truth unit physics  
