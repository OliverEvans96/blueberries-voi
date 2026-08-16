# T-127 tuning-dock implement handoff (wave 1, round 2)

**Branch:** `team/T-127/tuning-dock-implement`  
**Role:** implement (tuning-dock shard)

## data-section rename (critical fix)

Renamed legacy control blocks to match `StudioLayout.tsx` / `studioLogic.ts` tuning-dock tabs and `STUDIO_SECTIONS[].controlSection`:

| Legacy | New |
|--------|-----|
| `play` | removed — seed/window moved into `demand` block |
| `belief` | `observation` |
| `controller` | `autopilot` |

**Verification:** `web/src/controls.test.ts` mounts `mountSectionControlsDom`, calls `showSection()` for each tuning-dock tab (`demand`, `observation`, `arrival`, `physics`, `logistics`, `autopilot`), and asserts exactly one matching `.controls-block` is visible (not hidden) per tab. Source assertions confirm legacy ids are absent and new ids are present.

## New controls / fields

| Section | Change |
|---------|--------|
| **Demand** | Moved `sigma` (picking variability) from Physics; inline D3 chart via `renderPickingVariability()` mirroring `picking_weights_f`; read-only “next few days” projected μ from `demand_summary` + `episodeDay` (`projectedDemandDays`); seed/window sliders retained here |
| **Physics** | Removed `sigma`; added read-only note that gamma shape is not separately tunable post f-native migration |
| **Arrival** | Scenario dim/hide for `f2a_transit_sd` (F2a show) and `sensor_sigma` (F2 show) via `syncControlAvailability()` + existing `scenarioAvailability.ts` rules |
| **Logistics** | Added `lead_time` slider (0–7 days, Reset tier); read-only delivery/order weekday display from `ScheduleWire` |
| **Autopilot** | Replaced separate α/ρ range sliders with SVG 2D drag-pad (`#alpha-rho-pad`); policy chips remain `damped_sw` / `rollout` / `constant` only (comment: `base_stock` policy blocked on backend) |

## Supporting modules

- `web/src/charts/demandDist.ts`: `pickingWeightsF`, `pickingWeightCurve`, `renderPickingVariability`, `projectedDemandDays`, `formatWeekdayList`
- `web/src/paramLabels.ts`: `lead_time` label
- `web/src/scenarioAvailability.ts`: `lead_time` in `ALL_CONTROL_IDS`

## ViewModel / types gaps

- **None blocking.** `ControlsState` now carries `demand_summary` from `controlsFromVm(vm, …)` which reads `ViewModel.demand_summary` (already on `types.ts`). Schedule weekdays use `ControlsState.schedule` (`ScheduleWire`). No edits to `types.ts` or `studioLogic.ts` in this shard.

## Tests updated / added

- `web/src/controls.test.ts` (new)
- `web/src/charts/demandDist.test.ts` (new)
- `web/src/sections.autopilot.test.ts` (autopilot block + alpha-rho pad)
- `web/src/react/DecisionRail.test.ts` (`observation` selector)

## Verify

```bash
cd web && npm run test   # 48 files, 349 passed
cd web && npm run build  # tsc + vite build OK
```
