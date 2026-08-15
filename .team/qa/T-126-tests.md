# T-126 — QA RED map (obschip shard)

## Coverage of acceptance criteria

### AC-obschip

- `patchEngineState` updates `this.config.obs_scenario` from `snapshot.applied_config?.obs_scenario` before returning ViewModel → `web/src/engine/projector.obsScenarioSync.test.ts::returned ViewModel.config.obs_scenario reflects applied_config after P0 → F2` — currently failing: `patchEngineState` merges `applied_config` into `appliedConfig` only; `this.config.obs_scenario` stays at the prior value (`"P0"`), so returned `vm.config.obs_scenario` is `"P0"` not `"F2"`.
- Second rung transition (P1 → F1s) → `web/src/engine/projector.obsScenarioSync.test.ts::returned ViewModel.config.obs_scenario reflects applied_config after P1 → F1s` — currently failing: same root cause (`"P1"` stale on returned ViewModel).
- `config_dirty` stays `false` when only `obs_scenario` changes via `patchEngineState` → `web/src/engine/projector.obsScenarioSync.test.ts::obs_scenario switch via patchEngineState alone does not set config_dirty` — currently failing: assertion on `vm.config.obs_scenario === "F2"` fails before `config_dirty` is reached (would pass on dirty flag once obs sync lands; `configsEqual` already excludes `obs_scenario`).
- `patchEngineState` does not widen `this.config` for non-`obs_scenario` keys in `applied_config` → `web/src/engine/projector.obsScenarioSync.test.ts::patchEngineState syncs only obs_scenario to config, not other applied_config keys` — currently failing: `vm.config.obs_scenario` assertion (`"F2"`) fails; `case_size` non-widening assertion passes on current code.

## Not covered by tests

- AC-hatch, AC-tabs, AC-refdrawer, AC-dayinspector, AC-storetabs, AC-merge, AC-verify — out of scope for this qa worktree (obschip shard only).

## Field names asserted

| Surface | Field |
|---------|-------|
| Patch input | `snapshot.applied_config.obs_scenario` (`Partial<SimConfig>` on `Snapshot.applied_config`) |
| Patch return | `ViewModel.config.obs_scenario` (`SimConfig.obs_scenario`, type `ScenarioId`) |
| Dirty flag | `ViewModel.config_dirty` |
