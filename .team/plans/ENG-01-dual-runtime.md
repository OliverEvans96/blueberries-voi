# ENG-01 dual-runtime simulator (T-042–T-058)

**Status:** Wave 0 architect lock (T-042)  
**Date:** 2026-08-12  
**Board:** ENG-01  
**Supersedes:** ADR 0073 option C (static only) → ADR **0097** A′ dual runtime

## Decisions locked (Oliver)

| Topic | Lock |
|-------|------|
| Runtimes | **Pyodide = prod**, **API = dev** |
| Order | **Common + Pyodide → API → D3 mockup** |
| Scope | ADR/export, façade, packaging, hosts, UI |
| Browser v1 | **sim + filter + controller** (dialed budgets) |
| Pin | **Pyodide 314.0.4** / **CPython 3.14.2**; CI adds 3.14; keep 3.11+3.12 native/API |
| D3 | Slice 3; worktree / branch `web/d3-simulator-mockup` |
| Prefs | Derived Abdella; CI→GH Release wheels; no matplotlib in-browser; worker-only Pyodide; Snapshot/DayDelta + JS presentation; flat belief; `step_n`; avoid deep `toJs` |

ADRs: [0097](../adr/0097-eng-01-dual-runtime-ap.md) reopen · [0098](../adr/0098-simulator-export-contract.md) export · [0099](../adr/0099-eng-01-packaging-pyodide-wheels.md) packaging · [0100](../adr/0100-eng-01-api-asgi-session.md) API.

## Architecture

```text
Slice 3 (D3)          Slice 1 (common + Pyodide)         Slice 2 (API)
UI → Projector  ──►  EngineSession ← slim wheel ← worker
     ├ PyodideAdapter (prod) ──► worker RPC JSON
     └ HttpAdapter (dev) ─────► ASGI session store
```

**Python:** `src/blueberries_voi/simulator/` — `EngineSession` with `init` / `step` / `step_n` /
`reset` / `act`. Returns Snapshot / DayDelta only.

**JS (Slice 3):** `ViewModelProjector`; economics / PnL / ghost / heatmap stay local.

## Ticket map

### Slice 1 — Common + Pyodide (prod path)

| Wave | Tickets | Parallelism |
|------|---------|-------------|
| 0 | **T-042** docs lock | Serial architect |
| 1 | **T-043** EngineSession + day driver + `act` + `step_n` ∥ **T-044** derived Abdella + extras | **T-043 ∥ T-044** (independent) |
| 2 | **T-045** golden Snapshot/DayDelta fixtures ∥ **T-046** slim wheel + GH Release | Merge Wave 1 tip first; then **T-045 ∥ T-046** (045 needs 043; 046 needs 044) |
| 3 | **T-047** Pyodide worker RPC + budget smoke | Serial on Wave 2 tip |
| 4 | **T-048** Slice-1 close-out | Serial |

### Slice 2 — API (dev path)

| Wave | Tickets | Parallelism |
|------|---------|-------------|
| 0 | **T-049** API ADR/spec already in Wave 0 (ADR 0100); implement gated | Spec done in T-042 |
| 1 | **T-050** ASGI app ∥ **T-051** Http vs golden contract tests | After Slice-1 green tip |
| 2 | **T-052** Slice-2 close-out | Serial |

### Slice 3 — D3 mockup

| Wave | Tickets | Parallelism |
|------|---------|-------------|
| 0 | **T-053** UI ADR (EngineAdapter + projector ownership) | Architect in mockup worktree |
| 1 | **T-054** projector + Mock deltas ∥ **T-055** PyodideAdapter ∥ **T-056** HttpAdapter | **T-054 ∥ T-055 ∥ T-056** (055 needs T-047 artifact; 056 needs T-050; 054 can start after export ADR) |
| 2 | **T-057** Wire studio (dev=HTTP, prod=Pyodide) | Serial |
| 3 | **T-058** ENG-01 / Slice-3 close-out | Serial |

## Orchestrator concurrency

1. After T-042 commit: fan out **qa T-043 ∥ qa T-044** on separate worktrees from architect tip.
2. After each qa tip: implement in its own worktree; then **reviewer ∥ verifier**.
3. One writer per worktree; eager cleanup of superseded role worktrees.
4. Slice-2 implement only from Slice-1 verify-green tip.
5. Do not merge to `main` / force-push (human).

## Non-goals

- Full WASM rewrite (not A)
- JS-only physics as production engine (not B)
- Matplotlib / pyarrow in browser
- Production-N RBPF + full rollout in-tab without budget dials
- Honesty / cadence ⚑ cards
- Merging to parent branches (human)

## Key library touchpoints

- `model.day_step`, `filter` RBPF / `ShelfBelief`, `controller.rollout_order` / policies via `act`
- Extract shared closed-loop day driver into `simulator/`
- Break eager Abdella parquet imports on browser path (`model/abdella.py`)
- Mock reference: web mockup `web/src/types.ts`, `web/src/mock/adapter.ts`
