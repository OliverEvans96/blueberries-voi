# T-084 RED map — CRN / VOI day-indexed demand wire (CAL-B4)

## Coverage of acceptance criteria

- VOI CRN cell / physics path passes calendar `day` into demand draws so μ(day)
  is deterministic given day + profile  
  → `tests/test_t084_crn_day_demand.py::test_crn_passes_calendar_day_into_draw_demand`
  — currently failing: `day_step` called with `day=None` (CRN omits `day=`)  
  → `…::test_crn_day_indexed_demand_matches_physics_addressed_draws` — currently
  failing: `DayLog.demand` uses constant-μ draws (`[31,26,…]`) not
  `draw_demand(..., day=)` under `PHYSICS_RUN_ID` (`[25,21,…]`)

- Demand RNG addressing remains `(root_seed, PHYSICS_RUN_ID, day, :demand)` —
  never keyed by knowledge scenario id  
  → `…::test_demand_rng_addressing_uses_physics_run_id_not_scenario` — currently
  failing: episode demands ≠ day-indexed reference (spawn bit-stability vs
  scenario-keyed id **passes**; wire to μ(day) still missing)  
  → `…::test_changing_only_scenario_label_does_not_change_demand_draws` —
  currently failing: cross-scenario identity **passes**, but sequence ≠
  day-indexed reference under profile

- Regression: two scenarios in one CRN cell produce identical `DayLog.demand`
  under the calendar profile for a multi-day episode  
  → `…::test_two_scenarios_identical_demand_sequences_under_profile` — currently
  failing: P0/P1 identity **passes**; day-indexed expected sequence **fails**
  (guards against both scenarios omitting `day=`)

- Filter MC / shared kernels that call `draw_demand` compile/run with the new
  signature (or wrappers) without scenario-keyed demand streams  
  → `…::test_observation_loglik_mc_accepts_day_kwarg` — currently failing:
  `day` absent from `observation_loglik_mc` signature  
  → `…::test_observation_loglik_mc_forwards_day_without_scenario_demand_key` —
  currently failing: same (`day` missing; blocked before forward spy)

- Changing only the scenario label does not change demand draws when root seed,
  run id, and days match  
  → covered by `test_changing_only_scenario_label_does_not_change_demand_draws`

- X-06 cadence axis remains absent from VOI sweep config (no new cadence
  dimension)  
  → `…::test_voi_sweep_has_no_cadence_axis` — **passing** (lock)  
  → `…::test_crn_cell_params_accept_demand_profile_without_cadence_knob` —
  **passing** (lock; `params=` + no cadence knob)

- Focused CRN/VOI tests pass with `--no-cov`; ruff/mypy on touched paths pass  
  → prove RED here; green + ruff/mypy are implement / verify gates

## Proven RED

```text
uv sync --all-extras --python 3.11
uv run --python 3.11 pytest tests/test_t084_crn_day_demand.py --no-cov -v
# 7 failed, 2 passed — failures are missing day= on CRN day_step /
# DayLog.demand ≠ day-indexed PHYSICS_RUN_ID reference / missing day= on
# observation_loglik_mc (not import typos or collection errors)
```

## Not covered by tests

- Exact filter-MC wrapper shape (keyword on `observation_loglik_mc` vs RichObs
  field) — tests require callable `day=` and forward into `day_step`.
- Full production VOI grid overnight regen (OOS).
- Web Snapshot (T-085) / controller M2 gate retune (T-083).
- `ruff` / `mypy` on touched paths — implement / verify role gates.
