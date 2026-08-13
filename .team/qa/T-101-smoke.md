# T-101 Autopilot smoke evidence

**Date:** 2026-08-13  
**Host:** MockAdapter (scripted Autopilot loop; no HTTP / Pyodide run this pass)  
**Policy:** `damped_sw` (`alpha: 0.9`, `rho: 0.8`)

## Command

```bash
cd web && npm install && npm run smoke:autopilot
```

(`npm run smoke:autopilot` → `vitest run scripts/smoke-autopilot-mock.ts`)

## Outcome

**PASS** (exit 0)

```
RUN  v3.2.7 …/web
✓ scripts/smoke-autopilot-mock.ts (1 test) 18ms
Test Files  1 passed (1)
Tests  1 passed (1)
Duration  713ms
```

## Observed ticks (≥3)

Harness `createAutopilotLoop` + `MockAdapter.act`:

- Played until pause after **3** DayDelta ticks
- Each tick: `day.order_qty` present (UI sync signal), advancing `seq` and `episode_day`
- No overlapping `act` calls; loop not running after pause

HTTP and Pyodide hosts were not exercised; mock studio Autopilot path is sufficient per spec open question when documented.
