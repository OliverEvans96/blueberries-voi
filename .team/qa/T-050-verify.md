STATUS: PASS

Tip: `team/T-050/implement` @ `40c61f52fc0a70d128463b301cde84ff0476bbe8`
Worktree: `.worktrees/T-050-verify` on `team/T-050/verify`
Re-verify after `[dev]` deps fix (fastapi/httpx on `[dev]` for CI parity with `pip install -e ".[dev]"`).

## Commands run

- `uv sync --extra dev` → exit 0, installed fastapi/httpx (among 40 packages) into worktree `.venv`
- `uv run ruff check .` → exit 0, all checks passed
- `uv run ruff format --check .` → exit 0, 112 files already formatted
- `uv run mypy src tests` → exit 0, no issues in 86 source files
- `uv run pytest` → exit 0, 550 passed, 1 skipped, coverage 88.06% (≥80%)
- `uv run pytest tests/test_t050_asgi_api.py -v` → 15 passed (process exit 1 only from cov-fail-under on subset; all API assertions green)

## Acceptance criteria

- [x] Optional extra `[api]` installs the chosen ASGI stack (FastAPI or Starlette + JSON) — verified by `test_api_optional_extra_declares_asgi_stack`; `pyproject.toml` declares `[api]` with fastapi/httpx; `[dev]` also lists fastapi/httpx so `uv sync --extra dev` installs the stack
- [x] ASGI app module is importable (`blueberries_voi.api:app`) and creates server-side `EngineSession` instances keyed by `session_id` — verified by `test_api_app_module_exports_asgi_app`, `test_create_session_returns_session_id`
- [x] Routes implement session create, `init`, `step`, `step_n`, `reset`, `act`, and delete; responses validate as Snapshot / DayDelta — verified by corresponding `test_*` cases in `tests/test_t050_asgi_api.py` (all passed in full suite and focused run)
- [x] OpenAPI document is available from the app — verified by `test_openapi_document_available_from_app`
- [x] Unknown `session_id` returns HTTP 404 with a JSON error body — verified by `test_unknown_session_id_returns_404_json_error` and post-delete path in `test_delete_session_returns_204_then_unknown_is_404`
- [x] Invalid body returns HTTP 4xx with a JSON field list or explicit error type — verified by `test_step_missing_order_qty_returns_4xx_json_error`, `test_step_n_missing_orders_returns_4xx_json_error`
- [x] `uv run pytest` for API tests passes; ruff/mypy clean for new modules — full pytest exit 0; ruff/mypy exit 0; 15/15 API tests passed
- [x] App import graph does not require matplotlib for serving interactive routes — verified by `test_api_modules_do_not_import_matplotlib`, `test_importing_api_app_does_not_import_matplotlib`

## Incomplete

- (none)
