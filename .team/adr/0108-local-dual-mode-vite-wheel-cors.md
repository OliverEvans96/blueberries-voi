# 0108. Local dual-mode: Vite-served wheel + worker, wheelUrl, CORS

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: ENG-01 dual-mode readiness (T-070)
TIER: 1
MILESTONE: ENG-01 — dual-mode API/Pyodide readiness

## Context

ENG-01 Slice 3 wired the studio to HttpAdapter and PyodideAdapter, but local
end-to-end still fails: the Pyodide worker ignores `?wheelUrl=` and hardcodes a
placeholder GitHub Release URL; Vite does not serve
`/packaging/pyodide/worker.js` or a locally built slim wheel; the ASGI app has
no CORS for the Vite origin; the studio footer still says “Fake data studio.”
Live dual-mode proof needs real HTTP and real Pyodide — not FakeWorker-only
unit tests.

## Decision

We will:

1. Build the slim wheel locally via **`python scripts/build_slim_wheel.py`**
   (and keep `scripts/smoke_slim_wheel.py` as the offline wheel smoke).
2. Configure **Vite** so the studio can fetch:
   - the Pyodide **worker** under a stable URL (repo `packaging/pyodide/worker.js`
     via alias, middleware, or public copy — implementer chooses the smallest
     change), and
   - the **local slim `.whl`** (e.g. under `/wheels/` or equivalent from
     packaging dist output).
3. Require the **worker to honor `?wheelUrl=`** (and/or an explicit configure /
   init `wheelUrl` param) for micropip install; the hardcoded Release URL is
   fallback only when no override is present.
4. Add **`CORSMiddleware`** on the FastAPI app allowing localhost / 127.0.0.1
   Vite origins (typical ports including 5173) for the interactive session
   routes.
5. Replace placeholder `github.com/oliver/...` defaults in studio/adapter docs
   and defaults with **documented local / env-driven URLs** for readiness;
   production Release URLs remain valid when env supplies them.
6. Update the studio **footer / env / error** surface so it is not “Fake data
   studio” when running on live Http or Pyodide adapters.
7. Prove readiness with **live HTTP + live Pyodide smoke** (T-075); FakeWorker
   alone does not count.

## Alternatives considered

- **Keep Release-only wheel fetch** — rejected: local readiness cannot depend on
  a published GitHub Release asset that may not exist under the placeholder org.
- **Proxy API through Vite only (no CORS)** — rejected as sole fix: CORS is still
  required for the documented direct `VITE_ENGINE_API_BASE_URL` → ASGI path.
- **Ship worker only from `web/public` copy without Vite serve of packaging/**
  — acceptable implement detail if the URL contract stays stable; rejected as
  the only long-term source of truth if it drifts from `packaging/pyodide/`.
- **Edit live `.github/workflows/` in this milestone** — rejected: out of scope;
  human / privileged step.

## Consequences

**Easy:** Developers run API + Vite + local wheel and Advance/Reset against real
engines.

**Hard / cost:** Wheel build step before Pyodide smoke; CORS allowlist must stay
localhost-scoped; worker bootstrap complexity grows slightly.

**Locked in:** `wheelUrl` override; Vite serves worker+wheel; CORS for local
Vite→API; live smoke evidence required.

**Revisit if:** Production deploy / CDN wheel hosting lands — then env defaults
may point at real Release URLs without changing the override contract.

**Depends on:** ADR [0101](./0101-eng-01-packaging-pyodide-wheels.md),
[0102](./0102-eng-01-api-asgi-session.md), [0107](./0107-demo-hydrate-at-host-edges.md)

**Tickets:** T-072 (Vite/wheelUrl), T-073 (CORS), T-074 (footer/env), T-075 (smoke)
