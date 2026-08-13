# 0105. Arrival-only effective age; production filter is counts-only with exact sequential-WOR weights

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: FIL-01 / FIL-02 / FIL-06 / FIL-10 / FIL-11 / FIL-13 (production settle)
GROUP: FIL
PROVENANCE: Oliver lock (vault handoff 2026-08-13) — arrival-only age + counts-only PF + exact WOR
TIER: 1
MILESTONE: Arrival-only count filter

## Context

Production RBPF (ADR 0091) samples lot counts, scores particles with Monte Carlo
`observation_loglik_mc` (ADR 0087), and updates per-lot arrival-age marginals with
`mean_field_update` under P1 totals (ADR 0090 / 0103 hot path). Count “dynamics” are a
±1 random walk, not `day_step` physics. FIL-11 Stage A evidence showed that under default
rungs P0/P1/F1, in-store sales/waste **do not** contract age posteriors in a trustworthy
way; F2/F2a pass mainly via receipt / ASN priors.

Oliver locked a product redesign: **stop learning ages in store**. Effective age is set at
lot birth from the rung’s arrival information and advances only with the shared MOD-02 /
`day_step` clock. The particle filter tracks **counts** only. Particle weights use the
exact sequential without-replacement composition PMF that matches `allocate_sales`
(plus binomial waste), evaluated once per particle-day with ages held fixed. Multinomial
(with-replacement) sales likelihood remains available for ablation behind filter config,
not as the production VOI default.

This is **not** “bootstrap is simpler than Rao–Blackwellisation.” RB age was dropped
because **in-store age learning was dropped**.

FIL-11 Stage A’s production gate therefore shifts from “age posterior contracts under
P1 sales” to **count calibration + arrival-prior injection** (F2a/F2 priors still supply
age information on those rungs).

## Decision

We will:

1. **Arrival-only ages:** At lot birth, set τ_in from the scenario arrival prior
   (F2 Dirac / F2a pack-date prior / cold Abdella). Advance physiological age only by the
   shared calendar / MOD-02 clock (`days_on_shelf` · Δτ). **No** production path calls
   `mean_field_update`, lot-map soft age Bayes, or any other in-store LL update on τ.
2. **Counts-only particle filter:** Particles carry lot counts (and weights). Age mass is
   birth/prior state clocked forward — not a filtered MF posterior rewritten each day.
3. **Default weights = exact sequential WOR:** Production particle weights use
   `log_p_sales_waste_given_ages` / `sequential_wor_*` (one evaluation per particle-day
   with fixed ages). Monte Carlo `observation_loglik_mc` is **not** the production weight
   default (diagnostic / legacy only).
4. **Optional multinomial:** A filter config knob (e.g. `sales_likelihood`) may select
   `multinomial` for ablation; production VOI / closed-loop defaults remain
   `exact_sequential_wor`.
5. **Count transitions match `day_step` physics:** Replace the ±1 random walk with a
   proposal / transition consistent with shared allocate/spoil kernels (not an independent
   count RW).
6. **Keep diagnostic APIs:** `mean_field_update`, `exact_joint_update`, MC LL, and bakeoff
   backends remain importable for experiments / Stage C history; they are **not** on the
   production closed-loop path (`RBPF.step` / `_rbpf_update` / day_driver / M2 / VOI CRN).
7. **Supersede production use** of ADRs **0046**, **0047**, **0051**, **0087** (MC as
   production weight default), **0091**, the production MF role of **0090**, **0103**
   (MF hot-path speedup as production strategy), and the **MF-sweep production clause** of
   **0104**. Sim-side WOR allocation (ADR **0030**) is unchanged.
8. **Add no new runtime dependencies.**

## Alternatives considered

- **Keep production mean-field age updates (ADR 0091) + MC weights** — rejected: Oliver
  locked arrival-only ages; Stage A shows in-store age learning is not trustworthy on
  P0/P1/F1 defaults; MF+MC dual path is an honesty mismatch.
- **Drop ages entirely from belief exports** — rejected: F2a/F2 still inject useful arrival
  information; controller / ENG-01 keep `(L,K)` / flat wire shape (ADR 0106).
- **Multinomial as production default** — rejected: sim allocation is WOR; production
  weights must match `allocate_sales`. Multinomial stays ablation-only.
- **Keep ±1 count RW until a later ticket** — rejected: fake counts poison ShelfBelief /
  VOI; this settle requires physics-consistent count transitions in the same rewrite.
- **Claim “bootstrap PF is simpler than RBPF” as the rationale** — rejected: the locked
  reason is dropped in-store age learning, not algorithmic taste.

## Consequences

- Production closed-loop and VOI paths become much cheaper (~1 WOR eval per particle-day
  vs `S·L·K` MF sweeps) and conceptually honest about what is learned.
- FIL-11 Stage A docs/harness must stop claiming in-store age contraction for P0/P1/F1;
  success on F2a/F2 is via **priors** (T-069).
- Guard tests that require `mean_field_update` on `_rbpf_update`, ban
  `sequential_wor_pmf` in particle weights, or lock `PRODUCTION_BACKEND == "mean_field"`
  as the age-MF settle must be updated **in T-068** (named supersessions in the spec).
- Cost: we permanently give up citing in-store age posterior learning from sales/waste on
  the production path; any future reopen needs a new ADR and Stage A evidence.
- Cost: count proposal design must stay coupled to `day_step` kernels — a second shadow
  dynamics would reintroduce the audit fiction this ADR removes.
