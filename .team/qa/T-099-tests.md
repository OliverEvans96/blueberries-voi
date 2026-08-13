# T-099 — acceptance criteria → tests (RED)

## Coverage of acceptance criteria

- `web/src/sections.ts` includes section `id: "controller"`, label “Controller”,
  **8th** entry in `STUDIO_SECTIONS` (nav key 8)
  → `web/src/sections.controller.test.ts::Controller section registration (T-099) > STUDIO_SECTIONS has controller as the 8th entry (nav key 8)`
  — currently failing: `STUDIO_SECTIONS` length is `7` (no controller entry)

- `SectionId` union includes `"controller"`; `loadSection` / `saveSection` accept it;
  Belief and other sections remain intact
  → `… > SectionId union in sections.ts includes controller`
  — currently failing: `SectionId` type block has no `| "controller"`
  → `… > loadSection / saveSection accept controller and round-trip`
  — currently failing: after `saveSection("controller")`, `loadSection()` returns
  `"play"` (id not present in `STUDIO_SECTIONS`)
  → `… > Belief and earlier sections remain intact at their indices`
  — currently **passing** (regression guard: play @0, belief @6 with existing plotIds)

- Controller controls expose policy chips (`damped_sw` / `rollout` / `constant`),
  `alpha` / `rho`, rollout budgets (`H`, `n_rollout_paths`, `candidate_case_radius`,
  `n_particles`), and interval (ms)
  → `…::Controller controls (T-099) > controls.ts mounts a controller block with policy / alpha / rho / budgets / interval`
  — currently failing: no `data-section="controller"` (and thus no policy /
  numeric / interval controls) in `controls.ts`

- Chart module `web/src/charts/controllerOrders.ts` renders order quantity over
  episode days from history (`day.order_qty`)
  → `…::Controller chart wiring (T-099) > ships controllerOrders chart module`
  — currently failing: `controllerOrders.ts` missing (`existsSync` false)
  → `web/src/charts/controllerOrders.test.ts::controllerOrders series helper (T-099) > controllerOrdersSeries maps day.order_qty from sample history`
  — currently failing: module missing (same); once present, asserts
  `controllerOrdersSeries` maps sample `{day, order_qty}` history
  → `… > exports renderControllerOrders for plot mount`
  — currently failing: module missing; once present, asserts
  `renderControllerOrders` is a function

- Controller `plotIds` include controller orders plot id and reuse `plot-inventory`
  → `… > controller plotIds include orders plot and reuse plot-inventory`
  — currently failing: no controller section (`find` undefined)

- `web/src/main.ts` mounts the controller chart when that plot is visible and wires
  control changes into studio state
  → `… > main.ts mounts controller orders when that plot is visible`
  — currently failing: no `controllerOrders` / `renderControllerOrders`, no
  `data-plot="plot-controller-orders"`, no `plotVisible("plot-controller-orders")`
  Control→state wiring is covered by the controls source contract (mount block +
  input ids); full callback wiring is implement / visual verify (no jsdom).

- Vitest covers section registration and at least one chart helper / mount smoke
  → Covered by the section registration suite + `controllerOrdersSeries` sample
  history test above.

## Not covered by tests

- Exact default numeric values for budgets / alpha=0.9 / rho=0.8 / intervalMs=500
  (and rollout→1000 defaulting) — recommended in ADR/spec; T-100 may own interval
  defaulting. Verify on implement or T-100.
- Full D3 pixel layout of the orders chart — Node vitest has no jsdom; series helper
  + module / `main.ts` source contracts are the RED gate.
- ActOpts / Autopilot play loop — out of scope (T-098 / T-100).

## RED command

```bash
cd web && npx vitest run src/sections.controller.test.ts src/charts/controllerOrders.test.ts
```

## RED evidence (qa worktree)

```
Test Files  2 failed (2)
Tests       9 failed | 1 passed (10)
```

Failing for missing behaviour (section / controls / chart / main wiring), not
import typos. The one pass is the Belief regression guard.
