# T-079 RED map — Episode / session order gate (CAL-A2)

## Coverage of acceptance criteria

- Closed-loop episode forces `order_qty == 0` on non-order days even if policy
  returns nonzero
  → `tests/test_t079_order_gate.py::test_closed_loop_forces_zero_order_on_non_order_days`
  — currently failing: applied qty still 16 on Monday (day 0); no schedule gate
  → `tests/test_t079_order_gate.py::test_closed_loop_runner_accepts_schedule_kwarg`
  — currently failing: `run_closed_loop_episode` lacks `schedule=` parameter

- On order days, policy qty passes through (Sun/Tue/Thu nonzero when asked)
  → `tests/test_t079_order_gate.py::test_closed_loop_passes_policy_qty_on_order_days`
  — **passing** today (ungated path already applies qty every day including
  order days); remains the lock once the gate zeros non-order days
  → `tests/test_t079_order_gate.py::test_advance_day_passes_order_on_order_day`
  — **passing** (Tue episode_day=1 already accepts nonzero)

- `day_step` runs every calendar day (contiguous indices + demand each day)
  → `tests/test_t079_order_gate.py::test_closed_loop_runs_day_step_every_calendar_day_with_demand`
  — **passing** (physics already daily; documents non-order days still tick)

- `day_driver` / `EngineSession` honor the same gate
  → `tests/test_t079_order_gate.py::test_advance_day_forces_zero_order_on_non_order_day`
  — currently failing: Monday `advance_day(16)` still records order_qty=16
  → `tests/test_t079_order_gate.py::test_engine_session_step_forces_zero_on_non_order_day`
  — currently failing: `EngineSession.step(16)` on day 0 still applies 16
  → `tests/test_t079_order_gate.py::test_engine_session_step_n_gates_mixed_scripted_orders`
  — currently failing: scripted nonzero on non-order days not coerced

- Open-loop / scripted sequences: **coerce to 0** on non-order days (chosen over
  reject — matches closed-loop physics gate; keeps `step_n` usable mid-horizon)
  → `tests/test_t079_order_gate.py::test_open_loop_coerces_orders_to_zero_on_non_order_days`
  — currently failing: open-loop still places base-stock qty on Monday
  → `tests/test_t079_order_gate.py::test_open_loop_may_order_on_sun_tue_thu`
  — **passing** (order days already receive stock under S=60)
  → scripted coerce also covered by
  `test_engine_session_step_n_gates_mixed_scripted_orders` (above)

- `draw_demand` / `day_step` `day=` compatibility shim (ADR 0116)
  → `tests/test_t079_order_gate.py::test_draw_demand_without_day_keeps_prior_mu`
  — **passing** (pre-T-082 signature / i.i.d. μ still works)
  → `tests/test_t079_order_gate.py::test_closed_loop_forwards_day_kw_to_day_step_when_supported`
  — currently failing: episode calls `day_step` without `day=` (recorded
  `[None, …]`); shim must forward episode day when the kwarg is accepted
  → `tests/test_t079_order_gate.py::test_advance_day_forwards_day_kw_to_day_step_when_supported`
  — currently failing: `advance_day` likewise omits `day=`

- Existing episode tests updated so they do not assume daily ordering
  → `tests/test_closed_loop_episode.py::test_constant_order_policy_scored_order_qty_case_rounded`
  — currently failing on nonzero non-order days (was daily-order assumption)
  → `tests/test_closed_loop_episode.py::test_constant_order_applies_on_burn_and_score_order_days`
  — renamed + gated; currently failing for the same reason
  → `tests/test_audit_t042_case_round.py::test_closed_loop_orders_use_nearest_not_ceil_on_disagree_band`
  — currently failing: non-order scored days still nonzero
  → `tests/test_audit_t042_case_round.py::test_closed_loop_midpoint_matches_controller_half_away`
  — currently failing: same T-079 gate expectation

## Not covered by tests

- Optional custom `OrderSchedule` on `EngineSession` init/config — spec open
  question; default `DEFAULT_ORDER_SCHEDULE` only locked here (custom schedule
  covered on closed-loop `schedule=`).
- Focused ruff/mypy green on production paths — implement / verify after gate
  lands; qa proves RED behaviour only.
- Golden `step_n([0,16,0])` fixtures already align with Mon=0 / Tue=order /
  Wed=0 and need no change for the default schedule.

## RED proof (qa)

```text
uv run pytest \
  tests/test_t079_order_gate.py \
  tests/test_closed_loop_episode.py::test_constant_order_policy_scored_order_qty_case_rounded \
  tests/test_closed_loop_episode.py::test_constant_order_applies_on_burn_and_score_order_days \
  tests/test_audit_t042_case_round.py::test_closed_loop_orders_use_nearest_not_ceil_on_disagree_band \
  tests/test_audit_t042_case_round.py::test_closed_loop_midpoint_matches_controller_half_away \
  --no-cov
14 failed, 7 passed
```

Failures are missing order gate / `schedule=` / `day=` forward (expected RED),
not collection typos. Passing cases document already-true daily physics, order-day
pass-through, and prior-μ `draw_demand` compat.
