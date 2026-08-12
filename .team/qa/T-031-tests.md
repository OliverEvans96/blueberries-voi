## Coverage of acceptance criteria

- `controller/toy_dp.py` runs backward induction on a **small** state space
  (demand `{0,1,2}`, τ grid length ≤4, `max_lots=2`, short horizon ≤4) and
  returns an optimal value / policy table (`ToyDpResult`)
  → `tests/test_toy_dp.py::test_solve_toy_dp_is_exportable` — currently
  failing: missing `blueberries_voi.controller.toy_dp`
  → `tests/test_toy_dp.py::test_toy_dp_result_type_is_exportable` — currently
  failing: missing `toy_dp` / `ToyDpResult`
  → `tests/test_toy_dp.py::test_solve_toy_dp_returns_optimal_value_and_policy_tables`
  — currently failing: missing `solve_toy_dp` / `ToyDpResult` tables
  → `tests/test_toy_dp.py::test_solve_toy_dp_uses_small_ci_state_space` —
  currently failing: missing documented toy grid dims on result/module
  → `tests/test_toy_dp.py::test_controller_package_exports_solve_toy_dp` —
  currently failing: `solve_toy_dp` not on controller `__all__`

- Documented comparison reports gap between toy-DP optimum and rollout (or
  base) policy value on the **same** toy instance via `gap_vs_rollout(...)`
  → `float` (gap ≥ 0, finite)
  → `tests/test_toy_dp.py::test_gap_vs_rollout_is_exportable` — currently
  failing: missing `gap_vs_rollout`
  → `tests/test_toy_dp.py::test_gap_vs_rollout_reports_float_on_same_toy_instance`
  — currently failing: missing `gap_vs_rollout` / same-instance gap float
  → `tests/test_toy_dp.py::test_gap_vs_rollout_documented_as_same_instance_comparison`
  — currently failing: missing module / docstring for same-instance gap

- β=1 / constant-`w` trap: age-aware (damped SW) and Rung 0 use the **same**
  protection interval `Δτ_L` on the toy instance (CTL-06 / ADR 0063);
  `q10_age_increment` / `DampedSurvivalWeightedPolicy.delta_tau_L` vs Rung 0
  `protection_days=2` / shared scalar; toy publishes `delta_tau_L`
  → `tests/test_toy_dp.py::test_beta1_trap_age_aware_and_rung0_share_delta_tau_l_on_toy`
  — currently failing: missing `toy_dp` (and its `delta_tau_L` publication)

- Module stays pure (no matplotlib / parquet); AST scan of `toy_dp` and
  `controller/`; figures / file writes outside controller
  → `tests/test_toy_dp.py::test_toy_dp_module_has_no_matplotlib_pyarrow_or_file_writes`
  — currently failing: missing `toy_dp` module source
  → `tests/test_toy_dp.py::test_controller_package_has_no_matplotlib_or_parquet`
  — AST scan of existing `controller/*.py` (will stay green; guards purity
  once `toy_dp.py` lands)
  → `tests/test_toy_dp.py::test_toy_dp_lives_under_controller_package` —
  currently failing: `src/blueberries_voi/controller/toy_dp.py` absent

## Not covered by tests

- `uv run pytest` for this ticket’s tests passes — because that is the
  verifier gate after GREEN, not a vacuous QA assertion; verify by
  `uv run pytest tests/test_toy_dp.py` once implement lands.
- Exact numeric gap magnitude / production-scale DP — out of scope per
  `.team/specs/T-031.md`.
- Full VOI claims from the toy gap — out of scope.
- Browser packaging — out of scope.
