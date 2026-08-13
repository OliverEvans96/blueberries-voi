# Studio Autopilot Mode

**Status:** Wave 0 architect (T-091) — ADR + plan + specs  
**Branch tip:** `team/T-091/architect`  
**ADR:** [0117](../adr/0117-studio-autopilot-mode.md)  
**Do not use for Autopilot:** T-076–T-081 (CAL-01); T-092–T-096 (other streams — **Pyodide owns T-092** / ADR 0111); provisional Autopilot draft that briefly claimed those ids is void.

## Why remapping (two collisions)

1. Original user plan used **T-076–T-081** / **ADR 0109** — taken by CAL-01 and
   ADR 0109–0110 on `main`.
2. First Autopilot architect draft then used **T-092–T-096** / **ADR 0111** —
   taken by concurrent **Pyodide module-worker** (`team/T-092/*`,
   `0111-pyodide-module-worker-host.md` on that tip; not on this branch).

Autopilot keeps Wave 0 as **T-091** and renumbers children to **T-097–T-101**
with **ADR 0117**.

## ID remap (binding)

| User plan id | First draft (void) | **Use instead** | Title |
|--------------|--------------------|-----------------|--------|
| T-076 | T-091 | **T-091** | ADR 0117 + this plan + specs T-097–T-101 |
| T-077 | T-092 | **T-097** | EngineSession.act damped_sw + SW-based rollout |
| T-078 | T-093 | **T-098** | ActOpts + adapters + MockAdapter.act |
| T-079 | T-094 | **T-099** | Controller section + chart |
| T-080 | T-095 | **T-100** | Autopilot play/pause loop |
| T-081 | T-096 | **T-101** | Smoke / verify / changelog |
| ADR 0109 (plan) | ADR 0111 (void for Autopilot) | **ADR 0117** | studio-autopilot-mode |

**Note:** ADR **0111** remains reserved for Pyodide module-worker host (other
stream). This branch intentionally has a numbering gap at 0111.

## Ticket map

| Ticket | Role | Deliverable |
|--------|------|-------------|
| **T-091** | architect (this tip) | ADR 0117, plan, specs T-091 + T-097–T-101, backlog/intake reservation |
| **T-097** | qa → implement → … | Python `_select_order`: `damped_sw`/`sw`; alpha/rho budgets; rollout base = `DampedSurvivalWeightedPolicy` |
| **T-098** | qa → implement → … | Typed `ActOpts`; HTTP nest / Pyodide flat normalize; `MockAdapter.act` |
| **T-099** | qa → implement → … | Section `controller` + controls + `controllerOrders` chart |
| **T-100** | qa → implement → … | `autopilotLoop.ts` + Play chrome Autopilot Play/Pause |
| **T-101** | qa → implement → … | Smoke evidence, changelog, CI-identical verify close-out |

## Wave concurrency

```
T-091 (architect, docs only)
    │
    ├─► T-097  ║  T-098  ║  T-099     (parallel after T-091 tip)
    │
    └─► T-100  (after T-097 + T-098 green; T-099 preferred in parallel or slightly ahead)
            │
            └─► T-101  (after T-100)
```

1. After T-091 commit: fan out **qa T-097 ∥ T-098 ∥ T-099**.
2. Implement from each qa tip; review ∥ verify each implement tip.
3. **T-100** starts only when **T-097** and **T-098** have implement tips that
   satisfy their AC (Controller UI from T-099 should be present before or with
   T-100 wiring — prefer T-099 tip merged into T-100 base).
4. **T-101** last: smoke + changelog + verify.
5. Do **not** merge Autopilot to `main` (human). Do **not** edit
   `.github/workflows/`.
6. Do **not** claim T-092–T-096 for Autopilot.

## Locked product defaults (ADR 0117)

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
- Pyodide module-worker (T-092 / ADR 0111)
- Live workflow YAML edits
- Citeable science VOI / overnight grids
- Merging to parent/integration branches

## Next free after Autopilot

Tickets **T-102+**; ADRs **0113+** (unless parallel streams claim first).
