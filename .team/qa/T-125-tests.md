# T-125 QA — RED test map (Wave 1 shard: qa-guards)

Track **T-125** / branch `team/T-125/qa-guards-implement`. Implements guard
acceptance from `.team/specs/T-125.md` (AC-pyodide, AC-api, AC-config,
AC-closeout runtime guards) before implement shards delete retired paths.

## Coverage of acceptance criteria

- **`packaging/pyodide/` directory is absent** →
  `tests/test_t125_runtime_guards.py::test_retired_paths_absent[packaging/pyodide]` —
  currently failing: directory still exists with `main.js`, `worker.js`, `session_rpc.py`.

- **`src/blueberries_voi/api/` directory is absent** →
  `tests/test_t125_runtime_guards.py::test_retired_paths_absent[src/blueberries_voi/api]` —
  currently failing: FastAPI `app.py` package still present.

- **`browser.py` and `slim_wheel_metadata.py` absent** →
  `tests/test_t125_runtime_guards.py::test_retired_paths_absent[src/blueberries_voi/browser.py]` —
  currently failing: both modules still on disk;
  `test_browser_and_slim_wheel_modules_not_importable` — modules still importable.

- **No `httpAdapter` / `pyodideAdapter` in `web/src/engine`** →
  `tests/test_t125_runtime_guards.py::test_engine_dir_has_no_http_or_pyodide_adapter_files` —
  currently failing: `httpAdapter.ts`, `pyodideAdapter.ts`, and their vitest files exist;
  parametrized `test_retired_paths_absent[web/src/engine/httpAdapter.ts]` etc. also fail.

- **Pyodide-only scripts, workflow draft, and tests absent** →
  `tests/test_t125_runtime_guards.py::test_retired_paths_absent[...]` for
  `scripts/build_slim_wheel.py`, `release-slim-wheel.yml`, `test_t047_pyodide_worker_rpc.py`,
  and siblings — currently failing: all paths still present.

- **API-only tests absent** →
  `tests/test_t125_runtime_guards.py::test_retired_paths_absent[tests/test_t050_asgi_api.py]` —
  currently failing: ASGI/API contract/CORS tests still present;
  `test_api_package_not_importable` — `blueberries_voi.api` still importable.

- **`pyproject.toml` has no `api` or `browser` optional-dependencies** →
  `tests/test_t044_packaging_extras.py::test_retired_browser_and_api_extras_absent` —
  currently failing: `[browser]` and `[api]` tables still defined;
  `test_eng01_extras_are_data_and_viz_only` — eng extras include `browser` and `api`.

- **`[data]` retains pyarrow; `[viz]` owns matplotlib** →
  `tests/test_t044_packaging_extras.py::test_data_extra_retains_pyarrow_for_desktop_parquet` —
  currently passing (should stay green after implement);
  `test_viz_extra_owns_matplotlib` — currently passing.

- **`tests/test_t125_runtime_guards.py` passes after closeout** →
  entire module — currently RED (22 parametrized path failures + 3 import/adapter failures).

## Not covered by tests

- **Studio WASM default / adapter kind** — owned by qa-studio shard
  (`studioAdapter.test.ts`, etc.).

- **Mixed-host test migration (T-071, T-113, T-097)** — owned by qa-hydrate-obs shard.

- **Closeout changelog phrase updates** — owned by impl-closeout shard
  (`test_m2_closeout.py`, `test_eng01_closeout.py`, slice closeouts).

- **`rg` hygiene over src/scripts/web/tests** — guard file asserts concrete paths;
  implement should still run spec `rg` checklist manually or in verify.

- **README / packaging docs** — verify at ship via human review and AC-docs.

## RED proof

```bash
cd .worktrees/T-125-qa-guards-implement
uv sync
uv run pytest tests/test_t125_runtime_guards.py tests/test_t044_packaging_extras.py --no-cov -v
```

Expected: 25 failures in `test_t125_runtime_guards.py` (22 paths + 3 behavioural),
2 failures in `test_t044_packaging_extras.py` (retired extras + eng01 key set);
2 tests pass (`test_data_extra_*`, `test_viz_extra_*`, `test_python_314_*`).
