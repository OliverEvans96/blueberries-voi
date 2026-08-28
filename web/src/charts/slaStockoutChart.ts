/**
 * Belief-pane SLA stockout chart — protection demand PMF + P(stockout|q).
 */
import * as d3 from "d3";
import type { DemandSummary, ScheduleWire } from "../engine/types";
import type { SlaStockoutCurveResult } from "../engine/types";
import {
  dowSeriesFromDemandSummary,
  protectionCoverageFromSchedule,
} from "./demandDist";
import { protectionDemandPmf } from "./dampedSwDemo";

export type SlaStockoutChartOpts = {
  curve: SlaStockoutCurveResult | null;
  orderQty: number;
  demandVm: number;
  demandSummary: DemandSummary | null | undefined;
  schedule: ScheduleWire | null | undefined;
  episodeDay: number;
  height?: number;
};

const FALLBACK_SUMMARY: DemandSummary = {
  scale_mu: 30,
  dow_means: [30, 30, 30, 30, 30, 30, 30],
};

function defaultProtectionDays(
  episodeDay: number,
  schedule: ScheduleWire | null | undefined,
): number {
  if (schedule) {
    const rows = protectionCoverageFromSchedule(schedule);
    const wd = episodeDay % 7;
    const match = rows.find((r) => r.order_weekday === wd);
    if (match) return match.demand_days;
    if (rows.length > 0) return rows[0]!.demand_days;
  }
  return 3;
}

function windowMus(
  summary: DemandSummary,
  episodeDay: number,
  protectionDays: number,
): number[] {
  const series = dowSeriesFromDemandSummary(summary);
  const mus: number[] = [];
  for (let k = 0; k < protectionDays; k += 1) {
    const wd = (episodeDay + k) % 7;
    mus.push(series[wd] ?? summary.scale_mu);
  }
  return mus;
}

function protectionDaysFor(
  schedule: ScheduleWire | null | undefined,
  episodeDay: number,
): number {
  return defaultProtectionDays(episodeDay, schedule);
}

/** Render the SLA stockout curve with dual Y-axes. */
export function renderSlaStockoutChart(
  container: HTMLElement,
  opts: SlaStockoutChartOpts,
): void {
  const height = opts.height ?? 130;
  const width = container.clientWidth > 60 ? container.clientWidth : 360;
  const margin = { top: 18, right: 44, bottom: 32, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  if (innerW <= 0 || innerH <= 0) return;

  const curve = opts.curve;
  if (!curve?.candidates.length) {
    const hint = document.createElement("p");
    hint.className = "chart-empty-hint";
    hint.textContent = "SLA stockout curve unavailable.";
    container.appendChild(hint);
    return;
  }

  const summary = opts.demandSummary ?? FALLBACK_SUMMARY;
  const protectionDays = protectionDaysFor(opts.schedule, opts.episodeDay);
  const mus = windowMus(summary, opts.episodeDay, protectionDays);
  const pmf = protectionDemandPmf(opts.demandVm, protectionDays, mus);

  const xMax = Math.max(
    d3.max(curve.candidates, (d) => d.q) ?? 1,
    d3.max(pmf, (d) => d.k) ?? 1,
    opts.orderQty,
    1,
  ) * 1.04;

  const yLeftMax =
    (d3.max(pmf, (d) => d.p) ?? 0.05) * 1.15;
  const yRightMax = Math.min(
    1,
    (d3.max(curve.candidates, (d) => d.p_stockout) ?? 0.1) * 1.12 + 0.02,
  );

  const x = d3.scaleLinear().domain([0, xMax]).nice().range([0, innerW]);
  const yLeft = d3.scaleLinear().domain([0, yLeftMax]).nice().range([innerH, 0]);
  const yRight = d3
    .scaleLinear()
    .domain([0, Math.max(yRightMax, 0.05)])
    .nice()
    .range([innerH, 0]);

  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg sla-stockout-chart")
    .attr("data-x-max", String(xMax))
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr(
      "aria-label",
      "Protection demand distribution with stockout probability by order quantity",
    );

  const root = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const barW = Math.max(1, innerW / Math.max(pmf.length, 1) - 0.5);
  root
    .selectAll(".sla-demand-bar")
    .data(pmf.filter((d) => d.p > 1e-12))
    .join("rect")
    .attr("class", "sla-demand-bar")
    .attr("x", (d) => x(d.k) - barW / 2)
    .attr("y", (d) => yLeft(d.p))
    .attr("width", barW)
    .attr("height", (d) => Math.max(0, yLeft(0) - yLeft(d.p)))
    .attr("fill", "var(--chart-band, #dbeafe)")
    .attr("opacity", 0.85);

  const lineStockout = d3
    .line<(typeof curve.candidates)[number]>()
    .x((d) => x(d.q))
    .y((d) => yRight(d.p_stockout));

  root
    .append("path")
    .datum(curve.candidates)
    .attr("class", "sla-stockout-line")
    .attr("fill", "none")
    .attr("stroke", "var(--missed, #c44)")
    .attr("stroke-width", 2)
    .attr("d", lineStockout);

  root
    .append("line")
    .attr("class", "sla-order-q-marker")
    .attr("data-order-q", String(opts.orderQty))
    .attr("x1", x(opts.orderQty))
    .attr("x2", x(opts.orderQty))
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("stroke", "#333")
    .attr("stroke-width", 2)
    .attr("stroke-dasharray", "4 3");

  root
    .append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  root
    .append("g")
    .attr("class", "axis axis-y axis-y-left")
    .call(
      d3
        .axisLeft(yLeft)
        .ticks(3)
        .tickFormat((v) => d3.format(".2f")(v as number))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").remove());

  root
    .append("g")
    .attr("class", "axis axis-y axis-y-right")
    .attr("transform", `translate(${innerW},0)`)
    .call(
      d3
        .axisRight(yRight)
        .ticks(3)
        .tickFormat((v) => d3.format(".0%")(v as number))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").remove());

  root
    .append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 26)
    .attr("text-anchor", "middle")
    .text("Order quantity (units)");

  const legend = svg
    .append("g")
    .attr("class", "legend sla-stockout-legend")
    .attr("transform", `translate(${margin.left + 4}, 4)`);

  const items = [
    { label: "Protection demand", color: "var(--chart-band, #dbeafe)", dash: "" },
    { label: "P(stockout|q)", color: "var(--missed, #c44)", dash: "" },
    { label: "Order q", color: "#333", dash: "4 3" },
  ];
  items.forEach((item, i) => {
    const row = legend
      .append("g")
      .attr("transform", `translate(0, ${i * 14})`);
    row
      .append("line")
      .attr("x1", 0)
      .attr("x2", 12)
      .attr("y1", 6)
      .attr("y2", 6)
      .attr("stroke", item.color)
      .attr("stroke-width", 2)
      .attr("stroke-dasharray", item.dash || null);
    row
      .append("text")
      .attr("x", 16)
      .attr("y", 10)
      .attr("class", "legend-label")
      .text(item.label);
  });
}

/** Marker-only refresh when orderQty changes without re-fetching the curve. */
export function refreshSlaStockoutMarker(
  container: HTMLElement,
  orderQty: number,
  _curve: SlaStockoutCurveResult | null,
): void {
  const svg = container.querySelector("svg.sla-stockout-chart");
  if (!svg) return;
  const width = container.clientWidth > 60 ? container.clientWidth : 360;
  const margin = { top: 18, right: 44, bottom: 32, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = 130 - margin.top - margin.bottom;
  const stored = Number(svg.getAttribute("data-x-max"));
  const xMax = Number.isFinite(stored) && stored > 0 ? stored : Math.max(orderQty, 1);
  const x = d3.scaleLinear().domain([0, xMax]).nice().range([0, innerW]);
  d3.select(svg)
    .select(".sla-order-q-marker")
    .attr("data-order-q", String(orderQty))
    .attr("x1", x(orderQty))
    .attr("x2", x(orderQty))
    .attr("y2", innerH);
}
