## Coverage of acceptance criteria

- Optional extra `[api]` installs the chosen ASGI stack (FastAPI or Starlette + JSON)
  → `tests/test_t050_asgi_api.py::test_api_optional_extra_declares_asgi_stack`
  — currently failing: `optional-dependencies.api` missing from `pyproject.toml`

- ASGI app module is importable (documented entry, e.g. `blueberries_voi.api:app`)
  and creates server-side `EngineSession` instances keyed by `session_id`
  → `tests/test_t050_asgi_api.py::test_api_app_module_exports_asgi_app`
  — currently failing: `ModuleNotFoundError: blueberries_voi.api`
  → `tests/test_t050_asgi_api.py::test_create_session_returns_session_id`
  — currently failing: same missing `api` module (blocks POST `/sessions`)

- Routes implement session create, `init`, `step`, `step_n`, `reset`, `act`, and
  delete per T-049 Interfaces; responses validate as Snapshot / DayDelta (no
  PnL/economics/ghost/heatmap keys)
  → `tests/test_t050_asgi_api.py::test_init_returns_validated_snapshot`
  → `tests/test_t050_asgi_api.py::test_step_returns_validated_day_delta`
  → `tests/test_t050_asgi_api.py::test_step_n_returns_framed_validated_deltas`
  → `tests/test_t050_asgi_api.py::test_reset_returns_validated_snapshot`
  → `tests/test_t050_asgi_api.py::test_act_returns_validated_day_delta`
  → `tests/test_t050_asgi_api.py::test_delete_session_returns_204_then_unknown_is_404`
  — currently failing: missing `blueberries_voi.api:app` (validators ready from T-045)

- OpenAPI document is available from the app (FastAPI `/openapi.json` or
  equivalent export checked into tests)
  → `tests/test_t050_asgi_api.py::test_openapi_document_available_from_app`
  — currently failing: missing app (cannot GET `/openapi.json`)

- Unknown `session_id` returns HTTP 404 with a JSON error body
  → `tests/test_t050_asgi_api.py::test_unknown_session_id_returns_404_json_error`
  — currently failing: missing app
  → also covered after delete in
    `test_delete_session_returns_204_then_unknown_is_404`

- Invalid body (e.g. missing `order_qty` on step) returns HTTP 4xx with a JSON
  field list or explicit error type
  → `tests/test_t050_asgi_api.py::test_step_missing_order_qty_returns_4xx_json_error`
  → `tests/test_t050_asgi_api.py::test_step_n_missing_orders_returns_4xx_json_error`
  — currently failing: missing app

- App import graph does not require matplotlib for serving interactive routes
  → `tests/test_t050_asgi_api.py::test_api_modules_do_not_import_matplotlib`
  — currently failing: `src/blueberries_voi/api/` package directory missing
  → `tests/test_t050_asgi_api.py::test_importing_api_app_does_not_import_matplotlib`
  — currently failing: missing `blueberries_voi.api`

- `uv run pytest` for API tests passes; ruff/mypy clean for new modules
  — not asserted as a RED criterion here (implement + verifier gate). Verify by
    green `tests/test_t050_asgi_api.py` plus `ruff` / `mypy` on `src/blueberries_voi/api`
    after implement.

## Not covered by tests

- Session TTL / max sessions — open question in T-050; default in-process dict
  with no TTL is acceptable; document “not production multi-tenant” in implement
  docs / module docstring (manual / review check).
- D3 HttpAdapter (T-056), Pyodide worker (T-047), VOI / episode batch endpoints —
  out of scope per spec.
- Full OpenAPI schema field parity vs goldens — T-051.
