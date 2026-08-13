# T-071 test map (RED — demo hydrate at API + Pyodide worker/RPC edges)

## Coverage of acceptance criteria

- FastAPI `POST /sessions/{id}/init` without `shipments` (or with empty
  `shipments`) injects demo shipments and returns **200** Snapshot (not 422)
  → `tests/test_t071_demo_hydrate_edges.py::test_api_init_without_shipments_returns_200_snapshot`
  — currently failing: HTTP 422 `config['shipments'] must be a non-empty list`
  → `tests/test_t071_demo_hydrate_edges.py::test_api_init_with_empty_shipments_returns_200_snapshot`
  — currently failing: same 422 (no demo hydrate at API edge yet)

- FastAPI `POST /sessions/{id}/reset` without/empty `shipments` injects demo
  shipments and returns **200** Snapshot
  → `tests/test_t071_demo_hydrate_edges.py::test_api_reset_with_empty_shipments_returns_200_snapshot`
  — currently failing: HTTP 422 non-empty shipments validation
  → `tests/test_t071_demo_hydrate_edges.py::test_api_reset_without_shipments_key_returns_200_snapshot`
  — currently failing: same 422

- Non-empty client `shipments` on FastAPI init/reset are preserved (not
  overwritten by the demo fixture)
  → `tests/test_t071_demo_hydrate_edges.py::test_api_init_preserves_nonempty_client_shipments`
  — currently passing (edge already forwards client shipments; lock for implement)
  → `tests/test_t071_demo_hydrate_edges.py::test_api_reset_preserves_nonempty_client_shipments`
  — currently passing (same lock)

- `packaging/pyodide/session_rpc.py` (and worker dispatch that mirrors it)
  hydrates missing/empty `shipments` on `init` / `reset` before `EngineSession`
  → `tests/test_t071_demo_hydrate_edges.py::test_rpc_init_without_shipments_returns_ok_snapshot`
  — currently failing: RPC error envelope `ValueError` /
    `config['shipments'] must be a non-empty sequence`
  → `tests/test_t071_demo_hydrate_edges.py::test_rpc_init_with_empty_shipments_returns_ok_snapshot`
  — currently failing: same ValueError (handle_rpc does not hydrate)
  → `tests/test_t071_demo_hydrate_edges.py::test_rpc_reset_with_empty_shipments_returns_ok_snapshot`
  — currently failing: same ValueError on reset with empty shipments
  → `tests/test_t071_demo_hydrate_edges.py::test_rpc_preserves_nonempty_client_shipments`
  — currently passing (explicit shipments already reach EngineSession)
  → `tests/test_t071_demo_hydrate_edges.py::test_worker_js_dispatch_mentions_demo_hydrate_source`
  — currently failing: `worker.js` has no `smoke_cool_shipments` /
    `ensure_demo_shipments` / `prepare_demo_config` hydrate hook

- Direct `EngineSession.init({})` / empty shipments still raises `ValueError`
  (no Abdella FS default inside the session)
  → `tests/test_t071_demo_hydrate_edges.py::test_engine_session_init_without_shipments_still_raises_value_error`
  — currently passing (strict contract already locked)
  → `tests/test_t071_demo_hydrate_edges.py::test_engine_session_init_with_empty_shipments_still_raises_value_error`
  — currently passing

- Demo hydrate source is parquet-free (`smoke_cool_shipments` or equivalent);
  tests must not require `data/abdella`
  → `tests/test_t071_demo_hydrate_edges.py::test_demo_hydrate_edges_do_not_require_data_abdella`
  — currently failing: API init without shipments still 422 (hydrate missing);
    Abdella load is banned via monkeypatch so implement must use parquet-free fixture
  → also covered by `_ban_abdella_parquet` on the API/RPC hydrate tests above

- Focused tests under `tests/` prove API and RPC hydrate with `--no-cov`
  → this file (`tests/test_t071_demo_hydrate_edges.py`); RED proven via
    `uv run pytest tests/test_t071_demo_hydrate_edges.py --no-cov`

## Not covered by tests

- Vite wheel serving / `wheelUrl` (T-072), CORS (T-073), studio footer (T-074),
  live browser smoke (T-075) — out of scope per spec.
- Exact shared-helper name (`ensure_demo_shipments` vs inline) — behaviour-only;
  worker source check accepts any of the three hydrate markers.
- Golden Snapshot schema changes — forbidden by ADR 0100 / out of scope.
- Arrival-only filter tickets T-067–T-069 — must not be edited here.
