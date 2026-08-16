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
  const width = 190;
  const height = 150;
  const margin = { top: 8, right: 10, bottom: 32, left: 40 };
  const root = d3.select(svg);
  root.selectAll("*").remove();
  root.attr("viewBox", `0 0 ${width} ${height}`);
  root.attr("data-order-q", String(currentQ));

  const g = root
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  // waste_bins / missed_bins are bin *edges* (length = bin count + 1); the
  // degenerate fallback ({ waste_bins: [0], missed_bins: [0], counts: [[0]] }
  // from nearestForecast) has a single edge for a single cell.
  const nMissedBins = Math.max(1, hist.missed_bins.length - 1);
  const nWasteBins = Math.max(1, hist.waste_bins.length - 1);
  const cellW = innerW / nMissedBins;
  const cellH = innerH / nWasteBins;
  const maxCount = d3.max(hist.counts.flat()) || 1;

  hist.counts.forEach((row, wi) => {
    row.forEach((c, mi) => {
      if (c <= 0) return;
      g.append("rect")
        .attr("class", "hist-cell")
        .attr("x", mi * cellW)
        // Waste bin 0 at the bottom, increasing upward (conventional y-axis).
        .attr("y", innerH - (wi + 1) * cellH)
        .attr("width", Math.max(0, cellW - 1))
        .attr("height", Math.max(0, cellH - 1))
        .attr("fill", "#5a7")
        .attr("opacity", Math.min(1, c / Math.max(10, maxCount)));
    });
  });

  const missedExtent: [number, number] = [
    hist.missed_bins[0] ?? 0,
    hist.missed_bins[hist.missed_bins.length - 1] ?? 1,
  ];
  const wasteExtent: [number, number] = [
    hist.waste_bins[0] ?? 0,
    hist.waste_bins[hist.waste_bins.length - 1] ?? 1,
  ];
  const x = d3.scaleLinear().domain(missedExtent).range([0, innerW]);
  const y = d3.scaleLinear().domain(wasteExtent).range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 26)
    .attr("text-anchor", "middle")
    .text("Missed sales (units)");

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", -innerH / 2)
    .attr("y", -30)
    .attr("transform", "rotate(-90)")
    .attr("text-anchor", "middle")
    .text("Waste (units)");
}
