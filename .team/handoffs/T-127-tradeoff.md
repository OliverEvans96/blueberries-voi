# T-127 tradeoff implement handoff (wave 1, round 2)

## `renderTradeoffCurve` signature

**Unchanged.** Still `(svg: SVGSVGElement, data: QForecastEntry[], currentQ: number) => void`.

The host wrapper in `tradeoffForecast.ts` (`renderTradeoffCurve(host, data, currentQ)`) is also unchanged.

## Chart changes

`tradeoffCurve.ts` now draws solid `d3.line()` overlays for `waste_mean` and `missed_mean` on top of the existing p10–p90 bands:

- `.tradeoff-mean-waste` / `[data-series='waste_mean']` — stroke `var(--missed, #c44)` (matches waste band color)
- `.tradeoff-mean-missed` / `[data-series='missed_mean']` — stroke `var(--sales, #48a)` (matches missed band color)

Y-domain max now includes mean values alongside p90.

## Placement in `DecisionRail.tsx`

**Unaffected.** `renderTradeoffCurve` and `renderTradeoffHistogram` remain inside `decision-rail-run`, directly under the order-qty slider/buttons (`#tradeoff-curve-host` / `#tradeoff-histogram-host` within `.tradeoff-charts`). No edits to `DecisionRail.tsx`.

## Tests

Extended `web/src/charts/tradeoffForecast.test.ts` with a case asserting both mean-line paths render with correct stroke colors and `d` attributes.
