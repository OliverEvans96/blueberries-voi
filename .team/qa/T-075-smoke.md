# T-075 dual-mode live smoke evidence

**STATUS:** PASS  
**Date:** 2026-08-13  
**Tip:** `team/T-075/implement` (from `team/ENG-01-readiness/wave2` @ `aa61201` + close-out)  
**FakeWorker / unit-only:** **not** used as sole evidence

## Prerequisites

```bash
uv sync --extra api   # also used --all-extras for pyarrow import path on native API
uv pip install uvicorn build   # runtime helpers for local smoke hosts
uv run python scripts/build_slim_wheel.py
uv run python scripts/smoke_slim_wheel.py
```

**Wheel build:** `Built slim wheel: blueberries_voi-0.1.0-py3-none-any.whl`  
**Wheel smoke:** `OK blueberries_voi-0.1.0-py3-none-any.whl: hard Requires-Dist=['numpy', 'scipy']`

## Live HTTP mode — PASS

**Servers**
- ASGI: `uv run python -m uvicorn blueberries_voi.api.app:app --host 127.0.0.1 --port 8000`
- Vite: `npm run dev -- --host 127.0.0.1 --port 5173` (cwd `web/`)

**Checks**
1. Vite `GET /packaging/pyodide/worker.js` → **200** `application/javascript`
2. Vite `GET /wheels/blueberries_voi-0.1.0-py3-none-any.whl` → **200** `application/octet-stream`
3. CORS `OPTIONS /sessions` with `Origin: http://127.0.0.1:5173` → Allow-Origin echo
4. `POST /sessions` → session_id + CORS header
5. `POST .../init` with `{"config": {}}` → **200** Snapshot (demo hydrate)
6. `POST .../step` `{order_qty: 8}` → **200** DayDelta
7. `POST .../reset` with empty config → **200** Snapshot

Marker: `HTTP_LIVE_SMOKE_PASS` (captured under `/tmp/t075-http-smoke.txt` during run).

No MockAdapter / FakeWorker.

## Live Pyodide mode — PASS

**Method:** Node + real **Pyodide 314.0.4** (`web/node_modules/pyodide`) installing the **same** dist wheel Vite serves, then `EngineSession.init` + `step`.

Script (committed): `scripts/smoke_pyodide_local_wheel.mjs`

Evidence markers:
- `VITE_WHEEL_URL_OK http://127.0.0.1:5173/wheels/blueberries_voi-0.1.0-py3-none-any.whl 200`
- `VITE_WORKER_OK 200` (worker source includes `wheelUrl` / `URLSearchParams`)
- `PYODIDE_RESULT {"seq": 0, "episode_day": 0, "belief_L": 2}`
- `PYODIDE_LIVE_SMOKE_PASS`

**Note:** Importing the simulator currently pulls `model.abdella` which imports `pyarrow` at module load; smoke therefore also `loadPackage("pyarrow")` inside Pyodide. Slim wheel still declares only numpy/scipy hard deps. Follow-up optional: lazy-import pyarrow so browser path stays parquet-free without loading pyarrow.

No FakeWorker.

## Upstream tip SHAs (implement)

| Ticket | Branch | SHA |
|--------|--------|-----|
| T-070 architect | `team/T-070/architect` | `160d229` |
| T-071 | `team/T-071/implement` | `49e0f1e` |
| T-072 | `team/T-072/implement` | `b2dcd30` |
| T-073 | `team/T-073/implement` | `8a1aff7` |
| T-074 | `team/T-074/implement` | `aa61201` |
| Wave2 merge tip | `team/ENG-01-readiness/wave2` | `aa61201` (+ gate hygiene `8c63b38` ancestry) |
