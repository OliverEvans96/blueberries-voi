# T-126 — RED test map (all shards)

## Coverage of acceptance criteria

### AC-hatch

- `.chart-unavailable` declares `position: relative` → `web/src/react/ChartUnavailable.test.ts::".chart-unavailable rule declares position: relative so hatch absolute inset is scoped"`
- `.chart-unavailable-hatch` declares `pointer-events: none` → `web/src/react/ChartUnavailable.test.ts::".chart-unavailable-hatch rule declares pointer-events: none so overlay cannot intercept clicks"`
- `ChartUnavailable` DOM structure unchanged → `web/src/react/ChartUnavailable.test.ts::"renders unchanged DOM markers for chartSlots consumers"`

### AC-obschip

- `patchEngineState` updates `this.config.obs_scenario` from `snapshot.applied_config?.obs_scenario` → `web/src/engine/projector.obsScenarioSync.test.ts`
- `config_dirty` stays `false` when only `obs_scenario` changes → same file
- Non-`obs_scenario` keys in `applied_config` do not widen `this.config` → same file

### AC-tabs

- `ChapterTabs` exports, tablist, grouping, aria, click wiring → `web/src/react/ChapterTabs.test.ts`

### AC-refdrawer

- `ReferenceDrawer` triggers, tabs, content, `?`/Escape → `web/src/react/ReferenceDrawer.test.ts`

### AC-dayinspector

- `hoverLink.ts` `HoverPoint` + `(day, point)` signature → `web/src/hoverLink.test.ts`
- `DayInspector` null render + positioned tooltip → `web/src/react/DayInspector.test.ts`

### AC-storetabs

- `StoreChartTabs` exports, tablist, both views mounted, `hidden` toggle → `web/src/react/StoreChartTabs.test.ts`

### AC-merge

- Two-pane grid CSS, `ChapterTabs`/`ReferenceDrawer`/`StoreChartTabs` wiring, hover tooltip integration → `web/src/main.stockout.test.ts`, `web/src/sections.controller.test.ts`, `web/src/studioScenarios.test.ts`

## Not covered by tests

- Playwright click-interception regression (manual UX review only)
- `web/src/styles/*.css` partials — component/CSS-source tests assert structure only where specified
