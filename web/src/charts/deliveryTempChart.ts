/**
 * Delivery temperature history from engine wire trace (times_d / temps_c).
 */
import * as d3 from "d3";

export type DeliveryTempPoint = { t: number; temp: number };

export function pointsFromWire(
  times: number[] | null | undefined,
  temps: number[] | null | undefined,
): DeliveryTempPoint[] {
  if (!times?.length || !temps?.length || times.length !== temps.length) {
    return [];
  }
  const t0 = times[0] ?? 0;
  const span = (times[times.length - 1] ?? t0) - t0 || 1;
  return times.map((time, i) => ({
    t: (time - t0) / span,
    temp: temps[i] ?? 0,
  }));
}

function ensureSvg(host: HTMLElement): SVGSVGElement {
  let svg = host.querySelector("svg");
  if (!svg) {
    svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    host.appendChild(svg);
  }
  return svg;
}

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
  if (!data.length) return;
  const temps = data.map((d) => d.temp);
  const yMin = Math.min(0, ...temps);
  const yMax = Math.max(6, ...temps);
  const x = d3
    .scaleLinear()
    .domain([0, 1])
    .range([pad, width - pad]);
  const y = d3.scaleLinear().domain([yMin, yMax]).range([height - pad, pad]);
  root
    .append("line")
    .attr("class", "delivery-temp-baseline")
    .attr("x1", pad)
    .attr("x2", width - pad)
    .attr("y1", y(2))
    .attr("y2", y(2))
    .attr("stroke", "var(--border, #ccc)")
    .attr("stroke-width", 0.5)
    .attr("stroke-dasharray", "2 2");
  const line = d3
    .line<DeliveryTempPoint>()
    .x((d) => x(d.t))
    .y((d) => y(d.temp));
  root
    .append("path")
    .datum(data)
    .attr("class", "delivery-temp-line")
    .attr("fill", "none")
    .attr("stroke", "var(--accent, #2563eb)")
    .attr("stroke-width", 1.5)
    .attr("d", line);
}

export function renderDeliveryTempHistory(
  host: HTMLElement,
  times: number[] | null | undefined,
  temps: number[] | null | undefined,
): void {
  const svg = ensureSvg(host);
  renderDeliveryTempHistorySvg(svg, pointsFromWire(times, temps));
}
