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

function tradeoffNumeric(v: unknown): number | null {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** X-domain for tradeoff curve — avoids NaN when data is empty or a single q. */
export function tradeoffXExtent(data: QForecastEntry[]): [number, number] {
  const qs = data
    .map((d) => tradeoffNumeric(d.q))
    .filter((q): q is number => q != null);
  if (qs.length === 0) return [0, 1];
  const lo = d3.min(qs) ?? 0;
  const hi = d3.max(qs) ?? 0;
  if (lo === hi) return [lo - 0.5, hi + 0.5];
  return [lo, hi];
}

/** Y-domain for tradeoff curve — padded extent with minimum span when flat. */
export function tradeoffYExtent(data: QForecastEntry[]): [number, number] {
  const values = data
    .flatMap((d) => [
      d.waste_p10,
      d.waste_p50,
      d.waste_p90,
      d.waste_mean,
      d.missed_p10,
      d.missed_p50,
      d.missed_p90,
      d.missed_mean,
    ])
    .map((v) => tradeoffNumeric(v))
    .filter((v): v is number => v != null);

  if (values.length === 0) return [0, 1];

  const yMin = d3.min(values) ?? 0;
  const yMax = d3.max(values) ?? 0;
  const span = yMax - yMin;
  if (span > 0) {
    const pad = Math.max(1, span * 0.08);
    return [Math.max(0, yMin - pad), yMax + pad];
  }

  const half = Math.max(1, Math.abs(yMax) * 0.05);
  if (yMin === 0 && yMax === 0) {
    return [-half, half];
  }
  return [Math.max(0, yMax - half), yMax + half];
}

function tradeoffYTickFormat(
  domain: [number, number],
): (value: d3.NumberValue) => string {
  const span = domain[1] - domain[0];
  if (domain[0] < 0 || span <= 2) {
    return (value) => d3.format(".1f")(value as number);
  }
  return (value) => d3.format("~s")(value as number);
}

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
  const innerH = Math.max(1, height - margin.top - margin.bottom);
  const [x0, x1] = tradeoffXExtent(data);
  const x = d3.scaleLinear().domain([x0, x1]).nice().range([0, innerW]);
  const [y0, y1] = tradeoffYExtent(data);
  const y = d3
    .scaleLinear()
    .domain([y0, y1])
    .nice()
    .range([innerH, 0]);
  const yDomain = y.domain() as [number, number];
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
    .call(
      d3
        .axisLeft(y)
        .ticks(4)
        .tickFormat(tradeoffYTickFormat(yDomain))
        .tickSizeOuter(0),
    )
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

  const legend = root
    .append("g")
    .attr("class", "legend tradeoff-curve-legend")
    .attr("transform", `translate(${margin.left + 4}, 6)`);

  const legendItems: Array<{
    label: string;
    color: string;
    fillOpacity: number;
  }> = [
    { label: "Waste", color: "var(--missed, #c44)", fillOpacity: 0.25 },
    { label: "Missed sales", color: "var(--sales, #48a)", fillOpacity: 0.2 },
  ];

  legendItems.forEach((item, i) => {
    const itemG = legend
      .append("g")
      .attr("transform", `translate(${i * 72},0)`);
    itemG
      .append("rect")
      .attr("width", 10)
      .attr("height", 10)
      .attr("rx", 2)
      .attr("fill", item.color)
      .attr("fill-opacity", item.fillOpacity);
    itemG
      .append("text")
      .attr("class", "legend-label")
      .attr("x", 14)
      .attr("y", 9)
      .text(item.label);
  });
}
