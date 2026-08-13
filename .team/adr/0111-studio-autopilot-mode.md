# 0111. Studio Autopilot Mode: act-driven play loop + Controller section

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: *(studio)*
GROUP: ENG
PROVENANCE: Studio Autopilot Mode Wave 0 (T-091)
TIER: 1
MILESTONE: Studio Autopilot Mode

## Context

The Vite+D3 studio (`web/`) already advances one sim day via manual **Advance**
(`adapter.step(order_qty)` → Snapshot/DayDelta → ViewModelProjector). Operators
want an **Autopilot** mode that repeatedly asks the engine for the next order
(`adapter.act`) at interactive wall-clock cadence, while exposing policy and
budget knobs in a **Controller** section with order charts — without inventing a
second presentation path or mapping every physics slider into `ModelParams`.

`EngineSession._select_order` today understands `constant` / `rollout` only, and
rollout’s base policy is `ConstantOrderPolicy(0)` — not the M2 damped
survival-weighted family (ADR [0058](./0058-ctl-01-base-policy-family.md)).
`ActOpts` on the TS side is still `Record<string, unknown>`. MockAdapter has no
real `act`. An old `autopilot` flag inside `web/src/mock/generate.ts` `runDay`
implements a base-stock heuristic in-process; that path must not become Autopilot
Mode.

Plan IDs T-076–T-081 / ADR 0109 were already taken (CAL-01 calendar realism;
ADR 0109–0110 on `main`). This milestone uses **T-091–T-096** and **ADR 0111**.

## Decision

We will:

1. **Keep decision = order quantity for one sim day** (ADR
   [0004](./0004-x-04-controller-action-space.md)). Autopilot never adds cull /
   markdown / sequencing actions.
2. **Drive Autopilot exclusively through `adapter.act` → DayDelta → existing
   projector / charts**, identical to manual Advance after the delta lands. Do
   **not** revive or extend `generate.ts` `runDay(..., autopilot)` as the product
   path (that flag remains a mock-internal heuristic; Autopilot Mode supersedes
   it for UI play).
3. **Policy names (locked aliases):**
   - Default: `damped_sw` (aliases `sw`) → `DampedSurvivalWeightedPolicy`
   - `rollout` (aliases `ctl`, `rollout_order`) → `rollout_order` with base =
     `DampedSurvivalWeightedPolicy` (M2-aligned), **not** `ConstantOrderPolicy(0)`
   - `constant` (aliases `const`, `fixed`) → `ConstantOrderPolicy`
4. **Budgets / knobs** pass through existing `act(..., **budget_overrides)` /
   ASGI `budgets` dict. Locked knobs: `alpha` (required for damped_sw / rollout
   base; studio default **0.9** when omitted), `rho` (default **0.8**), plus
   existing DEMO_BUDGETS fields `H`, `n_rollout_paths`, `candidate_case_radius`,
   `n_particles`. Constant may use `order_qty` / `q`.
5. **Wall-clock cadence:** target **1–2** `act` calls per second. Single-flight
   loop: `await act` → apply delta → schedule next with
   `max(0, intervalMs - elapsed)`; **never** overlap RPCs. Default intervals:
   **500 ms** for `damped_sw` / `constant`; **1000 ms** for `rollout`.
6. **UI ownership:** new studio section id `controller` (nav key **8**) owns
   policy chips, alpha/rho, rollout budgets, interval, and order chart(s);
   Play chrome owns Autopilot Play/Pause. JS continues to own presentation
   economics / ViewModel (ADR 0100 ownership split as updated by later ADRs).
7. **Typed `ActOpts`** on the TS boundary; HttpAdapter nests `policy` +
   `budgets`; PyodideAdapter flattens the same logical fields into the worker
   `act` call. MockAdapter implements `act` with a documented UI heuristic
   (≠ Python rollout numeric parity).

## Alternatives considered

- **Reuse `generate.ts` autopilot base-stock in the Play loop** — rejected:
  bypasses Python / Pyodide / HTTP controller surface and diverges from
  Snapshot/DayDelta `act` contract.
- **Decide-only peek RPC (return order without advancing)** — rejected for this
  milestone: Autopilot needs closed-loop days; peek adds API surface without
  shipping Play.
- **Keep rollout base as `ConstantOrderPolicy(0)`** — rejected: contradicts
  ADR 0058 / M2 (rollout wraps damped SW).
- **Map ModelParams from every studio slider on each act** — rejected: out of
  scope; config still applies on Reset/init only for physics.
- **Overlapping concurrent `act` RPCs for “faster” play** — rejected: races
  session state and projector history; single-flight is mandatory.
- **Reuse ticket ids T-076–T-081 / ADR 0109** — rejected: already claimed by
  CAL-01 and landed belief/scenario ADRs on `main`.

## Consequences

**Easy:** Autopilot and manual Advance share one delta → ViewModel path;
Controller knobs map cleanly onto existing `act` / ASGI budgets; M2 damped SW
becomes the interactive default base.

**Hard / cost:** Mock `act` will not match Python rollout; operators must not
treat mock Autopilot as citeable control performance. Interval defaults may feel
slow under heavy rollout budgets — dial DEMO_BUDGETS, not overlapping RPCs.

**Locked in:** policy alias set; cadence algorithm and default intervals;
`ActOpts` nesting rules; Controller section ownership; Autopilot = `adapter.act`
only; ticket/ADR remap T-091–T-096 / 0111.

**Non-goals (this milestone):** ModelParams-from-sliders mapping; decide-only
peek; Rung-0 on `act`; merge to `main`; live `.github/workflows/` edits.

**Revisit if:** interactive rollout latency routinely exceeds ~1 s under dialed
DEMO_BUDGETS — then reconsider budgets or a decide-only peek, not concurrency.

**Depends on:** ADR [0004](./0004-x-04-controller-action-space.md),
[0058](./0058-ctl-01-base-policy-family.md),
[0100](./0100-simulator-export-contract.md) (ownership / DayDelta),
[0102](./0102-eng-01-api-asgi-session.md) (`act` route).
