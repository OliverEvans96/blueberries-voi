/**
 * Delivery temperature history from engine wire trace (times_d / temps_c).
 */
import * as d3 from "d3";
import { CHART_PAPER } from "./beliefFreshnessPalette";
import type { MaskedObsWire } from "../obsMask";

/** Cold→warm segment colors (blue → orange → red), OKLab-friendly like belief heatmap. */
export const DELIVERY_TEMP_COLOR_STOPS = [
  "#3d7ea6",
  "#f97316",
  "#dc2626",
] as const;

export type DeliveryTempPoint = { t: number; temp: number };

export type DeliveryLotTempTrace = {
  lotId: number;
  times_d: number[];
  temps_c: number[];
};

export type TempSummary = {
  min: number;
  max: number;
  mean: number;
  std: number;
  n: number;
};

export const LOT_COLORS = [
  "var(--sales)",
  "#c2410c",
  "#15803d",
  "#7c3aed",
  "#b45309",
] as const;

export function lotColor(index: number): string {
  return LOT_COLORS[index % LOT_COLORS.length]!;
}

export function tracesFromEvent(ev: MaskedObsWire): DeliveryLotTempTrace[] {
  return (
    ev.temp_traces_by_lot?.map((trace) => ({
      lotId: trace.lot_id,
      times_d: trace.times_d,
      temps_c: trace.temps_c,
    })) ??
    (ev.temp_times_d?.length && ev.temp_temps_c?.length
      ? [
          {
            lotId: ev.arrival_lot_ids?.[0] ?? 0,
            times_d: ev.temp_times_d,
            temps_c: ev.temp_temps_c,
          },
        ]
      : [])
  );
}

export function tempSummaryFromTrace(
  trace: DeliveryLotTempTrace,
): TempSummary | null {
  const finite = trace.temps_c.filter((t) => Number.isFinite(t));
  if (!finite.length) return null;
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  const mean = d3.mean(finite) ?? 0;
  const std = finite.length < 2 ? 0 : (d3.deviation(finite) ?? 0);
  return { min, max, mean, std, n: finite.length };
}

export function formatTempC(v: number): string {
  return `${v.toFixed(1)}°C`;
}

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

export function tempColorScale(
  yMin: number,
  yMax: number,
): (temp: number) => string {
  return d3
    .scaleSequential(d3.interpolateRgbBasis([...DELIVERY_TEMP_COLOR_STOPS]))
    .domain([yMin, yMax]) as (temp: number) => string;
}

function appendPlotBackground(
  parent: d3.Selection<SVGGElement, unknown, null, undefined>,
  innerW: number,
  innerH: number,
): void {
  parent
    .append("rect")
    .attr("class", "delivery-temp-bg")
    .attr("width", innerW)
    .attr("height", innerH)
    .attr("fill", CHART_PAPER)
    .attr("opacity", 0.45);
}

function appendTempBaseline(
  parent: d3.Selection<SVGGElement, unknown, null, undefined>,
  x1: number,
  x2: number,
  y2C: number,
  y: (temp: number) => number,
): void {
  parent
    .append("line")
    .attr("class", "delivery-temp-baseline")
    .attr("x1", x1)
    .attr("x2", x2)
    .attr("y1", y(y2C))
    .attr("y2", y(y2C))
    .attr("stroke", "var(--border, #ccc)")
    .attr("stroke-width", 0.5)
    .attr("stroke-dasharray", "2 2");
}

function appendTempAxes(
  parent: d3.Selection<SVGGElement, unknown, null, undefined>,
  innerW: number,
  innerH: number,
): void {
  parent
    .append("line")
    .attr("class", "delivery-temp-axis-x")
    .attr("x1", 0)
    .attr("x2", innerW)
    .attr("y1", innerH)
    .attr("y2", innerH)
    .attr("stroke", "var(--border, #999)")
    .attr("stroke-width", 0.75);
  parent
    .append("line")
    .attr("class", "delivery-temp-axis-y")
    .attr("x1", innerW)
    .attr("x2", innerW)
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("stroke", "var(--border, #999)")
    .attr("stroke-width", 0.75);
}

function appendTempColoredSegments(
  parent: d3.Selection<SVGGElement, unknown, null, undefined>,
  points: DeliveryTempPoint[],
  x: (t: number) => number,
  y: (temp: number) => number,
  color: (temp: number) => string,
  attrs?: Record<string, string>,
): void {
  if (points.length < 2) return;
  const group = parent.append("g").attr("class", "delivery-temp-line");
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i]!;
    const b = points[i + 1]!;
    const midTemp = (a.temp + b.temp) / 2;
    const line = group
      .append("line")
      .attr("class", "delivery-temp-segment")
      .attr("x1", x(a.t))
      .attr("y1", y(a.temp))
      .attr("x2", x(b.t))
      .attr("y2", y(b.temp))
      .attr("stroke", color(midTemp))
      .attr("stroke-width", 1.5);
    if (attrs) {
      for (const [key, value] of Object.entries(attrs)) {
        line.attr(key, value);
      }
    }
  }
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
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const x = d3.scaleLinear().domain([tMin, 0]).range([0, innerW]);
  const y = d3.scaleLinear().domain([yMin, yMax]).range([innerH, 0]);
  const plot = root
    .append("g")
    .attr("class", "delivery-temp-plot")
    .attr("transform", `translate(${pad},${pad})`);
  appendPlotBackground(plot, innerW, innerH);
  appendTempBaseline(plot, 0, innerW, 2, y);
  appendTempAxes(plot, innerW, innerH);
  appendTempColoredSegments(
    plot,
    data,
    (t) => x(t),
    (temp) => y(temp),
    tempColorScale(yMin, yMax),
  );
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
  height = 48,
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

  appendPlotBackground(plot, innerW, innerH);
  appendTempBaseline(plot, 0, innerW, 2, y);
  appendTempAxes(plot, innerW, innerH);

  const color = tempColorScale(yMin, yMax);
  series.forEach((trace) => {
    appendTempColoredSegments(
      plot,
      trace.points,
      (t) => x(t),
      (temp) => y(temp),
      color,
      { "data-series": "temp", "data-lot": String(trace.lotId) },
    );
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
        .attr("stroke", lotColor(i))
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
