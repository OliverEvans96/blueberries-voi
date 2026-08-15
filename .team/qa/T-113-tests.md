# T-113 — acceptance criteria → tests (RED)

## Coverage of acceptance criteria

- After each Python `advance_day` / `EngineSession.step`, the session keeps a
  richest episode log (not a rolling drop) including totals plus `sales_by_lot`,
  `waste_by_lot`, `age_at_receipt`, and `pack_date` when those exist; Snapshot
  `history` / DayDelta `day` may stay thin
  → `tests/test_t113_obs_scenario_caches.py::test_session_keeps_richest_log_fields_after_steps`
  — currently failing: no `_richest_log` / `_episode_log` on the session
  → `…::test_snapshot_history_may_stay_thin_while_richest_log_is_separate`
  — currently failing: same (thin `_history` is not the richest log)

- `EngineSession.set_obs_scenario(id)` catch-up-steps only the selected rung:
  first select at day t initializes a new `RBPF` and steps `0…t-1`; switch-back
  steps only `last_synced+1 … now`; returns a Snapshot with
  `applied_config.obs_scenario` updated without Reset; invalid ids raise like
  `mask_for`
  → `…::test_set_obs_scenario_exists_and_returns_snapshot_without_reset`
  — currently failing: `set_obs_scenario` is missing
  → `…::test_first_select_catchup_steps_days_0_through_t_minus_1`
  — currently failing: method missing (cannot catch-up 0…t-1)
  → `…::test_switch_back_catchup_steps_only_the_gap`
  — currently failing: method missing
  → `…::test_set_obs_scenario_invalid_id_raises_like_mask_for`
  — currently failing: method missing (`P2` / `B-state` / empty / unknown)

- Catch-up vs a filter live the whole episode is CRN-stable (golden:
  replay-from-log matches never-switched)
  → `…::test_catchup_matches_never_switched_filter_crn`
  — currently failing: method missing (no catch-up belief to compare)

- `advance_day` / `act` step only the active filter; other warmed rungs fall
  behind. Reset / init / seed / physics knobs wipe the richest log and all
  per-rung caches
  → `…::test_step_and_act_advance_only_the_active_filter`
  — currently failing: cannot warm a second rung without `set_obs_scenario`
  → `…::test_reset_wipes_richest_log_and_per_rung_caches`
  — currently failing: no richest log / caches to wipe
  → `…::test_init_wipes_caches_like_reset`
  — currently failing: method missing before init wipe check

- Naive retarget of the current particles without replay remains forbidden
  (catch-up creates a distinct `RBPF`, does not mutate weights in place)
  → `…::test_set_obs_scenario_creates_a_distinct_rbpf_not_in_place_weights`
  — currently failing: method missing
  → `…::test_session_source_does_not_retarget_particle_obs_scenario_in_place`
  — currently failing: `set_obs_scenario` not in `session.py`

- HTTP FastAPI session object and Pyodide `session_rpc` forward
  `set_obs_scenario` (no new resource types)
  → `…::test_session_rpc_dispatches_set_obs_scenario`
  — currently failing: `_RPC_METHODS` is still `{init, step, step_n, reset, act}`
  → `…::test_pyodide_worker_mentions_set_obs_scenario`
  — currently failing: `worker.js` has no `set_obs_scenario`
  → `…::test_fastapi_forwards_set_obs_scenario_on_session_object`
  — currently failing: `POST /sessions/{id}/set_obs_scenario` is 404
  → `web/src/studioObsScenarioCaches.test.ts` HttpAdapter / PyodideAdapter
  — currently failing: adapters have no `setObsScenario` / `set_obs_scenario`

- Studio chips call that method (not `config_dirty` for `obs_scenario` alone).
  Catch-up shows progress / disables chips while running. Autopilot uses the
  selected rung’s belief for the next `act`; pause during catch-up then resume.
  Copy: knowledge changes what the store sees, so future orders can change
  → `web/src/studioObsScenarioCaches.test.ts` chip / copy / catch-up / Autopilot
  source-scan tests — currently failing: chips still `onConfigChange({ obs_scenario })`;
  no catch-up progress, chip disable, or store-sees copy
  → `web/src/studioScenarios.test.ts::staging obs_scenario alone does not set config_dirty`
  — currently failing: projector still treats `obs_scenario` as dirty (`true`)

- T-089 tests that required `obs_scenario` chip clicks to set `config_dirty`
  until Reset are updated in this ticket (ADR 0110 apply-path supersession)
  → `web/src/studioScenarios.test.ts` T-113 describe block replaces the old
  “staging obs_scenario sets config_dirty” tests; other knobs still dirty until
  Reset — currently failing on the new “not dirty” assertion (see above)

## Not covered by tests

- Rust/wasm `set_obs_scenario` — out of scope (later parity ticket)
- Renaming `RBPF` — out of scope
- Parallel live filters every Advance (6× step) — out of scope
- Editing `.github/workflows/` — out of scope
