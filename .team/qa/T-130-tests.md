# T-130 RED test map

| AC | Test file | Assertion |
|----|-----------|-----------|
| Layout v5 grid | `StudioLayout.test.ts` | `economics today events` in cockpitGrid.css; no decision-rail-host |
| Secondary chrome order | `StudioLayout.test.ts` | `#secondary-chrome-host` before `#operator-bar-host` |
| Tradeoff reactivity | `SecondaryChrome.tradeoff.test.ts` | tab switch + orderQty updates SVG |
| Controller bars | `controllerOrders.test.ts` | rect elements in SVG |
| PnL no dots | `pnlTimeseries.test.ts` | zero circles |
| Histogram single color | `freshnessHistogram.test.ts` | one bar fill |
| 1/σ label | `controls.test.ts` | inverse sigma label |
| Events daily log | `EventsPane.test.ts` | weekday log + zero-lot filter |
| Hidden sales hosts | `main.stockout.test.ts` | chart-sales in visually-hidden |

RED proof: `cd web && npm test` — layout + secondary tests fail on main baseline.
