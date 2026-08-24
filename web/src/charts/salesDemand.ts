import * as d3 from "d3";
import type { Day, HoverDay } from "../types";
import { CHART_MARGIN } from "../hoverLink";
import { padDaysToMinRange, pickDayTicks } from "./axisTicks";
import type { DemandForecastRow } from "./demandDist";

type DayHit = { day: number };

function rootG(
  container: HTMLElement,
): d3.Selection<SVGGElement, unknown, null, undefined> | null {
  const g = container.querySelector("svg g.chart-root");
  return g ? d3.select(g as SVGGElement) : null;
}

/** Style-only hover: vertical rule + day highlight. */
export function setSalesDemandHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = rootG(container);
  if (!g) return;

  g.classed("is-hovering", hoveredDay != null);
  g.selectAll<SVGRectElement, DayHit>(".day-hit").classed(
    "day-hit--active",
    (d) => hoveredDay === d.day,
  );

  const rule = g.select<SVGLineElement>(".hover-rule");
  if (hoveredDay == null) {
    rule.attr("opacity", 0);
    return;
  }
  const hit = g
    .selectAll<SVGRectElement, DayHit>(".day-hit")
    .filter((d) => d.day === hoveredDay);
  if (hit.empty()) {
    rule.attr("opacity", 0);
    return;
  }
  const x = Number(hit.attr("x")) + Number(hit.attr("width")) / 2;
  rule.attr("x1", x).attr("x2", x).attr("opacity", 1);
}

/** Shared day-band x position (center of each day column). */
export function salesDemandX(
  days: readonly number[],
  innerW: number,
  day: number,
): number {
  const step =
    days.length > 0 ? Math.max(0, innerW / days.length) : Math.max(0, innerW);
  const i = days.indexOf(day);
  return i * step + step / 2;
}

/** Sales vs demand over the rolling window, with optional demand forecast overlay. */
export function renderSalesDemand(
  container: HTMLElement,
  history: Day[],
  height = 130,
  forecastRows: DemandForecastRow[] = [],
): void {
  const width = container.clientWidth || 320;
  const margin = {
    top: 12,
    right: CHART_MARGIN.right,
    bottom: 28,
    left: 40,
  };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  if (innerW <= 0) return;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Sales versus demand over days");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const historyDays = history.map((d) => d.day);
  const forecastDays = forecastRows.map((r) => r.day);
  const allDays = [...new Set([...historyDays, ...forecastDays])].sort(
    (a, b) => a - b,
  );
  const days = padDaysToMinRange(allDays);
  const step = Math.max(0, innerW / days.length);
  const x = (day: number): number => salesDemandX(days, innerW, day);

  const yMax =
    d3.max([
      d3.max(history, (d) => Math.max(d.sales_total, d.demand, d.stockout)) ?? 0,
      d3.max(forecastRows, (r) => r.p90) ?? 0,
    ]) ?? 1;
  const y = d3.scaleLinear().domain([0, yMax * 1.1]).nice().range([innerH, 0]);

  const hitData: DayHit[] = [];
  const seenDays = new Set<number>();
  for (const d of history) {
    if (!seenDays.has(d.day)) {
      hitData.push({ day: d.day });
      seenDays.add(d.day);
    }
  }
  for (const row of forecastRows) {
    if (!seenDays.has(row.day)) {
      hitData.push({ day: row.day });
      seenDays.add(row.day);
    }
  }

  g.append("g")
    .attr("class", "day-hits")
    .attr("pointer-events", "none")
    .selectAll("rect")
    .data(hitData, (d) => String((d as DayHit).day))
    .join("rect")
    .attr("class", "day-hit")
    .attr("data-day", (d) => d.day)
    .attr("x", (d) => days.indexOf(d.day) * step)
    .attr("y", 0)
    .attr("width", step)
    .attr("height", innerH);

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(3).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(d3.scaleBand<number>().domain(days).range([0, innerW]).padding(0))
        .tickValues(pickDayTicks(days, innerW))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  if (forecastRows.length > 0) {
    const bandArea = d3
      .area<DemandForecastRow>()
      .x((d) => x(d.day))
      .y0((d) => y(d.p10))
      .y1((d) => y(d.p90))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(forecastRows)
      .attr("class", "sd-forecast-band")
      .attr("fill", "var(--chart-band, rgba(59, 130, 246, 0.18))")
      .attr("stroke", "none")
      .attr("d", bandArea)
      .attr("pointer-events", "none");
  }

  const stockoutArea = d3
    .area<Day>()
    .x((d) => x(d.day))
    .y0((d) => y(d.sales_total))
    .y1((d) => y(d.demand))
    .curve(d3.curveMonotoneX);

  const stockoutDays = history.filter((d) => d.demand > d.sales_total);
  if (stockoutDays.length > 0) {
    g.append("path")
      .datum(history)
      .attr("class", "sales-demand-gap")
      .attr("fill", "rgba(196, 58, 58, 0.22)")
      .attr("stroke", "none")
      .attr("d", stockoutArea)
      .attr("pointer-events", "none");
  }

  if (forecastRows.length > 0) {
    const meanLine = d3
      .line<DemandForecastRow>()
      .x((d) => x(d.day))
      .y((d) => y(d.mean))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(forecastRows)
      .attr("class", "sd-forecast-mean")
      .attr("fill", "none")
      .attr("stroke", "var(--chart-accent, #2563eb)")
      .attr("stroke-width", 2)
      .attr("stroke-dasharray", "5,3")
      .attr("d", meanLine);
  }

  const lineSales = d3
    .line<Day>()
    .x((d) => x(d.day))
    .y((d) => y(d.sales_total))
    .curve(d3.curveMonotoneX);
  const lineDemand = d3
    .line<Day>()
    .x((d) => x(d.day))
    .y((d) => y(d.demand))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(history)
    .attr("class", "sd-line sd-demand")
    .attr("fill", "none")
    .attr("d", lineDemand);

  g.append("path")
    .datum(history)
    .attr("class", "sd-line sd-sales")
    .attr("fill", "none")
    .attr("d", lineSales);

  if (forecastRows.length > 0) {
    const todayDay = forecastRows[0]!.day;
    g.append("line")
      .attr("class", "sd-forecast-today")
      .attr("x1", x(todayDay))
      .attr("x2", x(todayDay))
      .attr("y1", 0)
      .attr("y2", innerH)
      .attr("stroke", "var(--chart-muted, #94a3b8)")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "2,2")
      .attr("pointer-events", "none");
  }

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");

  const legend = svg
    .append("g")
    .attr("class", "legend")
    .attr("transform", `translate(${margin.left + 4}, 8)`);
  const legendItems: { kind: "line" | "band"; cls: string; label: string }[] = [
    { kind: "line", cls: "sd-demand", label: "Demand" },
    { kind: "line", cls: "sd-sales", label: "Sales" },
  ];
  if (forecastRows.length > 0) {
    legendItems.push(
      { kind: "line", cls: "sd-forecast-mean", label: "Forecast" },
      { kind: "band", cls: "sd-forecast-band", label: "p10–p90" },
    );
  }
  const row1 = legendItems.slice(0, 2);
  const row2 = legendItems.slice(2);
  const legendRowHeight = 14;
  const drawLegendRow = (
    items: typeof legendItems,
    rowIndex: number,
  ): number => {
    let legendX = 0;
    for (const item of items) {
      const group = legend
        .append("g")
        .attr("transform", `translate(${legendX},${rowIndex * legendRowHeight})`);
      if (item.kind === "line") {
        group
          .append("line")
          .attr("class", `sd-line ${item.cls}`)
          .attr("x1", 0)
          .attr("x2", 14)
          .attr("y1", 0)
          .attr("y2", 0);
      } else {
        group
          .append("rect")
          .attr("class", item.cls)
          .attr("x", 0)
          .attr("y", -4)
          .attr("width", 14)
          .attr("height", 8)
          .attr("fill", "var(--chart-band, rgba(59, 130, 246, 0.18))");
      }
      const labelW = item.label.length * 6 + 22;
      group
        .append("text")
        .attr("class", "legend-label")
        .attr("x", 18)
        .attr("y", 3)
        .text(item.label);
      legendX += labelW;
    }
    return legendX;
  };
  drawLegendRow(row1, 0);
  if (row2.length > 0) {
    drawLegendRow(row2, 1);
  }
}
