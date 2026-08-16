# T-C2-A unit-pf shard — RED map

Focused `uv run pytest tests/test_unit_pf.py --no-cov` (2026-08-16): **12 failed**, 6 passed.
Focused `cargo test -p voi_core --test unit_pf_ac -- --exact`: **9 failed**, 3 passed.

## Coverage of acceptance criteria

- `unit_ll.rs` exports `sequential_kernel_path_logprob`, `p1_totals_loglik`, `loglik_sales_by_units`; `unit_pf.rs` exports `UnitParticleBank`, `filter_step_unit`; production `systematic_resample` → `tests/test_unit_pf.py::test_unit_ll_rs_exports_required_functions`, `test_unit_pf_rs_exports_filter_step_unit`, `test_lib_rs_reexports_unit_pf_public_api`, `test_filter_step_unit_uses_systematic_resample` — currently failing: `unit_ll.rs` / `unit_pf.rs` missing; `lib.rs` has no `pub mod unit_ll` / `pub mod unit_pf`.
- Same (Rust integration) → `crates/voi_core/tests/unit_pf_ac.rs::unit_ll_module_file_present`, `unit_pf_module_file_present`, `filter_step_unit_uses_systematic_resample_not_multinomial` — currently failing: `AC-unit-pf: missing crates/voi_core/src/unit_ll.rs` / `unit_pf.rs`.
- `sales_by` `Some` + matching length → per-lot `loglik_sales_by_units`; totals-only → `p1_totals_loglik` → `test_filter_step_unit_f1_router_uses_loglik_sales_by_units`, `test_filter_step_unit_p1_router_uses_p1_totals_loglik`, `unit_pf_ac::f1_router_scores_via_loglik_sales_by_units`, `unit_pf_ac::p1_router_scores_via_p1_totals_loglik` — currently failing: `unit_pf.rs` missing.
- P1 mask never exposes `sales_by`; F1 exposes `sales_by` for router → `test_p1_mask_never_populates_sales_by`, `test_f1_mask_exposes_sales_by_for_per_lot_ll`, `unit_pf_ac::p1_mask_obs_sales_by_stays_none`, `unit_pf_ac::f1_mask_exposes_sales_by_for_router` — **passing** (obs.rs `mask_for` already correct; filter wiring still RED).
- Filter never synthesizes `sales_by` from totals → `test_filter_never_synthesizes_sales_by_from_totals`, `unit_pf_ac::filter_never_synthesizes_sales_by_from_totals` — currently failing: `unit_pf.rs` missing.
- `sequential_kernel_path_logprob` / `p1_totals_loglik` feasible & infeasible paths → `test_sequential_kernel_path_logprob_feasible_finite`, `test_p1_totals_loglik_feasible_matches_hand_reference`, `test_p1_totals_loglik_impossible_sales_is_neg_inf`, `test_loglik_sales_by_units_requires_sales_by_path`, `unit_pf_ac::sequential_kernel_path_logprob_feasible_finite`, `unit_pf_ac::p1_totals_loglik_impossible_sales_neg_inf` — currently failing: `unit_ll.rs` missing (hand-reference helpers in Python lock bench contract).
- Totals @ `L=20`, `N=200`, `U=15`: `mean_f` MAE &lt; **0.02** and **100%** damped-SW order match on scripted seeds → `test_scripted_l20_mean_f_mae_under_threshold`, `unit_pf_ac::unit_pf_l20_scripted_mean_f_mae_and_order_match` — currently failing: `unit_pf.rs` / `unit_ll.rs` missing.
- `bench_c2_a_totals_study` delegates to production `unit_ll` (not inline copy); bin registered → `test_bench_c2_a_totals_study_uses_production_unit_ll`, `test_bench_c2_a_totals_study_registered_in_cargo_toml`, `unit_pf_ac::bench_c2_a_totals_study_uses_unit_ll_not_inline_copy` — failing: bench still defines private `fn p1_totals_loglik` (registered bin **passes**).
- Meta RED harness → `test_cargo_unit_pf_ac_integration_suite_red` — **passing** (full `unit_pf_ac` suite non-zero exit).
- Normative `mask_for` table regression → `test_obs_mask_for_router_table_tests_pass` — **passing**.

## Not covered by tests

- `cargo run -p voi_core --release --bin bench_c2_a_totals_study` L=20 mean filter day &lt; **500 ms** — verify by release bench after `unit_ll` extraction (timing gate deferred to verify; study baseline ~11.6 ms documented in `experiments/c2_a_totals_study.md`).
- Runtime PyO3 exposure of `filter_step_unit` — owned by `impl-voi-py` / session shard; Python tests invoke Rust via `cargo test --test unit_pf_ac` until wire lands.
