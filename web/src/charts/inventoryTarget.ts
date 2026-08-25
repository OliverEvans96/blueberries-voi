import * as d3 from "d3";
import type { FlatBelief } from "../engine/types";
import type { BeliefHistoryDay, Day, HoverDay, SimConfig } from "../types";
import { CHART_MARGIN } from "../hoverLink";
import { effectiveInventoryFromLots } from "../mock/generate";
import { padDaysToMinRange, pickDayTicks } from "./axisTicks";
import { salesDemandX } from "./salesDemand";

function rootG(
  container: HTMLElement | null,
): d3.Selection<SVGGElement, unknown, null, undefined> | null {
  if (!container) return null;
  const g = container.querySelector("svg g.chart-root");
  return g ? d3.select(g as SVGGElement) : null;
}

/** Style-only hover for effective-inventory vs target chart. */
export function setInventoryTargetHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = rootG(container);
  if (!g) return;

  g.classed("is-hovering", hoveredDay != null);
  g.selectAll<SVGRectElement, InventoryPoint>(".day-hit").classed(
    "day-hit--active",
    (d) => hoveredDay === d.day,
  );

  const rule = g.select<SVGLineElement>(".hover-rule");
  if (hoveredDay == null) {
    rule.attr("opacity", 0);
    return;
  }
  const days = g
    .selectAll<SVGRectElement, InventoryPoint>(".day-hit")
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

/** Style-only hover for on-hand freshness-band composition chart. */
export function setFreshnessCompositionHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = rootG(container);
  if (!g) return;

  g.classed("is-hovering", hoveredDay != null);
  g.selectAll<SVGRectElement, FreshnessCompositionRow>(".day-hit").classed(
    "day-hit--active",
    (d) => hoveredDay === d.day,
  );

  const rule = g.select<SVGLineElement>(".hover-rule");
  if (hoveredDay == null) {
    rule.attr("opacity", 0);
    return;
  }
  const days = g
    .selectAll<SVGRectElement, FreshnessCompositionRow>(".day-hit")
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

export type InventoryPoint = {
  day: number;
  on_hand: number;
  effective: number;
};

export type FreshnessCompositionRow = {
  day: number;
  fresh: number;
  mid: number;
  stale: number;
};

export type InventorySeriesOpts = {
  from: "lots" | "belief";
  belief_history?: BeliefHistoryDay[];
};

/** E[f]-weighted on-hand: Σ_l n_l Σ_k p(l,k) f_k (ADR 0130). */
export function effectiveInventoryFromFlatBelief(flat: FlatBelief): number {
  const { L, K, lot_counts, f_marginals, f_grid } = flat;
  let sum = 0;
  for (let l = 0; l < L; l++) {
    const n = lot_counts[l] ?? 0;
    for (let k = 0; k < K; k++) {
      sum += n * (f_marginals[l * K + k] ?? 0) * (f_grid[k] ?? 0);
    }
  }
  return sum;
}

export function expectedFreshnessBands(
  flat: FlatBelief,
): Pick<FreshnessCompositionRow, "fresh" | "mid" | "stale"> {
  const { L, K, lot_counts, f_marginals, f_grid } = flat;
  const bands = { fresh: 0, mid: 0, stale: 0 };
  for (let l = 0; l < L; l++) {
    const n = lot_counts[l] ?? 0;
    for (let k = 0; k < K; k++) {
      const mass = n * (f_marginals[l * K + k] ?? 0);
      const f = f_grid[k] ?? 0;
      if (f >= 2 / 3) bands.fresh += mass;
      else if (f >= 1 / 3) bands.mid += mass;
      else bands.stale += mass;
    }
  }
  return bands;
}

export function inventorySeries(
  history: Day[],
  _config: SimConfig,
  opts?: InventorySeriesOpts,
): InventoryPoint[] {
  if (opts?.from === "belief" && opts.belief_history) {
    return inventorySeriesFromBelief(opts.belief_history, _config);
  }
  return history.map((d) => ({
    day: d.day,
    on_hand: d.lots.reduce((s, l) => s + l.n, 0),
    effective: effectiveInventoryFromLots(d.lots),
  }));
}

export function inventorySeriesFromBelief(
  beliefHistory: BeliefHistoryDay[],
  _config: SimConfig,
): InventoryPoint[] {
  return beliefHistory.map((b) => ({
    day: b.day,
    on_hand: b.flatBelief.lot_counts.reduce((s, n) => s + n, 0),
    effective: effectiveInventoryFromFlatBelief(b.flatBelief),
  }));
}

export function fCompositionSeries(
  history: Day[],
  opts?: InventorySeriesOpts,
): FreshnessCompositionRow[] {
  if (opts?.from === "belief" && opts.belief_history) {
    return fCompositionSeriesFromBelief(opts.belief_history);
  }
  return history.map((d) => {
    const row: FreshnessCompositionRow = { day: d.day, fresh: 0, mid: 0, stale: 0 };
    for (const lot of d.lots) {
      const f = lot.mean_f;
      if (f >= 2 / 3) row.fresh += lot.n;
      else if (f >= 1 / 3) row.mid += lot.n;
      else row.stale += lot.n;
    }
    return row;
  });
}

export function fCompositionSeriesFromBelief(
  beliefHistory: BeliefHistoryDay[],
): FreshnessCompositionRow[] {
  return beliefHistory.map((b) => ({
    day: b.day,
    ...expectedFreshnessBands(b.flatBelief),
  }));
}

/** On-hand + E[f]-weighted inventory vs base-stock target. */
export function renderInventoryTarget(
  container: HTMLElement,
  history: Day[],
  config: SimConfig,
  height = 160,
  seriesOverride?: InventoryPoint[],
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

  const series = seriesOverride ?? inventorySeries(history, config);

  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "On-hand and effective inventory versus base-stock target");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("data-inner-w", String(innerW))
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = padDaysToMinRange(series.map((d) => d.day));
  const step = Math.max(0, innerW / days.length);
  const x = (day: number): number => salesDemandX(days, innerW, day);

  g.append("g")
    .attr("class", "day-hits")
    .attr("pointer-events", "none")
    .selectAll("rect")
    .data(series, (d) => String((d as InventoryPoint).day))
    .join("rect")
    .attr("class", "day-hit")
    .attr("data-day", (d) => d.day)
    .attr("x", (_, i) => i * step)
    .attr("y", 0)
    .attr("width", step)
    .attr("height", innerH);

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
        .tickValues(pickDayTicks(days, innerW))
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

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");

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

/**
 * Stacked on-hand by freshness band over the window.
 *
 * The legend always shows the consumer-facing "fresh" / "fair" / "old"
 * labels — regardless of whether `rowsOverride` came from the truth-data
 * path (`fCompositionSeries`) or the belief path
 * (`fCompositionSeriesFromBelief`). Both paths bucket units with the same
 * ≥⅔ / [⅓,⅔) / <⅓ freshness thresholds (see `expectedFreshnessBands`), so
 * there is no underlying data distinction left to label differently; a
 * former `bandMode` param that swapped in old fraction-threshold wording for
 * the truth path was a leftover of the pre-"fresh/fair/old" copy and made
 * the labels regress whenever "Sim truth overlay" was on.
 */
export type EffectiveInventoryPoint = {
  day: number;
  effective: number;
};

export function renderFreshnessComposition(
  container: HTMLElement,
  history: Day[],
  height = 140,
  rowsOverride?: FreshnessCompositionRow[],
  effectiveSeries?: EffectiveInventoryPoint[],
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 10, right: 12, bottom: 28, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  if (innerW <= 0) return;

  const bands = [
    { key: "fresh", label: "fresh", cls: "freshness-young" },
    { key: "mid", label: "fair", cls: "freshness-mid" },
    { key: "stale", label: "old", cls: "freshness-old" },
  ] as const;

  type Row = FreshnessCompositionRow;
  const rows: Row[] = rowsOverride ?? fCompositionSeries(history);

  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr(
      "aria-label",
      "On-hand inventory composition by freshness band",
    );

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("data-inner-w", String(innerW))
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = padDaysToMinRange(rows.map((r) => r.day));
  const step = Math.max(0, innerW / days.length);

  g.append("g")
    .attr("class", "day-hits")
    .attr("pointer-events", "none")
    .selectAll("rect")
    .data(rows, (d) => String((d as FreshnessCompositionRow).day))
    .join("rect")
    .attr("class", "day-hit")
    .attr("data-day", (d) => d.day)
    .attr("x", (_, i) => i * step)
    .attr("y", 0)
    .attr("width", step)
    .attr("height", innerH);

  const x = d3.scaleBand<number>().domain(days).range([0, innerW]).padding(0.18);
  const stackMax = d3.max(rows, (r) => r.fresh + r.mid + r.stale) ?? 0;
  const effectiveMax =
    effectiveSeries && effectiveSeries.length > 0
      ? (d3.max(effectiveSeries, (d) => d.effective) ?? 0)
      : 0;
  const yMax = Math.max(stackMax, effectiveMax, 1);
  const y = d3.scaleLinear().domain([0, yMax]).nice().range([innerH, 0]);

  const stack = d3
    .stack<Row>()
    .keys(["fresh", "mid", "stale"] as const)
    .order(d3.stackOrderNone)
    .offset(d3.stackOffsetNone);
  const series = stack(rows);
  const bandClassByKey = new Map(bands.map((b) => [b.key, b.cls]));

  g.selectAll(".freshness-series")
    .data(series)
    .join("g")
    .attr(
      "class",
      (d) => `freshness-series ${bandClassByKey.get(d.key as (typeof bands)[number]["key"]) ?? ""}`,
    )
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

  g.selectAll<SVGGElement, d3.Series<Row, string>>(".freshness-series").each(function (s) {
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
        .tickValues(pickDayTicks(days, innerW))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  if (effectiveSeries && effectiveSeries.length > 0) {
    const xCenter = (day: number): number =>
      (x(day) ?? 0) + x.bandwidth() / 2;
    const lineEff = d3
      .line<EffectiveInventoryPoint>()
      .x((d) => xCenter(d.day))
      .y((d) => y(d.effective))
      .curve(d3.curveMonotoneX);
    g.append("path")
      .datum(effectiveSeries)
      .attr("class", "inv-line inv-effective")
      .attr("fill", "none")
      .attr("d", lineEff);
  }

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
  let legendX = 0;
  for (const b of bands) {
    const item = legend.append("g").attr("transform", `translate(${legendX},0)`);
    item
      .append("rect")
      .attr("class", b.cls)
      .attr("width", 10)
      .attr("height", 10)
      .attr("rx", 2);
    item.append("text").attr("class", "legend-label").attr("x", 14).attr("y", 9).text(b.label);
    legendX += 58;
  }
  if (effectiveSeries && effectiveSeries.length > 0) {
    const item = legend.append("g").attr("transform", `translate(${legendX},0)`);
    item
      .append("line")
      .attr("class", "inv-line inv-effective")
      .attr("x1", 0)
      .attr("x2", 14)
      .attr("y1", 5)
      .attr("y2", 5);
    item
      .append("text")
      .attr("class", "legend-label")
      .attr("x", 18)
      .attr("y", 9)
      .text("Effective");
  }
}
