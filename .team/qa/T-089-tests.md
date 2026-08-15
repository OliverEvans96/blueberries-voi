# T-089 test map (RED — studio ScenarioId ladder + masked day_driver)

## Commands (RED proof)

```bash
uv run pytest tests/test_t089_studio_obs_scenarios.py -q
# → 18 failed, 5 passed

cd web && npx vitest run src/studioScenarios.test.ts
# → 8 failed | 6 passed (14)
```

## Coverage of acceptance criteria

| AC (spec) | Test(s) | Expected RED failure (current tip) |
|-----------|---------|--------------------------------------|
| Chips exactly `P0\|P1\|F1\|F1s\|F2a\|F2`; no P2 under `web/src` | `web/src/studioScenarios.test.ts` chip-order + no-P2 walk | Controls still have P0/P1/P2 chips; ObsScenario still includes P2 |
| Locked title + description per id | `studioScenarios.test.ts` locked copy | Missing Books only / Shrink gun / … strings in `controls.ts` |
| TS `ScenarioId` six-rung; default P1 | `studioScenarios.test.ts` ScenarioId + DEFAULT_SIM_CONFIG | No `ScenarioId` export; still `ObsScenario = P0\|P1\|P2` (default P1 already locks green) |
| `config_dirty` until Reset; Advance does not clear | `studioScenarios.test.ts` dirty projector cases | Already green (projector stages correctly) — lock |
| `main.ts` passes staged config to `init`/`reset` | `studioScenarios.test.ts` main.ts source asserts | Still bare `adapter.init()` / `adapter.reset()` |
| `EngineSession` echoes `obs_scenario` (default P1); invalid raises | `tests/test_t089_studio_obs_scenarios.py` session applied_config / default / reset / reject | `applied_config` omits `obs_scenario`; invalid ids accepted |
| Session forwards scenario into `advance_day` | `test_engine_session_forwards_obs_scenario_into_advance_day` | Kwarg `MISSING` (not passed) |
| `advance_day` no `P1Obs`; `mask_for` + `rich_obs_from_day_log` | source AST/import tests + `test_advance_day_*` | Still constructs `P1Obs`; no `obs_scenario` kw; passes `P1Obs` to ResearchParticleFilter |
| Mask observability P0/P1/F1/F1s/F2a/F2; no invented 0/`{}` | interactive mask tests | Fail before masks (missing `obs_scenario`) or still fully observed P1Obs fields |
| HTTP/Pyodide/mock forward scenario; mock drops P2 | `studioScenarios.test.ts` adapter cases | Mock still has `scenario === "P2"` blur; HTTP/Pyodide already forward config keys when provided (may pass) |
| SCN-P2 stays Out | Python + vitest SCN-P2 guards | Mostly green (backlog/ADR/mask_for already Out); chip P2 still fails on web |
| No Ticket A chart rebin requirement | (intentionally untested) | — |

## Files

- `tests/test_t089_studio_obs_scenarios.py` — session + day_driver + mask path
- `web/src/studioScenarios.test.ts` — controls ladder/copy, main config pass, adapters, P2 ban

## Notes for implementer

- Prefer delete `ObsScenario`; rename call sites to `ScenarioId`.
- Pattern for richest DayLog: `sim/episode.py` / `sim/m2_multi_scenario.py`.
- Touch `main.ts` only to pass staged config into `init`/`reset` — do not rewrite belief charts.
- Do not reopen SCN-P2 / ADR 0022.
