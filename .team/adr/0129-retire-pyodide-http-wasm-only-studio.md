# 0129. Retire Pyodide + HTTP API — WASM-only browser studio

STATUS: PROPOSED
DATE: 2026-08-15
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: T-125 — Rust WASM studio cleanup (post T-121 Wave F)
TIER: 1
MILESTONE: ENG-01 — interactive studio
SUPERSEDES (partial): [0120](./0120-studio-wasm-adapter-third-host.md), [0108](./0108-local-dual-mode-vite-wheel-cors.md),
[0099](./0099-eng-01-dual-runtime-ap.md) (browser hosts), [0101](./0101-eng-01-packaging-pyodide-wheels.md),
[0102](./0102-eng-01-api-asgi-session.md), [0111](./0111-pyodide-module-worker-host.md)
RELATED: [0127](./0127-tier2-rust-compute-kernel.md), [0121](./0121-rust-workspace-pyo3-wasm-deps.md)

## Context

After T-121 Wave F, all **hot** compute lives in `crates/voi_core` and is exposed to the browser
via `voi_wasm` (`packaging/wasm/worker.js`) and to notebooks/CLI via PyO3 (`voi_py`). ADR
[0120](./0120-studio-wasm-adapter-third-host.md) added a third studio adapter `wasm` while
**retaining** Pyodide and the FastAPI HTTP dev host. ADR [0108](./0108-local-dual-mode-vite-wheel-cors.md)
and [0099](./0099-eng-01-dual-runtime-ap.md) locked dual-mode: Pyodide = prod interactive path,
ASGI API = dev path, both calling Python `EngineSession`.

That triple-host model made sense while WASM parity was unproven. T-121 delivered golden parity,
`set_obs_scenario` in WASM (ADR [0124](./0124-rust-wasm-set-obs-scenario.md)), and benches showing
Pyodide ~10–100× slower than native Rust for Autopilot cadence (ADR [0117](./0117-studio-autopilot-mode.md)).
Maintaining Pyodide packaging (slim wheel, micropip worker, CPython 3.14 ABI pin), FastAPI session
glue, and three frontend adapters (`http`, `pyodide`, `wasm`) is now pure maintenance cost with no
reader-visible benefit.

ADR [0127](./0127-tier2-rust-compute-kernel.md) §Decision item 6 noted Pyodide retirement as a human
decision after Wave F — this ADR records that decision. **Bakeoff/research Python**
(`filter/particle/`, `sim/bakeoff_*`, `sim/episode.py`, `model/constitutive.py`) stays in scope for
viz diagnostics and remains **out of scope for deletion** in T-125.

## Decision

We will:

1. **Browser studio = WASM only.** `StudioAdapterKind` is `wasm | mock` (mock debug-only). Default
   adapter in dev and prod is `wasm`. `VITE_ENGINE_ADAPTER` override still wins. Remove `http` and
   `pyodide` adapter kinds, workers, and env-driven dual-mode selection.
2. **Delete Pyodide packaging and slim-wheel pipeline:** `packaging/pyodide/`, `browser.py`,
   `slim_wheel_metadata.py`, slim-wheel build/smoke scripts, Pyodide-only tests, and the
   `release-slim-wheel` workflow draft. Remove `browser` optional extra from `pyproject.toml`.
3. **Delete HTTP API host:** `src/blueberries_voi/api/`, `httpAdapter.ts`, API-only tests, and the
   `api` optional extra. Remove `fastapi` / `httpx` from dev dependencies when only API tests used
   them.
4. **Keep native PyO3 Python host** (`simulator/session.py`, `voi/crn.py`, `voi/sweep.py`,
   `voi/bootstrap.py`, `viz/*`, Abdella parquet I/O). Notebooks, CLI, sweep, and bootstrap continue
   via `maturin develop` / `BLUEBERRIES_VOI_BACKEND=rust`.
5. **Migrate mixed-host tests** (T-071 demo hydrate, T-113 obs scenario caches, closeout guards,
   T-044 packaging extras, T-097 API-only sections) to WASM + native `EngineSession` only — not
   delete coverage.
6. **Demo hydrate split:** `ensure_demo_shipments` stays in `sim/shipments.py` for Python tests;
   browser demo hydrate remains in `packaging/wasm/worker.js` (already implemented per ADR
   [0107](./0107-demo-hydrate-at-host-edges.md)).
7. **Docs:** README and `packaging/README.md` describe WASM-only browser studio
   (`./scripts/build-wasm.sh` + `./scripts/studio.sh`). Human copies updated CI draft and deletes
   live `release-slim-wheel.yml` — agents do not edit `.github/workflows/`.

## Alternatives considered

- **Keep Pyodide as fallback adapter** — rejected: duplicate host maintenance; WASM is parity-proven;
  Pyodide cannot share `voi_core` without emscripten PyO3 (ADR 0120 already rejected that).
- **Keep HTTP API for dev only** — rejected: dev and prod should exercise the same browser engine;
  native PyO3 covers notebook/CLI dev; HTTP adds CORS, ASGI, and a fourth code path for session RPC.
- **Delete bakeoff Python in the same milestone** — rejected: ADR 0127 Tier 3 explicitly out of
  scope; viz and research still reference those modules.
- **Flip default to WASM without deleting Pyodide files** — rejected: dead code rots; guard tests and
  CI would still pay slim-wheel and Pyodide smoke cost indefinitely.

## Consequences

**Easy:** One browser engine; smaller frontend surface; no CPython-in-the-tab ABI pin; CI drops
slim-wheel and Pyodide smoke jobs; studio footer and scripts simplify to WASM-only narrative.

**Hard / cost:** Large deletion diff risks coverage drop (mitigate with wasm vitest or targeted
Python guards); mixed-host tests (T-071, T-113) need careful rewrite to avoid xdist flakes;
closeout tests that scan changelog for "pyodide" / "ASGI" must be updated in the same ticket;
human must sync live GitHub workflows from packaging drafts.

**Locked in:** Browser interactive compute path is `voi_wasm` only; PyO3 is the sole Python compute
host; bakeoff/research Python modules remain until a future ADR.

**Revisit if:** A future requirement demands offline Python-in-browser (unlikely) — would need a new
ADR and likely a different packaging strategy than the retired slim wheel.

**Tickets:** T-125 (this milestone); concurrency plan `.team/plans/T-125-concurrency.yaml`.
