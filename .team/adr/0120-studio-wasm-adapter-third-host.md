# 0120. Studio adapter `wasm`; Pyodide retained

STATUS: ACCEPTED
DATE: 2026-08-14
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: Oliver reopen (Rust WASM PyO3 plan)
TIER: 1
AMENDS: 0099

## Context

ADR [0099](./0099-eng-01-dual-runtime-ap.md) locked **A′ dual runtime**: Pyodide worker = prod
interactive path; ASGI API = dev path; both call one Python `EngineSession`. Option A (full WASM
port of filter/rollout) was rejected then as a rewrite with little reader-visible payoff.

Interactive latency under dialed budgets is still unusable for Autopilot cadence (ADR 0117:
1–2 act/s). The revisit clause on 0099 already allowed re-scoping browser compute. Oliver
reopened option A as a **third adapter**, not a deletion of Pyodide.

## Decision

1. **Third studio adapter kind `wasm`:** `VITE_ENGINE_ADAPTER=http | pyodide | wasm | mock`.
2. **Pyodide is retained** (files, wheel path, default until wasm is proven). Production default
   may stay `pyodide` until a dedicated flip ticket.
3. **WASM host:** `crates/voi_wasm` (wasm-bindgen) + `packaging/wasm/worker.js` mirroring
   Pyodide JSON RPC (`init` / `step` / `step_n` / `reset` / `act`). One `postMessage` per user
   action; `step_n` must not round-trip per day.
4. **Env:** `VITE_WASM_WORKER_URL` default `/packaging/wasm/worker.js`; `VITE_WASM_PKG_URL`
   default `/wasm/`.
5. Presentation stays in JS (`ViewModelProjector`). HTTP adapter unchanged; when
   `BLUEBERRIES_VOI_BACKEND=rust`, ASGI uses PyO3 automatically.

## Alternatives considered

- **Keep 0099 A′ only (Pyodide + HTTP)** — rejected: Oliver asked for wasm-bindgen worker.
- **Replace Pyodide immediately as prod default** — rejected: wasm must pass golden + benches
  first; keep Pyodide files.
- **PyO3 compiled for Pyodide** — rejected: fights leaving CPython-in-the-tab; ABI/emscripten
  cost without a shared `voi_core` wasm path.

## Consequences

**Easy:** same RPC envelope as today’s worker; studio can A/B pyodide vs wasm.

**Hard / cost:** three interactive hosts to maintain; wasm payload size and no rayon in the tab;
human must copy packaging CI drafts for `wasm-pack`.

**Locked in:** adapter enum includes `wasm`; Pyodide not deleted.

**Amends:** [0099](./0099-eng-01-dual-runtime-ap.md) (adds wasm; does not drop Pyodide or HTTP).
