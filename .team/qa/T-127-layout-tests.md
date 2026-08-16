# T-127 — RED test map (qa-layout)

## AC-layout

- Cockpit grid shell, not two-pane → `web/src/react/StudioLayout.test.ts`
- Three row regions → same file
- Row 1 Primary/Secondary always visible → same file
- Row 2 Economics/Events/Run → same file
- Row 3 tuning dock tablist + Future chip → same file
- All 14 chart ids exactly once → same file
- StoreChartTabs removed for always-on panes → same file
- Responsive breakpoints → `web/src/main.stockout.test.ts` (cockpit grid CSS)
