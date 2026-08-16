/**
 * Tradeoff forecast chart helpers (T-127) — barrel for DecisionRail + tests.
 */
export type { QForecastEntry } from "./tradeoffCurve";
export {
  nearestCandidateQ,
  renderTradeoffCurve as renderTradeoffCurveSvg,
} from "./tradeoffCurve";
export { renderTradeoffHistogram as renderTradeoffHistogramSvg } from "./tradeoffHistogram";
import type { QForecastEntry } from "./tradeoffCurve";
import {
  nearestCandidateQ,
  renderTradeoffCurve as renderTradeoffCurveSvg,
} from "./tradeoffCurve";
import {
  renderTradeoffHistogram as renderTradeoffHistogramSvg,
  type JointHist,
} from "./tradeoffHistogram";

export function nearestForecast(
  candidates: QForecastEntry[],
  currentQ: number,
): JointHist {
  const q = nearestCandidateQ(candidates, currentQ);
  const hit = candidates.find((c) => c.q === q) ?? candidates[0];
  return hit?.joint_hist ?? { waste_bins: [0], missed_bins: [0], counts: [[0]] };
}

function ensureSvg(host: HTMLElement): SVGSVGElement {
  let svg = host.querySelector("svg");
  if (!svg) {
    svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    host.appendChild(svg);
  }
  return svg;
}

export function renderTradeoffCurve(
  host: HTMLElement,
  data: QForecastEntry[],
  currentQ: number,
): void {
  renderTradeoffCurveSvg(ensureSvg(host), data, currentQ);
}

export function renderTradeoffHistogram(
  host: HTMLElement,
  hist: JointHist,
  currentQ?: number,
): void {
  renderTradeoffHistogramSvg(ensureSvg(host), hist, currentQ ?? 0);
}
