/**
 * Belief-pane SLA stockout chart — protection demand PMF + P(stockout|q).
 */
import * as d3 from "d3";
import type { DemandSummary, ScheduleWire } from "../engine/types";
import type { SlaStockoutCurveResult } from "../engine/types";
import { ORDER_Q_SLIDER_MIN_MAX } from "../react/studioShellDefaults";
import {
  dowSeriesFromDemandSummary,
  protectionCoverageFromSchedule,
} from "./demandDist";
import { protectionDemandPmf } from "./dampedSwDemo";
import { SLA_STOCKOUT_HEIGHT } from "./chartHeights";

export type SlaStockoutChartOpts = {
  curve: SlaStockoutCurveResult | null;
  orderQty: number;
  demandVm: number;
  demandSummary: DemandSummary | null | undefined;
  schedule: ScheduleWire | null | undefined;
  episodeDay: number;
  height?: number;
};

/** Fixed x-domain — matches OperatorBar order-q slider range. */
export const SLA_STOCKOUT_X_MAX = ORDER_Q_SLIDER_MIN_MAX;

const FALLBACK_SUMMARY: DemandSummary = {
  scale_mu: 30,
  dow_means: [30, 30, 30, 30, 30, 30, 30],
};

const CHART_MARGIN = { top: 28, right: 48, bottom: 32, left: 40 };

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

function slaStockoutXScale(innerW: number): d3.ScaleLinear<number, number> {
  return d3
    .scaleLinear()
    .domain([0, SLA_STOCKOUT_X_MAX])
    .range([0, innerW]);
}

/** Render the SLA stockout curve with dual Y-axes. */
export function renderSlaStockoutChart(
  container: HTMLElement,
  opts: SlaStockoutChartOpts,
): void {
  const height = opts.height ?? SLA_STOCKOUT_HEIGHT;
  const width = container.clientWidth > 60 ? container.clientWidth : 360;
  const margin = CHART_MARGIN;
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
  const pmf = protectionDemandPmf(opts.demandVm, protectionDays, mus).filter(
    (d) => d.k <= SLA_STOCKOUT_X_MAX && d.p > 1e-12,
  );

  const yLeftMax = (d3.max(pmf, (d) => d.p) ?? 0.05) * 1.15;
  const yRightMax = Math.min(
    1,
    (d3.max(curve.candidates, (d) => d.p_stockout) ?? 0.1) * 1.12 + 0.02,
  );

  const x = slaStockoutXScale(innerW);
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
    .attr("data-x-max", String(SLA_STOCKOUT_X_MAX))
    .attr("data-height", String(height))
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

  const unitBarW = Math.max(1, x(1) - x(0));
  root
    .selectAll(".sla-demand-bar")
    .data(pmf)
    .join("rect")
    .attr("class", "sla-demand-bar")
    .attr("x", (d) => x(d.k) - unitBarW / 2)
    .attr("y", (d) => yLeft(d.p))
    .attr("width", unitBarW * 0.88)
    .attr("height", (d) => Math.max(0, yLeft(0) - yLeft(d.p)))
    .attr("fill", "var(--chart-band, #dbeafe)")
    .attr("opacity", 0.82);

  const curveInDomain = curve.candidates.filter((d) => d.q <= SLA_STOCKOUT_X_MAX);
  const lineStockout = d3
    .line<(typeof curve.candidates)[number]>()
    .x((d) => x(d.q))
    .y((d) => yRight(d.p_stockout));

  root
    .append("path")
    .datum(curveInDomain)
    .attr("class", "sla-stockout-line")
    .attr("fill", "none")
    .attr("stroke", "var(--missed, #c44)")
    .attr("stroke-width", 2)
    .attr("d", lineStockout);

  root
    .append("line")
    .attr("class", "sla-order-q-marker")
    .attr("data-order-q", String(opts.orderQty))
    .attr("x1", x(Math.min(opts.orderQty, SLA_STOCKOUT_X_MAX)))
    .attr("x2", x(Math.min(opts.orderQty, SLA_STOCKOUT_X_MAX)))
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("stroke", "var(--ink, #333)")
    .attr("stroke-width", 2)
    .attr("stroke-dasharray", "4 3");

  root
    .append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(x)
        .ticks(5)
        .tickValues([0, 40, 80, 120, SLA_STOCKOUT_X_MAX])
        .tickSizeOuter(0),
    )
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

  root
    .append("text")
    .attr("class", "axis-label sla-stockout-y-left-label")
    .attr("transform", "rotate(-90)")
    .attr("x", -innerH / 2)
    .attr("y", -32)
    .attr("text-anchor", "middle")
    .text("Demand PMF");

  root
    .append("text")
    .attr("class", "axis-label sla-stockout-y-right-label")
    .attr("transform", "rotate(-90)")
    .attr("x", -innerH / 2)
    .attr("y", innerW + 36)
    .attr("text-anchor", "middle")
    .text("P(stockout)");

  const legend = svg
    .append("g")
    .attr("class", "legend sla-stockout-legend")
    .attr("transform", `translate(${margin.left + 2}, 6)`);

  const legendItems: Array<{
    label: string;
    kind: "rect" | "line" | "dash";
    color: string;
  }> = [
    { label: "Protection demand", kind: "rect", color: "var(--chart-band, #dbeafe)" },
    { label: "P(stockout|q)", kind: "line", color: "var(--missed, #c44)" },
    { label: "Order q", kind: "dash", color: "var(--ink, #333)" },
  ];

  const legendSpacing = [96, 88, 64];
  legendItems.forEach((item, i) => {
    const itemG = legend
      .append("g")
      .attr("class", "sla-stockout-legend-item")
      .attr("transform", `translate(${legendSpacing.slice(0, i).reduce((a, b) => a + b, 0)},0)`);
    if (item.kind === "rect") {
      itemG
        .append("rect")
        .attr("width", 10)
        .attr("height", 10)
        .attr("rx", 2)
        .attr("y", 1)
        .attr("fill", item.color)
        .attr("fill-opacity", 0.82);
    } else {
      itemG
        .append("line")
        .attr("x1", 0)
        .attr("x2", 12)
        .attr("y1", 6)
        .attr("y2", 6)
        .attr("stroke", item.color)
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", item.kind === "dash" ? "4 3" : null);
    }
    itemG
      .append("text")
      .attr("class", "legend-label")
      .attr("x", 16)
      .attr("y", 10)
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
  const margin = CHART_MARGIN;
  const innerW = width - margin.left - margin.right;
  const storedHeight = Number(svg.getAttribute("data-height"));
  const height =
    Number.isFinite(storedHeight) && storedHeight > 0
      ? storedHeight
      : SLA_STOCKOUT_HEIGHT;
  const innerH = height - margin.top - margin.bottom;
  const x = slaStockoutXScale(innerW);
  const clampedQ = Math.min(orderQty, SLA_STOCKOUT_X_MAX);
  d3.select(svg)
    .select(".sla-order-q-marker")
    .attr("data-order-q", String(orderQty))
    .attr("x1", x(clampedQ))
    .attr("x2", x(clampedQ))
    .attr("y2", innerH);
}
