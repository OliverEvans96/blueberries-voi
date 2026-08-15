# T-121c — RED test map (Wave C calendar demand)

Track **C1** (`DemandProfile::mu`), **C3** (session calendar wire), and **C4** (VOI CRN
calendar wire). Rust unit tests for C2 `draw_demand` and JSON `from_json` live in
`voi_core` (implementer).

## Coverage of acceptance criteria

### C1 — μ(day) goldens vs Python (`demand_profile_mu_from_json_py`)

- Golden day 0 → `tests/test_rust_calendar_demand.py::test_rust_demand_profile_mu_from_json_matches_python[0]` — failing: PyO3 export missing
- Golden day 6 → `::test_rust_demand_profile_mu_from_json_matches_python[6]` — failing: PyO3 export missing
- Golden day 7 → `::test_rust_demand_profile_mu_from_json_matches_python[7]` — failing: PyO3 export missing
- Golden day 13 → `::test_rust_demand_profile_mu_from_json_matches_python[13]` — failing: PyO3 export missing
- Golden day 89 → `::test_rust_demand_profile_mu_from_json_matches_python[89]` — failing: PyO3 export missing

Reference: `src/blueberries_voi/model/demand_profile.py` and `data/freshnet/demand_profile.json`.

### C3 — 90-day rust-backend `EngineSession` with profile in config vs flat

- Profile vs flat mean demand differs by >1.0 cases/day → `tests/test_rust_calendar_demand.py::test_rust_backend_session_profile_mean_differs_from_flat_by_more_than_one` — failing: Rust session ignores `demand_profile` / `demand_profile_json` config (identical series today)

### C4 — VOI CRN episode demands (profile vs flat)

- 90-day mean demand differs by >1.0 → `tests/test_rust_calendar_demand.py::test_voi_crn_episode_demands_profile_differs_from_flat` — failing: `run_voi_crn_episode_demands_py` missing and `run_voi_crn_cell_py` has no `demand_profile_json` kw

## Not covered by tests

- **C1** `DemandProfile::from_json` Rust unit tests — `cargo test -p voi_core`
- **C2** `draw_demand` day index + `ModelParams.demand_profile` — Rust units in `physics.rs` / `day_step.rs`
- **C3** `demand_summary_wire` DOW factor parity — implementer Rust + optional Python wire test

## RED proof command

```bash
cd .worktrees/T-121-c-qa
uv sync --all-extras --python 3.11
uv run maturin develop --release -m crates/voi_py/Cargo.toml
uv run pytest tests/test_rust_calendar_demand.py -o addopts= -v
```

Uses `_require_rust_core()` (pytest.fail if `_core` missing; no module-level skip).
