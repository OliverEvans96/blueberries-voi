import * as d3 from "d3";
import type { HoverDay } from "../types";
import { CHART_MARGIN } from "../hoverLink";
import { padDaysToMinRange, pickDayTicks } from "./axisTicks";
import { salesDemandX } from "./salesDemand";

export type ControllerOrderPoint = {
  day: number;
  order_qty: number;
};

export type OrdersWastePoint = {
  day: number;
  order_qty: number;
  waste_total: number;
};

function rootG(
  container: HTMLElement,
): d3.Selection<SVGGElement, unknown, null, undefined> | null {
  const g = container.querySelector("svg g.chart-root");
  return g ? d3.select(g as SVGGElement) : null;
}

/** Map day history into an order-qty series (mirrors inventorySeries). */
export function controllerOrdersSeries(
  history: ReadonlyArray<{ day: number; order_qty: number }>,
): ControllerOrderPoint[] {
  return history.map((d) => ({ day: d.day, order_qty: d.order_qty }));
}

/** Order qty + waste totals per episode day. */
export function ordersWasteSeries(
  history: ReadonlyArray<{
    day: number;
    order_qty: number;
    waste_total: number;
  }>,
): OrdersWastePoint[] {
  return history.map((d) => ({
    day: d.day,
    order_qty: d.order_qty,
    waste_total: d.waste_total,
  }));
}

/** Style-only hover: vertical rule + day highlight. */
export function setControllerOrdersHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = rootG(container);
  if (!g) return;

  g.classed("is-hovering", hoveredDay != null);
  g.selectAll<SVGRectElement, ControllerOrderPoint>(".day-hit").classed(
    "day-hit--active",
    (d) => hoveredDay === d.day,
  );

  const rule = g.select<SVGLineElement>(".hover-rule");
  if (hoveredDay == null) {
    rule.attr("opacity", 0);
    return;
  }
  const days = g
    .selectAll<SVGRectElement, ControllerOrderPoint>(".day-hit")
    .data();
  const innerW = Number(g.attr("data-inner-w") ?? 0);
  if (!innerW || !days.length) {
    rule.attr("opacity", 0);
    return;
  }
  const dayNums = days.map((d) => d.day);
  const x = salesDemandX(dayNums, innerW, hoveredDay);
  rule.attr("x1", x).attr("x2", x).attr("opacity", 1);
}

/** Style-only hover for combined orders + waste chart. */
export function setOrdersWasteHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = rootG(container);
  if (!g) return;

  g.classed("is-hovering", hoveredDay != null);
  g.selectAll<SVGRectElement, OrdersWastePoint>(".day-hit").classed(
    "day-hit--active",
    (d) => hoveredDay === d.day,
  );

  const rule = g.select<SVGLineElement>(".hover-rule");
  if (hoveredDay == null) {
    rule.attr("opacity", 0);
    return;
  }
  const days = g
    .selectAll<SVGRectElement, OrdersWastePoint>(".day-hit")
    .data();
  const innerW = Number(g.attr("data-inner-w") ?? 0);
  if (!innerW || !days.length) {
    rule.attr("opacity", 0);
    return;
  }
  const dayNums = days.map((d) => d.day);
  const x = salesDemandX(dayNums, innerW, hoveredDay);
  rule.attr("x1", x).attr("x2", x).attr("opacity", 1);
}

/** Order quantity + spoilage over episode days — dual line chart. */
export function renderOrdersWaste(
  container: HTMLElement,
  history: ReadonlyArray<{
    day: number;
    order_qty: number;
    waste_total: number;
  }>,
  height = 130,
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

  const series = ordersWasteSeries(history);

  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Order quantity and spoilage over days");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("data-inner-w", String(innerW))
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = padDaysToMinRange(series.map((d) => d.day));
  const step = Math.max(0, innerW / days.length);
  const x = (day: number): number => salesDemandX(days, innerW, day);

  const orderMax = d3.max(series, (d) => d.order_qty) ?? 0;
  const wasteMax = d3.max(series, (d) => d.waste_total) ?? 0;
  const yMax = Math.max(orderMax, wasteMax, 1);
  const y = d3.scaleLinear().domain([0, yMax * 1.1]).nice().range([innerH, 0]);

  g.append("g")
    .attr("class", "day-hits")
    .attr("pointer-events", "none")
    .selectAll("rect")
    .data(series, (d) => String((d as OrdersWastePoint).day))
    .join("rect")
    .attr("class", "day-hit")
    .attr("data-day", (d) => d.day)
    .attr("x", (_, i) => i * step)
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

  const lineOrders = d3
    .line<OrdersWastePoint>()
    .x((d) => x(d.day))
    .y((d) => y(d.order_qty))
    .curve(d3.curveMonotoneX);
  const lineWaste = d3
    .line<OrdersWastePoint>()
    .x((d) => x(d.day))
    .y((d) => y(d.waste_total))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(series)
    .attr("class", "order-line")
    .attr("fill", "none")
    .attr("d", lineOrders);

  g.append("path")
    .datum(series)
    .attr("class", "waste-line")
    .attr("fill", "none")
    .attr("d", lineWaste);

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
  (
    [
      ["order-line", "Orders"],
      ["waste-line", "Spoilage"],
    ] as const
  ).forEach(([cls, label], i) => {
    const item = legend.append("g").attr("transform", `translate(${i * 72},0)`);
    item
      .append("line")
      .attr("class", cls)
      .attr("x1", 0)
      .attr("x2", 14)
      .attr("y1", 0)
      .attr("y2", 0);
    item
      .append("text")
      .attr("class", "legend-label")
      .attr("x", 18)
      .attr("y", 3)
      .text(label);
  });
}

/** Order quantity over episode days — per-day bar chart. */
export function renderControllerOrders(
  container: HTMLElement,
  history: ReadonlyArray<{ day: number; order_qty: number }>,
  height = 160,
): void {
  const width = container.clientWidth || 320;
  const margin = {
    top: 14,
    right: CHART_MARGIN.right,
    bottom: 28,
    left: 40,
  };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  if (innerW <= 0) return;

  const series = controllerOrdersSeries(history);

  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Order quantity over days");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("data-inner-w", String(innerW))
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = padDaysToMinRange(series.map((d) => d.day));
  const step = Math.max(0, innerW / days.length);
  const xBand = d3.scaleBand<number>().domain(days).range([0, innerW]).padding(0.22);

  g.append("g")
    .attr("class", "day-hits")
    .attr("pointer-events", "none")
    .selectAll("rect")
    .data(series, (d) => String((d as ControllerOrderPoint).day))
    .join("rect")
    .attr("class", "day-hit")
    .attr("data-day", (d) => d.day)
    .attr("x", (_, i) => i * step)
    .attr("y", 0)
    .attr("width", step)
    .attr("height", innerH);

  const orderMax = d3.max(series, (d) => d.order_qty) ?? 0;
  const yOrders = d3
    .scaleLinear()
    .domain([0, Math.max(orderMax, 1) * 1.1])
    .nice()
    .range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-y axis-y--orders")
    .call(d3.axisLeft(yOrders).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove())
    .call((sel) => sel.selectAll(".tick text").attr("fill", "var(--accent)"))
    .call((sel) => sel.selectAll(".tick line").attr("stroke", "var(--accent)"));

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(xBand)
        .tickValues(pickDayTicks(days, innerW))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.selectAll<SVGRectElement, ControllerOrderPoint>(".order-bar")
    .data(series, (d) => String((d as ControllerOrderPoint).day))
    .join("rect")
    .attr("class", "order-bar")
    .attr("data-day", (d) => d.day)
    .attr("x", (d) => xBand(d.day) ?? 0)
    .attr("width", Math.max(0, xBand.bandwidth()))
    .attr("y", (d) => yOrders(d.order_qty))
    .attr("height", (d) => Math.max(0, innerH - yOrders(d.order_qty)));

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");
}
