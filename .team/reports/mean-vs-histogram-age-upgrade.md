# Mean vs histogram age plug-in — decision note + timing

**Date:** 2026-08-13  
**Status:** Decision consideration + measured (combined-upgrade upper bound)  
**Tip timed:** `main` @ `2eb2947e7936b6ba39e256a4a06da9870f23df67`  
**Prior compute baseline:** [timing-study-arrival-only-filter.md](./timing-study-arrival-only-filter.md)  
**Filter settle:** ADR [0105](../adr/0105-arrival-only-age-counts-only-exact-wor.md) + [0106](../adr/0106-shelfbelief-arrival-prior-age-exports.md)  
**Raw JSON (not committed):** `/tmp/timing_histogram_upgrade_k_sweep.json`  
**Harness (not committed):** `/tmp/timing_histogram_upgrade_k_sweep.py`

---

## 1. Decision under consideration

Under arrival-only ages (ADR 0105), each lot carries a **frozen birth prior** over arrival age
`τ_in` on a length-`K` grid. That mass is **not** updated from in-store sales/waste; only
`days_on_shelf` advances (MOD-02 clock).

Belief **storage and export** already use the histogram (`age_post` / `ShelfBelief.age_marginals`).
The open question is whether **consumers** of age should keep collapsing to a single number
(`E[τ]`) or use the full distribution when they evaluate nonlinear physics.

### Two upgrade sites (considered **together**)

| Site | Today | Proposed upgrade | Cost shape |
|------|--------|------------------|------------|
| **A. Filter WOR + count transitions** | Collapse histogram → mean physiological age; score `log_p_sales_waste_given_ages` and step allocate/spoil once | Average (or mix) picking / death / WOR over the `K` bins | ~`K×` on that hot path |
| **B. Controller rollouts** | Collapse `age_marginals` → mean `τ`, run `day_step`, rebuild belief as Dirac | Sample or mix ages from the histogram across rollout physics | ~`K×` if full mix; ~`1×` if sample-once per lot per path |

**Out of scope for this note (already correct or unrelated):**

- `effective_inventory` / `survival_weighted_on_hand` — already uses `E[S(τ)]` over the histogram, not `S(E[τ])`.
- Simulator ground truth — one true `τ` per lot (not a belief).
- Adding process noise or in-store age Bayes — rejected for this consideration; we are **not** introducing more age uncertainty, only using the existing prior more honestly.

We did **not** ablate A vs B alone. All timing below is **both upgrades together** under a naive
full-mix `K×` stub (upper bound).

---

## 2. Why accuracy / outcomes could improve

Hazard, survival, and picking weights are **nonlinear** in age. Plugging in the mean commits a
Jensen gap:

\[
h(\mathbb{E}[\tau]) \neq \mathbb{E}[h(\tau)], \qquad
S(\mathbb{E}[\tau]) \neq \mathbb{E}[S(\tau)].
\]

### Filter (site A)

- **Weights:** WOR + binomial waste likelihoods see “everyone is average age.” Broad priors
  (cold Abdella, F2a) put real mass on older bins that spoil and get picked differently; the mean
  understates that.
- **Transitions:** allocate/spoil paths are too middle-of-the-road; particle count clouds are
  slightly mis-weighted.
- **Effect size:** small on F2 (near-Dirac); larger on cold / F2a and at high Weibull `β` (steeper
  hazard). Stage A already showed P0/P1 do not learn age from sales — this upgrade does **not**
  change that; it only scores counts given a better use of the **birth** prior.

### Rollouts / decisions (site B)

- Today rollouts destroy spread (mean → Dirac). Planned waste and sales mix look **overconfident**.
- Histogram-aware rollouts restore age-driven outcome variance → better risk-sensitive planning and
  more honest VOI when policies plan via nested rollouts.
- Gate 0b already showed that base-stock targets from a **prior-mean age** differ from a true age
  **mix**; the same gap appears inside rollout physics when the controller collapses the belief.

### What would *not* improve

- Reported `SD(τ_in)` on the belief wire (already the birth prior).
- Identification of age from storewide totals (still arrival-only).
- Within-lot frailty (MOD-05) — a different model change.

---

## 3. Timing method

| Item | Choice |
|------|--------|
| Machine | Same class as prior study (i7-8550U, 8 logical CPUs, Linux, Python 3.11.13) |
| Filter stub | From a fixed pre-state, call full `_particle_filter_update` **K** times (conservative ≈`K×` on entire update, not only the age collapse) |
| Rollout stub | Each rollout `day_step` repeated **K** times (last kept) |
| Combined | Both stubs on |
| `K` sweep | `{4, 8, 16}` (production default `K≈8`) |
| Interactive | `DEMO_BUDGETS` (`N=200`, `H=7`, paths=`2`), `act(policy="rollout")`, `L=3` |
| VOI smoke | 7 scenarios, burn=1, score=2, `filter_n=16`, `H=2`, paths=1 |
| VOI medium-lite | 7 scenarios, burn=3, score=5, `filter_n=32`, `H=7`, paths=2 |
| Pyodide | Assumed **5×** native (same caveat as prior study) |
| Scaling | Medium-lite measured ratio applied to prior study’s ~1208 s/cell and ~67 h one-box |

**Caveats:** naive full-mix is an **upper bound**. Smarter per-lot `E[f(τ)]` can be cheaper than
`K` full PF updates. **Sample-once** rollouts are ≈`1×` on site B. Joint age integration over lots
would be `K^L` (not modeled). VOI headline ETAs remain extrapolations, not a full 200-cell run.

Microbench sanity (real WOR / `day_step` looped over bins): ratios ≈ **3.7× / 7.7× / 19–22×** for
`K ∈ {4,8,16}` — tracks `K` as expected.

---

## 4. Findings — interactive / Pyodide

Baseline attribution (re-measured): **filter ~92%**, rollout `day_step` ~3–4%, other ~4%.
Filter histogramization dominates; rollout `K×` is a small add-on on this path.

| K | Baseline native | Both upgrades | Cost factor | Pyodide×5 base → both | vs &lt;1 s/day |
|---|---------------:|--------------:|------------:|----------------------:|----------------|
| 4 | 170 ms | 698 ms | ~4.1× | 849 → **3492 ms** | **FAIL** |
| 8 | 183 ms | 1375 ms | ~7.5× | 913 → **6873 ms** | **FAIL** |
| 16 | 161 ms | 2913 ms | ~18× | 804 → **14564 ms** | **FAIL** |

Prior study’s 132 ms native day used an older tip / smaller `L`; this re-run is labeled separately
but the **budget conclusion** is the same: baseline still passes at 5×; **combined full-mix does not**
at any swept `K`.

---

## 5. Findings — offline VOI

### Smoke (measured)

| K | Baseline | Both upgrades | Cost factor |
|---|--------:|--------------:|------------:|
| 4 | 0.71 s | 2.54 s | ~3.6× |
| 8 | 0.70 s | 5.69 s | ~8.1× |
| 16 | 0.72 s | 9.88 s | ~13.8× |

### Medium-lite (measured) → scaled to prior headline grid

Attribution: **filter ~46%**, **rollout ~39%**, other ~15% — both sites matter for VOI.

| K | Lite cell | Cost factor | Prior prod cell (~20 min) | Prior one-box (~67 h) |
|---|----------:|------------:|--------------------------:|----------------------:|
| 4 | 13.6 → 45.3 s | ~3.3× | → **~67 min** | → **~223 h** |
| 8 | 13.1 → 86.2 s | ~6.6× | → **~2.2 h** | → **~441 h** |
| 16 | 15.6 → 197 s | ~12.6× | → **~4.2 h** | → **~845 h** |

---

## 6. Recommendation

**Do not ship naive full-mix `K×` on both sites** as the production default.

| Path | Verdict |
|------|---------|
| **Browser / ENG-01 demo** | Combined full-mix at `K=8` leaves the **&lt;1 s/day** budget by a large margin (~7× native; ~7 s @ Pyodide×5). Filter alone is enough to break it. |
| **Offline VOI** | Expect ~**6–7×** wall at `K=8` under the same stub (~67 h → ~**440 h** one-box). Affordable only with fanout + cheaper age integration. |

### Preferable realizations (same accuracy intent, better cost)

1. **Rollouts (site B):** sample **once** (or few times) per lot per path from the birth histogram — restores outcome uncertainty at ~`1×` physics cost.
2. **Filter (site A):** per-lot `E[f(τ)]` for picking weights / death probs (and optionally likelihood), vectorized over `K`, **not** `K` full `_particle_filter_update` passes. Avoid joint `K^L` unless `L` is tiny.
3. **Demo path:** keep `N≤200`; do not enable full-mix histogram scoring in interactive `act(rollout)`.
4. **Keep** `effective_inventory`’s histogram survival average; optionally align pipeline weight with the cold arrival prior instead of a flat grid mean (separate, cheap).

### Accuracy ROI vs cost

| Change | Accuracy / decision gain | Cost |
|--------|--------------------------|------|
| Full-mix A + B (this study) | Honest nonlinear use of birth prior in filter + rollouts | **~K×** total on both streams — **too expensive** for demo; heavy for VOI |
| Sample-once B only | Most of the **decision/VOI** honesty (outcome variance in plans) | ~baseline |
| Cheap `E[f(τ)]` A | Most of the **filter weight** honesty without `K` PF passes | small constant ×`K` on thin kernels |
| A + sample-once B | Best accuracy/cost compromise | likely **&lt;2×** if implemented carefully (not measured here) |

---

## 7. Bottom line

Belief already stores a frozen age histogram. The decision is whether WOR/transitions and rollouts
should keep using the **mean** or the **distribution**. Full-mix use of the histogram on **both**
sites improves honesty of particle weights and planned outcomes (especially under broad arrival
priors and high `β`), but a naive `K×` implementation is **runtime-prohibitive** for the Pyodide
demo and multiplies VOI wall time by roughly `K`. Prefer sample-once rollouts and cheap per-lot
expectations for the filter if that honesty is pursued.
