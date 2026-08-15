# T-112 — acceptance criteria → tests (RED)

## Coverage of acceptance criteria

- After more than 14 Python `EngineSession.step` calls, Snapshot `history` and
  every DayDelta keep all days so far; `drop_oldest` is always `false`; Python
  does not pop old thin-day records
  → `tests/test_t112_episode_horizon.py::test_history_keeps_all_days_past_former_14_day_window`
  — currently failing: `drop_oldest` is `True` once the 14-day window fills
  → `…::test_default_backend_does_not_pop_old_thin_days`
  — currently failing: same (`drop_oldest` True with filter-on default backend)

- `EngineSession.step`, `act`, and `step_n` refuse when `episode_day >= 90`
  (before advancing), raising a documented error whose message mentions the
  episode end and Reset. `step_n` that would cross the cap refuses without
  applying a partial prefix
  → `…::test_step_refuses_at_episode_day_90_with_reset_message`
  — currently failing: `DID NOT RAISE ValueError` (session still advances)
  → `…::test_act_refuses_at_episode_day_90`
  — currently failing: `DID NOT RAISE ValueError`
  → `…::test_step_n_crossing_cap_refuses_without_partial_prefix`
  — currently failing: `DID NOT RAISE ValueError` (would also apply a prefix)
  → `…::test_step_allowed_on_day_89_then_refuses_at_90`
  — currently failing: first assertion is `drop_oldest` True on the 90th day
  (cap refuse is not implemented)

- Reset / init clears history and allows a new episode from day 0
  → `…::test_reset_clears_history_and_allows_new_episode_from_day_0`
  — currently failing: `DID NOT RAISE ValueError` at the cap, so the Reset
  after-horizon path is not reached (Reset/init already clear history today)
  → `…::test_init_clears_history_like_reset`
  — currently passing: `init` already wipes history (kept as a regression lock)

- JS projector and mock adapter append history and never drop until Reset; they
  do not slice to 14. `pnl_totals` and chart series use the full accumulated
  history. Ghost-vs-last-reset compares two full episodes (or the overlapping
  prefix if the previous run was shorter)
  → `web/src/engine/projector.test.ts::never drops history for drop_oldest true or a 14-day window_days cap (T-112)`
  — currently failing: history length 14, not 16
  → `web/src/engine/projector.test.ts::ghost vs last reset compares two full episodes…`
  — currently failing: ghost `days` is 14, not 20
  → `web/src/engine/episodeHorizon.test.ts::drop_oldest is always false and history grows past 14 steps`
  — currently failing: mock `drop_oldest` becomes true
  → `…::stepSimulation appends and does not slice(-window_days)`
  — currently failing: history stays at `window_days` (14)
  → `…::mock generate does not slice history to window_days`
  — currently failing: `slice(-config.window_days)` still present
  → `…::mock adapter drop_oldest is always false`
  — currently failing: still computed from `history.length >= window_days`
  → `…::projector does not slice to windowDays or drop on drop_oldest`
  — currently failing: projector still slices and honours `drop_oldest`

- Studio UI: at episode day 90, Advance is disabled, Autopilot pauses (or
  refuses play), and copy tells the user the episode finished and they must
  Reset. PnL labels are episode totals, not “Window …”
  → `…::PnL labels are episode totals, not Window …`
  — currently failing: `pnlTotals.ts` still says “Window revenue/cost/profit”
  → `…::at day 90 Advance is disabled and copy tells the user to Reset`
  — currently failing: no episode-complete / day-90 disable in `controls.ts` /
  `main.ts`
  → `…::Autopilot pauses or refuses play at episode day 90`
  — currently failing: no `90` / horizon guard in Autopilot wiring

- `window_days` is no longer a user-facing rolling chart knob (default/cap is
  episode length 90). Existing 14-day drop tests updated in this ticket
  → `…::DEFAULT_SIM_CONFIG.window_days is episode length 90…`
  — currently failing: default is still `14`
  → `…::controls has no user-facing window_days rolling chart knob`
  — currently passing: `CONFIG_SLIDERS` already omits `window_days`
  → projector rolling-window test superseded (see above)

- DayDelta still includes the `drop_oldest` key (always false)
  → asserted on every Python DayDelta in the T-112 session tests (`"drop_oldest"
  in delta` and `is False`). ADR 0100 schema tests in
  `tests/test_simulator_schema.py` are unchanged and still require the key.

## Not covered by tests

- Rust/wasm session cap — out of scope (spec / ADR 0122).
- Visual click-through of disabled Advance / Autopilot Pause at day 90 — Node
  vitest has no jsdom; source-scan + Python refuse are the RED gate.
- Per-rung caches / `set_obs_scenario` — out of scope.
- Other SimConfig knobs remaining dirty-until-Reset — already locked by T-089
  (`studioScenarios.test.ts`); not re-specified here.

## RED command

```bash
uv run --python 3.11 pytest tests/test_t112_episode_horizon.py --no-cov
cd web && npx vitest run src/engine/episodeHorizon.test.ts src/engine/projector.test.ts
```

## RED evidence (qa worktree)

Python (`7 failed, 1 passed`):

- `test_history_keeps_all_days_past_former_14_day_window` — `drop_oldest` True
- `test_default_backend_does_not_pop_old_thin_days` — `drop_oldest` True
- `test_step_refuses_at_episode_day_90_with_reset_message` — no ValueError
- `test_act_refuses_at_episode_day_90` — no ValueError
- `test_step_n_crossing_cap_refuses_without_partial_prefix` — no ValueError
- `test_step_allowed_on_day_89_then_refuses_at_90` — `drop_oldest` True
- `test_reset_clears_history_and_allows_new_episode_from_day_0` — no ValueError at cap
- `test_init_clears_history_like_reset` — passed (existing init wipe)

Vitest (`11 failed` across the two files, plus pre-existing projector tests still green):

Failures listed in the mapping above. They fail for missing horizon behaviour
(rolling 14-day drop still present; no day-90 refuse/UI copy), not import typos.
