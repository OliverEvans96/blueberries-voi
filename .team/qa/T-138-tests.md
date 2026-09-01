# T-138 qa RED map (Stage A heterogeneous arrivals)

Proved with `cargo test -p voi_core <filter>` on branch `team/T-138/qa-arrivals-implement`
(parent `team/T-138/architect` @ 23e66ae). No production code changed.

## Coverage of acceptance criteria

- **AC-1** → `t134_arrival_f.rs::model_params_arrival_dispersion_sd_distinct_from_f2a_transit` — currently failing: `params.rs` lacks `arrival_dispersion_sd` field
- **AC-2** → `t134_arrival_f.rs::birth_f_units_sd_zero_yields_uniform_copies` — currently failing: `shipments.rs` lacks `pub fn birth_f_units`
- **AC-3** → `t134_arrival_f.rs::birth_f_units_positive_sd_spreads_and_centers` — currently failing: `birth_f_units` not exported / spread law absent
- **AC-4** → `day_step.rs::t138_arrival_dispersion::delivery_calls_birth_f_units_not_uniform_vec` — currently failing: delivery still uses `vec![birth_f; total_units]`, no `birth_f_units` / `:birth`
- **AC-4** → `day_step.rs::t138_arrival_dispersion::delivery_appends_distinct_freshness_when_dispersion_enabled` — currently failing: `arrival_dispersion_sd` missing; appended segment is lot-uniform
- **AC-5** → `t134_arrival_f.rs::filter_birth_uses_birth_f_units_per_particle` — currently failing: `unit_pf.rs` uniform-fills with `extend(vec![birth; upl])`, no `birth_f_units`
- **AC-6** → `t134_arrival_f.rs::filter_particles_differ_within_lot_under_dispersion` — currently failing: within-lot segment remains uniform (guard also requires `arrival_dispersion_sd` + `birth_f_units`)
- **AC-7** → `t134_arrival_f.rs::stream_birth_wired_in_production_paths` — currently failing: `session.rs` / `voi.rs` / `rollout.rs` / `alpha_tune.rs` lack `:birth` / `STREAM_BIRTH`
- **AC-9** → `t134_arrival_f.rs::rollout_unit_state_from_f_belief_samples_per_unit` — currently failing: `rollout.rs` still uses `repeat_n(e_f.max(0.0), alive)` and no `:birth` draws
- **AC-10** → `unit_pf_ac.rs::lgtin_waste_can_strictly_narrow_under_within_lot_dispersion` — currently failing: guard requires `birth_f_units` before dispersion-backed narrowing is in scope
- **AC-11** → `unit_pf_ac.rs::lgtin_waste_uniform_freshness_never_strictly_narrows` — **passing** (lot-uniform regression guard; ADR 0137 limit recovered)
- **AC-13** → `unit_pf_ac.rs::production_likelihood_terms_take_no_rng` — currently failing: architect tip lacks `delta_interval_loglik` / `spoil_delta_interval` exports in `unit_ll.rs` (0137 baseline not on this branch)
- **AC-13** → `unit_pf_ac.rs::superseded_binomial_waste_primitives_are_gone` — **passing** on architect tip
- **AC-15** → `t134_arrival_f.rs::dispersion_sd_positive_enables_non_uniform_birth_path` — currently failing: lot-uniform birth paths remain in `day_step.rs` / `unit_pf.rs`

## Not covered by tests (this qa shard)

- **AC-8** (`:birth` in Python `rng.py` + `tests/test_rng.py` parity) — owned by **impl-crn-streams** shard per plan; verify on that worktree
- **AC-12** (`lgtin_upc_diag` homogeneous `count_bias` ≤ 0.05) — owned by **impl-diag-sweep**; requires diag example + regen script
- **AC-14** (Dispersion sweep regime + `regen_lgtin_upc_data.sh`) — owned by **impl-diag-sweep**

## T-134 guards retained (pre-existing RED on architect tip)

- `t134_arrival_f.rs::session_passes_precomputed_delivery_f` — failing: `session.rs` still has `delivery_f: None`
- `t134_arrival_f.rs::voi_passes_precomputed_delivery_f` — failing: `voi.rs` lacks `delivery_f: f_at_receipt` wiring
- `t134_arrival_f.rs::filter_birth_f2_dirac_from_age_at_receipt` — failing: filter birth ignores `age_at_receipt` on this tip

## Suggested implement wave order (from plan)

1. **impl-params-shipments** — AC-1, AC-2, AC-3
2. **impl-daystep** — AC-4 (+ `:birth` hook in day step)
3. **impl-unit-pf-birth** — AC-5, AC-6
4. **impl-rollout-init** — AC-9
5. **impl-crn-streams** — AC-7, AC-8
6. **impl-diag-sweep** — AC-12, AC-14

Merge after all shards; **AC-10** guard lifts once `birth_f_units` lands; **AC-11** stays green as regression.
