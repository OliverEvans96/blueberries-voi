# 0107. Demo hydrate shipments at API + Pyodide worker edges

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: ENG-01 dual-mode readiness (T-070)
TIER: 1
MILESTONE: ENG-01 — dual-mode API/Pyodide readiness

## Context

Studio `adapter.init()` with an empty or shipment-less config fails because
`EngineSession` requires a non-empty injectable `config["shipments"]`. The live
HTTP and Pyodide edges currently forward that requirement to the UI, so Advance
and Reset do not work without MockAdapter or hand-built fixtures. Abdella
parquet must not become an implicit filesystem default inside `EngineSession`
(browser has no repo `data/`).

## Decision

We will:

1. Keep **`EngineSession.init` / `reset` requiring a non-empty injectable
   `shipments` sequence** — no Abdella FS default and no silent empty init.
2. **Hydrate demo shipments at the host edges only** when `shipments` is missing
   or empty on **init/reset**:
   - FastAPI ASGI (`/sessions/{id}/init` and reset) injects a deterministic
     demo shipment list before calling `EngineSession`.
   - Pyodide worker / `session_rpc` prepare path does the same before
     `EngineSession.init` / `reset`.
3. Use **`smoke_cool_shipments()`** (or an equivalent deterministic, parquet-free
   fixture already in the library) as the demo hydrate source — not Abdella
   filesystem loads.
4. If the client **does** supply non-empty `shipments`, leave them untouched
   (no overwrite).

## Alternatives considered

- **Hydrate inside `EngineSession`** — rejected: paints FS / demo defaults into
  the core library and breaks the injectable-contract tests that require
  explicit shipments.
- **Require the UI to always send shipments** — rejected: studio bootstrap and
  Reset with empty config must work for dual-mode demo without MockAdapter.
- **Load Abdella parquet at the API edge** — rejected for browser parity and
  packaging: Pyodide cannot rely on repo `data/`; hydrate must be parquet-free.

## Consequences

**Easy:** Studio init/reset works over HTTP and Pyodide without MockAdapter;
library contract stays strict.

**Hard / cost:** Two edges must stay in sync on the hydrate fixture; tests must
assert both API and RPC paths, not only `EngineSession`.

**Locked in:** Hydrate at host edges; `EngineSession` stays strict; demo fixture
is parquet-free.

**Revisit if:** A shared pure-Python hydrate helper is extracted later — still
must not live inside `EngineSession` defaults.

**Depends on:** ADR [0100](./0100-simulator-export-contract.md),
[0102](./0102-eng-01-api-asgi-session.md), [0099](./0099-eng-01-dual-runtime-ap.md)

**Tickets:** T-071 (hydrate), T-074 (studio), T-075 (live smoke)
