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
  width = 300,
  heightScale = 1,
): void {
  const height = Math.max(200, Math.round(width * 0.55)) * heightScale;
  const margin = { top: 16, right: 10, bottom: 32, left: 40 };
  const root = d3.select(svg);
  root.selectAll("*").remove();
  root
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height);
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
      d3.max(data, (d) =>
        Math.max(d.waste_p90, d.missed_p90, d.waste_mean, d.missed_mean),
      ) ?? 1,
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
  const lineWasteMean = d3
    .line<QForecastEntry>()
    .x((d) => x(d.q))
    .y((d) => y(d.waste_mean));
  g.append("path")
    .datum(data)
    .attr("class", "tradeoff-mean-waste")
    .attr("data-series", "waste_mean")
    .attr("fill", "none")
    .attr("stroke", "var(--missed, #c44)")
    .attr("stroke-width", 2)
    .attr("d", lineWasteMean);
  const lineMissedMean = d3
    .line<QForecastEntry>()
    .x((d) => x(d.q))
    .y((d) => y(d.missed_mean));
  g.append("path")
    .datum(data)
    .attr("class", "tradeoff-mean-missed")
    .attr("data-series", "missed_mean")
    .attr("fill", "none")
    .attr("stroke", "var(--sales, #48a)")
    .attr("stroke-width", 2)
    .attr("d", lineMissedMean);
  g.append("line")
    .attr("class", "order-q-marker")
    .attr("data-order-q", String(currentQ))
    .attr("x1", x(currentQ))
    .attr("x2", x(currentQ))
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("stroke", "#333")
    .attr("stroke-width", 2);

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 26)
    .attr("text-anchor", "middle")
    .text("Order quantity (units)");

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", -innerH / 2)
    .attr("y", -30)
    .attr("transform", "rotate(-90)")
    .attr("text-anchor", "middle")
    .text("Expected units");
}
