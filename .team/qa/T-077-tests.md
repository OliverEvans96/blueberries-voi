# T-077 RED map — OrderSchedule API (CAL-A1)

## Coverage of acceptance criteria

- Frozen `OrderSchedule` importable from Track A module (`sim/` or `controller/`) with
  defaults `delivery_weekdays={0,2,4}`, `lead_time_days=1`, `order_weekdays={6,1,3}`
  → `tests/test_order_schedule.py::test_order_schedule_module_is_importable` — currently
  failing: missing `blueberries_voi.sim.order_schedule` /
  `blueberries_voi.controller.order_schedule`
  → `tests/test_order_schedule.py::test_order_schedule_type_is_frozen_dataclass` — currently
  failing: same missing module
  → `tests/test_order_schedule.py::test_default_order_schedule_mwf_lt1_order_days` —
  currently failing: missing `DEFAULT_ORDER_SCHEDULE`
  → `tests/test_order_schedule.py::test_order_schedule_constructor_defaults_match_base_case`
  — currently failing: missing `OrderSchedule`
  → `tests/test_order_schedule.py::test_order_schedule_module_lives_under_track_a` —
  currently failing: missing module under `sim/` or `controller/`

- `can_order(day)` True exactly when epoch weekday ∈ `{6,1,3}` for days 0..20
  → `tests/test_order_schedule.py::test_can_order_matches_epoch_weekdays_over_multi_week_range`
  — currently failing: missing `OrderSchedule` / `can_order`

- `protection_days` == 3 / 3 / 4 on Sun / Tue / Thu order days
  → `tests/test_order_schedule.py::test_protection_days_sun_tue_thu[...]` (6 parametrized
  cases) — currently failing: missing `protection_days`

- `next_order_day(day)` = smallest `d > day` with `can_order(d)` (strictly after);
  Monday → following Tuesday
  → `tests/test_order_schedule.py::test_next_order_day_strictly_after_monday_lands_on_tuesday`
  — currently failing: missing `next_order_day`
  → `tests/test_order_schedule.py::test_next_order_day_from_order_day_skips_today` —
  currently failing: same
  → `tests/test_order_schedule.py::test_next_order_day_is_smallest_strict_successor` —
  currently failing: same

- `can_order` False on Mon/Wed/Fri (delivery under LT=1) and Saturday
  → `tests/test_order_schedule.py::test_can_order_false_on_delivery_days_and_saturday[...]`
  (8 parametrized cases) — currently failing: missing `can_order`

- Unit tests fail if epoch weekday alignment drifts (day 0 = Monday 2024-01-01)
  → `tests/test_order_schedule.py::test_epoch_day_zero_is_monday_2024_01_01` — **passing**
  (calendar pin independent of production code)
  → `tests/test_order_schedule.py::test_order_schedule_uses_epoch_monday_alignment` —
  currently failing: missing schedule; will fail on epoch drift once implemented

- Public exports expose `OrderSchedule` without importing HF / `datasets` / web
  → `tests/test_order_schedule.py::test_order_schedule_exported_on_package_all_or_documented_module`
  — currently failing: missing export surface
  → `tests/test_order_schedule.py::test_importing_order_schedule_does_not_load_hf_or_web`
  — currently failing: missing module (AST / `sys.modules` guard once present)

## Not covered by tests

- `uv run ruff check` and `uv run mypy` on touched paths pass; focused pytest green
  with `--no-cov` — verifier / implement green gate after production code lands; prove
  RED here with missing API, not by asserting toolchain.

## RED proof (qa)

```text
uv run pytest tests/test_order_schedule.py --no-cov
26 failed, 1 passed
```

Failures are missing `order_schedule` module / API (expected RED), not collection typos.
