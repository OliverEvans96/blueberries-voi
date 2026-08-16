# Wave 1 verify (T-009 + T-010)

DATE: 2026-08-12
STATUS: FAIL

Full AGENTS.md toolchain is **not** clean. Wave 1 **scope** (mission definition) is met:
T-009/T-010 tests pass; `mypy src tests` and `ruff` on `src`/`tests` are green; full-suite
coverage ≥80% when measured. Blockers are **out of wave** (experiments lint; T-011 RED tests).

## Commands run

| Command | Exit | Result |
| --- | ---: | --- |
| `uv sync --all-extras` | 0 | Resolved/checked 119 packages |
| `uv run ruff check .` | 1 | 7 errors, all in `experiments/fil11_a_scenarios.py` (E501×2, RUF001×5) |
| `uv run ruff format --check .` | 1 | 1 file would be reformatted: `experiments/fil11_a_scenarios.py` |
| `uv run mypy src tests` | 0 | Success: no issues in 26 source files |
| `uv run pytest` | 1 | **9 failed**, 67 passed; coverage **86.02%** (≥80%) |

### Scoped checks (Wave 1 definition)

| Command | Exit | Result |
| --- | ---: | --- |
| `uv run ruff check src tests` | 0 | All checks passed |
| `uv run ruff format --check src tests` | 0 | 26 files already formatted |
| `uv run pytest tests/test_sim.py tests/test_rich_obs.py` | * | **25 passed** (exit 1 only from subset coverage fail-under=80 at 53.6%; all Wave 1 tests green) |

In the full suite, `tests/test_sim.py` (10) and `tests/test_rich_obs.py` (15) all passed.

## Failures / blockers (out of Wave 1)

1. **`experiments/fil11_a_scenarios.py` (pre-existing)** — RUF001 ambiguous unicode (`σ`, `×`) and E501 / format drift. Not under `src`/`tests`. Do not weaken ruff config. Tracked in `.team/backlog.md`.
2. **`tests/test_mc_likelihood.py` (T-011 RED)** — 9 failures: missing `observation_loglik_mc`, soft-LL symbols still in `_particle_filter_update`, UNOBSERVED waste still scored like zero. Expected until T-011 lands; not Wave 1 scope.

## Coverage

Full `uv run pytest`: **86.02%** total (required ≥80%). Gate number met; suite still red on T-011.

## Acceptance criteria — T-009

- [x] Per-lot `sales_by_lot` / `waste_by_lot` on `DayLog` — `tests/test_sim.py::test_daylog_sales_waste_by_lot_maps`
- [x] Live lots keep `n`, `tau`, `lot_id` — `test_daylog_lots_keep_n_tau_lot_id`
- [x] Delivery `age_at_receipt` / `pack_date`; non-delivery `None` — `test_daylog_receipt_metadata_delivery_vs_none`
- [x] Totals == sum(by-lot maps); empty when zero — `test_daylog_totals_match_by_lot_sums`
- [x] CRN scored aggregates stable — `test_daylog_crn_scored_aggregates_stable`
- [x] Shared `model.day_step` (ENG-02) — `test_sim_shares_day_step`
- [ ] Full repo `ruff check .` / `pytest` green — **blocked** by experiments + T-011 (src/tests ruff + mypy green; W1 tests pass; coverage 86%)

## Acceptance criteria — T-010

- [x] Frozen `RichObs` required fields — `tests/test_rich_obs.py::test_rich_obs_is_frozen_dataclass_with_required_fields`
- [x] `UNOBSERVED` / `is_unobserved` — `test_unobserved_sentinel_distinct_from_zero_none_empty`
- [x] `ObsMask.apply` → `UNOBSERVED` not `0`/`{}` — `test_obs_mask_apply_sets_absent_fields_to_unobserved_never_zero_or_empty`
- [x] `mask_for` P0–F2 + P0/P1 waste — parametrized + `test_mask_for_p0_hides_waste_total_p1_presents_it`
- [x] P0 + waste=0 → `UNOBSERVED` — `test_p0_mask_turns_observed_zero_waste_into_unobserved`
- [x] `rich_obs_from_day_log` — project + no invented delivery metadata tests
- [x] `ResearchParticleFilter.step` accepts `RichObs` — `test_particle_filter_step_type_boundary_accepts_rich_obs`
- [x] B-state not a fabricating mask — `test_mask_for_rejects_b_state_scenario`
- [ ] Quality gates green (`ruff` / `mypy` / `pytest` ≥80%) — **partial**: mypy green; src/tests ruff green; coverage 86%; full `ruff check .` and full pytest still fail (out-of-wave)

## Incomplete

- Full-repo AGENTS.md green blocked by experiments lint/format and T-011 RED suite.
- Wave 1 behavioural work for T-009/T-010 is demonstrably working under scoped gates.

## Verdict summary

| Gate | Result |
| --- | --- |
| Wave 1 definition (T-009/T-010 tests + mypy + ruff on src/tests) | **PASS** |
| Full AGENTS.md toolchain (all listed commands exit 0) | **FAIL** |
| Coverage ≥80% (full suite measurement) | **PASS** (86.02%) |
