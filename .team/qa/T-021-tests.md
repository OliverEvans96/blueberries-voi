# T-021 QA — Production RBPF → mean-field (Phase 1 RED)

DATE: 2026-08-12
STATUS: RED — failing for missing production mean-field wiring / defaults (not import errors)

## Spec under test

`.team/specs/T-021.md` + ADR 0091

## RED confirmation

```bash
uv run pytest \
  tests/test_production_mean_field.py \
  tests/test_filter.py::test_production_backend_is_mean_field \
  tests/test_l_fallback.py \
  tests/test_age_likelihood.py::test_production_rbpf_update_still_uses_mc_ll \
  tests/test_age_likelihood.py::test_adr_0049_fil04_c_and_0057_historical_after_0091 \
  -v --tb=short --no-cov
```

Result: **22 failed, 12 passed**. Failures are `AssertionError` on
`PRODUCTION_BACKEND` / `choose_backend` still returning `full_joint` or
`sliding_window`, missing `mean_field_update` in `_rbpf_update`, P1 age TV≈0,
or missing changelog entry — not import/typo failures.

## Coverage of acceptance criteria

- `PRODUCTION_BACKEND == "mean_field"` and default `RBPF` backend identity
  `mean_field`
  → `tests/test_filter.py::test_production_backend_is_mean_field` — failing:
  `PRODUCTION_BACKEND` still `"full_joint"`
  → `tests/test_production_mean_field.py::test_production_backend_constant_is_mean_field`
  — failing: same
  → `tests/test_production_mean_field.py::test_default_rbpf_backend_identity_is_mean_field`
  — failing: `backend_choice.backend == "full_joint"`
  → `tests/test_l_fallback.py::test_production_default_is_mean_field_fil04_c`
  — failing: production default still `"full_joint"`

- P1 fixture (totals observed, lot maps `UNOBSERVED`) invokes
  `mean_field_update`; posterior rows simplex; TV moves under non-flat LL
  → `tests/test_production_mean_field.py::test_rbpf_update_source_calls_mean_field_update`
  — failing: `mean_field_update` not in `_rbpf_update`
  → `tests/test_production_mean_field.py::test_p1_unobserved_maps_invokes_mean_field_update`
  — failing: spy call list empty
  → `tests/test_production_mean_field.py::test_p1_mean_field_age_rows_are_simplex_and_move_under_nonflat_ll`
  — failing: lot-0 TV ≈ 0 (age belief unchanged)

- Particle weights still from `observation_loglik_mc` (not `sequential_wor_pmf`)
  → `tests/test_production_mean_field.py::test_production_weights_still_use_observation_loglik_mc_not_wor_pmf`
  — currently **passing** (MC LL already wired)
  → `tests/test_production_mean_field.py::test_production_step_calls_observation_loglik_mc`
  — currently **passing**
  → `tests/test_age_likelihood.py::test_production_rbpf_update_still_uses_mc_ll`
  — currently **passing** (rewritten: keeps MC LL; allows `mean_field_update`)

- Lot maps present → `_apply_lot_map_age_update`; excess lot moves
  → `tests/test_production_mean_field.py::test_lot_map_path_invokes_apply_lot_map_age_update`
  — currently **passing**
  → `tests/test_production_mean_field.py::test_lot_map_excess_moves_target_lot_age_marginal`
  — currently **passing**

- `choose_backend(K,L,N)` always `"mean_field"` even over `MAX_JOINT_FLOATS`;
  `L` preserved (no silent truncation)
  → `tests/test_l_fallback.py::test_choose_backend_selects_mean_field_when_within_budget`
  — failing: returns `"full_joint"`
  → `tests/test_l_fallback.py::test_choose_backend_selects_mean_field_at_exact_budget_edge`
  — failing: returns `"full_joint"`
  → `tests/test_l_fallback.py::test_choose_backend_selects_mean_field_when_over_budget`
  — failing: returns `"sliding_window"`
  → `tests/test_l_fallback.py::test_choice_records_structured_fields_under_mean_field`
  — failing: backend still `"sliding_window"`
  → `tests/test_l_fallback.py::test_choose_backend_never_silently_truncates_l`
  — failing: backend `"sliding_window"` (L already preserved)
  → `tests/test_l_fallback.py::test_rbpf_within_budget_uses_mean_field` — failing:
  `"full_joint"`
  → `tests/test_l_fallback.py::test_rbpf_over_budget_uses_mean_field_without_memory_error`
  — failing: `"sliding_window"`
  → `tests/test_l_fallback.py::test_rbpf_initialize_over_budget_preserves_l_and_uses_mean_field`
  — failing: `"sliding_window"`
  → `tests/test_l_fallback.py::test_dynamic_l_follows_configured_max_with_mean_field`
  — failing: `"full_joint"`
  → `tests/test_production_mean_field.py::test_choose_backend_returns_mean_field_when_over_joint_budget`
  — failing: `"sliding_window"`
  → `tests/test_production_mean_field.py::test_choose_backend_preserves_long_dwell_l_no_silent_truncation`
  — failing: `"sliding_window"`
  → `tests/test_production_mean_field.py::test_production_rbpf_over_budget_constructs_mean_field_without_memory_error`
  — failing: `"sliding_window"`

- Bakeoff A–E still exposed; `full_joint` guard for that arm only
  → `tests/test_production_mean_field.py::test_bakeoff_registry_still_exposes_arms_a_through_e`
  — currently **passing**
  → `tests/test_production_mean_field.py::test_full_joint_bakeoff_arm_still_guards_memory_production_does_not`
  — failing: production `choose_backend` still `"sliding_window"` (guard assert
  not reached until production selector flips)
  → `tests/test_filter.py::test_full_joint_memory_guard` — pre-existing bakeoff
  guard (not re-run in RED batch; still valid)

- ADR 0091 ACCEPTED; 0049 FIL-04→C superseded; 0082/0089 superseded; 0057
  historical; no new runtime deps
  → `tests/test_production_mean_field.py::test_adr_0091_accepted_and_related_cards_record_fil04_c`
  — currently **passing** (ADR text already settled)
  → `tests/test_age_likelihood.py::test_adr_0049_fil04_c_and_0057_historical_after_0091`
  — currently **passing** (rewrote T-020 ACCEPTED lock)
  → `tests/test_production_mean_field.py::test_no_new_runtime_dependencies_for_t021`
  — currently **passing**

- Changelog plain-English production mean-field settle (post-green)
  → `tests/test_production_mean_field.py::test_changelog_has_plain_english_production_mean_field_entry`
  — failing: no T-021 / production mean-field settle entry yet

## Boundary / regression helpers

- Legacy `P1Obs` still accepted on production path
  → `tests/test_production_mean_field.py::test_legacy_p1obs_step_still_accepted_on_mean_field_path`
  — currently **passing** (smoke; identity asserted elsewhere)
- Frozen `BackendChoice`
  → `tests/test_l_fallback.py::test_backend_choice_type_is_frozen_structured_record`
  — failing: asserts `backend == "mean_field"` before freeze mutation
- Joint float budget numbers still locked (diagnostics only)
  → `tests/test_l_fallback.py::test_joint_budget_boundary_l4_fits_l5_trips`
  — currently **passing**
- Historical M1.5 note retained
  → `tests/test_l_fallback.py::test_m15_l_remeasure_experiment_note_documents_fallback`
  — currently **passing**

## Not covered by tests

- Full verifier green / coverage ≥80% — because post-implementation CI bar,
  verify by `uv run ruff check . && uv run mypy src tests && uv run pytest`
- Replacing MC weights with `sequential_wor_pmf` — out of scope; tests only
  guard against accidental replacement
- Full RBPF-vs-RBPF re-bakeoff / VOI — out of scope
- Removing bakeoff A–E arms — out of scope; registry test locks retention
- Re-running FIL-11 Stage C experiment gates — evidence already accepted

## Contracts rewritten (explore inventory)

| Old (full_joint / forbid MF) | New |
| --- | --- |
| `test_production_backend_is_full_joint` | `test_production_backend_is_mean_field` |
| `test_production_default_remains_full_joint_fil12_not_reopened` | `test_production_default_is_mean_field_fil04_c` |
| `test_choose_backend_selects_full_joint_when_within_budget` | `…_mean_field_when_within_budget` |
| `test_choose_backend_selects_full_joint_at_exact_budget_edge` | `…_mean_field_at_exact_budget_edge` |
| `test_rbpf_within_budget_uses_full_joint` | `test_rbpf_within_budget_uses_mean_field` |
| `test_dynamic_l_follows_configured_max_when_joint_fits` | `…_with_mean_field` |
| `test_choose_backend_falls_back_to_sliding_window_when_over_budget` | `test_choose_backend_selects_mean_field_when_over_budget` |
| `test_rbpf_over_budget_falls_back_without_memory_error` | `test_rbpf_over_budget_uses_mean_field_without_memory_error` |
| `test_rbpf_initialize_over_budget_preserves_l_and_falls_back` | `…_preserves_l_and_uses_mean_field` |
| `test_production_rbpf_update_still_uses_mc_ll` (`mean_field_update not in`) | keeps MC LL; allows MF wiring; forbids `sequential_wor_pmf` |
| `test_adr_0049_and_0057_status_still_accepted` | `test_adr_0049_fil04_c_and_0057_historical_after_0091` |
