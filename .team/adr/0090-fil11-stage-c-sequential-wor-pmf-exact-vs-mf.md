# 0090. Filter age likelihood for FIL-11 Stage C (`sequential_wor_pmf`) — exact joint vs mean-field check

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-11 / FIL-04 evidence
GROUP: FIL
PROVENANCE: newly-raised; Stage C redesign after soft-LL tautology
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

**Numbering note:** Originally drafted as ADR 0086 on `exp/fil11-stage-c-mf`; renumbered to **0090** on merge into `main` because 0086–0089 already lock M1.5 RichObs / MC LL / generative Stage C / L fallback. This ADR is an **additive FIL-04 evidence** path, not a replacement for ADR 0088.

FIL-11=D requires Stage C as an exact comparison at small `L`/`K`, and that comparison is also the
**FIL-04 factorisation check**: does a mean-field age posterior match the exact joint well enough
that decisions (and VOI deltas) stay honest?

The current production soft observation path in `_rbpf_update` (powered picking / death terms with
Gaussian-style total matching — the M1 `sales_pow` / `waste_pow` stub) makes a “TV vs exact”
self-check **tautological**: the same soft likelihood drives both sides. That does not validate
generative agreement with the simulator, nor does it produce FIL-04 evidence.

MOD-08=A remains **simulate Wallenius; no density** for the simulator (`allocate_sales` sequential
without-replacement pick loop). The filter still needs a **named density** for Bayesian updates.
The integral Wallenius PMF is expensive; the sequential product over the same pick loop is the exact
simulation law as a PMF over compositions. Spoilage stays MOD-04=A (`death_prob_survival_ratio`)
after sales (MOD-12 order).

FIL-04 and FIL-12 are already ACCEPTED with ⚑ board overrides (joint / coarse joint). This ADR does
**not** flip those statuses. It locks the Stage C evidence machinery and freeze gates so a later
settle note can recommend a board move if mean-field fails (or if MF is good enough to revisit
tractability).

## Decision

We will:

1. Add a **named shared filter likelihood** `sequential_wor_pmf`: the sequential without-replacement
   product matching the `allocate_sales` pick loop (exact Wallenius *simulation* law as a PMF over
   compositions — **not** the integral Wallenius formula). Spoilage: independent Binomials with
   `death_prob_survival_ratio` (MOD-04=A) after sales (MOD-12).
2. For **P1 observations**: marginalize latent per-lot sales/waste compositions consistent with
   observed totals; if `sales_tot < sum(n)` then demand `D = sales_tot`, else treat as stockout
   (sold out the shelf).
3. Expose APIs in a new module `src/blueberries_voi/filter/age_likelihood.py`:
   - `log_p_sales_waste_given_ages(n, tau, sales_tot, waste_tot, params) -> float`
   - `exact_joint_update(n, prior_joint, y, params) -> posterior_joint` (flat `K^L`)
   - `mean_field_update(n, prior_marginals, y, params) -> posterior_marginals` shape `(L, K)` via
     **coordinate ascent** with posterior-mean picking/death plug-ins for other lots, max **5**
     sweeps, stop when max marginal total-variation change `< 1e-6`
4. Run **FIL-11 Stage C** as exact joint vs mean-field **induced joint** on **fixed count paths**
   (not a full RBPF-vs-RBPF bakeoff). Leave production MC `_rbpf_update` / RBPF unchanged; this ADR is evidence-only.
5. **Do not** flip ⚑ FIL-04 (ADR 0049) or FIL-12 (ADR 0057) statuses in this ADR; this ADR produces
   **evidence**. A settle note after green verifier may recommend a board move later.
6. Record that **MOD-08=A remains sim-only** (simulate Wallenius; no density in the simulator);
   the filter uses the named `sequential_wor_pmf` density for updates.

**Freeze gates (pass/fail for FIL-04 evidence):**

| Gate | Pass rule |
| --- | --- |
| Marginal TV (P1 base) | median `< 0.02`, p95 `< 0.05` |
| Joint TV (P1 base) | median `< 0.05`, **or** Stage 4 action agreement `≥ 95%` |
| Stress | LIFO + rich info with action flips ⇒ **fail MF for production** |

## Alternatives considered

- **Soft `sales_pow` / `waste_pow` Gaussian (M1 stub) as Stage C law** — rejected because comparison
  against an “exact” path that uses the same soft LL is tautological and does not check FIL-04.
- **Full Wallenius integral PMF** — rejected as expensive; the sequential product matches the
  simulator’s sampling law exactly and is the density we need for Stage C.
- **Multinomial with the same weights** — rejected unless `sequential_wor_pmf` proves numerically
  bad (MOD-08 already rejected multinomial for near-clear shelves).
- **Wiring mean-field into production RBPF before settle** — rejected as premature; this check is
  evidence-only until gates and a settle note say otherwise. M1.5 production uses MC LL + generative Stage C (ADRs 0087–0088).

## Consequences

**Easy:** a shared, named likelihood that can be unit-tested against hand grids; Stage C produces
explicit FIL-04 pass/fail tables (TV / KL / MI / decision Δ) without touching production RBPF.

**Hard / cost:** implementers must enumerate or otherwise marginalize latent sales/waste
compositions for P1 totals; coordinate-ascent MF is an approximation of the factorised posterior,
not a free lunch, and stress failures may force keeping joint (FIL-04=B) despite tractability
pressure.

**Locked in:** This evidence Stage C uses `sequential_wor_pmf` + exact joint vs MF on fixed counts;
production RBPF keeps M1.5 MC LL (ADR 0087) and generative Stage C (ADR 0088); ADR 0049 / 0057
statuses are unchanged by this work.

**Revisit when:** Stage C gates fail under P1 base or stress (recommend board reopen of FIL-04/12),
or `sequential_wor_pmf` is numerically intractable at the grids used — then reconsider multinomial
or integral Wallenius with a new ADR.

**Depends on:** `FIL-11`, `FIL-04`, `MOD-04`, `MOD-08`, `MOD-12`, T-006/T-007 machinery

**Milestone:** M1 — filter recovers truth from synthetic P1 data
