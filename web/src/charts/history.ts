import * as d3 from "d3";
import type { Day, HoverDay } from "../types";
import { CHART_MARGIN } from "../hoverLink";

export type HistoryDims = {
  width: number;
  height: number;
  margin: { top: number; right: number; bottom: number; left: number };
};

type HeatCell = {
  day: number;
  dayIndex: number;
  age: number;
  n: number;
};

export function dayDomain(history: Day[]): [number, number] {
  if (history.length === 0) return [0, 1];
  const days = history.map((d) => d.day);
  return [Math.min(...days), Math.max(...days)];
}

function rootG(
  container: HTMLElement,
): d3.Selection<SVGGElement, unknown, null, undefined> | null {
  const g = container.querySelector("svg g.chart-root");
  return g ? d3.select(g as SVGGElement) : null;
}

/** Aggregate lot counts into day × integer age bins. */
export function binDayAge(history: Day[]): {
  days: number[];
  ages: number[];
  cells: HeatCell[];
  maxN: number;
} {
  const days = history.map((d) => d.day);
  const maxTau = Math.max(
    10,
    d3.max(history, (d) => d3.max(d.lots, (l) => Math.floor(l.tau))) ?? 10,
  );
  const ages = d3.range(0, maxTau + 1);
  const map = new Map<string, HeatCell>();

  history.forEach((d, dayIndex) => {
    for (const lot of d.lots) {
      const age = Math.max(0, Math.min(maxTau, Math.floor(lot.tau)));
      const key = `${d.day}:${age}`;
      const prev = map.get(key);
      if (prev) prev.n += lot.n;
      else map.set(key, { day: d.day, dayIndex, age, n: lot.n });
    }
  });

  // Ensure every day×age cell exists (zeros for empty bins → clean grid)
  const cells: HeatCell[] = [];
  history.forEach((d, dayIndex) => {
    for (const age of ages) {
      const key = `${d.day}:${age}`;
      cells.push(map.get(key) ?? { day: d.day, dayIndex, age, n: 0 });
    }
  });

  const maxN = d3.max(cells, (c) => c.n) ?? 0;
  return { days, ages, cells, maxN };
}

/** Style-only hover: day column + rule. Never rebinds geometry. */
export function setHistoryHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = rootG(container);
  if (!g) return;

  g.classed("is-hovering", hoveredDay != null);

  g.selectAll<SVGRectElement, Day>(".day-col").classed(
    "day-col--active",
    (d) => hoveredDay === d.day,
  );

  g.selectAll<SVGRectElement, HeatCell>(".heat-cell").classed(
    "heat-cell--dim",
    (d) => hoveredDay != null && hoveredDay !== d.day,
  );

  const rule = g.select<SVGLineElement>(".hover-rule");
  if (hoveredDay == null) {
    rule.attr("opacity", 0);
    return;
  }
  const col = g
    .selectAll<SVGRectElement, Day>(".day-col")
    .filter((d) => d.day === hoveredDay);
  if (col.empty()) {
    rule.attr("opacity", 0);
    return;
  }
  const x = Number(col.attr("x")) + Number(col.attr("width")) / 2;
  rule.attr("x1", x).attr("x2", x).attr("opacity", 1);
}

/** Day × age quantity heatmap (Viridis). Call on step / resize, not hover. */
export function renderHistory(
  container: HTMLElement,
  history: Day[],
  dims?: Partial<HistoryDims>,
): void {
  const width = dims?.width ?? (container.clientWidth || 720);
  const height = dims?.height ?? 220;
  const margin = {
    ...CHART_MARGIN,
    right: Math.max(CHART_MARGIN.right, 52),
    ...dims?.margin,
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
    .attr("role", "img")
    .attr("aria-label", "Inventory quantity heatmap by day and effective age");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const { days, ages, cells, maxN } = binDayAge(history);
  if (days.length === 0 || ages.length === 0) return;

  const cellW = innerW / days.length;
  const cellH = innerH / ages.length;

  // Age 0 at bottom (matches prior scatter y orientation)
  const y = d3
    .scaleBand<number>()
    .domain(ages)
    .range([innerH, 0])
    .paddingInner(0.04)
    .paddingOuter(0);

  const xAxis = d3
    .scaleBand<number>()
    .domain(days)
    .range([0, innerW])
    .padding(0);

  // Perceptually uniform sequential scale (Viridis)
  const color = d3
    .scaleSequential(d3.interpolateViridis)
    .domain([0, Math.max(1, maxN)]);

  g.append("g")
    .attr("class", "axis axis-y")
    .call(
      d3
        .axisLeft(y)
        .tickValues(ages.filter((a) => a % 2 === 0 || ages.length <= 8))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").remove());

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

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", -innerH / 2)
    .attr("y", -34)
    .attr("transform", "rotate(-90)")
    .attr("text-anchor", "middle")
    .text("Effective age τ (days)");

  // Heatmap cells (zeros get near-floor viridis for grid continuity)
  g.append("g")
    .attr("class", "heat-layer")
    .attr("pointer-events", "none")
    .selectAll("rect")
    .data(cells, (d) => `${(d as HeatCell).day}:${(d as HeatCell).age}`)
    .join("rect")
    .attr("class", "heat-cell")
    .attr("data-day", (d) => d.day)
    .attr("x", (d) => d.dayIndex * cellW)
    .attr("y", (d) => y(d.age) ?? 0)
    .attr("width", Math.max(0.5, cellW - 0.5))
    .attr("height", Math.max(0.5, (y.bandwidth() || cellH) - 0.25))
    .attr("fill", (d) => (d.n <= 0 ? "rgba(28, 36, 32, 0.04)" : color(d.n)))
    .attr("rx", 1)
    .append("title")
    .text((d) => `Day ${d.day} · age ${d.age} · qty ${d.n}`);

  // Day highlight bands (on top of heat for linked hover)
  g.append("g")
    .attr("class", "day-cols")
    .attr("pointer-events", "none")
    .selectAll("rect")
    .data(history, (d) => String((d as Day).day))
    .join("rect")
    .attr("class", "day-col")
    .attr("data-day", (d) => d.day)
    .attr("x", (_, i) => i * cellW)
    .attr("y", 0)
    .attr("width", cellW)
    .attr("height", innerH);

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");

  // Color legend (Viridis)
  const legendH = Math.min(innerH, 110);
  const legendW = 10;
  const legendX = innerW + 14;
  const legendY = (innerH - legendH) / 2;
  const legend = g.append("g").attr("class", "heat-legend");

  const defs = svg.append("defs");
  const gradId = `viridis-grad-${Math.round(Math.random() * 1e9)}`;
  const grad = defs
    .append("linearGradient")
    .attr("id", gradId)
    .attr("x1", "0%")
    .attr("x2", "0%")
    .attr("y1", "100%")
    .attr("y2", "0%");
  const stops = 12;
  for (let i = 0; i <= stops; i++) {
    const t = i / stops;
    grad
      .append("stop")
      .attr("offset", `${t * 100}%`)
      .attr("stop-color", d3.interpolateViridis(t));
  }

  legend
    .append("rect")
    .attr("x", legendX)
    .attr("y", legendY)
    .attr("width", legendW)
    .attr("height", legendH)
    .attr("fill", `url(#${gradId})`)
    .attr("rx", 2);

  const legendScale = d3
    .scaleLinear()
    .domain([0, Math.max(1, maxN)])
    .range([legendY + legendH, legendY]);

  legend
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(${legendX + legendW},0)`)
    .call(d3.axisRight(legendScale).ticks(4).tickSize(3).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  legend
    .append("text")
    .attr("class", "axis-label")
    .attr("x", legendX + legendW / 2)
    .attr("y", legendY - 6)
    .attr("text-anchor", "middle")
    .text("qty");
}
