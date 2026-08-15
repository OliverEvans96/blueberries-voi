import * as d3 from "d3";
import type { DemandSummary, ScheduleWire } from "../engine/types";

const DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

const ORDER_WD_LABEL: Record<number, string> = {
  0: "Mon",
  1: "Tue",
  2: "Wed",
  3: "Thu",
  4: "Fri",
  5: "Sat",
  6: "Sun",
};

export type ProtectionCoverageRow = {
  order_weekday: number;
  demand_days: number;
  label: string;
};

/** Length-7 monday0 DOW means from Snapshot demand_summary. */
export function dowSeriesFromDemandSummary(summary: DemandSummary): number[] {
  return [...summary.dow_means];
}

/**
 * Protection demand-day spans per order weekday (ADR 0114):
 * days until next order day + lead_time_days → 3 / 3 / 4 on Sun / Tue / Thu.
 */
export function protectionCoverageFromSchedule(
  schedule: ScheduleWire,
): ProtectionCoverageRow[] {
  const order = [...schedule.order_weekdays];
  const lead = Math.max(0, schedule.lead_time_days);
  return order.map((order_weekday) => {
    let gap = 7;
    for (let d = 1; d <= 7; d += 1) {
      const wd = (order_weekday + d) % 7;
      if (order.includes(wd)) {
        gap = d;
        break;
      }
    }
    const demand_days = gap + lead;
    const name = ORDER_WD_LABEL[order_weekday] ?? `wd${order_weekday}`;
    return {
      order_weekday,
      demand_days,
      label: `${name} ${demand_days}`,
    };
  });
}

/** Fallback when Snapshot has not yet supplied a profile. */
const FALLBACK_SUMMARY: DemandSummary = {
  scale_mu: 30,
  dow_means: [30, 30, 30, 30, 30, 30, 30],
};

/**
 * DOW demand profile (seven-day means) + protection coverage labels
 * (Sun/Tue/Thu → 3 / 3 / 4). Replaces the former i.i.d. μ-only PMF chart.
 */
export function renderDemandDist(
  container: HTMLElement,
  summary: DemandSummary | null | undefined,
  schedule: ScheduleWire | null | undefined,
  height = 140,
): void {
  const profile = summary ?? FALLBACK_SUMMARY;
  const series = dowSeriesFromDemandSummary(profile);
  const coverage = schedule
    ? protectionCoverageFromSchedule(schedule)
    : [];

  const width = container.clientWidth || 320;
  const margin = { top: 28, right: 12, bottom: 36, left: 36 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr(
      "aria-label",
      "Demand DOW profile with order-day protection coverage",
    );

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const maxY = d3.max(series) ?? profile.scale_mu;
  const x = d3
    .scaleBand<string>()
    .domain([...DOW_LABELS])
    .range([0, innerW])
    .padding(0.2);
  const y = d3
    .scaleLinear()
    .domain([0, maxY * 1.15])
    .nice()
    .range([innerH, 0]);

  g.selectAll(".dow-bar")
    .data(series)
    .join("rect")
    .attr("class", "dow-bar pmf-bar")
    .attr("data-dow-mean", (d) => String(d))
    .attr("x", (_d, i) => x(DOW_LABELS[i]!) ?? 0)
    .attr("y", (d) => y(d))
    .attr("width", x.bandwidth())
    .attr("height", (d) => Math.max(0, innerH - y(d)));

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  const protText =
    coverage.length > 0
      ? `Protection ${coverage
          .map((r) => ORDER_WD_LABEL[r.order_weekday] ?? r.order_weekday)
          .join("/")} ${coverage.map((r) => r.demand_days).join(" / ")}`
      : "Protection —";

  // Explicit 3 / 3 / 4 chrome for default Sun/Tue/Thu schedule.
  const numericHint =
    coverage.length >= 3
      ? (() => {
          const by = new Map(coverage.map((r) => [r.order_weekday, r.demand_days]));
          if (by.get(6) === 3 && by.get(1) === 3 && by.get(3) === 4) {
            return " · Sun/Tue/Thu 3 / 3 / 4";
          }
          return "";
        })()
      : "";

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", 0)
    .attr("y", -10)
    .attr("text-anchor", "start")
    .text(`${protText}${numericHint}`);

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 30)
    .attr("text-anchor", "middle")
    .text(`DOW means · scale μ=${profile.scale_mu.toFixed(0)}`);
}
