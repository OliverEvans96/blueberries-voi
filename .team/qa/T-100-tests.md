# T-100 — acceptance criteria → tests (RED)

## Coverage of acceptance criteria

- Module `web/src/autopilotLoop.ts` exports start/stop (play/pause) API that awaits
  one `act`, applies DayDelta, schedules with `max(0, intervalMs - elapsed)`, and
  never overlaps `act` calls
  → `web/src/autopilotLoop.test.ts::createAutopilotLoop single-flight + scheduling (T-100) > exports createAutopilotLoop with play / pause / isRunning`
  — currently failing: `autopilotLoop.ts` missing (`existsSync` false)
  → `… > never starts a second act while one is in flight (single-flight)`
  — currently failing: module missing (same); once present, asserts no overlapping `act`
  → `… > schedules next tick with max(0, intervalMs - elapsed) via fake timers`
  — currently failing: module missing; once present, asserts schedule delay
  `max(0, intervalMs - elapsed)` (including clamp to `0` when elapsed > interval)
  → `… > pause clears the scheduled timer and stops further acts`
  — currently failing: module missing; once present, asserts pause stops further ticks

- Default `intervalMs` is **500** for `damped_sw` / `constant` and **1000** for
  `rollout`; user Controller interval override wins
  → `…::defaultIntervalMsForPolicy (T-100) > returns 500 for damped_sw and constant, 1000 for rollout`
  — currently failing: module missing (no `defaultIntervalMsForPolicy` export)
  → `… > uses getIntervalMs (user override) for scheduling, not a hardcoded policy default`
  — currently failing: module missing; once present, asserts schedule uses
  `getIntervalMs()` (e.g. 750) even when policy is `rollout`

- Play chrome exposes **Autopilot Play** / **Autopilot Pause**; play runs the loop;
  pause clears the timer
  → `…::Play chrome Autopilot Play/Pause (T-100) > mountPlayChrome exposes Autopilot Play and Autopilot Pause labels`
  — currently failing: `controls.ts` `mountPlayChrome` has Advance/Reset only (no
  Autopilot Play/Pause labels)
  → `… > main.ts wires createAutopilotLoop (adapter.act path, not generate autopilot)`
  — currently failing: no `createAutopilotLoop` / `autopilotLoop` import in `main.ts`
  → Pause-clears-timer behaviour covered by loop suite above

- After each successful Autopilot `act`, order slider / inputs sync via
  `day.order_qty` callback
  → `…::createAutopilotLoop pause on error / config_dirty + order sync (T-100) > invokes onTick with the applied delta so order_qty can sync`
  — currently failing: module missing; once present, asserts `onTick(delta)` with
  `day.order_qty`

- Autopilot pauses when `config_dirty` is true and when `act` rejects / throws
  → `… > pauses when isConfigDirty becomes true (no further acts)`
  — currently failing: module missing; once present, asserts no second `act` after dirty
  → `… > pauses and surfaces onError when act rejects`
  — currently failing: module missing; once present, asserts `onError`, no
  `applyDelta`, `isRunning() === false`

- Vitest covers single-flight, `max(0, intervalMs - elapsed)`, pause on error,
  pause when dirty, order sync from delta
  → Covered by the suites listed above (fake timers for scheduling / single-flight).

## Not covered by tests

- Advance-while-Autopilot-running: disable Advance **or** one manual step + pause
  — open question in spec; implementer picks one and adds Vitest. Verify in
  implement / review against the chosen UI hint.
- Full DOM interaction of Play chrome buttons (Node vitest has no jsdom) — source
  label contract + `main.ts` wiring are the RED gate; visual click-through after
  implement.
- End-to-end studio error banner text for Autopilot failures — loop calls
  `onError`; `main.ts` should route to existing `reportStudioAdapterError` (source
  wiring verify on implement).

## RED command

```bash
cd web && npx vitest run src/autopilotLoop.test.ts
```

## RED evidence (qa worktree)

```
Test Files  1 failed (1)
Tests       11 failed (11)
```

Failing for missing behaviour (`autopilotLoop.ts` absent; Play chrome / `main.ts`
Autopilot wiring absent), not import typos. Behavioral assertions (single-flight,
scheduling math, dirty/error pause, `onTick`) are gated behind module presence and
will stay RED until implement lands the API.
