# T-086 RED map — Next-order-day UI via step_n (CAL-C2)

## Coverage of acceptance criteria

- Primary play / advance advances to the **next order day** (strictly after
  current) via `step_n` with `order_qty=0` on intervening non-order days and a
  real order on the target  
  → `web/src/engine/nextOrderDayUi.test.ts` › main.ts primary onAdvance calls
  adapter.step_n — currently failing: `onAdvance` still uses `adapter.step`  
  → `…` › play chrome primary button labels next-order-day advance — currently
  failing: button still reads `Advance day`  
  → `web/src/calendar/nextOrderAdvance.test.ts` › buildStepNOrders from Monday /
  zeros intervening / from Friday / strictly after today — currently failing:
  no `nextOrderAdvance` helper module  
  → `web/src/engine/studioWiring.test.ts` › Advance / Reset / bootstrap go
  through adapter.step_n (primary) — currently failing: main has no `step_n`
  (guard supersession from T-057 `adapter.step`)

- Optional single-day step remains available for debugging if cheap; if omitted,
  document why  
  → `…/nextOrderDayUi.test.ts` › optional single-day step remains available or
  is documented as omitted — currently failing: no debug single-day control and
  no `.team/qa/T-086-smoke.md` omission note

- UI shows weekday labels derived from epoch `2024-01-01` + episode day  
  → `…/nextOrderAdvance.test.ts` › weekdayLabel derives Mon..Sun from epoch —
  currently failing: missing helper  
  → `…/nextOrderDayUi.test.ts` › play chrome / main surfaces weekday labels —
  currently failing: no weekdayLabel / epoch wiring in controls or main

- UI surfaces next delivery / pipeline hint consistent with LT=1  
  → `…/nextOrderAdvance.test.ts` › pipelineDeliveryHint surfaces next-day
  delivery — currently failing: missing helper  
  → `…/nextOrderDayUi.test.ts` › UI surfaces next delivery / pipeline hint —
  currently failing: no pipelineDeliveryHint / delivery-hint chrome

- Mock mode exercises the same advance semantics without a live wheel  
  → `…/nextOrderDayUi.test.ts` › MockAdapter init exposes schedule stubs —
  **passing** (T-085 stubs present)  
  → `…` › mock adapter step_n with zeros-then-qty advances episode_day —
  **passing** (adapter already supports batched steps)  
  → `…` › studio mock path builds step_n orders — currently failing: main has
  no `step_n` / schedule wiring  
  → `…` › advance helper + MockAdapter.step_n receives padded orders —
  currently failing: helper module missing

- Manual or automated UI/smoke check recorded proving advance skips non-order
  days  
  → `…/nextOrderDayUi.test.ts` › records a dedicated smoke note — currently
  failing: no `.team/qa/T-086-smoke.md`  
  → Unit proofs in `nextOrderAdvance.test.ts` (zeros-on-skip vectors) once the
  helper lands

- Does not redefine OrderSchedule math in JS beyond consuming Snapshot schedule
  fields (ADR 0114)  
  → `…/nextOrderAdvance.test.ts` › helpers consume schedule.order_weekdays /
  epoch — currently failing: helper source missing (will assert no
  `protection_days` once present)  
  → `…/nextOrderDayUi.test.ts` › does not redefine OrderSchedule math —
  **passing** on current controls/main (no invented protection formula)

## Proven RED

```text
# From .worktrees/T-086-qa on team/T-086/qa
cd web && pnpm install
./node_modules/.bin/vitest run \
  src/calendar/nextOrderAdvance.test.ts \
  src/engine/nextOrderDayUi.test.ts \
  src/engine/studioWiring.test.ts
# 17 failed, 18 passed — failures are missing next-order helper, main still on
# adapter.step / "Advance day", missing weekday/pipeline chrome + T-086-smoke.md
# (assertion failures, not import typos). Passing rows are T-057 suite + mock
# schedule stubs / step_n physics already on tip.
```

## Not covered by tests

- Live Pyodide / HttpAdapter browser click-through against a wheel or ASGI
  server — because RED uses vitest source + mock unit contracts; verify via
  `.team/qa/T-086-smoke.md` after implement.
- Exact button copy / CSS class names beyond the regex contract — implement may
  choose phrasing matching `next order|order day|Advance to|Skip to`.
- Python `OrderSchedule` / `EngineSession.step_n` behaviour — already shipped;
  this ticket consumes Snapshot schedule fields in the web UI only.
- Full suite / coverage ≥80% — verifier owns CI-parity gates.
