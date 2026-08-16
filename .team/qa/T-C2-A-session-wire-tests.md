# T-C2-A session-wire shard — RED map (qa)

Ticket: **T-C2-A** · Shard: **qa-session-wire** · Branch: `team/feature-c2-a-f-native/qa-session-wire`

Prove command:

```bash
uv run pytest tests/test_rust_session_wire.py tests/test_simulator_schema.py --no-cov
```

Result (2026-08-16): **13 failed**, 14 passed, 15 skipped (`_core` not built in this worktree).

## Coverage of acceptance criteria

### AC-session — `EngineSession`, catch-up, and VOI

- `advance_one` uses `filter_step_unit` on production hot path → `tests/test_rust_session_wire.py::test_voi_core_session_production_uses_filter_step_unit` — currently failing: `session.rs` still imports `particle_filter::filter_step` / `ParticleBank`, no `filter_step_unit`
- `run_voi_crn_cell` uses `UnitParticleBank` / `filter_step_unit` → `tests/test_rust_session_wire.py::test_voi_core_voi_production_uses_filter_step_unit` — currently failing: `voi.rs` still calls legacy `filter_step(&bank, …)`
- `configure` accepts `units_per_lot` (default 15) → `tests/test_rust_session_wire.py::test_voi_core_session_configure_accepts_units_per_lot` — currently failing: `units_per_lot` absent from `session.rs`
- `set_obs_scenario` catch-up: F2 vs P1 differ in `belief.f_marginals`, `live_lots` identical → `tests/test_rust_session_wire.py::test_rust_set_obs_scenario_f2_vs_p1_f_marginals_differ_live_lots_match` — skipped here (`_core` not built); will fail on τ-wire payloads once extension is present
- Snapshot / DayDelta belief from rust backend uses f-native fields → `tests/test_rust_session_wire.py::test_rust_init_snapshot_belief_lot_counts_nonempty` (and sibling runtime wire tests) — skipped here; `_assert_belief_populated` requires `f_grid` / `f_marginals`
- Supersede `session.rs` `#[cfg(test)]` τ keys → `tests/test_rust_session_wire.py::test_voi_core_session_tests_use_f_marginals_not_age_marginals` — currently failing: test module still references `age_marginals`

### AC-python-wire — Python schema and PyO3 fidelity

- `schema._FLAT_BELIEF_KEYS` is `{lot_counts, f_marginals, f_grid, L, K}` → `tests/test_simulator_schema.py::test_schema_module_flat_belief_keys_f_native` — currently failing: module still exports `{age_marginals, tau_grid, …}`
- `validate_flat_belief` enforces f-field lengths and rejects legacy keys → `tests/test_simulator_schema.py::test_validate_snapshot_rejects_wrong_f_marginals_length`, `::test_validate_snapshot_rejects_nested_f_marginals_rows`, `::test_validate_snapshot_rejects_legacy_tau_wire_keys` — currently failing: validator still requires `age_marginals` / `tau_grid`
- Golden fixtures under `tests/fixtures/simulator/` regenerated for f-wire → `tests/test_simulator_schema.py::test_golden_fixtures_use_f_native_belief_wire`, `::test_golden_flat_belief_lengths_match_l_and_k`, `::test_golden_snapshot_validates_required_keys_and_flat_belief`, `::test_golden_day_delta_validates_day_and_drop_oldest` — currently failing: JSON still carries `age_marginals` / `tau_grid`
- Live `EngineSession` payloads validate under f-schema → `tests/test_simulator_schema.py::test_live_init_snapshot_validates_like_golden` (and live step/round-trip siblings) — skipped here (`_core` not built); will fail once rust returns τ-wire belief
- PyO3 init/step belief populated with f-fields → `tests/test_rust_session_wire.py::test_pyo3_init_belief_delegates_to_session_bank` — skipped here; same `_assert_belief_populated` contract
- `belief_flat_from_unit_bank` export on session hot path → `tests/test_rust_session_wire.py::test_voi_core_session_belief_export_uses_f_native_wire` — currently failing: `session.rs` still uses `particle_bank_to_flat` / τ keys

### AC-guards — supersede ADR 0105/0106 τ-wire guards

- `tests/test_rust_session_wire.py` — updated to f-native `_FLAT_BELIEF_KEYS`; runtime helpers reject legacy keys
- `tests/test_simulator_schema.py` — updated to f-native `_FLAT_BELIEF_KEYS` + golden guard `test_golden_fixtures_use_f_native_belief_wire`
- `tests/fixtures/simulator/*.json` — gated by golden f-wire tests above (implement shard regenerates)
- `tests/test_belief_arrival_priors.py` — already module-skipped (`T-121 F3`); no change in this shard
- `tests/test_damped_sw_policy.py` — already module-skipped (`T-121 F3`); production f-policy covered by `impl-policy` shard
- `crates/voi_core` session tests — gated by `test_voi_core_session_tests_use_f_marginals_not_age_marginals`
- `unit_pf` / `unit_ll` allowed on hot path — implied green once `filter_step_unit` source tests pass (no separate guard test added)

## Not covered by tests

- `scripts/smoke_wasm.mjs` end-to-end — verify after WASM rebuild (`impl-python-tests` shard)
- `src/blueberries_voi/filter/belief.py` / `simulator/belief.py` flatten helpers — owned by `impl-python-wire` shard (schema + wire runtime tests above will fail until updated)
- Bit-identical CRN parity with legacy filter — explicitly out of scope per spec
