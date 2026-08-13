# T-092 RED test map

## Spec → tests

| Acceptance criterion | Test(s) | Expected RED failure |
|---|---|---|
| worker.js bans `importScripts` / classic `pyodide.js`; ESM `pyodide.mjs` under 314.0.4 | `tests/test_t092_pyodide_module_worker.py::test_worker_bans_importscripts_and_classic_pyodide_js`, `::test_worker_esm_imports_pyodide_mjs_under_pin`; `web/src/engine/pyodideAdapter.test.ts` «packaging worker uses ESM pyodide.mjs…» | worker still has `importScripts` + `pyodide.js` |
| wheelUrl / RPC / DEMO_BUDGETS retained | `::test_worker_retains_wheelurl_rpc_and_demo_budgets_hooks` | (should stay green once worker present; guards regressions) |
| `PyodideAdapter` uses `{ type: "module" }` | `::test_pyodide_adapter_spawns_module_worker`; Vitest «spawns a module Worker…» | adapter still `new Worker(url)` without options |
| `main.js` uses `{ type: "module" }` not classic | `::test_main_js_spawns_module_worker_not_classic` | still `{ type: "classic" }` |
| FakeWorker asserts module options | Vitest «spawns a module Worker ({ type: "module" })…» | `options` undefined / not module |
| No new Playwright | `::test_no_new_playwright_dependency` | green unless dep added |
| No workflow edit / no pin downgrade | covered by pin assertions + process; no workflow test edits | — |

## Commands (prove RED)

```bash
uv run pytest tests/test_t092_pyodide_module_worker.py --no-cov -q
cd web && npm test -- --run src/engine/pyodideAdapter.test.ts
```
