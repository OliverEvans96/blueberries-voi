# 0102. ENG-01 API host: ASGI sessions wrapping EngineSession

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: ENG-01 reopen Wave 0 (implement gated after Slice 1)
TIER: 1
MILESTONE: ENG-01 — interactive dual-runtime simulator

## Context

Oliver locked **API = development host** and **Pyodide = production host**, sharing one export
schema (ADR [0100](./0100-simulator-export-contract.md)). Developers need keep-alive sessions so
each Advance is not a cold start, OpenAPI for contract tests, and the same Snapshot / DayDelta /
step_n shapes the worker uses — without inventing a second façade.

Slice 1 must land `EngineSession` and golden fixtures before ASGI code. This ADR freezes the API
shape now so Slice 2 implement can start from a green Slice-1 tip without redesign.

## Decision

We will:

1. Implement a thin **ASGI** app (Starlette or FastAPI under an optional **`[api]`** extra) that
   wraps **`EngineSession`** with a server-side **session store** (session id → session instance).
2. Expose HTTP routes aligned 1:1 with the interactive protocol: `init`, `step`, `step_n`, `reset`,
   `act` (and documented error envelope). Request/response JSON **must** match ADR 0100 schemas —
   no ViewModel, PnL, economics, ghost, or heatmap in API responses.
3. Publish **OpenAPI** (FastAPI auto or equivalent) describing the same schemas used by golden
   fixtures / HttpAdapter contract tests.
4. Keep heavy / offline endpoints (`run_episode`, VOI cell, figure writers) **out** of the
   interactive hot path; if added later, they are separate routes and not required for ENG-01 UI.
5. **Implement gate:** production ASGI code and `[api]` dependency land in Slice 2 (**T-050+**),
   only after Slice 1 verify-green tip (`EngineSession` + fixtures). Spec text and this ADR are
   written in Wave 0.

## Alternatives considered

- **Custom WSGI / Flask** — rejected: ASGI is the current boring default for typed JSON APIs and
  OpenAPI tooling; Starlette/FastAPI fit the stack without inventing a framework.
- **Stateless one-shot process per Advance** — rejected: cold start dominates interactive latency;
  session ids are required for both API and mental model parity with the worker-bound session.
- **gRPC / websocket-only protocol** — rejected for v1: HTTP JSON matches golden fixtures and
  HttpAdapter; websockets can wait.
- **Implement API before Pyodide** — rejected: Oliver locked order common+Pyodide first, API second.
- **Diverge API schema from worker for “richer” debug payloads** — rejected: dual schemas break the
  shared projector and contract tests.

## Consequences

**Easy:** HttpAdapter and PyodideAdapter share projector + golden schemas; local `uv run` API
gives fast iteration without WASM.

**Hard / cost:** new optional dependency (Starlette/FastAPI + server); session lifecycle / eviction
must be specified in implement tickets; CORS and bind address are ops details for local dev only
in ENG-01.

**Locked in:** ASGI over EngineSession; same Snapshot/DayDelta schema; implement after Slice 1;
`[api]` extra.

**Revisit if:** FastAPI/Starlette cannot target the same Python matrix as the library — then pick
the thinner ASGI option without changing the JSON contract.

**Depends on:** ADR [0099](./0099-eng-01-dual-runtime-ap.md), [0100](./0100-simulator-export-contract.md)
