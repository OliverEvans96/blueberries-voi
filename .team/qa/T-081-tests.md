# T-081 RED map — Day-indexed controllers (CAL-A3)

## Coverage of acceptance criteria

- `damped_sw` uses `OrderSchedule.protection_days(day)` (or injected callable)
  instead of scalar `PROTECTION_DEMAND_DAYS=2` on order days
  → `tests/test_t081_day_indexed_controllers.py::test_damped_sw_empty_shelf_order_matches_day_indexed_protection[...]`
  — currently failing: empty-shelf order stays **72** (2-day NB quantile) on
  Sun/Tue/Thu; expected **104 / 104 / 144** for homogeneous-μ protection 3/3/4
  → `tests/test_t081_day_indexed_controllers.py::test_damped_sw_accepts_schedule_or_protection_days_callable`
  — currently failing: constructor accepts neither `schedule=` nor
  `protection_days` callable

- On Sun/Tue/Thu under the default schedule, protection lengths are 3 / 3 / 4
  → `tests/test_t081_day_indexed_controllers.py::test_damped_sw_sun_tue_thu_protection_lengths_are_3_3_4`
  — currently failing: inferred lengths stay `[2, 2, 2]` from orders
  → also locked by the parametrized empty-shelf test above (3/3/4 expected)

- Rung 0 / corrected age-blind survival weight is **day-indexed** (periodic),
  not scalar-only as the production default under CAL-01 schedule
  → `tests/test_t081_day_indexed_controllers.py::test_rung0_accepts_day_indexed_survival_weight_and_uses_day`
  — currently failing: Mapping/Callable / weekday-table construction rejected
  or ignored; no day→weight API
  → `tests/test_t081_day_indexed_controllers.py::test_rung0_cal_schedule_default_is_not_scalar_only_survival_weight`
  — currently failing: production path still exposes only float
  `mean_survival_weight` and discards `day`

- α-tuning inputs accept or compute day-indexed protection coverage;
  documented for T-083 retune
  → `tests/test_t081_day_indexed_controllers.py::test_alpha_tune_exposes_or_computes_day_indexed_protection_coverage`
  — currently failing: `_protection_demand_quantile(alpha, params)` has no
  `protection_days` / `day` / `schedule` parameter; no coverage helper
  → `tests/test_t081_day_indexed_controllers.py::test_alpha_tune_documents_day_indexed_protection_for_t083`
  — currently failing: module docs omit day-indexed / 3/3/4 / OrderSchedule
  coverage notes

- Homogeneous-μ + day-varying protection length path documented for T-084 / B4
  → `tests/test_t081_day_indexed_controllers.py::test_day_indexed_controllers_document_homogeneous_mu_path_for_b4`
  — currently failing: `damped_sw` / `rung0` / `alpha_tune` lack explicit
  homogeneous-μ + T-084/B4 upgrade wording

- Controllers do not place conceptual orders on non-order days (T-079-consistent)
  → `tests/test_t081_day_indexed_controllers.py::test_damped_sw_returns_zero_on_non_order_days[...]`
  — currently failing: Mon/Wed/Fri/Sat still order **72**
  → `tests/test_t081_day_indexed_controllers.py::test_rung0_returns_zero_on_non_order_days[...]`
  — currently failing: non-order days still order **104** (demand_target path)

- Focused tests cover SW 3/3/4 + Rung0 day-index smoke
  → covered by the tests above (qa proves RED only; ruff/mypy on production
  paths are implement / verify)

## Not covered by tests

- Exact α retune numeric targets — deferred to T-083 (spec open question)
- Heterogeneous daily μ / `draw_demand(day=)` wiring — T-082 / T-084 (out of
  scope; homogeneous μ allowed here)
- Rollout H×7 / toy DP / M2 gate retune — T-083
- Updating legacy daily `PROTECTION_DEMAND_DAYS=2` lock tests — T-083 closeout /
  guard supersession (not this ticket)

## RED proof (qa)

```text
uv run pytest tests/test_t081_day_indexed_controllers.py --no-cov
18 failed, 0 passed
```

All failures are assertion misses on missing day-indexed behaviour / docs
(not import or collection errors).
