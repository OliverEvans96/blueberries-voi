import * as d3 from "d3";
import type { Day, SimConfig } from "../types";
import { CHART_MARGIN } from "../hoverLink";
import { survivalWeightedInventory } from "../mock/generate";

export type InventoryPoint = {
  day: number;
  on_hand: number;
  effective: number;
};

export function inventorySeries(
  history: Day[],
  config: SimConfig,
): InventoryPoint[] {
  return history.map((d) => ({
    day: d.day,
    on_hand: d.lots.reduce((s, l) => s + l.n, 0),
    effective: survivalWeightedInventory(d.lots, config),
  }));
}

/** On-hand + survival-weighted inventory vs base-stock target. */
export function renderInventoryTarget(
  container: HTMLElement,
  history: Day[],
  config: SimConfig,
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
  const series = inventorySeries(history, config);
  if (series.length === 0) return;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "On-hand and effective inventory versus base-stock target");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = series.map((d) => d.day);
  const step = innerW / days.length;
  const x = (day: number): number => {
    const i = days.indexOf(day);
    return i * step + step / 2;
  };

  const target = config.base_stock;
  const yMax = Math.max(
    target,
    d3.max(series, (d) => Math.max(d.on_hand, d.effective)) ?? 0,
    1,
  );
  const y = d3.scaleLinear().domain([0, yMax * 1.08]).nice().range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(d3.scaleBand<number>().domain(days).range([0, innerW]).padding(0))
        .tickValues(days.filter((_, i) => i % 2 === 0 || days.length < 10))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("line")
    .attr("class", "target-line")
    .attr("x1", 0)
    .attr("x2", innerW)
    .attr("y1", y(target))
    .attr("y2", y(target));

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW - 2)
    .attr("y", y(target) - 4)
    .attr("text-anchor", "end")
    .text(`target ${target}`);

  const lineOn = d3
    .line<InventoryPoint>()
    .x((d) => x(d.day))
    .y((d) => y(d.on_hand))
    .curve(d3.curveMonotoneX);
  const lineEff = d3
    .line<InventoryPoint>()
    .x((d) => x(d.day))
    .y((d) => y(d.effective))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(series)
    .attr("class", "inv-line inv-onhand")
    .attr("fill", "none")
    .attr("d", lineOn);

  g.append("path")
    .datum(series)
    .attr("class", "inv-line inv-effective")
    .attr("fill", "none")
    .attr("d", lineEff);

  const legend = svg
    .append("g")
    .attr("class", "legend")
    .attr("transform", `translate(${margin.left + 4}, 10)`);
  (
    [
      ["inv-onhand", "On-hand"],
      ["inv-effective", "Effective"],
    ] as const
  ).forEach(([cls, label], i) => {
    const item = legend.append("g").attr("transform", `translate(${i * 88},0)`);
    item
      .append("line")
      .attr("class", `inv-line ${cls}`)
      .attr("x1", 0)
      .attr("x2", 14)
      .attr("y1", 0)
      .attr("y2", 0);
    item.append("text").attr("class", "legend-label").attr("x", 18).attr("y", 3).text(label);
  });
}

/** Stacked on-hand by age band over the window. */
export function renderAgeComposition(
  container: HTMLElement,
  history: Day[],
  height = 140,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 10, right: 12, bottom: 28, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  if (history.length === 0) return;

  const bands = [
    { key: "young", label: "0–2d", lo: 0, hi: 2, cls: "age-young" },
    { key: "mid", label: "3–5d", lo: 3, hi: 5, cls: "age-mid" },
    { key: "old", label: "6d+", lo: 6, hi: 999, cls: "age-old" },
  ] as const;

  type Row = { day: number; young: number; mid: number; old: number };
  const rows: Row[] = history.map((d) => {
    const row = { day: d.day, young: 0, mid: 0, old: 0 };
    for (const lot of d.lots) {
      if (lot.tau <= 2) row.young += lot.n;
      else if (lot.tau <= 5) row.mid += lot.n;
      else row.old += lot.n;
    }
    return row;
  });

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "On-hand inventory composition by age band");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = rows.map((r) => r.day);
  const x = d3.scaleBand<number>().domain(days).range([0, innerW]).padding(0.18);
  const yMax = d3.max(rows, (r) => r.young + r.mid + r.old) ?? 1;
  const y = d3.scaleLinear().domain([0, yMax]).nice().range([innerH, 0]);

  const stack = d3
    .stack<Row>()
    .keys(["young", "mid", "old"] as const)
    .order(d3.stackOrderNone)
    .offset(d3.stackOffsetNone);
  const series = stack(rows);

  g.selectAll(".age-series")
    .data(series)
    .join("g")
    .attr("class", (d) => `age-series age-${d.key}`)
    .selectAll("rect")
    .data((d) => d)
    .join("rect")
    .attr("x", (d) => x(d.data.day) ?? 0)
    .attr("width", x.bandwidth())
    .attr("y", (d) => y(d[1]))
    .attr("height", (d) => Math.max(0, y(d[0]) - y(d[1])))
    .append("title")
    .text((d) => {
      const key = (d as unknown as { key?: string }).key;
      void key;
      return `Day ${d.data.day}`;
    });

  // Fix titles with band labels
  g.selectAll<SVGGElement, d3.Series<Row, string>>(".age-series").each(function (s) {
    const band = bands.find((b) => b.key === s.key);
    d3.select(this)
      .selectAll("title")
      .text((d) => {
        const pt = d as d3.SeriesPoint<Row>;
        const v = pt[1] - pt[0];
        return `Day ${pt.data.day}: ${band?.label ?? s.key} ${v}`;
      });
  });

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(3).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(x)
        .tickValues(days.filter((_, i) => i % 2 === 0 || days.length < 10))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  const legend = svg
    .append("g")
    .attr("class", "legend")
    .attr("transform", `translate(${margin.left + 4}, 8)`);
  bands.forEach((b, i) => {
    const item = legend.append("g").attr("transform", `translate(${i * 58},0)`);
    item
      .append("rect")
      .attr("class", b.cls)
      .attr("width", 10)
      .attr("height", 10)
      .attr("rx", 2);
    item.append("text").attr("class", "legend-label").attr("x", 14).attr("y", 9).text(b.label);
  });
}
