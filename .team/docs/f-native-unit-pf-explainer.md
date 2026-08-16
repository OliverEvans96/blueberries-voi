# F-native unit particle filter — explainer

Plain-language guide to how the **f-native** belief works in the C2 unit-level particle filter (ADR 0130). Terminology: **units** (individual clamshells on the display) and **lots** (delivery cohorts). The filter does not use “shelf” as a state variable.

---

## 1. Unit-level belief vs histogram on the wire

### Ground truth (simulator)

Each alive inventory item carries one scalar **freshness** `f ∈ [0, 1]`. A value of `0` means dead (sold or wasted). The simulator stores a flat vector of `f` values plus `lot_offsets` that segment that vector into variable-length **lots** as deliveries arrive.

### Filter (particles)

The particle filter keeps **N** hypotheses. Each particle is a full copy of the inventory grid:

- **L** virtual lot **slots** (fixed width)
- **U** unit slots per lot (default **15**)
- So each particle holds **N × (L×U)** scalar `f` values

Particles disagree about the exact `f` on every unit slot. That is the full belief; nothing coarser is stored inside the filter.

### Wire export (UI and policy)

Charts and the ordering policy do not consume raw particles. `belief_flat_from_unit_bank` **collapses** the particle bank onto a fixed **L×K** grid:

| Field | Meaning |
|-------|---------|
| `lot_counts[L]` | Expected alive units per virtual lot slot (weighted over particles) |
| `f_marginals[L×K]` | Per-slot **histogram** over freshness bins |
| `f_grid[K]` | Bin centers in `[0, 1]` |

So: **unit-level inside the filter**, **histogram per virtual lot slot on the wire**. The histogram is a projection for display and control, not the internal state.

---

## 2. Observations do not re-learn arrival cohort age

This follows the spirit of **FIL-11** and **ADR 0105** (arrival-only age), expressed in **f coordinates** instead of τ.

### Birth `f` is set once at delivery

When a delivery is observed (`arrivals > 0`), each particle appends a new cohort of **U** units, all sharing one birth freshness drawn from the knowledge scenario:

| Scenario | Birth rule |
|----------|------------|
| **F2** | Dirac from `age_at_receipt` → `f` via `age_to_f` |
| **F2a** | Gaussian on pack-date transit age → `f` |
| **P0** / default | Mixed shipment prior (no receipt age) |

That birth draw happens **once per delivery event**, not updated by later sales or waste observations.

### Daily observation update

On each day with observations:

1. **Predict:** apply gamma aging to every `f` on every particle (shared MOD-02 clock in freshness space).
2. **Reweight:** score each particle with the observation likelihood (see §3). Weights change; **`f` values on that particle are not edited by the likelihood**.
3. **Deliver (if any):** FIFO shift on the virtual grid — drop the oldest lot slot, append the new birth cohort (§4).
4. **Resample:** systematic resample copies **entire** particle freshness vectors from parents. Surviving particles inherit a complete `L×U` state; there is no backward smoothing or per-unit Bayesian edit from the likelihood.

So in-store sales and waste **inform which particles are plausible**, not **rewrite freshness at receipt**. The filter does not “learn” that an old cohort was younger than believed; it only kills or keeps whole-world hypotheses.

### P1 totals vs F1 per-lot

- **P1** (`sales_total` / `waste_total` only): one likelihood pools **all** alive units on the particle — “did this world produce these totals?”
- **F1** (`sales_by` present): the same unit grid is scored **per virtual lot slot** — “did lot slot ℓ sell this many?”

Factorization is in the **likelihood routing**, not in separate filter banks.

---

## 3. Observation routing

`filter_step_unit` chooses one scoring path per day (first match wins):

```
sales_by present?
  yes → loglik_sales_by_units (per-lot sequential picking kernel)
        then, if waste_by present → loglik_waste_by_units
        else if waste_tot present → loglik_waste_tot_after_sales_by
  no  → if sales_tot (and optional waste_tot) → p1_totals_loglik
        else → 0 (no score)
```

Important details:

- **`sales_by` dominates.** If per-lot sales are observed, totals-only scoring is **not** used, even when `sales_total` is also on the wire.
- **`waste_by` without `sales_by` is ignored** — there is no per-lot waste kernel on the totals-only path.
- **`waste_tot` after `sales_by`** conditions waste on the already-scored sales allocation for that particle.

Mixed **F1** scenarios (uneven `sales_by` with fixed totals) therefore produce a **different** posterior than **P1**, because the per-lot kernel breaks exchangeability across lot slots.

---

## 4. Virtual lot slots vs ground-truth lots

### Ground truth

Lots **grow** with each delivery. Each lot has a stable `lot_id` for logging and truth overlays. `lot_offsets` is variable length.

### Filter

The filter uses a **fixed** `L × U` grid — **virtual lot slots** indexed `0 … L−1`:

- Slot **0** = oldest delivery cohort still in the window  
- Slot **L−1** = newest  

On delivery, the filter **does not** push a new offset like the simulator. It:

1. **Drops** the `U` units in slot 0 (`drain(0..U)` — FIFO eviction of the oldest virtual cohort).
2. **Appends** `U` new units with birth `f` at the end (newest slot).

The filter state **does not track `lot_id`**. IDs on the wire (`lot_ids`, `live_lots`) exist for **truth overlay** and scenario masks only.

**U** is a capacity per cohort (default 15), not necessarily the physical case size. It bounds grid width; alive count per slot can be lower when units die.

---

## 5. Picking is not FIFO

Two different “ordering” ideas:

| Mechanism | Rule |
|-----------|------|
| **Virtual lot eviction on delivery** | **FIFO** — oldest slot cleared when a new delivery arrives |
| **Customer picking (sales)** | **Freshness-weighted sequential WOR** — each sale draws among alive units with weights from `f` (via τ), without replacement, one unit at a time |

Ground-truth `pick_units_f` and the unit likelihoods share that sequential WOR kernel. Old units can remain alive under fresh-biased picking; they are not forced out because they arrived first.

---

## 6. Forgetting old deliveries and choosing L

The filter keeps a **sliding window** of the last **L** delivery cohorts on a fixed grid. Cohorts that fall off slot 0 are **forgotten** — not merged, not smoothed backward.

### How to pick L

Choose **L** large enough that:

\[
L \geq \text{peak concurrent open cohorts with alive units}
\]

under your delivery cadence and spoilage dynamics (see MOD-13: without a date pull, 8–10 concurrent cohorts is plausible on a 2-day cadence). When the window is sized correctly, slot 0 should be **dead** (all `f = 0`) at the moment it is shifted off — the eviction is then harmless. If **L** is too small, the filter silently drops live units.

### Default `L = 10`

The production default was raised from `2` to **`10`** (`DEFAULT_L_DIM`) so typical MWF / 2-day episodes retain all materially alive cohorts without tuning. At default particle counts, unit-PF cost is on the order of **~3 ms per filter day** in Rust — well inside the studio **~500 ms** per-day interaction budget (physics + policy dominate at episode scale).

---

## 7. Distribution per lot

For one virtual lot slot **ℓ** on one particle:

- **U** scalar freshness values (many zero if units are dead)

Across **N** particles:

- An **empirical distribution** over those values, weighted by particle weights

On the wire:

- **`f_marginals[ℓ, :]`** — histogram with **K** bins over `[0, 1]`, row-normalized  
- **`lot_counts[ℓ]`** — expected alive count (units with `f > 0`)

So “distribution per lot” means: **per-slot histogram across particles**, built by binning alive units’ `f` values, not a parametric family.

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

Here \(n_\ell =\) `lot_counts[ℓ]` (expected alive units in virtual lot slot ℓ) and the expectation over \(f\) uses row `f_marginals[ℓ, ·]` against `f_grid`. Pipeline units use default birth freshness \(f_{\mathrm{pipe}}\) (typically 1.0).

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
- ADR 0130 — f-native `L×U` unit grid and unit particle filter  
- `crates/voi_core/src/unit_pf.rs` — `filter_step_unit`  
- `crates/voi_core/src/belief_flat.rs` — wire projection  
- `crates/voi_core/src/day_step.rs` — ground-truth unit physics  
