# Studio Autopilot Mode

**Status:** Wave 0 architect (T-091) — ADR + plan + specs  
**Branch tip:** `team/T-091/architect`  
**ADR:** [0111](../adr/0111-studio-autopilot-mode.md)  
**Do not use:** T-076–T-081 for Autopilot (those IDs are **CAL-01** calendar realism)

## Why remapping

The original Autopilot plan used **T-076–T-081** and **ADR 0109**. Those IDs
are already taken:

| Claimed elsewhere | Owner |
|-------------------|--------|
| **T-076–T-088** | CAL-01 calendar realism (in-flight worktrees) |
| **ADR 0109–0110** | On `main` (JS belief rebin / Studio obs scenario ladder) |

Autopilot yields and takes the next free contiguous block.

## ID remap (binding)

| Plan id (abandoned) | **Use instead** | Title |
|---------------------|-----------------|--------|
| T-076 | **T-091** | ADR 0111 + this plan + specs T-092–T-096 |
| T-077 | **T-092** | EngineSession.act damped_sw + SW-based rollout |
| T-078 | **T-093** | ActOpts + adapters + MockAdapter.act |
| T-079 | **T-094** | Controller section + chart |
| T-080 | **T-095** | Autopilot play/pause loop |
| T-081 | **T-096** | Smoke / verify / changelog |
| ADR 0109 (plan) | **ADR 0111** | studio-autopilot-mode |

## Ticket map

| Ticket | Role | Deliverable |
|--------|------|-------------|
| **T-091** | architect (this tip) | ADR 0111, plan, specs T-091–T-096, backlog/intake reservation |
| **T-092** | qa → implement → … | Python `_select_order`: `damped_sw`/`sw`; alpha/rho budgets; rollout base = `DampedSurvivalWeightedPolicy` |
| **T-093** | qa → implement → … | Typed `ActOpts`; HTTP nest / Pyodide flat normalize; `MockAdapter.act` |
| **T-094** | qa → implement → … | Section `controller` + controls + `controllerOrders` chart |
| **T-095** | qa → implement → … | `autopilotLoop.ts` + Play chrome Autopilot Play/Pause |
| **T-096** | qa → implement → … | Smoke evidence, changelog, CI-identical verify close-out |

## Wave concurrency

```
T-091 (architect, docs only)
    │
    ├─► T-092  ║  T-093  ║  T-094     (parallel after T-091 tip)
    │
    └─► T-095  (after T-092 + T-093 green; T-094 preferred in parallel or slightly ahead)
            │
            └─► T-096  (after T-095)
```

1. After T-091 commit: fan out **qa T-092 ∥ T-093 ∥ T-094**.
2. Implement from each qa tip; review ∥ verify each implement tip.
3. **T-095** starts only when **T-092** and **T-093** have implement tips that
   satisfy their AC (Controller UI from T-094 should be present before or with
   T-095 wiring — prefer T-094 tip merged into T-095 base).
4. **T-096** last: smoke + changelog + verify.
5. Do **not** merge Autopilot to `main` (human). Do **not** edit
   `.github/workflows/`.

## Locked product defaults (ADR 0111)

| Topic | Lock |
|-------|------|
| Decision | Order qty / one sim day (ADR 0004) |
| Default policy | `damped_sw` (aliases `sw`) |
| Also exposed | `rollout` (`ctl`, `rollout_order`), `constant` (`const`, `fixed`) |
| Rollout base | `DampedSurvivalWeightedPolicy` (not constant-zero) |
| Cadence | 1–2 wall-clock `act`/s; single-flight; `max(0, intervalMs − elapsed)` |
| Default interval | 500 ms SW/constant; 1000 ms rollout |
| Path | `adapter.act` → DayDelta → projector (not `generate.ts` autopilot) |
| Out of scope | ModelParams-from-sliders; decide-only peek; Rung-0 on act; merge to main |

## Non-goals

- CAL-01 calendar work (T-076–T-088)
- Live workflow YAML edits
- Citeable science VOI / overnight grids
- Merging to parent/integration branches

## Next free after Autopilot

Tickets **T-097+**; ADRs **0112+** (unless parallel streams claim first).
