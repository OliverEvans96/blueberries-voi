# T-C2-A f-native C2 Algorithm A production filter

## Context

Ship **C2 Algorithm A** as the production inference engine for `EngineSession`, VOI, WASM studio,
and PyO3 wire: unit-level freshness `f ∈ [0, 1]` on a virtual `L×U` grid, gamma aging, spoil at
`f ≤ 0`, observation routing (per-lot `sales_by` when present, else P1 totals), f-marginal belief
export, and f-native damped-SW policy. Replaces the counts+τ / Weibull production stack per ADR
[0130](../adr/0130-f-native-c2-a-unit-pf.md). Evidence: `experiments/c2_a_totals_study.md`.

Concurrency plan: [feature-c2-a-f-native-concurrency.yaml](../plans/feature-c2-a-f-native-concurrency.yaml).

## Acceptance criteria

### AC-daystep — f-native ground truth (`day_step`)

- [ ] `day_step` (or successor `UnitDayStepIn`/`Out`) advances `L×U` freshness with gamma
      decrement parameterized by store temperature / Q10 (no `q10_age_increment` τ bump, no
      `death_prob_survival_ratio` Weibull spoil on the production path).
- [ ] Units with `f ≤ 0` after aging are dead; alive count per lot equals `#{f > 0}` in that lot's
      segment.
- [ ] Sales allocation calls `picking_weights_f` on alive units, zeros picked slots (`f = 0`), and
      `RichDay` / `DayStepOut` aggregates (`sales_total`, `sales_by`, `waste_total`, `waste_by`)
      match summed unit events.
- [ ] Delivery injects `units_per_lot` (default **15**) units with `f` from arrival prior: F2 Dirac
      from `age_at_receipt`, F2a Gaussian on pack-date age, default via `generate_arrival_age` /
      `shipments.rs`.
- [ ] `cargo test -p voi_core day_step` (and qa shard `tests/test_unit_pf.py` physics fixtures)
      pass with conservation of sales/waste totals on scripted seeds.

### AC-unit-pf — `unit_pf` filter and observation router

- [ ] `crates/voi_core/src/unit_ll.rs` exports `sequential_kernel_path_logprob`,
      `p1_totals_loglik`, and `loglik_sales_by_units`; `unit_pf.rs` exports `UnitParticleBank`,
      `filter_step_unit`, and uses production `systematic_resample` (not bench multinomial).
- [ ] When `FilterObs.sales_by` is `Some` with length matching live lots, `filter_step_unit` scores
      via per-lot `loglik_sales_by_units` (F1 / F1s / F2 paths); when only `sales_tot` is `Some`,
      scores via `p1_totals_loglik`; P1 mask never calls the sales_by path; F1 mask never requires
      totals-only joint LL alone.
- [ ] Filter never synthesizes `sales_by` from totals; absent fields remain `None` per `mask_for`.
- [ ] Totals @ `L=20`, `N=200`, `U=15`: `mean_f` MAE &lt; **0.02** and **100%** damped-SW order
      match vs f-truth controller on scripted seeds (`tests/test_unit_pf.py` or bench harness).
- [ ] `cargo run -p voi_core --release --bin bench_c2_a_totals_study` reports `L=20` mean filter
      day &lt; **500 ms** (study baseline ~11.6 ms).

### AC-belief — `f_grid` / `f_marginals` wire

- [ ] `belief_flat_from_unit_bank` produces flat belief with `f_grid[K]` ∈ `[0, 1]`, `f_marginals`
      length `L×K` (row-major), and `lot_counts[L]`; rows are alive-only normalized marginals.
- [ ] Snapshot / DayDelta `belief` from `EngineSession` contains `f_grid` and `f_marginals` (not
      `tau_grid` / `age_marginals`).
- [ ] `cargo test -p voi_core belief_flat` passes; exported `K` matches session `k_dim`.

### AC-policy — f-native inventory and ordering

- [ ] `effective_inventory_f_belief(lot_counts, f_marginals, f_grid, pending, f_pipeline_default)`
      equals `Σ_lot lot_count_l × Σ_bin f_marginal[l,b] × f_grid[b]` plus pipeline term.
- [ ] `damped_sw_order_f_belief` mirrors `damped_sw_order_belief` structure but uses f-belief
      helpers; `rollout.rs` calls f-native `day_step` and f-belief export.
- [ ] Production `session.rs` `act` path does not call `weibull_survival` or
      `effective_inventory_belief` (τ/Weibull).

### AC-session — `EngineSession`, catch-up, and VOI

- [ ] `advance_one`: f-native `day_step` → `mask_for(obs_scenario)` → `filter_step_unit` →
      `belief_flat_from_unit_bank`; `configure` accepts `units_per_lot` (default 15).
- [ ] `set_obs_scenario` catch-up (ADR 0123) replays richest `RichDay` log through the same unit-PF
      path; F2 vs P1 snapshots differ in `belief.f_marginals` while `live_lots` stay identical.
- [ ] `run_voi_crn_cell` uses `UnitParticleBank` / `filter_step_unit` (not `ParticleBank` /
      `filter_step`).
- [ ] `cargo test -p voi_core session` and `cargo test -p voi_core voi` pass.

### AC-python-wire — Python schema and PyO3 fidelity

- [ ] `src/blueberries_voi/simulator/schema.py` `_FLAT_BELIEF_KEYS` is
      `{lot_counts, f_marginals, f_grid, L, K}`; `validate_flat_belief` enforces lengths.
- [ ] `src/blueberries_voi/filter/belief.py` and `simulator/belief.py` flatten/unflatten f-fields;
      `tests/test_rust_session_wire.py` and `tests/test_simulator_schema.py` pass with regenerated
      goldens under `tests/fixtures/simulator/`.
- [ ] `BLUEBERRIES_VOI_BACKEND=rust` `EngineSession` init/step payloads validate under the new
      schema; `scripts/smoke_wasm.mjs` succeeds after WASM rebuild.

### AC-frontend — Studio f-marginals

- [ ] `web/src/engine/types.ts` `FlatBelief` uses `f_grid` / `f_marginals`; `projector.ts` maps
      belief heatmap axes to freshness `[0, 1]` (“Freshness × count”).
- [ ] `inventoryTarget.ts` bands use `E[f]` from f-marginals (not τ-day Weibull bands).
- [ ] `cd web && npm test` passes (`projector.test.ts`, `inventoryTarget.test.ts`, mock adapter).

### AC-bench-cleanup — benches and legacy hot-path removal

- [ ] `bench_c2_a_totals_study` and `experiments/c2_a_totals_study.md` live on main branch;
      `[[bin]]` entries registered in `crates/voi_core/Cargo.toml`.
- [ ] `rg 'death_prob_survival_ratio|weibull_survival' crates/voi_core/src/session.rs
      crates/voi_core/src/voi.rs crates/voi_core/src/day_step.rs` returns no matches (Weibull may
      remain in `physics.rs` for research / `#[cfg(test)]` only).
- [ ] `particle_filter::filter_step` is not referenced from `session.rs` or `voi.rs` production
      paths.

### AC-guards — supersede ADR 0105/0106 τ-wire and production-PF guards

- [ ] Qa updates or gates, in this ticket, tests that still require `tau_grid` / `age_marginals` on
      the production wire or ADR 0105 counts+τ production identity, including at minimum:
      `tests/test_rust_session_wire.py`, `tests/test_simulator_schema.py`,
      `tests/fixtures/simulator/*.json`, `tests/test_belief_arrival_priors.py`,
      `tests/test_damped_sw_policy.py` (production f-policy path), and `crates/voi_core` session
      tests asserting `age_marginals` / `tau_grid` keys — so verifier is not blocked by stale bans.
- [ ] New module paths `unit_pf`, `unit_ll` are allowed on the production hot path (no guard test
      fails merely because `session.rs` imports them).

## Out of scope

- Algorithm B (histogram PF) as production default; sales_by heuristic from `bench_c2_accuracy`
  (not the unit sequential kernel)
- Dual τ/f wire or parallel studio schema during migration
- Variable `units_per_lot` per lot (fixed virtual grid in MVP)
- Deleting research Python `filter/particle/` or bakeoff modules
- Editing live `.github/workflows/` (human syncs CI drafts)
- Bit-identical CRN parity with legacy NumPy counts+τ filter

## Interfaces

| Surface | Contract |
|---------|----------|
| `day_step` / `UnitDayStepIn` | `freshness: Vec<f64>` length `L×U`, `lot_offsets`, gamma step, `picking_weights_f`, delivery `f` birth |
| `physics::picking_weights_f` | `(f: &[f64], sigma, uniform) → Vec<f64>` normalized picking weights |
| `unit_ll::p1_totals_loglik` | `(units, sales_tot, waste_tot?, params) → f64` log-likelihood |
| `unit_ll::loglik_sales_by_units` | Per-lot slices → sum of `sequential_kernel_path_logprob` |
| `unit_pf::UnitParticleBank` | `{ weights: Vec<f64>, freshness: Vec<Vec<f64>> }`, shape `N × (L·U)` |
| `unit_pf::filter_step_unit` | `(bank, obs: &FilterObs, params, rng) → ()` applies router + resample |
| `belief_flat::belief_flat_from_unit_bank` | → `{ lot_counts, f_marginals, f_grid, L, K }` |
| `policy::effective_inventory_f_belief` | `E[f]`-weighted on-hand + pipeline |
| `policy::damped_sw_order_f_belief` | Damped SW from f-belief |
| `EngineSession::configure` | `units_per_lot: usize` default `15` |
| `simulator/schema._FLAT_BELIEF_KEYS` | `f_grid`, `f_marginals`, `lot_counts`, `L`, `K` |
| `web FlatBelief` | TypeScript mirror of f-wire |

Observation router (normative):

| Scenario | `sales_by` | `waste_by` | LL path |
|----------|------------|------------|---------|
| P0 | — | — | flat / support-only |
| P1 | — | `waste_tot` optional | `p1_totals_loglik` |
| F1 | yes | — (totals waste) | `loglik_sales_by_units` + totals waste if `waste_tot` |
| F1s | yes | yes | `loglik_sales_by_units` + per-lot waste on remainders |
| F2 / F2a | maps + receipt meta | maps | sales_by + birth `f` on arrivals |

## Open questions

- [ ] None — ADR 0130 locks unified f truth, breaking wire rename, and obs routing table; human
      lands timing-freshness bench merge at integrate.
