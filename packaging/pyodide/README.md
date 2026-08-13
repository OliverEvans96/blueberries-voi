# Pyodide worker RPC (T-047)

Prod interactive host: **Pyodide 314.0.4** runs only in a Web Worker, binds one
`EngineSession`, and exchanges JSON (no deep `toJs`, no main-thread PyProxy).

## Artifacts

| File | Role |
|------|------|
| `worker.js` | Worker: `loadPyodide` → `micropip.install` Release/slim wheel → RPC |
| `main.js` | Main-thread harness: `postMessage` only (no `runPython`) |
| `session_rpc.py` | Python JSON RPC mirror for pytest / local smoke |
| `smoke.py` | Demo-budget smoke (`init` + `step` + `step_n`); exit 0/1 |

## Wire protocol

```text
request:  { "id": str, "method": "init"|"step"|"step_n"|"reset"|"act", "params": {...} }
response: { "id": str, "ok": true, "result": Snapshot|DayDelta|list[DayDelta] }
       |  { "id": str, "ok": false, "error": { "type": str, "message": str } }
```

Payloads are JSON strings (`json.dumps` / `JSON.stringify`).

## Slim / browser wheel

Install the GitHub Release slim wheel via micropip (not PyPI), e.g.:

```js
await micropip.install(
  "https://github.com/<org>/blueberries-voi/releases/download/v0.1.0/" +
    "blueberries_voi-0.1.0-py3-none-any.whl"
);
```

See `../README.md` and ADR 0101.

## Demo budgets

Smoke and browser defaults use `DEMO_BUDGETS` (`n_particles ≤ 200`, `H ≤ 7`,
`n_rollout_paths ≤ 2`, `candidate_case_radius ≤ 1`) — not the full production particle count.

```bash
uv run python packaging/pyodide/smoke.py
```
