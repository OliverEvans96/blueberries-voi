import * as d3 from "d3";
import type { Day, EpisodeGhost, HoverDay } from "../types";
import { CHART_MARGIN } from "../hoverLink";

type MarginalKind = "sales" | "spoilage";

function rootG(
  container: HTMLElement,
): d3.Selection<SVGGElement, unknown, null, undefined> | null {
  const g = container.querySelector("svg g.chart-root");
  return g ? d3.select(g as SVGGElement) : null;
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

/** Data join only — call on step / resize / new ViewModel, not on hover. */
export function renderMarginal(
  container: HTMLElement,
  history: Day[],
  kind: MarginalKind,
  height = 72,
  ghost: EpisodeGhost | null = null,
): void {
  const width = container.clientWidth || 720;
  const margin = {
    top: 8,
    right: CHART_MARGIN.right,
    bottom: kind === "sales" ? 4 : 22,
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
    .attr("aria-label", kind === "sales" ? "Daily sales" : "Daily spoilage");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = history.map((d) => d.day);
  const step = days.length > 0 ? innerW / days.length : innerW;

  const values = history.map((d) =>
    kind === "sales" ? d.sales_total : d.waste_total,
  );
  const ghostVals =
    kind === "spoilage" && ghost
      ? ghost.series.slice(0, history.length).map((p) => p.waste)
      : [];
  const maxV = Math.max(1, d3.max(values) ?? 1, d3.max(ghostVals) ?? 0);
  const y =
    kind === "sales"
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

  if (kind === "spoilage" && ghostVals.length > 0) {
    g.selectAll(".bar-ghost")
      .data(ghostVals)
      .join("rect")
      .attr("class", "bar-ghost")
      .attr("pointer-events", "none")
      .attr("x", (_, i) => i * step + step * 0.12)
      .attr("width", Math.max(1, step * 0.76))
      .attr("y", 0)
      .attr("height", (v) => y(v))
      .attr("rx", 2);
  }

  g.selectAll(".bar")
    .data(history, (d) => String((d as Day).day))
    .join("rect")
    .attr("class", `bar bar--${kind}`)
    .attr("data-day", (d) => d.day)
    .attr("pointer-events", "none")
    .attr("x", (_, i) => i * step + step * 0.12)
    .attr("width", Math.max(1, step * 0.76))
    .attr("y", (d) => {
      const v = kind === "sales" ? d.sales_total : d.waste_total;
      return kind === "sales" ? y(v) : 0;
    })
    .attr("height", (d) => {
      const v = kind === "sales" ? d.sales_total : d.waste_total;
      return kind === "sales" ? innerH - y(v) : y(v);
    })
    .attr("rx", 2)
    .call((sel) =>
      sel.append("title").text((d) => {
        const v = kind === "sales" ? d.sales_total : d.waste_total;
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
          .tickValues(days.filter((_, i) => i % 2 === 0 || days.length < 10))
          .tickSizeOuter(0),
      )
      .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));
  }
}
