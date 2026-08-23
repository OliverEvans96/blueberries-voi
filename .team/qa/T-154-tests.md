# T-154 RED test map

| AC | Test |
|----|------|
| Outcomes panel head + note | `StudioLayout.test.ts` → metrics narration → Outcomes panel head |
| Group labels Economics/Inventory/Flow | `StudioLayout.test.ts` → metrics groups show labels |
| Belief note copy | `StudioLayout.test.ts` → belief panel note links hover |
| Metrics caption CSS bold | `StudioLayout.test.ts` → cockpitGrid.css boldens metrics chart captions |
| Impact stat de-bold CSS | `StudioLayout.test.ts` → cockpitGrid.css de-emphasizes impact stat |
| No `<strong>` in ImpactStat | `ImpactStat.test.ts` → renders single-line caption |

RED proof: `pnpm exec vitest run src/react/StudioLayout.test.ts src/react/ImpactStat.test.ts` (6 failures expected).
