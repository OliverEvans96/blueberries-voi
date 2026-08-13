STATUS: PASS

## Commands run
- `uv sync --all-extras` → exit 0, env synced / package installed
- `uv run ruff check .` → exit 0, all checks passed
- `uv run ruff format --check .` → exit 0, 122 files already formatted
- `uv run mypy src tests` → exit 0, no issues in 90 source files
- `uv run pytest` → exit 0, 582 passed, 1 skipped, coverage 88.05% (≥80%)
- `uv run pytest tests/test_t047_pyodide_worker_rpc.py -v` → 12 passed; process exit 1 only because isolated run hit `--cov-fail-under=80` (28% total); all T-047 assertions green
- `uv run python packaging/pyodide/smoke.py` → exit 0, `T-047 demo budget smoke OK: init + step + step_n`

## Acceptance criteria
- [x] Worker script loads Pyodide **314.0.4**, installs Release/slim wheel, binds one `EngineSession`, answers `init` / `step` / `step_n` / `reset` / `act` — verified by `tests/test_t047_pyodide_worker_rpc.py` (`test_worker_pins_pyodide_314_and_binds_engine_session`, `test_worker_or_docs_mention_slim_release_wheel_install`, `test_rpc_init_step_step_n_reset_act_json_protocol`) and artifacts at `packaging/pyodide/worker.js` + `session_rpc.py`
- [x] RPC payloads are JSON strings / JSON-cloneable (no nested PyProxy / deep toJs) — verified by `test_rpc_payloads_are_json_strings_or_cloneable_not_deep_tojs` and JSON round-trip asserts in `test_rpc_init_step_step_n_reset_act_json_protocol`
- [x] Main-thread smoke harness only `postMessage`s; no per-click `runPython` — verified by `test_main_thread_harness_postmessage_only_no_runpython` on `packaging/pyodide/main.js`
- [x] Demo budget smoke runs `init` + one `step` + `step_n` (≥2 orders) with pass/fail exit — verified by `uv run python packaging/pyodide/smoke.py` (exit 0) and `test_demo_budget_rpc_smoke_init_step_step_n_under_caps`
- [x] Smoke uses dialed demo budgets (≤ T-043 caps), not production `N=2000` — verified by `test_demo_budget_rpc_smoke_init_step_step_n_under_caps`, `test_rpc_rejects_or_documents_production_n_not_used_in_smoke`, and smoke assert `n_particles ≤ 200`

## Incomplete
- None
