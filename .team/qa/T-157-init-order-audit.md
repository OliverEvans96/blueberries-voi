# T-157 — First-order studio init audit

**Verdict:** PASS (web gates: vitest + `npm run build` + full Playwright e2e)

**Worktree:** `.worktrees/T-157-first-order-visual-qa`  
**Branch:** `team/T-157/first-order-visual-qa`

## What was checked

Playwright spec `web/tests/studio-init-order-audit.spec.ts` at:

1. Day 0 (engine ready, no Place Order)
2. After 1 Place Order
3. After 5 Place Orders

Assertions:

- Chart hosts have `svg.chart-svg` + axes (tradeoff / belief-lg included)
- P&L totals and impact stats (missed sales, waste) populated at day 0 with zeros
- Day-indexed chart x-span ≥ `MIN_CHART_DAY_SPAN` (5)
- Layout rects of chart + text hosts stable within 1px on first order (events sidebar excluded)
- No console / page errors

Screenshots (gitignored): `web/tests/__screenshots__/init-audit/`

| Shot | Path |
|------|------|
| Day 0 full / metrics / belief | `00-day0-*.png` |
| After 1 order | `01-after-1-order-*.png` |
| After 5 orders | `05-after-5-orders-*.png` |

## Issues found and fixed

| Issue | Before | After |
|-------|--------|-------|
| `#chart-belief-lg` SVG missing `chart-svg` class | Axes rendered, but audit/`hoverLink` selector failed | `renderFreshnessHistogram` sets `class="chart-svg"` |
| Tradeoff host SVG missing `chart-svg` | Same class gap via `ensureSvg` | `ensureSvg` adds `chart-svg` |
| On-hand freshness band y-axis garbled when all bands are 0 | After first order (pre-arrival), ticks looked like `0000` / `-` | `yMax = Math.max(…, 1)` in `renderFreshnessComposition` |
| Vite ENOSPC under many worktrees | Playwright webServer failed to start | `PW_E2E` / `CI` disables Vite file watch; Playwright sets `PW_E2E=1` |

## Package version

Publishable `web/src` behavior changed → bumped `web/package.json` **0.3.3 → 0.3.4**.

## Remaining known issues

- None blocking for init / first-order layout. Day-0 charts are empty of series data by design (axes + padded day span only). Place Order advances to next order weekday (not +1 calendar day), so “5 orders” spans more than 5 episode days — expected.
- Full Python CI-parity verify not run (web-only change set).

## Gate results (this worktree)

- `npm test` — PASS (575)
- `npm run build` — PASS
- `npm run build:lib` — PASS (needed for embed.lib.test)
- `npm run e2e` — PASS (11)
