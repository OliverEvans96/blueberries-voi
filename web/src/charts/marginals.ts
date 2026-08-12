import * as d3 from "d3";
import type { Day, HoverDay } from "../types";
import { dayDomain, type HoverHandler } from "./history";

type MarginalKind = "sales" | "spoilage";

function rootG(
  container: HTMLElement,
): d3.Selection<SVGGElement, unknown, null, undefined> | null {
  const g = container.querySelector("svg g.chart-root");
  return g ? d3.select(g as SVGGElement) : null;
}

/** Highlight bars for a day without recreating them. */
export function setMarginalHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = rootG(container);
  if (!g) return;
  g.selectAll<SVGRectElement, Day>(".bar").classed(
    "bar--active",
    (d) => hoveredDay === d.day,
  );
}

/** Data join only — call on step / resize / new ViewModel, not on hover. */
export function renderMarginal(
  container: HTMLElement,
  history: Day[],
  kind: MarginalKind,
  onHoverDay: HoverHandler,
  height = 72,
): void {
  const width = container.clientWidth || 720;
  const margin = {
    top: 8,
    right: 16,
    bottom: kind === "sales" ? 4 : 22,
    left: 44,
  };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", kind === "sales" ? "Daily sales" : "Daily spoilage");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const [d0, d1] = dayDomain(history);
  const x = d3
    .scaleBand<number>()
    .domain(d3.range(d0, d1 + 1))
    .range([0, innerW])
    .padding(0.18);

  const values = history.map((d) =>
    kind === "sales" ? d.sales_total : d.waste_total,
  );
  const maxV = Math.max(1, d3.max(values) ?? 1);
  const y =
    kind === "sales"
      ? d3.scaleLinear().domain([0, maxV]).range([innerH, 0])
      : d3.scaleLinear().domain([0, maxV]).range([0, innerH]);

  g.selectAll(".bar")
    .data(history, (d) => String((d as Day).day))
    .join("rect")
    .attr("class", `bar bar--${kind}`)
    .attr("data-day", (d) => d.day)
    .attr("x", (d) => x(d.day) ?? 0)
    .attr("width", x.bandwidth())
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

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(2).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  if (kind === "spoilage") {
    g.append("g")
      .attr("class", "axis axis-x")
      .attr("transform", `translate(0,${innerH})`)
      .call(
        d3
          .axisBottom(x)
          .tickValues(
            x.domain().filter((_, i) => i % 2 === 0 || x.domain().length < 10),
          )
          .tickSizeOuter(0),
      )
      .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));
  }

  g.on("mouseover", (event: MouseEvent) => {
    const target = event.target as Element | null;
    if (!target) return;
    const hit = target.closest("[data-day]");
    if (!hit || !g.node()?.contains(hit)) return;
    const day = Number((hit as HTMLElement).dataset.day);
    if (!Number.isFinite(day)) return;
    onHoverDay(day);
  }).on("mouseleave", () => onHoverDay(null));
}
