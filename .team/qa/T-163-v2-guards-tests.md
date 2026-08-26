# T-163 v2-guards — RED criterion → test map (qa)

Shard: `v2-guards` on `team/T-163/v2-guards`. ACs: **S1.3**, **S1.8**, **S1.12**.

## Coverage of acceptance criteria

- **S1.3 — Clean-chain φ̄ moments.** At `ρ = 0`, simulated mean and SD of `φ̄` (and mean `Λ`) within tolerances of the six Abdella shipments (~mean 1.36, SD ~0.07–0.08) → `crates/voi_core/tests/t163_v2_calibration.rs::clean_chain_phi_bar_moments` — currently failing: artifact lacks `sigma_hour` / `thermal_modes`; deterministic legged baseline gives ~zero `φ̄` spread; `shipments.rs` has no v2 OU/mode wiring
- **S1.3 (Python mirror)** → `tests/test_t163_calibration.py::test_clean_chain_phi_bar_moments` — currently failing: same v2 artifact / generative-path gaps; delegates MC to Rust test above
- **S1.8 — Ladder ordering (never relax).** `ac2_11a_empirical_ladder_tracking_mae` keeps strict MAE ordering richest → least-informed; `MAE(P0)/MAE(F2) ≥ 3.0` at `n ≥ 64` → `crates/voi_core/tests/t150_phase2_arrival_model.rs::ac2_11a_empirical_ladder_tracking_mae` — currently failing: `require_transit_generative_v2()` — v2 artifact fields and bottom-up generative path not implemented yet (ordering assertions unchanged)
- **S1.8 — F3 generative coherence under v2** → `crates/voi_core/tests/t150_phase2_arrival_model.rs::ac2_11a_f3_law_matches_generative_mean` — currently failing: same `require_transit_generative_v2()` guard
- **S1.12 — Per-day runtime.** `cargo run -p voi_core --release --bin bench_day_timing` within noise of baseline ~5.7 ms/day @ N=200 → `tests/test_t163_calibration.py::test_bench_day_timing_within_baseline` — currently failing: `bench_day_timing.rs` harness and `[[bin]]` target absent

## Not covered by tests

- (none for this shard — S1.3, S1.8, S1.12 each have at least one automated test)

## Focused RED commands (qa gate)

```bash
cargo test -p voi_core --test t163_v2_calibration clean_chain_phi_bar_moments -- --exact --nocapture
cargo test -p voi_core --test t150_phase2_arrival_model ac2_11a -- --nocapture
uv run pytest tests/test_t163_calibration.py -v --no-cov
```
