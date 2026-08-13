# T-072 RED map — Vite serve worker+wheel; honor wheelUrl (ADR 0108)

## Coverage of acceptance criteria

- `packaging/pyodide/worker.js` uses `wheelUrl` query param (and/or configure/init
  `wheelUrl`) for `micropip.install` when present; hardcoded Release URL is
  fallback only  
  → `tests/test_t072_vite_wheel_url.py::test_worker_js_honors_wheel_url_query_or_configure_for_micropip` — currently failing: worker has no `wheelUrl` / `URLSearchParams`; `micropip.install(SLIM_WHEEL_URL)` only  
  → `web/src/engine/viteWheelUrl.test.ts::T-072 packaging worker honors wheelUrl for micropip > reads ?wheelUrl= …` — currently failing: same (no `wheelUrl` in worker source)

- Vite config serves (or aliases) the worker so a browser request to the
  documented worker URL (`/packaging/pyodide/worker.js`) returns JavaScript
  (HTTP 200, not 404)  
  → `tests/test_t072_vite_wheel_url.py::test_vite_config_serves_documented_worker_url` — currently failing: `web/vite.config.ts` has no packaging/pyodide alias / middleware / publicDir / fs.allow wiring  
  → `web/src/engine/viteWheelUrl.test.ts::T-072 Vite config serves worker and local wheel > wires packaging/pyodide worker at the documented URL` — currently failing: same  
  → Live HTTP 200 vs 404 against a running Vite server — not asserted here (unit/static per spec); verify / T-075 smoke owns live fetch

- Vite serves a locally built slim wheel at a documented URL (e.g. `/wheels/*.whl`)  
  → `tests/test_t072_vite_wheel_url.py::test_vite_config_exposes_local_slim_wheel_path` — currently failing: no `/wheels` / `.whl` / public wheels dir  
  → `tests/test_t072_vite_wheel_url.py::test_vite_config_mentions_documented_local_urls_contract` — currently failing: config mentions neither packaging worker nor wheel path  
  → `web/src/engine/viteWheelUrl.test.ts::… > exposes a local slim wheel path (e.g. /wheels/*.whl)` — currently failing: same

- Studio / `PyodideAdapter` / `createStudioAdapter` can pass a **local** `wheelUrl`
  (via `VITE_PYODIDE_WHEEL_URL` or opts) that reaches the worker; override not dropped  
  → `web/src/engine/viteWheelUrl.test.ts::T-072 local wheelUrl reaches the worker … > PyodideAdapter puts local /wheels/*.whl into Worker URL query` — currently **passing** (adapter already appends `?wheelUrl=`)  
  → `… > createStudioAdapter passes VITE_PYODIDE_WHEEL_URL local path through to Worker` — currently **passing**  
  → `… > createStudioAdapter opts.wheelUrl local override is not dropped` — currently **passing**  
  → `tests/test_t072_vite_wheel_url.py::test_studio_env_keys_remain_wheel_worker_contract[*]` — currently **passing** (contract keys present)

- Placeholder `github.com/oliver/...` is not the only path for local readiness —
  README or `.team/qa` note documents the local wheel URL contract  
  → Documented in **Local wheel URL contract** below (this file). README update optional for implementer.

- Automated tests fail RED until worker honors `wheelUrl` and Vite serve contracts hold  
  → Proven: pytest 4 failed / 4 passed; vitest 3 failed / 3 passed (adapter path already green).

## Local wheel URL contract (qa note — ADR 0108 / T-072)

| Piece | Documented URL / key |
|-------|----------------------|
| Pyodide worker | `/packaging/pyodide/worker.js` (override: `VITE_PYODIDE_WORKER_URL`) |
| Local slim wheel | `/wheels/*.whl` (e.g. `/wheels/blueberries_voi-0.1.0-py3-none-any.whl`; override: `VITE_PYODIDE_WHEEL_URL`) |
| Worker override | Worker must read `?wheelUrl=` (and/or configure/init `wheelUrl`) for `micropip.install`; GitHub Release URL is fallback only |
| Build | `uv run python scripts/build_slim_wheel.py` → implementer places/serves the artifact under the Vite-visible `/wheels/` (or equivalent) path |

Studio env keys remain `VITE_PYODIDE_WORKER_URL` and `VITE_PYODIDE_WHEEL_URL`.

## Not covered by tests

- Live Vite HTTP 200 for worker/wheel fetches — verify by running `npm run dev` + curl / T-075 smoke after implement.
- Exact wheel static path under `web/` if implementer chooses a path other than `/wheels/` — implementer documents in smoke note; tests accept `/wheels`, `.whl` wiring, or `web/public/wheels` / `web/wheels`.
- API CORS (T-073), footer copy (T-074), demo hydrate (T-071), arrival-only filter (T-067–T-069).
