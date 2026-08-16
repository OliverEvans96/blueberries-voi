/**
 * Option A tradeoff curve — E[waste] / E[missed] vs q with p10–p90 bands.
 */
import * as d3 from "d3";

export type QForecastEntry = {
  q: number;
  waste_mean: number;
  waste_p10: number;
  waste_p50: number;
  waste_p90: number;
  missed_mean: number;
  missed_p10: number;
  missed_p50: number;
  missed_p90: number;
  joint_hist: {
    waste_bins: number[];
    missed_bins: number[];
    counts: number[][];
  };
};

export function nearestCandidateQ(
  candidates: QForecastEntry[],
  currentQ: number,
): number {
  if (!candidates.length) return currentQ;
  let best = candidates[0]!;
  let dist = Math.abs(best.q - currentQ);
  for (const c of candidates) {
    const d = Math.abs(c.q - currentQ);
    if (d < dist) {
      best = c;
      dist = d;
    }
  }
  return best.q;
}

export function renderTradeoffCurve(
  svg: SVGSVGElement,
  data: QForecastEntry[],
  currentQ: number,
): void {
  const width = 280;
  const height = 120;
  const margin = { top: 8, right: 8, bottom: 24, left: 32 };
  const root = d3.select(svg);
  root.selectAll("*").remove();
  root.attr("viewBox", `0 0 ${width} ${height}`);
  const g = root
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const x = d3
    .scaleLinear()
    .domain(d3.extent(data, (d) => d.q) as [number, number])
    .range([0, innerW]);
  const y = d3
    .scaleLinear()
    .domain([
      0,
      d3.max(data, (d) => Math.max(d.waste_p90, d.missed_p90)) ?? 1,
    ])
    .nice()
    .range([innerH, 0]);
  const areaWaste = d3
    .area<QForecastEntry>()
    .x((d) => x(d.q))
    .y0((d) => y(d.waste_p10))
    .y1((d) => y(d.waste_p90));
  g.append("path")
    .datum(data)
    .attr("class", "tradeoff-band-waste")
    .attr("data-band", "waste")
    .attr("fill", "var(--missed, #c44)")
    .attr("opacity", 0.25)
    .attr("d", areaWaste);
  const areaMissed = d3
    .area<QForecastEntry>()
    .x((d) => x(d.q))
    .y0((d) => y(d.missed_p10))
    .y1((d) => y(d.missed_p90));
  g.append("path")
    .datum(data)
    .attr("class", "tradeoff-band-missed")
    .attr("data-band", "missed")
    .attr("fill", "var(--sales, #48a)")
    .attr("opacity", 0.2)
    .attr("d", areaMissed);
  g.append("line")
    .attr("class", "order-q-marker")
    .attr("data-order-q", String(currentQ))
    .attr("x1", x(currentQ))
    .attr("x2", x(currentQ))
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("stroke", "#333")
    .attr("stroke-width", 2);
}
