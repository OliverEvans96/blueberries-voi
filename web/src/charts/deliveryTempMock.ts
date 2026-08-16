/**
 * Illustrative delivery temperature history — frontend mock (T-127 round 2).
 * No wire field today; seeded by (day, lot_id) for deterministic placeholder curves.
 */
import * as d3 from "d3";

export type DeliveryTempPoint = { t: number; temp: number };

/** Combine day and lot into a stable 32-bit seed. */
export function seedForDeliveryTemp(day: number, lotId: number): number {
  return (day * 7919 + lotId * 104729) >>> 0;
}

function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Deterministic cold-chain transit curve (roughly 0.5–6 °C). */
export function generateDeliveryTempHistory(
  day: number,
  lotId: number,
): DeliveryTempPoint[] {
  const rand = mulberry32(seedForDeliveryTemp(day, lotId));
  const n = 7;
  const points: DeliveryTempPoint[] = [];
  let temp = 2 + rand() * 0.4;
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1);
    const envelope = Math.sin(t * Math.PI) * 1.4;
    temp = 2 + envelope + (rand() - 0.5) * 0.35;
    temp = Math.max(0.5, Math.min(6, temp));
    points.push({ t, temp });
  }
  return points;
}

function ensureSvg(host: HTMLElement): SVGSVGElement {
  let svg = host.querySelector("svg");
  if (!svg) {
    svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    host.appendChild(svg);
  }
  return svg;
}

/** Minimal axis-less line chart for illustrative temp history. */
export function renderDeliveryTempHistorySvg(
  svg: SVGSVGElement,
  data: DeliveryTempPoint[],
): void {
  const width = 120;
  const height = 36;
  const pad = 2;
  const root = d3.select(svg);
  root.selectAll("*").remove();
  root.attr("viewBox", `0 0 ${width} ${height}`);
  root.attr("class", "delivery-temp-chart");
  const x = d3
    .scaleLinear()
    .domain([0, 1])
    .range([pad, width - pad]);
  const y = d3
    .scaleLinear()
    .domain([0, 6])
    .range([height - pad, pad]);
  root
    .append("line")
    .attr("class", "delivery-temp-baseline")
    .attr("x1", pad)
    .attr("x2", width - pad)
    .attr("y1", y(2))
    .attr("y2", y(2))
    .attr("stroke", "var(--border, #ccc)")
    .attr("stroke-width", 0.75)
    .attr("stroke-dasharray", "2,2");
  const line = d3
    .line<DeliveryTempPoint>()
    .x((d) => x(d.t))
    .y((d) => y(d.temp));
  root
    .append("path")
    .attr("class", "delivery-temp-line")
    .attr("data-series", "temp")
    .attr("fill", "none")
    .attr("stroke", "var(--sales, #48a)")
    .attr("stroke-width", 1.5)
    .attr("d", line(data));
}

export function renderDeliveryTempHistory(
  host: HTMLElement,
  day: number,
  lotId: number,
): void {
  renderDeliveryTempHistorySvg(
    ensureSvg(host),
    generateDeliveryTempHistory(day, lotId),
  );
}
