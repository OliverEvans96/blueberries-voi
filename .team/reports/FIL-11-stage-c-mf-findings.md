# FIL-11 Stage C / FIL-04 — mean-field vs exact-joint findings

**Date:** 2026-08-12  
**Board:** FIL-11 Stage C (exact check) · FIL-04 factorisation evidence  
**ADR:** [0090](../adr/0090-fil11-stage-c-sequential-wor-pmf-exact-vs-mf.md) (ACCEPTED — evidence machinery; does not flip ⚑ ADR 0049 / 0057)  
**Spec:** [T-020](../specs/T-020.md)  
**Primary numbers:** [`experiments/fil11_stage_c_mf_result.md`](../../experiments/fil11_stage_c_mf_result.md)

---

## 1. Executive summary

**Verdict: PASS** against ADR 0090 freeze gates on P1 base + mild multi-day path.

| Gate summary (base set) | Value |
| --- | --- |
| Marginal TV median | **0.0050** (limit `< 0.02`) |
| Marginal TV p95 (of max) | **0.0105** (limit `< 0.05`) |
| Joint TV median | **0.0435** (limit `< 0.05`) |
| Stage 4 action agreement | **1.000** (≥ 0.95 alternate) |
| Stress fail (LIFO+rich + action flip) | **False** |

**Board recommendation (settle move, not an ADR status flip):**

- Reopen **FIL-04** toward **mean-field (C)** as the production factorisation choice.
- **Park** joint / coarse-joint machinery pressure from **FIL-12 / FIL-13** (treat FIL-13 option **B — mean-field** as the intended production path for age belief, not full joint).
- ⚑ **Do not flip ADR 0049 (FIL-04) or ADR 0057 (FIL-12) until Oliver confirms.** This report is evidence + recommendation only.

Production soft `_rbpf_update` was **not** changed; Stage C is a fixed-count posterior comparison under a named shared likelihood, not a full RBPF bakeoff.

---

## 2. Question / why this experiment

FIL-11 = D requires Stage C as an **exact comparison at small `L`/`K`**. That comparison is also the **FIL-04 factorisation check**: does a mean-field age posterior match the exact joint well enough that decisions (and survival-weighted stock / VOI-adjacent deltas) stay honest?

Earlier soft `sales_pow` / `waste_pow` Gaussian stubs made “TV vs exact” **tautological** — the same soft likelihood drove both sides. ADR 0090 replaced that with a named density so Stage C can produce real FIL-04 evidence.

**This is not:**

- A full RBPF-vs-RBPF bakeoff
- A claim that production RBPF already uses mean-field
- A flip of ⚑ board ADRs

**This is:** exact joint vs mean-field **induced joint**, on **fixed count paths**, under one shared likelihood — isolating **factorisation risk**.

---

## 3. Method

### Shared likelihood name

Filter density: **`sequential_wor_pmf`** — sequential without-replacement product matching `allocate_sales` (exact Wallenius *simulation* law as a PMF over compositions; **not** the integral Wallenius formula). Spoilage: independent Binomials via `death_prob_survival_ratio` (MOD-04=A) after sales (MOD-12). P1 observations marginalize latent per-lot sales/waste compositions consistent with observed totals.

Public APIs live in `blueberries_voi.filter.age_likelihood`:

- `log_p_sales_waste_given_ages`
- `exact_joint_update` — flat joint over `K^L`
- `mean_field_update` — coordinate ascent on marginals `(L, K)`, max **5** sweeps, stop when max marginal TV change `< 1e-6`; other lots use posterior-mean picking/death plug-ins

Induced joint for comparison: `∏_ℓ q_ℓ` from MF marginals, compared to the exact joint posterior.

### Stages (brief)

| Stage | What ran |
| --- | --- |
| **0** (pytest) | Hand-grid / unit checks in `tests/test_age_likelihood.py` (e.g. `L=2,K=2` exact posterior TV ≈ 0); not re-tabulated in the experiment note |
| **1** | One-step synthetic cases (`L∈{2,3}`, `K=6`): balanced mild σ, age-gap LIFO, near-dead cohort, large waste, weak info, L=3 P1 base, L=3 LIFO+rich stress |
| **2** | Multi-day open-loop sim count path (`L=3`, `K=6`, `σ=0.5`, `T≈12`); carry exact + MF posteriors as next priors with discrete age shift |
| **3** | Frozen RBPF-style count trajectory replay (`N=32` RBPF for counts only; joint/MF updates still via Stage C APIs) — see caveat in §5 |
| **4** | Decision metric embedded in every case: survival-weighted on-hand relative delta `|E_exact − E_MF| / stock`; myopic order agree on grid `{0, 8, 16, 24}` |

Runner: `uv run python experiments/fil11_stage_c_mf.py`.

### Freeze gates (ADR 0090)

| Gate | Pass rule |
| --- | --- |
| Marginal TV (P1 base) | median `< 0.02`, p95 `< 0.05` |
| Joint TV (P1 base) | median `< 0.05` **or** Stage 4 action agreement `≥ 95%` |
| Stress | LIFO + rich info **with action flips** ⇒ fail MF for production |

Base set used by the gate script: Stage 1 cases `{balanced_mild_sigma, L3_base_P1, weak_info}` **plus** all Stage 2 rows.

---

## 4. Results

All numeric tables below are copied from [`experiments/fil11_stage_c_mf_result.md`](../../experiments/fil11_stage_c_mf_result.md). Do not invent additional digits.

### 4.1 Stage 1 — one-step synthetic

| case | L | K | sigma | joint TV | marg TV max | marg KL max | max MI | SW rel delta | action agree |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| balanced_mild_sigma | 2 | 6 | 0.50 | 0.0455 | 0.0080 | 0.0002 | 0.0104 | 0.0014 | True |
| age_gap_lifo | 2 | 6 | 0.20 | 0.0977 | 0.0112 | 0.0004 | 0.0380 | 0.0001 | True |
| near_dead_cohort | 2 | 6 | 0.50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | True |
| large_waste | 2 | 6 | 0.50 | 0.0185 | 0.0012 | 0.0000 | 0.0019 | 0.0001 | True |
| weak_info | 2 | 6 | 0.50 | 0.0007 | 0.0002 | 0.0000 | 0.0000 | 0.0000 | True |
| L3_base_P1 | 3 | 6 | 0.50 | 0.0496 | 0.0051 | 0.0001 | 0.0031 | 0.0009 | True |
| L3_stress_lifo_rich | 3 | 6 | 0.20 | 0.1324 | 0.0136 | 0.0005 | 0.0190 | 0.0004 | True |

**Stress:** `L3_stress_lifo_rich` has the largest joint TV (**0.1324**) and elevated MI (**0.0190**), but **action still agrees** → stress fail flag stays **False**.

### 4.2 Base gates (ADR 0090 evaluation)

From the experiment note header:

- Marginal TV: median **0.0050**, p95 of max **0.0105** → **pass**
- Joint TV median **0.0435** → **pass** (`< 0.05`); action agree **1.000** would also satisfy the alternate clause
- Stress fail **False**

### 4.3 Marginal TV vs σ (`L=3`)

Same `(n, y)` as `L3_base_P1`-style totals (`n=[8,8,8]`, sales 9, waste 3):

| sigma | mean marginal TV |
| --- | --- |
| 0.2 | 0.0050 |
| 0.5 | 0.0051 |
| 1.0 | 0.0057 |

![Marginal TV vs sigma at L=3](../../figures/m1/fil11_stage_c_mf_tv_vs_sigma.png)

Figure path: [`../../figures/m1/fil11_stage_c_mf_tv_vs_sigma.png`](../../figures/m1/fil11_stage_c_mf_tv_vs_sigma.png)

Mean marginal TV stays ~**0.005–0.006** across the three σ values; factorisation error is not strongly σ-driven on this one-step P1 base point.

### 4.4 Stage 2 — multi-day accumulation (`L=3`, `K=6`, `σ=0.5`, `T≈12`)

| case | L | K | sigma | joint TV | marg TV max | marg KL max | max MI | SW rel delta | action agree |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| multiday_t0 | 3 | 6 | 0.50 | 0.0500 | 0.0064 | 0.0001 | 0.0057 | 0.0007 | True |
| multiday_t2 | 3 | 6 | 0.50 | 0.0495 | 0.0072 | 0.0001 | 0.0055 | 0.0005 | True |
| multiday_t4 | 3 | 6 | 0.50 | 0.0435 | 0.0107 | 0.0003 | 0.0051 | 0.0004 | True |
| multiday_t6 | 3 | 6 | 0.50 | 0.0353 | 0.0100 | 0.0003 | 0.0037 | 0.0003 | True |
| multiday_t8 | 3 | 6 | 0.50 | 0.0128 | 0.0060 | 0.0002 | 0.0015 | 0.0001 | True |
| multiday_t10 | 3 | 6 | 0.50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | True |

Joint TV **shrinks** over the mild path (0.05 → 0 by t10); action agree remains **True** throughout. (Only even-day / retained rows appear in the note; skipped infeasible `(n,y)` steps are not listed.)

### 4.5 Stage 3 — frozen RBPF count path replay

| case | L | K | sigma | joint TV | marg TV max | marg KL max | max MI | SW rel delta | action agree |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| particle_t0 | 3 | 6 | 0.50 | 0.0340 | 0.0050 | 0.0001 | 0.0019 | 0.0008 | True |
| particle_t1 | 3 | 6 | 0.50 | 0.0523 | 0.0054 | 0.0001 | 0.0044 | 0.0002 | True |
| particle_t2 | 3 | 6 | 0.50 | 0.0644 | 0.0150 | 0.0007 | 0.0069 | 0.0015 | True |
| particle_t3 | 3 | 6 | 0.50 | 0.0732 | 0.0233 | 0.0017 | 0.0079 | 0.0026 | True |
| particle_t4 | 3 | 6 | 0.50 | 0.0818 | 0.0254 | 0.0022 | 0.0072 | 0.0036 | True |
| particle_t5 | 3 | 6 | 0.50 | 0.0897 | 0.0321 | 0.0033 | 0.0092 | 0.0041 | True |
| particle_t6 | 3 | 6 | 0.50 | 0.0956 | 0.0383 | 0.0046 | 0.0105 | 0.0046 | True |
| particle_t7 | 3 | 6 | 0.50 | 0.1025 | 0.0393 | 0.0050 | 0.0107 | 0.0054 | True |
| particle_t8 | 3 | 6 | 0.50 | 0.1093 | 0.0406 | 0.0055 | 0.0108 | 0.0057 | True |
| particle_t9 | 3 | 6 | 0.50 | 0.1155 | 0.0421 | 0.0060 | 0.0109 | 0.0060 | True |

Unlike Stage 2, joint TV and marg TV **accumulate upward** here (joint TV 0.034 → 0.116; marg TV max 0.005 → 0.042). Action agree still **True** on all listed steps. This path is **not** in the ADR freeze base set; see §5.

### 4.6 Stage 4 — decision

Embedded in every row:

- **SW rel delta** = `|E_exact[SW] − E_MF[SW]| / stock` — stays ≤ **0.0014** on Stage 1 base/mild cases; ≤ **0.0007** on Stage 2; rises to **0.0060** by `particle_t9` but remains small vs stock
- **action agree** — **True** on every tabulated case, including stress and Stage 3

---

## 5. Interpretation

**Marginal TV** is the FIL-04-relevant quantity for per-lot age beliefs under mean-field. Base median **0.005** is an order of magnitude under the **0.02** gate: MF marginals track exact marginals tightly on the P1 mild set.

**Joint TV** measures distance between the exact joint and the **product of MF marginals**. Mild base joint median **0.0435** clears `< 0.05`. Stress joint TV **0.132** shows residual dependence the factorisation cannot capture when σ is small and observations are rich — consistent with non-zero **max MI** (stress **0.019**; age-gap LIFO **0.038**). That dependence did **not** flip the myopic order on `{0,8,16,24}` in these runs.

**Decision agreement** is the practical settle criterion when joint TV is borderline: here it is perfect on the tabulated grid. **SW rel delta** confirms expected survival-weighted stock is nearly interchangeable for myopic restocking.

**Stage 3 accumulation caveat:** the particle-path replay **does** show growing joint/marginal TV over time. Treat this as a **diagnostic**, not a freeze-gate failure:

1. Counts come from a production-style RBPF shell, but observations are a **scripted** sales/waste schedule (not the same open-loop sim law as Stage 2).
2. Exact and MF priors are each carried forward independently; small factorisation errors can **compound** without the Stage 2-style sim feedback that drove beliefs toward agreement.
3. Even at the worst listed Stage 3 step, action still agrees and SW rel delta stays ~**0.6%** of stock.

So: Stage 3 warns that long MF-only rollouts under mismatched obs may drift in joint TV; it does **not** overturn the ADR base/mild **PASS** or the Stage 4 action evidence on the freeze set.

---

## 6. Recommendation

### Explicit settle moves (pending Oliver)

1. **Accept FIL-11 Stage C / FIL-04 evidence as PASS** under ADR 0090 gates.
2. **Recommend FIL-04 → C (mean-field)** for production age factorisation.
3. **Park** further investment in joint / coarse-joint as the default production path (**FIL-12=B / FIL-13=E** pressure); align FIL-13 option **B (mean-field)** with this evidence when reopening board cards.
4. Keep **⚑ ADR 0049 / 0057 statuses unchanged** until Oliver confirms a board settle note.

### What not to claim

- That production `_rbpf_update` already implements `sequential_wor_pmf` or mean-field (it does **not**; soft stub untouched).
- That Stage C is a full particle-filter accuracy bakeoff (fixed-count joint vs MF only).
- That joint TV is always small (stress and Stage 3 show otherwise) — only that **gates + decisions** pass on the defined base/mild set.
- That VOI / multi-step planning is proven insensitive to residual MI (only myopic order on a coarse grid was checked).
- That ADR 0049 / 0057 are flipped (they are **not**).

### Follow-ons (out of this ticket)

- Wire `sequential_wor_pmf` + MF into production RBPF under a later ticket after board settle.
- If belief-sensitive VOI later fails under MF, revisit sliding window / joint with a new ADR — Stage 3 drift is a reason to watch, not to reverse the current gate PASS.

---

## 7. Artifacts

| Artifact | Path |
| --- | --- |
| Experiment runner | `experiments/fil11_stage_c_mf.py` |
| Result note (tables + verdict) | `experiments/fil11_stage_c_mf_result.md` |
| TV vs σ figure | `figures/m1/fil11_stage_c_mf_tv_vs_sigma.png` |
| Likelihood module | `src/blueberries_voi/filter/age_likelihood.py` |
| Tests (Stage 0 / units) | `tests/test_age_likelihood.py` |
| ADR (evidence lock) | `.team/adr/0090-fil11-stage-c-sequential-wor-pmf-exact-vs-mf.md` |
| Spec | `.team/specs/T-020.md` |
| This report | `.team/reports/FIL-11-stage-c-mf-findings.md` |

**Re-run:**

```bash
uv run python experiments/fil11_stage_c_mf.py
uv run pytest tests/test_age_likelihood.py
```
