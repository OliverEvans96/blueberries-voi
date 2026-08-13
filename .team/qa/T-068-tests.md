# T-068 QA — Arrival-only ages, counts-only PF, exact WOR (RED map)

DATE: 2026-08-13
STATUS: RED — failing for ADR 0091 production path still present (MF ages, MC
weights, ±1 count RW, `PRODUCTION_BACKEND == "mean_field"`). Failures are
`AssertionError` on missing behaviour, not import/typo errors.

## Spec under test

`.team/specs/T-068.md` + ADR 0105 (+ ADR 0106 cascade noted; belief export is T-069)

## RED confirmation

```bash
uv run pytest \
  tests/test_arrival_only_count_filter.py \
  tests/test_production_mean_field.py \
  tests/test_age_likelihood.py::test_production_rbpf_update_uses_exact_wor_not_mc_ll \
  tests/test_rbpf_unique_mf.py \
  tests/test_audit_t044_mf_stubs_hygiene.py::test_production_rbpf_update_does_not_call_mean_field_update \
  tests/test_audit_t044_mf_stubs_hygiene.py::test_production_p1_does_not_invoke_mean_field_update \
  tests/test_mc_likelihood.py::test_production_rbpf_update_does_not_default_to_observation_loglik_mc \
  tests/test_filter.py::test_production_backend_is_not_age_mean_field \
  tests/test_l_fallback.py \
  tests/test_m2_closeout.py::test_production_backend_is_not_age_mean_field \
  tests/test_m2_multi_scenario.py::test_multi_scenario_config_production_backend_is_not_age_mean_field \
  tests/test_m2_multi_scenario.py::test_multi_scenario_module_source_does_not_silently_select_joint \
  -v --tb=short --no-cov
```

Result: **40 failed, 16 passed** on the focused set above (plus diagnostic/hygiene
passes). Representative RED names below.

## Coverage of acceptance criteria

- No production closed-loop path calls `mean_field_update` (AST + P1 spy; thin
  callers clean)
  → `tests/test_arrival_only_count_filter.py::test_rbpf_update_source_does_not_call_mean_field_update`
  — failing: `mean_field_update` still named in `_rbpf_update`
  → `tests/test_arrival_only_count_filter.py::test_p1_unobserved_maps_does_not_invoke_mean_field_update`
  — failing: spy sees MF calls on P1 UNOBSERVED maps
  → `tests/test_arrival_only_count_filter.py::test_thin_callers_do_not_name_mean_field_update`
  — currently **passing** (day_driver / m2 / crn already clean)
  → `tests/test_production_mean_field.py::test_rbpf_update_source_does_not_call_mean_field_update`
  — failing: same AST ban
  → `tests/test_production_mean_field.py::test_p1_unobserved_maps_does_not_invoke_mean_field_update`
  — failing: spy non-empty
  → `tests/test_rbpf_unique_mf.py::test_rbpf_update_does_not_name_mean_field_update`
  — failing: MF still present
  → `tests/test_rbpf_unique_mf.py::test_duplicate_particles_do_not_invoke_mean_field_update`
  — failing: MF still invoked
  → `tests/test_audit_t044_mf_stubs_hygiene.py::test_production_rbpf_update_does_not_call_mean_field_update`
  — failing: MF still in `_rbpf_update`
  → `tests/test_audit_t044_mf_stubs_hygiene.py::test_production_p1_does_not_invoke_mean_field_update`
  — failing: spy non-empty

- Each live lot’s τ is arrival-only + clock (no in-store age rewrite)
  → `tests/test_arrival_only_count_filter.py::test_p1_step_keeps_age_post_equal_to_clocked_prior_when_no_births`
  — failing: age_post TV moves under P1 sales (MF rewrite)
  → `tests/test_production_mean_field.py::test_p1_age_rows_stay_simplex_and_do_not_move_under_sales_ll`
  — failing: lot-0 age marginal moves
  → `tests/test_production_mean_field.py::test_lot_map_path_does_not_invoke_apply_lot_map_age_update`
  — failing: lot-map age update still runs
  → `tests/test_production_mean_field.py::test_lot_map_excess_does_not_move_target_lot_age_marginal`
  — failing: excess sales still move ages

- Default particle weights = exact sequential WOR; multinomial selectable
  → `tests/test_arrival_only_count_filter.py::test_rbpf_update_weights_use_exact_wor_not_mc_default`
  — failing: still names `observation_loglik_mc`, no WOR scorer
  → `tests/test_arrival_only_count_filter.py::test_production_step_calls_wor_likelihood_not_mc`
  — failing: WOR spy empty / MC spy non-empty
  → `tests/test_arrival_only_count_filter.py::test_rbpf_sales_likelihood_field_defaults_to_exact_sequential_wor`
  — failing: `sales_likelihood` field missing on `RBPF`
  → `tests/test_arrival_only_count_filter.py::test_rbpf_sales_likelihood_multinomial_selectable`
  — failing: `sales_likelihood` field missing
  → `tests/test_production_mean_field.py::test_production_weights_use_exact_wor_not_observation_loglik_mc`
  — failing: MC still default
  → `tests/test_production_mean_field.py::test_production_step_does_not_call_observation_loglik_mc`
  — failing: MC still called
  → `tests/test_age_likelihood.py::test_production_rbpf_update_uses_exact_wor_not_mc_ll`
  — failing: MC still in body; WOR absent
  → `tests/test_mc_likelihood.py::test_production_rbpf_update_does_not_default_to_observation_loglik_mc`
  — failing: MC still named in `_rbpf_update`

- Count transitions match `day_step` physics (not ±1 RW)
  → `tests/test_arrival_only_count_filter.py::test_rbpf_update_has_no_pm1_count_random_walk`
  — failing: `rng.integers(-1, 2, …)` still present
  → `tests/test_arrival_only_count_filter.py::test_rbpf_update_count_path_names_day_step_physics`
  — failing: no day_step / allocate_sales names in `_rbpf_update`
  → `tests/test_production_mean_field.py::test_rbpf_update_has_no_pm1_count_random_walk`
  — failing: same ±1 RW

- Guard supersessions (ADR 0105 contracts replace ADR 0091 locks)
  → `tests/test_production_mean_field.py` rewritten — see above RED failures
  → `tests/test_age_likelihood.py` MC-not-WOR ban retired/flipped — RED above
  → `tests/test_rbpf_unique_mf.py` unique-MF dedup retired — RED above
  → `tests/test_audit_t044_mf_stubs_hygiene.py` production MF-sweep=5 retired — RED above
  → `tests/test_filter.py::test_production_backend_is_not_age_mean_field`
  — failing: `PRODUCTION_BACKEND == "mean_field"`
  → `tests/test_l_fallback.py::test_production_default_is_not_age_mean_field`
  (+ other production-selector tests in that file)
  — failing: choose_backend / RBPF still `mean_field`
  → `tests/test_m2_closeout.py::test_production_backend_is_not_age_mean_field`
  — failing: same constant
  → `tests/test_belief.py` helper `_stepped_production_rbpf` now requires
  `PRODUCTION_BACKEND != "mean_field"` — belief tests that call it fail until
  implementer updates the constant
  → `tests/test_m2_multi_scenario.py::test_multi_scenario_config_production_backend_is_not_age_mean_field`
  — failing: still `"mean_field"`
  → `tests/test_m2_multi_scenario.py::test_multi_scenario_module_source_does_not_silently_select_joint`
  — failing: `MULTI_SCENARIO_PRODUCTION_BACKEND = "mean_field"` still in source

- `mean_field_update` / MC LL remain importable off production path
  → `tests/test_arrival_only_count_filter.py::test_mean_field_update_remains_importable_for_diagnostics`
  — currently **passing**
  → `tests/test_production_mean_field.py::test_mean_field_update_and_mc_ll_remain_importable`
  — currently **passing**
  → `tests/test_rbpf_unique_mf.py::test_mean_field_update_still_importable_off_production_path`
  — currently **passing**
  → Diagnostic MF API / bakeoff stub hygiene in
  `tests/test_age_likelihood.py` and `tests/test_audit_t044_mf_stubs_hygiene.py`
  retained (non-production)

- Quality gates: this qa RED with `--no-cov` (focused). Implement / verifier own
  green and full AGENTS rung.

## Not covered by tests

- Exact count-proposal algorithm details (bootstrap vs residual-after-obs) —
  left to implementer; tests only ban ±1 RW and require day_step-consistent
  kernel names.
- ShelfBelief arrival-prior export semantics / Stage A docs / changelog (T-069).
- Sim `allocate_sales` / MOD-08 law unchanged (out of scope).
