# ENG-01 dual-mode API/Pyodide readiness

**Status:** COMPLETE — dual-mode readiness T-070–T-075; pending human merge  
**Branch tip:** `team/T-075/implement` (integrate via `team/ENG-01-readiness/wave2`)  
**Do not use:** T-067–T-069 or ADR 0105–0106 (owned by arrival-only filter)

## Why renumber

Concurrent streams both planned **T-067+** / **ADR 0105+**:

| Stream | Parent chat | Claimed (committed) |
|--------|-------------|---------------------|
| **Arrival-only filter** | [arrival-only handoff](83101a60-a8aa-4157-a05e-9639ef97ac4b) | **T-067**–**T-069**, ADR **0105**–**0106** on `team/T-067/architect` |
| **Dual-mode readiness** | [API/pyodide readiness](63dee208-bd37-45af-bb45-d3f50900821b) | Planned T-067–T-072 / ADR 0105–0106; **never committed** (yields) |

Readiness yields. Next free contiguous block after arrival-only is **T-070–T-075**; next free ADRs are **0107–0108**.

## Reserved ticket map (binding for readiness worker)

| Old (abandoned) | **Use instead** | Role |
|-----------------|-----------------|------|
| T-067 | **T-070** | Architect: ADR + this plan + specs T-071–T-075 |
| T-068 | **T-071** | Demo hydrate at API + Pyodide worker/RPC edges |
| T-069 | **T-072** | Vite serve worker + local wheel; honor `wheelUrl` |
| T-070 | **T-073** | API CORS for local Vite |
| T-071 | **T-074** | Studio bootstrap/UX (footer, env example, errors) |
| T-072 | **T-075** | Dual-mode live smoke + close-out |

## Reserved ADRs (binding)

| Old (abandoned) | **Use instead** | Intent |
|-----------------|-----------------|--------|
| 0105 | **0107** | Demo hydrate shipments at API + Pyodide worker edges |
| 0106 | **0108** | Local dual-mode: Vite-served wheel + worker, `wheelUrl`, CORS |

## Binding technical decisions

| Topic | Lock |
|-------|------|
| Demo shipments | Hydrate at **API + Pyodide worker/RPC** edges when `shipments` missing on init/reset |
| EngineSession | Still requires non-empty injectable shipments (no Abdella FS default) |
| Local wheel | `python scripts/build_slim_wheel.py`; Vite serves it; worker honors `?wheelUrl=` |
| CORS | `CORSMiddleware` for localhost / 127.0.0.1 Vite → API |
| Out of scope | Live GH workflow edits; production deploy; citeable science VOI; arrival-only filter |

ADRs: [0107](../adr/0107-demo-hydrate-at-host-edges.md) · [0108](../adr/0108-local-dual-mode-vite-wheel-cors.md).

## Sequencing

T-070 (architect) → **T-071 ∥ T-072 ∥ T-073** → T-074 → T-075.

## Orchestrator concurrency

1. Worktrees/branches: `team/T-070/architect`, then `team/T-071/*` … `team/T-075/*` — **never** reuse `team/T-067/*` / `team/T-068/*` / `team/T-069/*`.
2. After T-070 commit: fan out **qa T-071 ∥ T-072 ∥ T-073**; then implement from each qa tip.
3. review ∥ verify each implement tip; eager cleanup of superseded role worktrees.
4. T-074 after T-071–T-073 green tips; T-075 last with **live** smoke evidence.
5. Do **not** create ADR files `0105-*` / `0106-*` for readiness.
6. Do **not** merge to `main` / force-push (human).

## T-075 mandatory live commands

```bash
uv sync --extra api
uv run python scripts/build_slim_wheel.py && uv run python scripts/smoke_slim_wheel.py
# real API + Vite http mode smoke
# real Pyodide + local wheel URL smoke
```

Evidence: `.team/qa/T-075-smoke.md`. FakeWorker alone does **not** count.

## Non-goals

Filter physics, arrival-only ages, counts-only PF, ShelfBelief age-semantics (those are T-067–T-069 / ADR 0105–0106).
Live `.github/workflows/` edits; production deploy; citeable science VOI; merge to parent.

## Note on cancelled alternate range

`team/ENG-01-readiness/architect` briefly reserved **T-073–T-078** by mistaking T-070–T-072
as arrival-only. That range is **cancelled**. Canonical remains **T-070–T-075** / **0107–0108**.
T-073 inside readiness is the **CORS** ticket only.
