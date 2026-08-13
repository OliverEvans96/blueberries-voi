# T-073 QA — RED criterion → test map

## Coverage of acceptance criteria

- FastAPI app installs `CORSMiddleware` (or equivalent) allowing local Vite
  origins (`http://localhost:5173`, `http://127.0.0.1:5173`) →
  `tests/test_t073_api_cors.py::test_app_installs_cors_middleware_for_local_vite`
  — currently failing: `user_middleware` empty (no CORSMiddleware)
- Preflight `OPTIONS` to a session route from an allowed Origin returns CORS
  success headers (`Access-Control-Allow-Origin` reflects origin; methods
  include POST) →
  `tests/test_t073_api_cors.py::test_options_preflight_sessions_returns_cors_success_headers`
  (parametrized for both origins) — currently failing: OPTIONS returns 405
  (no CORS preflight handling)
- `POST /sessions` with `Origin: http://localhost:5173` (and 127.0.0.1:5173)
  returns `Access-Control-Allow-Origin` →
  `tests/test_t073_api_cors.py::test_post_sessions_with_vite_origin_returns_allow_origin`
  (parametrized) — currently failing: create succeeds but
  `Access-Control-Allow-Origin` is absent
- Focused pytest under `tests/` with `--no-cov` → this file’s suite
  (`uv run pytest tests/test_t073_api_cors.py --no-cov`) — RED proven (5 failed)

## Not covered by tests

- Disallowed / missing CORS for non-localhost production-like origins
  documented as out of scope — because the ticket explicitly does not require
  asserting rejection of foreign origins or a wide `*`; local-dev scope is
  documented in the test module docstring
  (`tests/test_t073_api_cors.py`). Verify by reading that docstring (and the
  implementer’s app/module docs once added).
