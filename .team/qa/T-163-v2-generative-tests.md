# T-163 v2-generative — RED criterion → test map (qa)

Shard: `v2-generative` on `team/T-163/v2-generative-implement`.  
Authority: `.team/specs/T-163.md` Stage 1 (S1.1, S1.2, S1.4, S1.5, S1.6, S1.14, S1.16).

## Coverage of acceptance criteria

- **S1.1** — bottom-up stage draws match Abdella pooled `d_min + Gamma(a,b)` → `crates/voi_core/tests/t163_v2_generative.rs::abdella_marginal_d_matches_pooled_gamma` — currently failing: stage share variance is zero at fixed d=5 (fixed leg weights 0.15/0.60/0.25)
- **S1.2** — `Var(log d) ≈ 0.205` at `ρ=0` → `t163_v2_generative.rs::var_log_d_matches_abdella` — currently failing: pooled gamma draw gives Var(log d)≈0.112 vs target 0.205
- **S1.4** — hourly OU wiggle on path at `ρ=0` → `t163_v2_generative.rs::rho_zero_trace_has_hourly_ou_variation` — currently failing: line-haul segment is piecewise-flat
- **S1.5** — break pulses + additive exposure → `t151_cold_chain_breaks.rs::trace_shows_break_pulses_within_duration` + `break_exposure_is_exactly_additive` — kept; may pass on partial scaffold
- **S1.6** — trace ↔ integrator parity → `t151_cold_chain_breaks.rs::trace_integrates_back_to_reported_lambda` — kept; passes on current path
- **S1.14** — breaks inside calendar `d` → `t163_v2_generative.rs::breaks_clamped_inside_calendar_duration` — may pass on current clamp; regression guard
- **S1.16** — supersede deterministic `ρ=0` guards → deleted `t151::zero_break_rate_makes_exposure_a_function_of_duration_only` and `break_free_trip_has_deterministic_exposure`; replacement `t163_v2_generative.rs::rho_zero_exposure_varies_across_draws` — currently failing: identical exposure across seeds at fixed `d`

## Not covered by tests

- **S1.3** — clean-chain `φ̄` moments — owned by `v2-guards` shard (`t163_v2_calibration.rs`, Python calibration tests)
- **S1.7+** — filter coherence, ladder, artifact schema — other qa shards per `.team/qa/T-163-tests.md`

## Focused RED command

```bash
cargo test -p voi_core --test t163_v2_generative --test t151_cold_chain_breaks
```
