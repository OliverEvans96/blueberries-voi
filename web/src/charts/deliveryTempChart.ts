/**
 * Delivery temperature history from engine wire trace (times_d / temps_c).
 */
import * as d3 from "d3";

export type DeliveryTempPoint = { t: number; temp: number };

export type DeliveryLotTempTrace = {
  lotId: number;
  times_d: number[];
  temps_c: number[];
};

const LOT_COLORS = [
  "var(--accent, #2563eb)",
  "#c2410c",
  "#15803d",
  "#7c3aed",
  "#b45309",
];

export function pointsFromWire(
  times: number[] | null | undefined,
  temps: number[] | null | undefined,
): DeliveryTempPoint[] {
  if (!times?.length || !temps?.length || times.length !== temps.length) {
    return [];
  }
  const tEnd = times[times.length - 1] ?? 0;
  return times.map((time, i) => ({
    t: time - tEnd,
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
  const tMin = Math.min(...data.map((d) => d.t));
  const x = d3.scaleLinear().domain([tMin, 0]).range([pad, width - pad]);
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

/** Multi-lot delivery temperature traces — t=0 at the right edge. */
export function renderDeliveryTempMultiLot(
  host: HTMLElement,
  traces: DeliveryLotTempTrace[],
  height = 72,
): void {
  const width = host.clientWidth || 280;
  const legendW = traces.length > 1 ? 56 : 0;
  const plotW = width - legendW;
  const pad = { top: 6, right: 8, bottom: 4, left: 4 };
  const innerW = Math.max(40, plotW - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;

  host.replaceChildren();
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("class", "delivery-temp-chart delivery-temp-chart--multi");
  host.appendChild(svg);

  const root = d3.select(svg);
  const plot = root
    .append("g")
    .attr("class", "delivery-temp-plot")
    .attr("transform", `translate(${pad.left},${pad.top})`);

  const series = traces
    .map((trace) => ({
      lotId: trace.lotId,
      points: pointsFromWire(trace.times_d, trace.temps_c),
    }))
    .filter((trace) => trace.points.length > 0);

  if (!series.length) return;

  const allPoints = series.flatMap((s) => s.points);
  const temps = allPoints.map((d) => d.temp);
  const yMin = Math.min(0, ...temps);
  const yMax = Math.max(6, ...temps);
  const tMin = Math.min(...allPoints.map((d) => d.t));
  const x = d3.scaleLinear().domain([tMin, 0]).range([0, innerW]);
  const y = d3.scaleLinear().domain([yMin, yMax]).range([innerH, 0]);

  plot
    .append("line")
    .attr("class", "delivery-temp-baseline")
    .attr("x1", 0)
    .attr("x2", innerW)
    .attr("y1", y(2))
    .attr("y2", y(2))
    .attr("stroke", "var(--border, #ccc)")
    .attr("stroke-width", 0.5)
    .attr("stroke-dasharray", "2 2");

  const line = d3
    .line<DeliveryTempPoint>()
    .x((d) => x(d.t))
    .y((d) => y(d.temp))
    .curve(d3.curveMonotoneX);

  series.forEach((trace, i) => {
    plot
      .append("path")
      .datum(trace.points)
      .attr("class", "delivery-temp-line")
      .attr("data-series", "temp")
      .attr("data-lot", String(trace.lotId))
      .attr("fill", "none")
      .attr("stroke", LOT_COLORS[i % LOT_COLORS.length]!)
      .attr("stroke-width", 1.5)
      .attr("d", line);
  });

  if (series.length > 1) {
    const legend = root
      .append("g")
      .attr("class", "delivery-temp-legend")
      .attr("transform", `translate(${plotW + 4},${pad.top + 2})`);
    series.forEach((trace, i) => {
      const item = legend
        .append("g")
        .attr("transform", `translate(0,${i * 14})`);
      item
        .append("line")
        .attr("x1", 0)
        .attr("x2", 10)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", LOT_COLORS[i % LOT_COLORS.length]!)
        .attr("stroke-width", 1.5);
      item
        .append("text")
        .attr("class", "delivery-temp-legend-label")
        .attr("x", 14)
        .attr("y", 3)
        .text(String(trace.lotId));
    });
  }
}
