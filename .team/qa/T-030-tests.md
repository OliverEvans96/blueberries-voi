## Coverage of acceptance criteria

- Rollout evaluates candidate orders over horizon **H** with terminal salvage
  \(V_T = m \sum w_{\mathrm{long}}(\tau) n\) documented in code/docs; default
  `H = 2 * eta_ref = 28`; candidate neighbourhood base ± `{0,±case,±2*case}`
  → `tests/test_rollout.py::test_rollout_order_is_exportable` — currently failing:
  missing `rollout_order` export / module
  → `tests/test_rollout.py::test_rollout_order_signature_matches_spec_sketch` —
  currently failing: missing `rollout_order` export / module
  → `tests/test_rollout.py::test_default_horizon_is_twice_eta_ref` — currently
  failing: missing `rollout_order` export / module
  → `tests/test_rollout.py::test_candidate_neighbourhood_is_plus_minus_two_cases`
  — currently failing: missing `candidate_orders` / rollout module
  → `tests/test_rollout.py::test_candidate_orders_rejects_empty_or_invalid` —
  currently failing: missing `candidate_orders` / rollout module
  → `tests/test_rollout.py::test_rollout_order_rejects_nonpositive_horizon` —
  currently failing: missing `rollout_order` export / module
  → `tests/test_rollout.py::test_terminal_salvage_vt_matches_margin_times_w_long_sum`
  — currently failing: missing `terminal_salvage_value` / `w_long_oldest_first`
  → `tests/test_rollout.py::test_terminal_salvage_empty_lots_is_zero` — currently
  failing: missing `terminal_salvage_value`
  → `tests/test_rollout.py::test_rollout_module_documents_vt_formula_and_adr_0061`
  — currently failing: missing rollout module source/docs
  → `tests/test_rollout.py::test_rollout_order_returns_nonnegative_case_multiple`
  — currently failing: missing `rollout_order` export / module

- Under paired CRN, mean scored profit of rollout ≥ base SW on fixed fixture
  seeds (tie OK; abs tol 1e-6)
  → `tests/test_rollout.py::test_rollout_mean_profit_ge_base_sw_under_paired_crn`
  — currently failing: missing `RolloutPolicy` / rollout module

- Optional compute-budget kwargs (`n_rollout_paths`, `H`, candidate set size
  and/or particle caps) with full desktop defaults; omitting preserves
  production behaviour
  → `tests/test_rollout.py::test_rollout_order_budget_kwargs_have_desktop_defaults`
  — currently failing: missing `rollout_order` budget surface
  → `tests/test_rollout.py::test_omitting_budget_kwargs_preserves_production_behaviour`
  — currently failing: missing `rollout_order` export / module

- Forward steps call the same `model.day_step` (AST/identity; no shadow dynamics)
  → `tests/test_rollout.py::test_rollout_forward_steps_use_shared_model_day_step`
  — currently failing: missing rollout module to AST/identity-check
  → `tests/test_rollout.py::test_rollout_forward_steps_call_day_step_via_spy`
  — currently failing: missing rollout module / day_step call path

- Rollouts are sequential (AST: no `multiprocessing` / `ProcessPoolExecutor`)
  → `tests/test_rollout.py::test_rollout_module_is_sequential_no_multiprocessing`
  — currently failing: missing rollout module source to scan

- CRN desync detector fails when streams intentionally crossed; passes when
  SIM-05 addressing is correct (ENG-04 prep)
  → `tests/test_rollout.py::test_crn_desync_detector_passes_when_addressing_correct`
  — currently failing: missing `detect_crn_desync` API
  → `tests/test_rollout.py::test_crn_desync_detector_fails_when_streams_intentionally_crossed`
  — currently failing: missing `detect_crn_desync` API

- `controller/` remains free of figure/FS writers
  → `tests/test_rollout.py::test_rollout_module_has_no_figure_or_fs_writers` —
  currently failing: missing rollout module
  → `tests/test_rollout.py::test_controller_package_exports_rollout_order` —
  currently failing: missing package export

## Not covered by tests

- `uv run pytest` / full-suite green — because qa wave must stay RED and must
  not run pytest (orchestrator); verify by implement + verifier per `AGENTS.md`
- Exact closed-form numeric values for `w_long` beyond the product lock with
  exported `w_long_oldest_first` — because ADR 0061 freezes structure/queue
  rule; implement chooses the position→weight map and locks it via the helper
