# T-083 RED map — Baselines, rollout, M2 gates (CAL-A4)

## Coverage of acceptance criteria

- Rollout horizon sweep / defaults step in **multiples of 7**; tests lock
  H ∈ {7, 14, …} for production presets
  → `tests/test_t083_baselines_rollout_m2.py::test_default_rollout_horizons_export_multiples_of_seven`
  — currently failing: `DEFAULT_ROLLOUT_HORIZONS` not exported
  → `tests/test_t083_baselines_rollout_m2.py::test_default_rollout_h_is_member_of_horizons_presets`
  — currently failing: same missing export
  → `tests/test_t083_baselines_rollout_m2.py::test_production_voi_sweep_rollout_h_is_multiple_of_seven`
  — currently failing: VOI H not locked into `DEFAULT_ROLLOUT_HORIZONS`
  → `tests/test_t083_baselines_rollout_m2.py::test_rollout_module_documents_weekly_horizon_presets`
  — currently failing: rollout docs omit H×7 / weekly / MWF wording

- `toy_dp` documents and uses schedule-aware protection / decision epochs
  → `tests/test_t083_baselines_rollout_m2.py::test_toy_dp_documents_schedule_aware_certificate`
  — currently failing: module/docs still silent daily-order certificate
  → `tests/test_t083_baselines_rollout_m2.py::test_toy_dp_default_certificate_uses_order_day_epochs`
  — currently failing: no `ORDER_WEEKDAYS` / schedule / `solve_toy_dp(schedule=)`
  → `tests/test_t083_baselines_rollout_m2.py::test_toy_dp_base_policy_protection_is_not_silent_daily_two`
  — currently failing: AST shows no OrderSchedule / day-indexed epochs
  → `tests/test_toy_dp.py::test_beta1_trap_age_aware_and_rung0_share_delta_tau_l_on_toy`
  — currently failing: supersession now requires schedule-aware toy_dp text

- M2 ladder / `m2_gates` under default `OrderSchedule`; day-indexed Rung0
  → `tests/test_t083_baselines_rollout_m2.py::test_m2_gates_module_wires_default_order_schedule`
  — currently failing: no `OrderSchedule` / `DEFAULT_ORDER_SCHEDULE` in gates
  → `tests/test_t083_baselines_rollout_m2.py::test_m2_gates_beta1_consumes_day_indexed_rung0_weights`
  — currently failing: `assert_beta1_degeneracy` still scalar-only Rung0
  → `tests/test_t083_baselines_rollout_m2.py::test_m2_gates_beta1_exercises_order_days_under_schedule`
  — currently failing: gate does not exercise Sun/Tue/Thu order days
  → `tests/test_t083_baselines_rollout_m2.py::test_assert_beta1_degeneracy_passes_under_default_schedule`
  — currently failing: schedule not wired yet (precondition for retune)
  → `tests/test_t083_baselines_rollout_m2.py::test_m2_ladder_or_alpha_tune_attaches_order_schedule`
  — currently failing: adapters do not pass `schedule=` into controllers
  → `tests/test_t083_baselines_rollout_m2.py::test_assert_dp_certificate_uses_schedule_aware_toy_dp`
  — currently failing: toy_dp still not schedule-aware for DP gate

- Burn-in notes / test acknowledge **periodic** age under MWF
  → `tests/test_t083_baselines_rollout_m2.py::test_burn_in_docs_acknowledge_periodic_age_under_mwf`
  — currently failing: episode / sweep / ladder lack “periodic” burn-in note
  → `tests/test_t083_baselines_rollout_m2.py::test_production_burn_in_default_is_multiple_of_seven`
  — currently failing: `_PROD_N_BURN=30` not ×7
  → `tests/test_t083_baselines_rollout_m2.py::test_episode_default_n_burn_documents_or_uses_weekly_alignment`
  — currently failing: default `n_burn=30` without periodic docs

- Age-blind / Rung0 paths in gates consume day-indexed weights (T-081)
  → covered by `test_m2_gates_beta1_consumes_day_indexed_rung0_weights` (above)

- Closeout/guard tests that locked daily `PROTECTION_DEMAND_DAYS=2` as immutable
  base case updated / gated in this ticket
  → `tests/test_damped_sw_policy.py::test_damped_sw_protection_interval_lt1_legacy_scalar_not_immutable_base`
  — **passing** (T-081 schedule path already resolves 3/3/4; legacy 2 retained)
  → `tests/test_rung0.py::test_rung0_documents_protection_interval_not_immutable_daily_two`
  — **passing** (docs already mention periodic / day-indexed)
  → `tests/test_toy_dp.py::test_beta1_trap_age_aware_and_rung0_share_delta_tau_l_on_toy`
  — currently failing (see schedule-aware requirement above)
  → `tests/test_damped_sw_policy.py::test_damped_sw_demand_quantile_uses_protection_demand_days`
  — reframed as no-schedule legacy path (not immutable base case)
  → `tests/test_m2_gates.py::test_beta1_degeneracy_orders_match_on_same_age_fixture`
  — comment notes legacy scalar unit check; MWF path locked in T-083 file

- Focused pytest for rollout/gates; ruff/mypy on touched paths
  → focused RED proof below (qa); ruff/mypy owned by implement / verify

## Not covered by tests

- Exact new M2 gate numeric thresholds — implementer retunes from failing gates
  and records values in `m2_gates` / qa note (spec open question)
- Full citeable production VOI grid regen — out of scope (T-088)
- CI smoke budgets that stay tiny (`_SMOKE_H=2`, `_CI_N_BURN=2`) — intentionally
  not forced to ×7; production presets are the lock

## Implement retune record (T-083)

β=1 gate remains an **equality** check (no numeric profit threshold). Under
`DEFAULT_ORDER_SCHEDULE` the gate now exercises order days Sun/Tue/Thu with
day-indexed protection lengths **3 / 3 / 4** (recorded as
`_MWF_ORDER_PROTECTION_DAYS` in `sim/m2_gates.py`) and matched NB fractiles per
day. DP certificate uses schedule-aware `solve_toy_dp(schedule=…)`. Production
presets: `DEFAULT_ROLLOUT_HORIZONS=(7,14,21,28)`, `DEFAULT_ROLLOUT_H=28`,
`PRODUCTION_N_BURN=28`, `PRODUCTION_ROLLOUT_H=28`.

## RED proof (qa)

```text
uv run --python 3.11 pytest \
  tests/test_t083_baselines_rollout_m2.py \
  tests/test_damped_sw_policy.py::test_damped_sw_protection_interval_lt1_legacy_scalar_not_immutable_base \
  tests/test_rung0.py::test_rung0_documents_protection_interval_not_immutable_daily_two \
  tests/test_toy_dp.py::test_beta1_trap_age_aware_and_rung0_share_delta_tau_l_on_toy \
  --no-cov
17 failed, 2 passed
```

Failures are assertion misses on missing H×7 presets, schedule-aware toy_dp,
OrderSchedule-wired M2 gates / day-indexed Rung0, and periodic burn-in — not
import or collection errors. The 2 passes are supersession guards already
satisfied by T-081 (legacy scalar ≠ immutable daily base case).
