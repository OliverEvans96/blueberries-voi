STATUS: PASS

## Commands run
- `uv sync --all-extras` → exit 0, installed blueberries-voi + 118 deps in worktree `.venv`
- `uv run ruff check .` → exit 0, all checks passed
- `uv run ruff format --check .` → exit 0, 109 files already formatted
- `uv run mypy src tests` → exit 0, no issues in 83 source files
- `uv run pytest` → exit 0, 535 passed, 1 skipped, coverage 88.15% (≥80%)
- `uv run pytest tests/test_simulator_schema.py -q --no-cov` → exit 0, 23 passed
- `uv run python` golden load + `validate_snapshot` / `validate_day_delta` → exit 0, L=2 K=4 flat lengths OK

## Acceptance criteria
- [x] Golden JSON fixtures for at least one Snapshot and one DayDelta under a documented path — `tests/fixtures/simulator/{snapshot_seed42,day_delta_seed42_step0,step_n_seed42}.json` + README; confirmed by file presence and schema tests
- [x] Schema tests load fixtures and assert required keys (`seq`, `episode_day`, flat `belief` on Snapshot; DayDelta `day` + `drop_oldest`) — `tests/test_simulator_schema.py` (23 passed)
- [x] Schema tests assert absence of forbidden presentation keys — same suite + validators in `blueberries_voi.simulator.schema`
- [x] Live `EngineSession` under fixed seed validates via same schema helpers — live init/step tests in `test_simulator_schema.py` passed under full pytest
- [x] Flat belief: `len(age_marginals)==L*K`, `len(lot_counts)==L`, `len(tau_grid)==K` on goldens and live output — schema tests + manual golden check (L=2, K=4, age_marginals=8)
- [x] `uv run pytest` passes — 535 passed, 1 skipped (unrelated optional ResearchParticleFilter aux), coverage gate met

## Incomplete
- (none)
