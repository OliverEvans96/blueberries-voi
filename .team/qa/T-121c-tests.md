# T-121c QA — RED test map (calendar demand / Wave C)

Track **C1** (`DemandProfile::mu`) and **C3** (session calendar wire). Rust unit tests
for C2 `draw_demand` and JSON `from_json` live in `voi_core` (implementer).

## Coverage of acceptance criteria

### C1 — μ(day) goldens vs Python

- Golden day 0 → `tests/test_rust_calendar_demand.py::test_rust_demand_profile_mu_matches_python_golden[0]` — currently failing: no PyO3 `demand_profile_mu_py` / `DemandProfile.from_json`
- Golden day 6 → `::test_rust_demand_profile_mu_matches_python_golden[6]` — currently failing: Rust μ export missing
- Golden day 7 → `::test_rust_demand_profile_mu_matches_python_golden[7]` — currently failing: Rust μ export missing
- Golden day 13 → `::test_rust_demand_profile_mu_matches_python_golden[13]` — currently failing: Rust μ export missing
- Golden day 89 → `::test_rust_demand_profile_mu_matches_python_golden[89]` — currently failing: Rust μ export missing

Reference: `src/blueberries_voi/model/demand_profile.py` and `data/freshnet/demand_profile.json`.

### C3 — 90-day rust-backend session calendar demand ≠ flat μ=30

- Rust session mean tracks Python calendar reference (not flat μ=30) → `tests/test_rust_calendar_demand.py::test_rust_90day_session_mean_demand_tracks_calendar_not_flat_mu` — currently failing: Rust session uses flat `demand_mu` physics (mean diverges from calendar reference by >1.0)

## Not covered by tests

- **C2** `draw_demand(rng, params, day)` + `ModelParams.demand_profile` — Rust unit tests in `physics.rs` / `day_step.rs`
- **C3** `demand_summary_wire` DOW factor parity — implementer Rust tests + optional wire test
- **C4** VOI CRN calendar in `run_voi_crn_cell` — Wave D / separate track

## RED proof command

```bash
uv sync --all-extras --python 3.11
cd crates/voi_py && uv run maturin develop --release
uv run pytest tests/test_rust_calendar_demand.py --no-cov -v
```

Expected: C1 pytest.fail on missing PyO3 μ surface; C3 assertion `rust_mean` vs calendar reference.
