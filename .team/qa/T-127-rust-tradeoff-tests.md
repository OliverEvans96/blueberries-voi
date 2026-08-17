# T-127 — RED test map (qa-rust-tradeoff)

## AC-rust-tradeoff

- tradeoff.rs module → `tests/test_t127_tradeoff_forecast.py::test_tradeoff_rs_module_exists`
- RPC dispatch → `::test_session_rs_dispatches_tradeoff_forecast`
- ADR 0130 bank sampling → `::test_tradeoff_rs_uses_systematic_resample_not_mean_collapse`
- Criterion bench file → `::test_bench_tradeoff_forecast_exists`
- Full q-sweep candidates + joint_hist → `::test_tradeoff_forecast_returns_candidates_sweep`
- Optional params → `::test_tradeoff_forecast_optional_params`
- Read-only session → `::test_tradeoff_forecast_does_not_advance_day`
- Autopilot unchanged → `::test_act_rollout_unchanged_after_tradeoff_module`
- P0 band width → `::test_adr0130_p0_bands_wider_than_mean_collapse`
