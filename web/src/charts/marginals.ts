import * as d3 from "d3";
import type { Day, HoverDay } from "../types";
import { CHART_MARGIN } from "../hoverLink";
import { padDaysToMinRange, pickDayTicks } from "./axisTicks";

export type MarginalKind = "sales" | "spoilage" | "stockout";

function rootG(
  container: HTMLElement,
): d3.Selection<SVGGElement, unknown, null, undefined> | null {
  const g = container.querySelector("svg g.chart-root");
  return g ? d3.select(g as SVGGElement) : null;
}

/** Shared y-domain for sales + missed-sales bars. */
export function marginalYMax(history: Day[]): number {
  const salesMax = d3.max(history, (d) => d.sales_total) ?? 0;
  const stockMax = d3.max(history, (d) => d.stockout) ?? 0;
  return Math.max(1, salesMax, stockMax);
}

/** Style-only: bar active class + vertical rule. */
export function setMarginalHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = rootG(container);
  if (!g) return;

  g.classed("is-hovering", hoveredDay != null);
  g.selectAll<SVGRectElement, Day>(".bar").classed(
    "bar--active",
    (d) => hoveredDay === d.day,
  );
  g.selectAll<SVGRectElement, Day>(".day-hit").classed(
    "day-hit--active",
    (d) => hoveredDay === d.day,
  );

  const rule = g.select<SVGLineElement>(".hover-rule");
  if (hoveredDay == null) {
    rule.attr("opacity", 0);
    return;
  }
  const hit = g
    .selectAll<SVGRectElement, Day>(".day-hit")
    .filter((d) => d.day === hoveredDay);
  if (hit.empty()) {
    rule.attr("opacity", 0);
    return;
  }
  const x = Number(hit.attr("x")) + Number(hit.attr("width")) / 2;
  rule.attr("x1", x).attr("x2", x).attr("opacity", 1);
}

function ariaLabel(kind: MarginalKind): string {
  if (kind === "sales") return "Daily sales";
  if (kind === "stockout") return "Daily missed sales";
  return "Daily spoilage";
}

/** Data join only — call on step / resize / new ViewModel, not on hover. */
export function renderMarginal(
  container: HTMLElement,
  history: Day[],
  kind: MarginalKind,
  height = 72,
  yMax?: number,
): void {
  const width = container.clientWidth || 720;
  const margin = {
    top: 8,
    right: CHART_MARGIN.right,
    bottom: kind === "spoilage" ? 22 : 4,
    left: CHART_MARGIN.left,
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
    .attr("aria-label", ariaLabel(kind));

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = padDaysToMinRange(history.map((d) => d.day));
  const step =
    days.length > 0 ? Math.max(0, innerW / days.length) : Math.max(0, innerW);

  const values = history.map((d) => {
    if (kind === "sales") return d.sales_total;
    if (kind === "stockout") return d.stockout;
    if (kind === "spoilage") return d.waste_total;
    return 0;
  });
  const maxV =
    (kind === "sales" || kind === "stockout") && yMax != null
      ? Math.max(1, yMax)
      : Math.max(1, d3.max(values) ?? 1);
  const y =
    kind === "sales" || kind === "stockout"
      ? d3.scaleLinear().domain([0, maxV]).range([innerH, 0])
      : d3.scaleLinear().domain([0, maxV]).range([0, innerH]);

  g.append("g")
    .attr("class", "day-hits")
    .attr("pointer-events", "none")
    .selectAll("rect")
    .data(history, (d) => String((d as Day).day))
    .join("rect")
    .attr("class", "day-hit")
    .attr("data-day", (d) => d.day)
    .attr("x", (_, i) => i * step)
    .attr("y", 0)
    .attr("width", step)
    .attr("height", innerH);

  g.selectAll(".bar")
    .data(history, (d) => String((d as Day).day))
    .join("rect")
    .attr("class", `bar bar--${kind}`)
    .attr("data-day", (d) => d.day)
    .attr("pointer-events", "none")
    .attr("x", (_, i) => i * step + step * 0.12)
    .attr("width", Math.max(1, step * 0.76))
    .attr("y", (d) => {
      const v =
        kind === "stockout"
          ? d.stockout
          : kind === "sales"
            ? d.sales_total
            : d.waste_total;
      return kind === "spoilage" ? 0 : y(v);
    })
    .attr("height", (d) => {
      const v =
        kind === "stockout"
          ? d.stockout
          : kind === "sales"
            ? d.sales_total
            : d.waste_total;
      return kind === "spoilage" ? y(v) : innerH - y(v);
    })
    .attr("rx", 2)
    .call((sel) =>
      sel.append("title").text((d) => {
        const v =
          kind === "stockout"
            ? d.stockout
            : kind === "sales"
              ? d.sales_total
              : d.waste_total;
        return `Day ${d.day}: ${kind} ${v}`;
      }),
    );

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(2).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  if (kind === "spoilage") {
    const xAxis = d3
      .scaleBand<number>()
      .domain(days)
      .range([0, innerW])
      .padding(0);
    g.append("g")
      .attr("class", "axis axis-x")
      .attr("transform", `translate(0,${innerH})`)
      .call(
        d3
          .axisBottom(xAxis)
          .tickValues(pickDayTicks(days, innerW))
          .tickSizeOuter(0),
      )
      .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));
  }
}

/** Shared y-domain for waste / spoilage bars in the Primary stack. */
export function wasteBarYMax(history: Day[]): number {
  return Math.max(1, d3.max(history, (d) => d.waste_total) ?? 0);
}

/**
 * Waste (spoilage) bars over days — same x-band convention as `renderSalesDemand`
 * for hover-linking in the Primary chart stack.
 */
export function renderWasteBars(
  container: HTMLElement,
  history: Day[],
  height = 72,
  yMax?: number,
): void {
  const width = container.clientWidth || 720;
  const margin = {
    top: 8,
    right: CHART_MARGIN.right,
    bottom: 22,
    left: CHART_MARGIN.left,
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
    .attr("aria-label", "Daily spoilage");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = padDaysToMinRange(history.map((d) => d.day));
  const step =
    days.length > 0 ? Math.max(0, innerW / days.length) : Math.max(0, innerW);
  const maxV = yMax != null ? Math.max(1, yMax) : wasteBarYMax(history);
  const y = d3.scaleLinear().domain([0, maxV]).nice().range([innerH, 0]);

  g.append("g")
    .attr("class", "day-hits")
    .attr("pointer-events", "none")
    .selectAll("rect")
    .data(history, (d) => String((d as Day).day))
    .join("rect")
    .attr("class", "day-hit")
    .attr("data-day", (d) => d.day)
    .attr("x", (_, i) => i * step)
    .attr("y", 0)
    .attr("width", step)
    .attr("height", innerH);

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(2).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  const xAxis = d3
    .scaleBand<number>()
    .domain(days)
    .range([0, innerW])
    .padding(0.22);
  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(xAxis)
        .tickValues(pickDayTicks(days, innerW))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.selectAll<SVGRectElement, Day>(".bar")
    .data(history, (d) => String((d as Day).day))
    .join("rect")
    .attr("class", "bar bar--spoilage")
    .attr("data-day", (d) => d.day)
    .attr("pointer-events", "none")
    .attr("x", (d) => xAxis(d.day) ?? 0)
    .attr("width", Math.max(0, xAxis.bandwidth()))
    .attr("y", (d) => y(d.waste_total))
    .attr("height", (d) => Math.max(0, innerH - y(d.waste_total)))
    .attr("rx", 2);

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");
}

/** Hover styling for `renderWasteBars` (same contract as `setMarginalHover`). */
export function setWasteBarsHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  setMarginalHover(container, hoveredDay);
}
