## Coverage of acceptance criteria

- Golden JSON fixtures for at least one **Snapshot** and one **DayDelta** under
  a documented path (`tests/fixtures/simulator/`)
  → `tests/test_simulator_schema.py::test_fixture_directory_and_readme_document_path`
  — currently **passing** (fixtures + README committed in QA)
  → `tests/test_simulator_schema.py::test_snapshot_and_day_delta_golden_files_exist`
  — currently **passing**
  → `tests/test_simulator_schema.py::test_step_n_framed_golden_file_exists`
  — currently **passing** (framed `{deltas: [...]}` golden for step_n)

- Schema tests load fixtures and assert required keys per ADR 0100 / T-043
  (`seq`, `episode_day`, flat `belief` on Snapshot; DayDelta `day` +
  `drop_oldest`)
  → `tests/test_simulator_schema.py::test_schema_module_exports_validators` —
  currently failing: missing `blueberries_voi.simulator.schema`
  → `tests/test_simulator_schema.py::test_golden_snapshot_validates_required_keys_and_flat_belief`
  — currently failing: missing `validate_snapshot`
  → `tests/test_simulator_schema.py::test_golden_day_delta_validates_day_and_drop_oldest`
  — currently failing: missing `validate_day_delta`
  → `tests/test_simulator_schema.py::test_golden_step_n_framed_deltas_validate`
  — currently failing: missing `validate_day_delta`

- Schema tests assert **absence** of forbidden presentation keys: `economics`,
  `pnl_series`, `pnl_totals`, `ghost`, `ghost_deltas`, `heatmap`, nested
  `density` (and ViewModel)
  → `tests/test_simulator_schema.py::test_goldens_exclude_forbidden_presentation_keys`
  — currently failing for Snapshot/DayDelta params: missing validators
    (step_n param asserts key absence locally and passes)
  → `tests/test_simulator_schema.py::test_validate_snapshot_rejects_forbidden_economics_key`
  — currently failing: missing `validate_snapshot`
  → `tests/test_simulator_schema.py::test_validate_day_delta_rejects_forbidden_heatmap_key`
  — currently failing: missing `validate_day_delta`
  → `tests/test_simulator_schema.py::test_validate_snapshot_rejects_nested_density_under_belief`
  — currently failing: missing `validate_snapshot`

- Live `EngineSession` under fixed seed validates against the same schema
  helpers (schema + shape; byte equality optional)
  → `tests/test_simulator_schema.py::test_live_init_snapshot_validates_like_golden`
  — currently failing: missing `validate_snapshot`
  → `tests/test_simulator_schema.py::test_live_step_day_delta_validates_like_golden`
  — currently failing: missing `validate_day_delta`
  → `tests/test_simulator_schema.py::test_live_step_n_deltas_validate_with_same_helpers`
  — currently failing: missing `validate_day_delta`
  → `tests/test_simulator_schema.py::test_live_snapshot_json_round_trip_excludes_presentation_keys`
  — currently failing: missing `validate_snapshot`

- Flat belief: `len(age_marginals) == L * K`, `len(lot_counts) == L`,
  `len(tau_grid) == K` on goldens and live output
  → `tests/test_simulator_schema.py::test_golden_flat_belief_lengths_match_l_and_k`
  — currently **passing** (golden lengths already `L=2`, `K=4`, `L*K=8`)
  → `tests/test_simulator_schema.py::test_validate_snapshot_rejects_wrong_age_marginals_length`
  — currently failing: missing `validate_snapshot`
  → `tests/test_simulator_schema.py::test_validate_snapshot_rejects_nested_age_marginals_rows`
  — currently failing: missing `validate_snapshot`
  → live tests above also assert flat lengths once validators exist

- Unhappy / boundary paths implied by the schema helpers
  → `tests/test_simulator_schema.py::test_validate_day_delta_rejects_missing_drop_oldest`
  — currently failing: missing validator
  → `tests/test_simulator_schema.py::test_validate_snapshot_rejects_empty_mapping`
  — currently failing: missing validator
  → `tests/test_simulator_schema.py::test_validate_day_delta_rejects_non_mapping_day`
  — currently failing: missing validator

- `uv run pytest` for these tests passes on CI Python versions at merge time
  → verifier gate once GREEN; RED while `schema` module is absent

## Not covered by tests

- Exact live↔golden float byte equality — optional per T-045; shape/schema only.
- Wheel publishing / Abdella packaging (T-046 / T-044) — parallel / out of scope.
- HTTP / OpenAPI / TS projector (T-050–T-051, T-054) — consume these goldens later.
