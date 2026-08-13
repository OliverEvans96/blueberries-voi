## Coverage of acceptance criteria

- `DEFAULT_PROFIT_COSTS = ProfitCosts(2.0, 1.5, 3.0)` + uncalibrated docs → `tests/test_audit_t043_defaults_alpha.py::test_default_profit_costs_exported_with_scaffold_values`, `::test_default_profit_costs_documented_as_uncalibrated` — currently failing: constant missing / no “uncalibrated” wording
- Production modules resolve `costs is None` to shared default (not private `_DEFAULT_COSTS`) → `::test_production_modules_use_shared_default_profit_costs[...]` (crn, m2_ladder, m2_multi_scenario, alpha_tune), `::test_voi_crn_none_costs_uses_default_profit_costs_object` — currently failing: still `_DEFAULT_COSTS = ProfitCosts(...)`
- `shipments is None` → Abdella via `load_abdella_shipments` / `default_shipments` → `::test_production_voi_crn_default_shipments_load_abdella`, `::test_m2_and_alpha_default_shipments_not_cool_fixture[...]`, `::test_default_shipments_helper_calls_abdella` — currently failing: cool `_fixture_shipments` default; no public `default_shipments`
- Public `smoke_cool_shipments` (1°C cool; no Abdella FS) → `::test_smoke_cool_shipments_returns_1c_cool_without_abdella` — currently failing: helper not importable
- Production VOI requires tuned α table; uses table α not hardcoded 0.9 → `::test_production_voi_crn_requires_tuned_alpha_table`, `::test_production_voi_crn_uses_table_alpha_not_hardcoded_0_9` — currently failing: no `alpha_table_path` on `run_voi_crn_cell`
- Smoke VOI may keep fixed α=0.9 without table → `::test_smoke_voi_allows_fixed_alpha_without_table` — currently **passing** (smoke path ungated today)

## Not covered by tests

- Exhaustive “no production-facing path names cool unless explicit” AST of every call site beyond the four modules — verify by grep at review
- `run_voi_sweep(..., smoke=False)` α gate specifically — covered via `run_voi_crn_cell` production gate; sweep wiring is implement detail (may forward `alpha_table_path`)
- Incomplete α-table (missing arms) raise — same gate family as missing file; optional deepen at implement

## Notes for implement (T-043)

- Own: `sim/profit.py`, `voi/*`, `sim/m2_ladder.py`, `sim/m2_multi_scenario.py`, `sim/alpha_tune.py` (+ shipment helper module of choice)
- Do **not** edit `sim/episode.py` `case_round` (T-042)
- Abdella tests: monkeypatch `load_abdella_shipments` or use `data/abdella/`
- Existing `tests/test_voi_crn.py` calls without α table / with implicit cool default will need updates (explicit `smoke_cool_shipments()` and/or α table for production API)
