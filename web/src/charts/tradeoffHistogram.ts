/**
 * Option B joint histogram for nearest order-q candidate.
 */
import * as d3 from "d3";

export type JointHist = {
  waste_bins: number[];
  missed_bins: number[];
  counts: number[][];
};

export function renderTradeoffHistogram(
  svg: SVGSVGElement,
  hist: JointHist,
  currentQ: number,
): void {
  const width = 160;
  const height = 120;
  const root = d3.select(svg);
  root.selectAll("*").remove();
  root.attr("viewBox", `0 0 ${width} ${height}`);
  root.attr("data-order-q", String(currentQ));
  const cellW = width / hist.missed_bins.length;
  const cellH = height / hist.waste_bins.length;
  hist.counts.forEach((row, wi) => {
    row.forEach((c, mi) => {
      if (c <= 0) return;
      root
        .append("rect")
        .attr("class", "hist-cell")
        .attr("x", mi * cellW)
        .attr("y", wi * cellH)
        .attr("width", cellW - 1)
        .attr("height", cellH - 1)
        .attr("fill", "#5a7")
        .attr("opacity", Math.min(1, c / 10));
    });
  });
}
