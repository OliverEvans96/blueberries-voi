## Coverage of acceptance criteria

- Package module `src/blueberries_voi/simulator/` exists and is importable via
  `import blueberries_voi.simulator`
  → `tests/test_simulator_session.py::test_simulator_package_importable` — currently
  failing: missing `blueberries_voi.simulator`
  → `tests/test_simulator_session.py::test_simulator_package_directory_exists` —
  currently failing: `src/blueberries_voi/simulator/` absent

- `EngineSession` exposes `init`, `step`, `step_n`, `reset`, and `act`
  → `tests/test_simulator_session.py::test_engine_session_exported` — currently
  failing: missing module / `EngineSession`
  → `tests/test_simulator_session.py::test_engine_session_exposes_required_methods`
  — currently failing: missing `EngineSession` methods
  → `tests/test_simulator_session.py::test_engine_session_method_signatures_match_interfaces`
  — currently failing: missing `EngineSession` signatures

- `init` / `reset` return Snapshot with `seq`, `episode_day`, flat `belief`
  (`lot_counts`, `age_marginals` length `L*K`, `tau_grid`, `L`, `K`)
  → `tests/test_simulator_session.py::test_init_returns_snapshot_with_flat_belief`
  — currently failing: missing `EngineSession.init`
  → `tests/test_simulator_session.py::test_reset_returns_snapshot_with_flat_belief`
  — currently failing: missing `EngineSession.reset`
  → `tests/test_simulator_session.py::test_reset_without_config_reuses_session`
  — currently failing: missing `EngineSession.reset`

- `step` returns DayDelta; `step_n` returns exactly `k` DayDeltas (or framed
  `deltas` of length `k`)
  → `tests/test_simulator_session.py::test_step_returns_day_delta` — currently
  failing: missing `EngineSession.step`
  → `tests/test_simulator_session.py::test_step_n_returns_exactly_k_day_deltas`
  — currently failing: missing `EngineSession.step_n`
  → `tests/test_simulator_session.py::test_step_n_empty_orders_returns_empty_sequence`
  — currently failing: missing `EngineSession.step_n` (boundary `k=0`)

- JSON round-trip of Snapshot / DayDelta; no `economics`, `pnl_series`,
  `pnl_totals`, `ghost`, `ghost_deltas`, `heatmap` / `density` (or ViewModel)
  → `tests/test_simulator_session.py::test_snapshot_and_day_delta_json_round_trip_excludes_presentation_keys`
  — currently failing: missing session API

- `act` selects via controller (budget knobs) and advances equivalently to
  `step` (same DayDelta shape)
  → `tests/test_simulator_session.py::test_act_returns_day_delta_and_accepts_budget_knobs`
  — currently failing: missing `EngineSession.act`
  → `tests/test_simulator_session.py::test_act_advances_equivalently_to_step_with_same_order`
  — currently failing: missing `act` / `step`

- First-class budget knobs (`n_particles`, `H`, `n_rollout_paths`, candidate
  radius); documented browser demo preset ≤ dialed caps
  → `tests/test_simulator_session.py::test_session_accepts_first_class_budget_knobs_on_init`
  — currently failing: missing `init` budget surface
  → `tests/test_simulator_session.py::test_browser_demo_budget_preset_within_dialed_caps`
  — currently failing: missing demo preset export

- Shared day driver (order → pending/arrival → `day_step` → obs → optional
  ResearchParticleFilter → belief → DayDelta) without matplotlib / pyarrow
  → `tests/test_simulator_session.py::test_shared_day_driver_symbol_exists` —
  currently failing: missing day driver symbol
  → `tests/test_simulator_session.py::test_simulator_modules_have_no_matplotlib_or_pyarrow_imports`
  — currently failing: `simulator/` package directory absent

- Unhappy / boundary paths implied by the façade
  → `tests/test_simulator_session.py::test_step_before_init_raises` — currently
  failing: missing session
  → `tests/test_simulator_session.py::test_step_rejects_non_int_order_qty` —
  currently failing: missing session
  → `tests/test_simulator_session.py::test_step_n_empty_orders_returns_empty_sequence`
  — currently failing: missing session (`k=0`)

## Not covered by tests

- `uv run pytest` / `mypy` / `ruff` clean for the full tree after implementation —
  verifier gate once GREEN; not assertable while the module is absent.
- Exact minimal `Day` chart field subset — open question on the spec;
  implementer documents in module docstring; T-045 freezes goldens.
- Abdella packaging / extras (T-044) — parallel ticket; do not touch here.
