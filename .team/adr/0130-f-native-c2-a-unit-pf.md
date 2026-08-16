# 0130. Production filter is f-native C2 Algorithm A with unit-level freshness state

STATUS: PROPOSED
DATE: 2026-08-16
BOARD-ID: FIL / CTL / ENG-01
GROUP: FIL
PROVENANCE: T-C2-A — f-native C2-A production filter (timing-freshness bench evidence)
TIER: 1
MILESTONE: C2 Algorithm A — f-native production inference
SUPERSEDES (production semantics): [0105](./0105-arrival-only-age-counts-only-exact-wor.md),
[0106](./0106-shelfbelief-arrival-prior-age-exports.md), MOD-02 τ-clock in-store dynamics
(`q10_age_increment` + Weibull spoil on cohort τ)
RELATED: [0100](./0100-simulator-export-contract.md) (flat `L×K` wire shape),
[0123](./0123-lazy-obs-scenario-filter-caches.md) (lazy catch-up),
[0124](./0124-rust-wasm-set-obs-scenario.md), [0126](./0126-wasm-rich-filterobs-particle-belief.md)

## Context

Production `EngineSession` today runs a **counts + τ** particle filter (`ParticleBank`,
`filter_step`, exact sequential-WOR on lot counts with arrival-only τ clocked by MOD-02 /
`q10_age_increment`, Weibull spoil via `death_prob_survival_ratio`). `day_step` uses the same
cohort `{n, τ}` representation. Belief export flattens weighted counts and τ-binned
`age_marginals` on `tau_grid ∈ [0, 8]` days. Policy integrates Weibull survival over those τ
bins (`effective_inventory_belief`, `damped_sw_order_belief`).

Timing-freshness bench work (`bench_c2_a_totals_study`, `experiments/c2_a_totals_study.md`)
validated **C2 Algorithm A**: `N=200` particles × `L×U` unit freshness values `f ∈ [0, 1]`,
gamma aging, spoil at `f ≤ 0`, sequential picking kernel on alive units, and P1 totals
likelihood (`p1_totals_loglik`). At `L=20`, `U=15`: **11.6 ms/day** (p95 16 ms), mean_f MAE
**0.0014**, **100%** damped-SW order match vs f-truth controller — well inside the 500 ms/day
studio budget.

ADR 0105 correctly dropped in-store τ learning but kept a **cohort abstraction** mismatched
with unit-level picking physics and the bench kernel. ADR 0106 preserved `tau_grid` /
`age_marginals` field names while redefining rows as arrival-prior exports — still τ-centric
and still disconnected from the filter posterior under totals-only obs. Maintaining dual truth
(cohort `day_step` vs unit-f bench) guarantees drift between simulation, filter, policy, and
visualization.

Product direction (orchestrator lock): **one f coordinate end-to-end** — ground truth,
particle state, likelihood, belief wire, and policy all use unit freshness; **no Weibull** on
the production hot path.

## Decision

We will:

1. **Unified unit-f truth:** Replace cohort `{n, τ}` `day_step` with a fixed virtual grid
   `L × U` (`units_per_lot`, default **15**, configurable on `EngineSession.configure`). Each
   slot holds freshness `f ∈ [0, 1]`. Alive count per lot = `#{f > 0}`. Gamma decrement on `f`
   each day; units with `f ≤ 0` after aging are dead (no Weibull hazard). Picking uses
   `picking_weights_f(f, σ, uniform)` (monotone in `f`, e.g. `w_i ∝ f_i^σ`). Sales zero picked
   slots (`f = 0`); waste is units crossing `f ≤ 0` from the gamma step. Deliveries inject `U`
   units with `f` drawn from arrival metadata (F2 Dirac from `age_at_receipt`, F2a Gaussian on
   pack-date age, default shipments mix via `generate_arrival_age` / `shipments.rs` mapped once
   at birth). **No in-store Bayesian update of arrival cohort identity** — daily obs update the
   current unit layout only (FIL-11 / 0105 intent, in f coordinates).

2. **Production filter = C2 Algorithm A (`unit_pf`):** New modules `unit_ll.rs` (likelihoods) and
   `unit_pf.rs` (`UnitParticleBank`, `filter_step_unit`, systematic resample). Particle state is
   `freshness: Vec<Vec<f64>>` length `N × (L·U)` with lot offsets. **Observation router**
   (single entry point):
   - if `FilterObs.sales_by` is `Some` with valid length → per-lot
     `loglik_sales_by_units` (factorized `sequential_kernel_path_logprob` on alive units in each
     lot slice);
   - else if `FilterObs.sales_tot` is `Some` → `p1_totals_loglik` (sequential sales kernel +
     waste term aligned with day_step spoil accounting);
   - else → flat / support-only (P0). **Never invent `sales_by` from totals.** Mask logic stays
     in `mask_for` / Python parity; filter only sees `Some` fields.

3. **Belief wire (breaking rename, same flat `L×K` shape per ADR 0100):** Replace `tau_grid` /
   `age_marginals` with **`f_grid[K]`** (bin centers in `[0, 1]`) and **`f_marginals[L×K]`**
   (per-lot mass over freshness bins). `lot_counts[L]` keeps its role (expected alive units per
   slot). Export via `belief_flat_from_unit_bank` using **alive-only normalized** marginals for
   visualization. No dual τ/f wire in MVP.

4. **f-native policy:** Add `effective_inventory_f_belief` and `damped_sw_order_f_belief` using
   `E[f]` from `f_marginals × f_grid` (plus pipeline term with `f_pipeline_default`). Production
   `EngineSession::act` and `rollout.rs` use these helpers; remove Weibull integration from the
   production policy path.

5. **Session / VOI integration:** `advance_one` runs f-native `day_step` → `mask_for` →
   `filter_step_unit` → `belief_flat_from_unit_bank`. `set_obs_scenario` catch-up (ADR 0123)
   replays the same path on richest `RichDay` logs. `run_voi_crn_cell` uses the unit PF. Legacy
   `ParticleBank` / `filter_step` may remain behind `#[cfg(test)]` or a `legacy` feature until
   bakeoff cleanup; they are **not** on the production closed-loop path.

6. **Promote bench code:** Land `bench_c2_a_totals_study` (and obs-routing companion bench) from
   timing-freshness; register bins in `crates/voi_core/Cargo.toml`. Shared test truth helpers may
   live in `sim_truth.rs` (test-only).

7. **Supersede production role** of ADR **0105** (counts-only PF + exact WOR on counts + τ),
   ADR **0106** (τ `age_marginals` / arrival-prior semantics), and **MOD-02 τ-clock** spoil/aging
   on the hot path. **Keep:** six-rung obs ladder (0086), richest log + lazy catch-up (0123),
   flat `L×K` buffer contract (0100), `live_lots` as physics truth overlay (0126).

8. **Add no new runtime dependencies.**

## Alternatives considered

- **Keep ADR 0105 counts+τ PF and only change belief labels** — rejected: bench evidence and
  picking physics are unit-f; cohort τ + Weibull spoil cannot match sequential kernel truth;
  policy would still integrate the wrong survival curve.
- **Dual wire (τ and f fields during migration)** — rejected: studio, schema validators, and
  frontend would carry two semantics; orchestrator locked a breaking rename in one landing.
- **Algorithm B (histogram PF) as production default** — rejected: higher hist-TV shape fidelity
  does not justify cost at `L=20`; C2-A wins on mean_f, order match, and runtime (study
  recommendation). B remains research/bakeoff.
- **Invent `sales_by` from totals when only P1 is observed** — rejected: fabricates information;
  totals path (`p1_totals_loglik`) is the correct fallback; within-lot shape weakness is accepted
  and documented.
- **Keep Weibull in policy while filter uses f** — rejected: breaks unified truth; `E[f]` is the
  direct sufficient statistic for damped-SW under f-native inventory.
- **Variable U per lot from observed case size** — rejected for MVP: fixed virtual grid simplifies
  particle alignment, catch-up, and wire flattening; `U` default 15 matches benches (cap may tie
  to `case_size` later).

## Consequences

**Easy:** One coordinate system from `day_step` through studio heatmaps; bench timings and accuracy
gates transfer directly; obs routing reuses existing `FilterObs` / `mask_for` without ladder
changes; ADR 0123 catch-up protocol unchanged (replay richest log with per-rung masks).

**Hard / cost:** Breaking wire rename requires coordinated Python schema, golden fixtures, WASM
smoke, and frontend migration in the same milestone. `L×U` state is larger than cohort counts
(but study shows ample headroom). Totals-only observations cannot recover within-lot f shape —
sales_by path required for lot-resolved fidelity. Guard tests locked to ADR 0105/0106 τ semantics,
`tau_grid` / `age_marginals` keys, and Weibull policy must be updated in **T-C2-A** (named in
spec). `particle_filter.rs` remains for research/diagnostics but must not be called from
`session.rs` / `voi.rs` hot paths after landing.

**Locked in:** f-native unified truth; `filter_step_unit` + obs router; `f_grid` / `f_marginals`
wire; `units_per_lot` default 15; gamma spoil at `f ≤ 0`; no Weibull on production hot path.

**Revisit if:** measured session latency exceeds 500 ms/day at demo budgets after integration, or
product requires variable units-per-lot without virtual padding — both need new ADR + bench
evidence.
