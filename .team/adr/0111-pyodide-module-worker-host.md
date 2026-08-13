# 0111. Pyodide 314 host uses module workers + pyodide.mjs

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: Fix Pyodide classic-worker failure (pin 314.0.4)
TIER: 1
MILESTONE: ENG-01 — interactive dual-runtime simulator

## Context

ADR 0101 pins **Pyodide 314.0.4** and requires a worker-only host. The packaging
worker still bootstraps via classic-worker `importScripts(.../pyodide.js)`, and
hosts construct `new Worker(url)` / `{ type: "classic" }`.

Pyodide **314.0.4** rejects classic workers. Keeping the pin (no downgrade) forces
a host-side migration: **module workers** loading **`pyodide.mjs`** via ESM
`import`, while preserving wheelUrl resolution, JSON RPC, and DEMO_BUDGETS.

## Decision

We will:

1. Load Pyodide in the packaging worker with an ESM import of
   `https://cdn.jsdelivr.net/pyodide/v314.0.4/full/pyodide.mjs` (no
   `importScripts`, no classic `pyodide.js`).
2. Construct the worker as a **module worker**:
   `new Worker(url, { type: "module" })` from both `PyodideAdapter` and
   `packaging/pyodide/main.js`.
3. Keep the existing wheelUrl / RPC / DEMO_BUDGETS contracts unchanged.
4. **Not** downgrade Pyodide below 314.0.4 to restore classic-worker support.

## Alternatives considered

- **Downgrade Pyodide to a classic-worker-friendly release** — rejected: ADR 0101
  and Oliver lock 314.0.4 / CPython 3.14.2; classic restore is not an option.
- **Keep classic workers and polyfill / vendor an older loader** — rejected:
  fights the pin and leaves the host on a path Pyodide 314 explicitly rejects.
- **Move Pyodide onto the main thread** — rejected: ADR 0101 worker-only rule;
  main thread must not hold PyProxy.

## Consequences

**Easy:** browser hosts under pin 314.0.4 can bootstrap again; Vite/module
tooling aligns with ESM worker scripts.

**Hard / cost:** every host that spawns the packaging worker must pass
`{ type: "module" }`; FakeWorker / contract tests must assert module options and
ban `importScripts`. Classic-only environments cannot host this worker.

**Locked in:** module-worker + `pyodide.mjs` bootstrap under Pyodide 314.0.4.

**Revisit if:** a future Pyodide major restores classic workers *and* product
policy allows leaving ESM module workers — until then, module host stays.

**Depends on:** ADR [0101](./0101-eng-01-packaging-pyodide-wheels.md),
[0099](./0099-eng-01-dual-runtime-ap.md)
