# T-114 RED map

Focused: `uv run pytest tests/test_t114_rust_set_obs_scenario.py --no-cov`
Rust: `cargo test -p voi_core set_obs_scenario -- --nocapture`
Web: `npx vitest run web/src/studioWasmSetObsScenario.test.ts`

| AC | Test |
| --- | --- |
| voi_core set_obs_scenario catch-up / invalid | `crates/voi_core/src/session.rs` T-114 tests |
| catch-up ≡ never-switched; switch-back gap-only | `catch_up_matches_never_switched_weights`, `switch_back_is_gap_only` |
| RPC + worker | `rpc_set_obs_scenario_ok`, `test_wasm_worker_dispatches_set_obs_scenario` |
| WasmAdapter | `studioWasmSetObsScenario.test.ts` |
| Mock 90-day | same vitest file |
| PyO3 method | `test_pyo3_session_mentions_set_obs_scenario` |
