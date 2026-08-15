# T-125 hydrate / obs QA shard (RED — `qa-hydrate-obs`)

Migrated `tests/test_t071_demo_hydrate_edges.py` and
`tests/test_t113_obs_scenario_caches.py` from ASGI FastAPI + Pyodide
`session_rpc` paths to WASM worker + PyO3 `EngineSession` only.

Gate (focused, no coverage):

```bash
uv run pytest tests/test_t071_demo_hydrate_edges.py \
  tests/test_t113_obs_scenario_caches.py --no-cov -v
```

## Coverage of acceptance criteria

### AC-mixed — `test_t071_demo_hydrate_edges.py`

- Native `EngineSession.init` without / empty `shipments` still raises
  `ValueError` (strict; no demo hydrate inside session)
  → `tests/test_t071_demo_hydrate_edges.py::test_engine_session_init_without_shipments_still_raises_value_error`
  — currently passing
  → `tests/test_t071_demo_hydrate_edges.py::test_engine_session_init_with_empty_shipments_still_raises_value_error`
  — currently passing

- WASM `packaging/wasm/worker.js` hydrates missing/empty shipments on
  init/reset via `ensureDemoShipments` / `hydrateRpcRequest` with parquet-free
  smoke fixture
  → `tests/test_t071_demo_hydrate_edges.py::test_wasm_worker_contains_ensure_demo_shipments_hydrate`
  — currently passing
  → `tests/test_t071_demo_hydrate_edges.py::test_wasm_worker_uses_parquet_free_smoke_fixture`
  — currently passing
  → `tests/test_t071_demo_hydrate_edges.py::test_wasm_worker_hydrate_applies_on_init_and_reset`
  — currently passing

- Retired Pyodide RPC paths absent (T-125 AC-pyodide)
  → `tests/test_t071_demo_hydrate_edges.py::test_packaging_pyodide_session_rpc_absent`
  — currently failing: `packaging/pyodide/session_rpc.py` still present
  → `tests/test_t071_demo_hydrate_edges.py::test_packaging_pyodide_worker_absent`
  — currently failing: `packaging/pyodide/worker.js` still present

### AC-mixed — `test_t113_obs_scenario_caches.py`

- `EngineSession.set_obs_scenario` exists, validates ids like `mask_for`,
  returns Snapshot with updated `applied_config`, delegates to PyO3 rust backend
  → `tests/test_t113_obs_scenario_caches.py::test_set_obs_scenario_exists_and_returns_snapshot`
  — currently passing
  → `tests/test_t113_obs_scenario_caches.py::test_set_obs_scenario_delegates_to_pyo3_rust_backend`
  — currently passing
  → `tests/test_t113_obs_scenario_caches.py::test_set_obs_scenario_invalid_id_raises_like_mask_for`
  — currently passing (parametrize: `P2`, `B-state`, `not-a-scenario`, ``)

- WASM worker dispatches `set_obs_scenario` alongside init/step/act
  → `tests/test_t113_obs_scenario_caches.py::test_wasm_worker_mentions_set_obs_scenario`
  — currently passing
  → `tests/test_t113_obs_scenario_caches.py::test_wasm_worker_rpc_surface_matches_session_contract`
  — currently passing

- Retired Pyodide `session_rpc` and FastAPI API package absent (T-125 AC-pyodide
  / AC-api)
  → `tests/test_t113_obs_scenario_caches.py::test_packaging_pyodide_session_rpc_absent`
  — currently failing: `packaging/pyodide/session_rpc.py` still present
  → `tests/test_t113_obs_scenario_caches.py::test_fastapi_api_package_absent`
  — currently failing: `src/blueberries_voi/api/` still present
  → `tests/test_t113_obs_scenario_caches.py::test_blueberries_voi_api_not_importable`
  — currently failing: `blueberries_voi.api` still importable

## Not covered by tests

- Full Pyodide directory deletion (`packaging/pyodide/`), browser.py, slim-wheel
  scripts, pyodide-only test files — other T-125 implement shards (AC-pyodide).
- Studio vitest / `studioAdapter` default wasm — `qa-studio` shard.
- `tests/test_t097_act_damped_sw.py` API section removal — separate shard.
- Live browser smoke or `npm test` — verify / human ship steps.
- Python ResearchParticleFilter richest-log / per-rung cache internals — superseded by T-121 Wave F
  Rust session; not re-tested here.

## RED summary (2026-08-15)

`18 collected` → **13 passed**, **5 failed** (expected RED until implement deletes
retired paths):

| Test | Failure reason |
|------|----------------|
| `test_packaging_pyodide_session_rpc_absent` (t071 + t113) | `session_rpc.py` exists |
| `test_packaging_pyodide_worker_absent` (t071) | pyodide `worker.js` exists |
| `test_fastapi_api_package_absent` (t113) | `src/blueberries_voi/api/` exists |
| `test_blueberries_voi_api_not_importable` (t113) | API package importable |

Removed from migrated tests (no longer asserted here): FastAPI init/reset
hydrate, `session_rpc.handle_rpc`, pyodide worker source grep, Python ResearchParticleFilter
richest-log catch-up (T-121 F3).
