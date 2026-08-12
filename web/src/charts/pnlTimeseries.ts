import * as d3 from "d3";
import type { DayPnL, HoverDay } from "../types";
import { CHART_MARGIN } from "../hoverLink";

function rootG(
  container: HTMLElement,
): d3.Selection<SVGGElement, unknown, null, undefined> | null {
  const g = container.querySelector("svg g.chart-root");
  return g ? d3.select(g as SVGGElement) : null;
}

/** Style-only: one guide + active class. No geometry rebuild. */
export function setPnLHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = rootG(container);
  if (!g) return;

  g.classed("is-hovering", hoveredDay != null);
  g.selectAll<SVGGElement, DayPnL>(".pnl-day").classed(
    "pnl-day--active",
    (d) => hoveredDay === d.day,
  );

  const rule = g.select<SVGLineElement>(".hover-rule");
  if (hoveredDay == null) {
    rule.attr("opacity", 0);
    return;
  }
  const hit = g
    .selectAll<SVGRectElement, DayPnL>(".day-hit")
    .filter((d) => d.day === hoveredDay);
  if (hit.empty()) {
    rule.attr("opacity", 0);
    return;
  }
  const x = Number(hit.attr("x")) + Number(hit.attr("width")) / 2;
  rule.attr("x1", x).attr("x2", x).attr("opacity", 1);
}

/** Data join only — stroke-only revenue / cost / profit lines. */
export function renderPnLTimeseries(
  container: HTMLElement,
  series: DayPnL[],
  height = 140,
): void {
  const width = container.clientWidth || 720;
  const margin = {
    top: 16,
    right: CHART_MARGIN.right,
    bottom: 28,
    left: CHART_MARGIN.left,
  };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Revenue, cost, and profit over days");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  if (series.length === 0) return;

  const days = series.map((d) => d.day);
  const step = innerW / days.length;
  const xCenter = (day: number): number => {
    const i = days.indexOf(day);
    return i * step + step / 2;
  };

  const yExtent = d3.extent(
    series.flatMap((d) => [d.revenue, d.cost_total, d.profit]),
  ) as [number, number];
  const pad = Math.max(2, (yExtent[1] - yExtent[0]) * 0.08);
  const y = d3
    .scaleLinear()
    .domain([yExtent[0] - pad, yExtent[1] + pad])
    .nice()
    .range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-y")
    .call(
      d3
        .axisLeft(y)
        .ticks(4)
        .tickFormat((v) => `$${d3.format(",.0f")(v as number)}`)
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").remove());

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
        .tickValues(days.filter((_, i) => i % 2 === 0 || days.length < 10))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  if (yExtent[0] < 0 && yExtent[1] > 0) {
    g.append("line")
      .attr("class", "zero-line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", y(0))
      .attr("y2", y(0))
      .attr("pointer-events", "none");
  }

  // Contiguous day bands for aligned hover + highlight
  g.append("g")
    .attr("class", "day-hits")
    .attr("pointer-events", "none")
    .selectAll("rect")
    .data(series, (d) => String((d as DayPnL).day))
    .join("rect")
    .attr("class", "day-hit")
    .attr("data-day", (d) => d.day)
    .attr("x", (_, i) => i * step)
    .attr("y", 0)
    .attr("width", step)
    .attr("height", innerH);

  const line = (key: keyof DayPnL) =>
    d3
      .line<DayPnL>()
      .x((d) => xCenter(d.day))
      .y((d) => y(d[key] as number))
      .curve(d3.curveMonotoneX);

  const seriesSpec: { key: keyof DayPnL; cls: string; label: string }[] = [
    { key: "revenue", cls: "series-revenue", label: "Revenue" },
    { key: "cost_total", cls: "series-cost", label: "Cost" },
    { key: "profit", cls: "series-profit", label: "Profit" },
  ];

  for (const s of seriesSpec) {
    g.append("path")
      .datum(series)
      .attr("class", `pnl-line ${s.cls}`)
      .attr("fill", "none")
      .attr("stroke-linejoin", "round")
      .attr("stroke-linecap", "round")
      .attr("pointer-events", "none")
      .attr("d", line(s.key));
  }

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");

  g.selectAll(".pnl-day")
    .data(series, (d) => String((d as DayPnL).day))
    .join("g")
    .attr("class", "pnl-day")
    .attr("data-day", (d) => d.day)
    .attr("transform", (d) => `translate(${xCenter(d.day)},0)`)
    .attr("pointer-events", "none")
    .each(function (d) {
      const gg = d3.select(this);
      for (const s of seriesSpec) {
        gg.append("circle")
          .attr("class", `pnl-dot ${s.cls}`)
          .attr("cy", y(d[s.key] as number))
          .attr("r", 3)
          .attr("fill", "currentColor")
          .attr("stroke", "var(--paper)")
          .attr("stroke-width", 1.5);
      }
      gg.append("title").text(
        `Day ${d.day}\nRev $${d.revenue.toFixed(0)} · Cost $${d.cost_total.toFixed(0)} · Profit $${d.profit.toFixed(0)}`,
      );
    });

  const legend = svg
    .append("g")
    .attr("class", "legend")
    .attr("pointer-events", "none")
    .attr("transform", `translate(${margin.left + 8}, 10)`);

  seriesSpec.forEach((s, i) => {
    const item = legend.append("g").attr("transform", `translate(${i * 88},0)`);
    item
      .append("line")
      .attr("class", `pnl-line ${s.cls}`)
      .attr("x1", 0)
      .attr("x2", 16)
      .attr("y1", 0)
      .attr("y2", 0);
    item
      .append("text")
      .attr("x", 22)
      .attr("y", 3)
      .attr("class", "legend-label")
      .text(s.label);
  });
}
