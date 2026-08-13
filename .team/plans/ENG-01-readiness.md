# ENG-01 dual-mode API/Pyodide readiness

**Status:** numbering locked (2026-08-13) — Wave 0 architect not yet re-run  
**Branch tip for this lock:** `team/T-070/architect`  
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

## Sequencing (unchanged; IDs only)

T-070 (architect) → **T-071 ∥ T-072 ∥ T-073** → T-074 → T-075.

## Orchestrator instructions

1. Worktrees/branches: `team/T-070/architect`, then `team/T-071/*` … `team/T-075/*` — **never** reuse `team/T-067/*` / `team/T-068/*` / `team/T-069/*`.
2. Do **not** create ADR files `0105-*` / `0106-*` for readiness.
3. Do **not** touch arrival-only artifacts under `.worktrees/T-067-architect` or `.worktrees/T-068-qa`.
4. After this numbering lock, re-run Wave 0 architect on **T-070** writing ADR 0107–0108 + specs T-071–T-075.

## Non-goals

Filter physics, arrival-only ages, counts-only PF, ShelfBelief age-semantics (those are T-067–T-069 / ADR 0105–0106).
