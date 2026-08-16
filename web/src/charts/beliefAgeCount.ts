import * as d3 from "d3";
import { beliefHeatmapAxisLabels } from "../engine/projector";
import type { BeliefGrid, Lot } from "../types";

function freshnessEdges(belief: BeliefGrid): number[] {
  return belief.f_edges ?? belief.freshness_edges ?? [];
}

function formatAxisValue(value: number): string {
  return value.toFixed(2);
}

/** Belief freshness×count heatmap with truth lot overlays. */
export function renderBeliefAgeCount(
  container: HTMLElement,
  belief: BeliefGrid,
  truthLots: Lot[] = [],
  height = 240,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 12, right: 12, bottom: 36, left: 44 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const xEdges = freshnessEdges(belief);
  const axisLabels = beliefHeatmapAxisLabels();

  container.replaceChildren();
  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Belief freshness heatmap with truth lot overlay");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const nF = belief.density.length;
  const nCount = belief.density[0]?.length ?? 0;
  if (nF === 0 || nCount === 0) return;

  const x = d3
    .scaleLinear()
    .domain([xEdges[0]!, xEdges[xEdges.length - 1]!])
    .range([0, innerW]);
  const y = d3
    .scaleLinear()
    .domain([
      belief.count_edges[0]!,
      belief.count_edges[belief.count_edges.length - 1]!,
    ])
    .range([innerH, 0]);

  const maxD = d3.max(belief.density, (row) => d3.max(row)) ?? 1;
  const color = d3
    .scaleSequential(d3.interpolateRgbBasis(["#f3efe6", "#9bbf9a", "#2f5d4a", "#17362c"]))
    .domain([0, maxD]);

  for (let fi = 0; fi < nF; fi++) {
    for (let ci = 0; ci < nCount; ci++) {
      const v = belief.density[fi]![ci]!;
      const x0 = x(xEdges[fi]!);
      const x1 = x(xEdges[fi + 1]!);
      const y0 = y(belief.count_edges[ci]!);
      const y1 = y(belief.count_edges[ci + 1]!);
      g.append("rect")
        .attr("x", x0)
        .attr("y", y1)
        .attr("width", Math.max(0, x1 - x0) + 0.5)
        .attr("height", Math.max(0, y0 - y1) + 0.5)
        .attr("fill", color(v))
        .append("title")
        .text(
          `freshness ${formatAxisValue(xEdges[fi]!)}–${formatAxisValue(xEdges[fi + 1]!)}, count ${belief.count_edges[ci]!.toFixed(0)}–${belief.count_edges[ci + 1]!.toFixed(0)}: ${(v * 100).toFixed(2)}%`,
        );
    }
  }

  const maxN = d3.max(truthLots, (l) => l.n) ?? 1;
  const r = d3.scaleSqrt().domain([0, maxN]).range([4, 11]);

  const truth = g.append("g").attr("class", "truth-overlay");
  truth
    .selectAll(".truth-lot")
    .data(truthLots)
    .join("g")
    .attr("class", "truth-lot")
    .attr("transform", (d) => `translate(${x(d.mean_f)},${y(d.n)})`)
    .each(function (d) {
      const gg = d3.select(this);
      const rad = r(d.n);
      gg.append("line")
        .attr("class", "truth-cross")
        .attr("x1", -rad - 2)
        .attr("x2", rad + 2)
        .attr("y1", 0)
        .attr("y2", 0);
      gg.append("line")
        .attr("class", "truth-cross")
        .attr("x1", 0)
        .attr("x2", 0)
        .attr("y1", -rad - 2)
        .attr("y2", rad + 2);
      gg.append("circle")
        .attr("class", "truth-circle")
        .attr("r", rad)
        .attr("fill", "none");
      gg.append("title").text(
        `truth lot ${d.lot_id}: f=${d.mean_f.toFixed(2)}, n=${d.n}`,
      );
    });

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(6).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(5).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 30)
    .attr("text-anchor", "middle")
    .text(axisLabels.x);

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", -innerH / 2)
    .attr("y", -34)
    .attr("transform", "rotate(-90)")
    .attr("text-anchor", "middle")
    .text(axisLabels.y);
}
