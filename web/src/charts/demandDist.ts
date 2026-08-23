import * as d3 from "d3";
import type { DemandSummary, ScheduleWire } from "../engine/types";
import type { Day, HoverDay } from "../types";
import { CHART_MARGIN } from "../hoverLink";
import { padDaysToMinRange, pickDayTicks } from "./axisTicks";
import { salesDemandX } from "./salesDemand";

const DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export const WEEKDAY_LABELS_MONDAY0 = [
  "Mon",
  "Tue",
  "Wed",
  "Thu",
  "Fri",
  "Sat",
  "Sun",
] as const;

const ORDER_WD_LABEL: Record<number, string> = {
  0: "Mon",
  1: "Tue",
  2: "Wed",
  3: "Thu",
  4: "Fri",
  5: "Sat",
  6: "Sun",
};

export function formatWeekdayList(weekdays: number[]): string {
  return weekdays
    .map((w) => ORDER_WD_LABEL[w] ?? `wd${w}`)
    .join(", ");
}

export type ProjectedDemandRow = {
  day: number;
  weekday: string;
  mean: number;
};

export const DEMAND_FORECAST_HORIZON = 5;

export type DemandForecastRow = ProjectedDemandRow & {
  p10: number;
  p50: number;
  p90: number;
};

/** Truncated NB pmf under ModelParams convention (r = μ/(vm−1), p = r/(r+μ)). */
export function nbPmf(
  mu: number,
  vm: number,
  kMax?: number,
): { k: number; p: number }[] {
  const safeMu = Math.max(0.1, mu);
  const safeVm = Math.max(1.05, vm);
  const r = safeMu / (safeVm - 1);
  const successP = r / (r + safeMu);
  const maxK =
    kMax ?? Math.min(200, Math.ceil(safeMu + 8 * Math.sqrt(safeMu * safeVm) + 20));

  const out: { k: number; p: number }[] = [];
  let pk = successP ** r;
  let sum = 0;
  for (let k = 0; k <= maxK; k += 1) {
    out.push({ k, p: pk });
    sum += pk;
    pk *= ((k + r) / (k + 1)) * (1 - successP);
    if (pk < 1e-12 && k > safeMu) break;
  }
  if (sum > 0) {
    for (const row of out) row.p /= sum;
  }
  return out;
}

function quantileFromPmf(pmf: { k: number; p: number }[], q: number): number {
  let cum = 0;
  for (const row of pmf) {
    cum += row.p;
    if (cum >= q) return row.k;
  }
  return pmf[pmf.length - 1]?.k ?? 0;
}

/** NB p10 / p50 / p90 for a single calendar day mean. */
export function nbQuantiles(
  mu: number,
  vm: number,
): { p10: number; p50: number; p90: number } {
  const pmf = nbPmf(mu, vm);
  return {
    p10: quantileFromPmf(pmf, 0.1),
    p50: quantileFromPmf(pmf, 0.5),
    p90: quantileFromPmf(pmf, 0.9),
  };
}

/**
 * Episode day for Sales & demand forecast overlay.
 * ViewModel `episode_day` is the next-act cursor (completed + 1); history ends on the
 * last completed day. Anchor on that day so the forecast band/line meets history.
 */
export function salesDemandForecastAnchor(
  history: readonly Pick<Day, "day">[],
  episodeDay: number,
): number {
  if (history.length === 0) return episodeDay;
  return history[history.length - 1]!.day;
}

/** Build forecast rows for Sales & demand overlay (episode day + DOW profile + NB bands). */
export function buildDemandForecastRows(
  episodeDay: number,
  summary: DemandSummary | null | undefined,
  demandVm: number,
): DemandForecastRow[] {
  return demandForecastRows(episodeDay, summary ?? FALLBACK_SUMMARY, demandVm);
}

/** Next N episode days with expected μ and NB uncertainty bands. */
export function demandForecastRows(
  episodeDay: number,
  summary: DemandSummary,
  demandVm: number,
  days = DEMAND_FORECAST_HORIZON,
): DemandForecastRow[] {
  const projected = projectedDemandDays(episodeDay, summary, days);
  return projected.map((row) => {
    const q = nbQuantiles(row.mean, demandVm);
    return { ...row, ...q };
  });
}

/** Next N episode days of expected demand from DOW profile (monday0 weekdays). */
export function projectedDemandDays(
  episodeDay: number,
  summary: DemandSummary,
  days = 5,
): ProjectedDemandRow[] {
  const series = dowSeriesFromDemandSummary(summary);
  const rows: ProjectedDemandRow[] = [];
  for (let offset = 0; offset < days; offset += 1) {
    const day = episodeDay + offset;
    const wd = day % 7;
    rows.push({
      day,
      weekday: WEEKDAY_LABELS_MONDAY0[wd] ?? `wd${wd}`,
      mean: series[wd] ?? summary.scale_mu,
    });
  }
  return rows;
}

/**
 * Picking weights on freshness bins — mirrors `physics::picking_weights_f`
 * (`w_i ∝ max(f_i, 0)^σ`, normalized).
 */
export function pickingWeightsF(freshness: number[], sigma: number): number[] {
  const n = freshness.length;
  if (n === 0) return [];
  if (sigma <= 0) {
    return Array.from({ length: n }, () => 1 / n);
  }
  const raw = freshness.map((fi) => Math.max(fi, 0) ** sigma);
  const total = raw.reduce((sum, w) => sum + w, 0);
  if (total <= 0) {
    return Array.from({ length: n }, () => 1 / n);
  }
  return raw.map((w) => w / total);
}

/** Unnormalized w(f) = f^σ on [0, 1] for illustrative σ curve. */
export function pickingWeightCurve(
  sigma: number,
  steps = 40,
): { f: number; w: number }[] {
  const pts: { f: number; w: number }[] = [];
  for (let i = 0; i <= steps; i += 1) {
    const f = i / steps;
    pts.push({ f, w: f ** Math.max(0, sigma) });
  }
  const total = pts.reduce((sum, p) => sum + p.w, 0);
  return pts.map((p) => ({
    f: p.f,
    w: total > 0 ? p.w / total : 0,
  }));
}

/** Small inline chart: how σ shapes lot picking weights across freshness. */
export function renderPickingVariability(
  container: HTMLElement,
  sigma: number,
  height = 72,
): void {
  const curve = pickingWeightCurve(sigma);
  // Guard against a not-yet-laid-out or still-hidden container reporting a
  // near-zero clientWidth (e.g. right after a tuning-dock tab switch) —
  // falling back only on exactly 0 let degenerate single-digit widths
  // through and produced a collapsed/garbled chart.
  const width = container.clientWidth > 60 ? container.clientWidth : 200;
  const margin = { top: 8, right: 8, bottom: 20, left: 28 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Picking weight curve w proportional to freshness sigma");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, 1]).range([0, innerW]);
  const y = d3
    .scaleLinear()
    .domain([0, d3.max(curve, (d) => d.w) ?? 1])
    .nice()
    .range([innerH, 0]);

  const area = d3
    .area<{ f: number; w: number }>()
    .x((d) => x(d.f))
    .y0(innerH)
    .y1((d) => y(d.w))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .attr("class", "picking-var-area")
    .attr("d", area(curve) ?? "");

  g.append("path")
    .attr("class", "picking-var-line")
    .attr("fill", "none")
    .attr(
      "d",
      d3
        .line<{ f: number; w: number }>()
        .x((d) => x(d.f))
        .y((d) => y(d.w))
        .curve(d3.curveMonotoneX)(curve) ?? "",
    );

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", 0)
    .attr("y", -2)
    .text(`w ∝ f^σ (σ=${sigma.toFixed(2)})`);
}

function demandRootG(
  container: HTMLElement,
): d3.Selection<SVGGElement, unknown, null, undefined> | null {
  const g = container.querySelector("svg g.chart-root");
  return g ? d3.select(g as SVGGElement) : null;
}

/** Style-only hover for daily demand chart. */
export function setDemandHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = demandRootG(container);
  if (!g) return;

  g.classed("is-hovering", hoveredDay != null);
  g.selectAll<SVGRectElement, Day>(".day-hit").classed(
    "day-hit--active",
    (d) => hoveredDay === d.day,
  );

  const rule = g.select<SVGLineElement>(".hover-rule");
  if (hoveredDay == null) {
    rule.attr("opacity", 0);
    return;
  }
  const days = g
    .selectAll<SVGRectElement, Day>(".day-hit")
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

/** Realized daily demand over the episode window. */
export function renderDailyDemand(
  container: HTMLElement,
  history: Day[],
  height = 140,
): void {
  const width = container.clientWidth > 60 ? container.clientWidth : 320;
  const margin = { top: 14, right: CHART_MARGIN.right, bottom: 28, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  if (innerW <= 0) return;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Daily demand over episode days");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("data-inner-w", String(innerW))
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = padDaysToMinRange(history.map((d) => d.day));
  const step = Math.max(0, innerW / days.length);
  const x = (day: number): number => salesDemandX(days, innerW, day);
  const yMax = d3.max(history, (d) => d.demand) ?? 1;
  const y = d3.scaleLinear().domain([0, yMax * 1.1]).nice().range([innerH, 0]);

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

  const lineDemand = d3
    .line<Day>()
    .x((d) => x(d.day))
    .y((d) => y(d.demand))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(history)
    .attr("class", "sd-line sd-demand daily-demand-line")
    .attr("fill", "none")
    .attr("d", lineDemand);

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");
}

export type ProtectionCoverageRow = {
  order_weekday: number;
  demand_days: number;
  label: string;
};

/** Length-7 monday0 DOW means from Snapshot demand_summary. */
export function dowSeriesFromDemandSummary(summary: DemandSummary): number[] {
  return [...summary.dow_means];
}

/**
 * Protection demand-day spans per order weekday (ADR 0114):
 * days until next order day + lead_time_days → 3 / 3 / 4 on Sun / Tue / Thu.
 */
export function protectionCoverageFromSchedule(
  schedule: ScheduleWire,
): ProtectionCoverageRow[] {
  const order = [...schedule.order_weekdays];
  const lead = Math.max(0, schedule.lead_time_days);
  return order.map((order_weekday) => {
    let gap = 7;
    for (let d = 1; d <= 7; d += 1) {
      const wd = (order_weekday + d) % 7;
      if (order.includes(wd)) {
        gap = d;
        break;
      }
    }
    const demand_days = gap + lead;
    const name = ORDER_WD_LABEL[order_weekday] ?? `wd${order_weekday}`;
    return {
      order_weekday,
      demand_days,
      label: `${name} ${demand_days}`,
    };
  });
}

/** Fallback when Snapshot has not yet supplied a profile. */
const FALLBACK_SUMMARY: DemandSummary = {
  scale_mu: 30,
  dow_means: [30, 30, 30, 30, 30, 30, 30],
};

/**
 * DOW demand profile (seven-day means) + protection coverage labels
 * (Sun/Tue/Thu → 3 / 3 / 4). Replaces the former i.i.d. μ-only PMF chart.
 */
export function renderDemandDist(
  container: HTMLElement,
  summary: DemandSummary | null | undefined,
  schedule: ScheduleWire | null | undefined,
  height = 140,
): void {
  const profile = summary ?? FALLBACK_SUMMARY;
  const series = dowSeriesFromDemandSummary(profile);
  const coverage = schedule
    ? protectionCoverageFromSchedule(schedule)
    : [];

  // Same not-yet-laid-out/hidden-container guard as renderPickingVariability.
  const width = container.clientWidth > 60 ? container.clientWidth : 320;
  const margin = { top: 28, right: 12, bottom: 36, left: 36 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr(
      "aria-label",
      "Demand DOW profile with order-day protection coverage",
    );

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const maxY = d3.max(series) ?? profile.scale_mu;
  const x = d3
    .scaleBand<string>()
    .domain([...DOW_LABELS])
    .range([0, innerW])
    .padding(0.2);
  const y = d3
    .scaleLinear()
    .domain([0, maxY * 1.15])
    .nice()
    .range([innerH, 0]);

  g.selectAll(".dow-bar")
    .data(series)
    .join("rect")
    .attr("class", "dow-bar pmf-bar")
    .attr("data-dow-mean", (d) => String(d))
    .attr("x", (_d, i) => x(DOW_LABELS[i]!) ?? 0)
    .attr("y", (d) => y(d))
    .attr("width", x.bandwidth())
    .attr("height", (d) => Math.max(0, innerH - y(d)));

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  const protText =
    coverage.length > 0
      ? `Protection ${coverage
          .map((r) => ORDER_WD_LABEL[r.order_weekday] ?? r.order_weekday)
          .join("/")} ${coverage.map((r) => r.demand_days).join(" / ")}`
      : "Protection —";

  // Explicit 3 / 3 / 4 chrome for default Sun/Tue/Thu schedule.
  const numericHint =
    coverage.length >= 3
      ? (() => {
          const by = new Map(coverage.map((r) => [r.order_weekday, r.demand_days]));
          if (by.get(6) === 3 && by.get(1) === 3 && by.get(3) === 4) {
            return " · Sun/Tue/Thu 3 / 3 / 4";
          }
          return "";
        })()
      : "";

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", 0)
    .attr("y", -10)
    .attr("text-anchor", "start")
    .text(`${protText}${numericHint}`);

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 30)
    .attr("text-anchor", "middle")
    .text(`DOW means · scale μ=${profile.scale_mu.toFixed(0)}`);
}

function forecastRootG(
  container: HTMLElement,
): d3.Selection<SVGGElement, unknown, null, undefined> | null {
  const g = container.querySelector("svg g.chart-root");
  return g ? d3.select(g as SVGGElement) : null;
}

/** Style-only hover for demand forecast chart. */
export function setDemandForecastHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = forecastRootG(container);
  if (!g) return;

  g.classed("is-hovering", hoveredDay != null);
  g.selectAll<SVGRectElement, DemandForecastRow>(".day-hit").classed(
    "day-hit--active",
    (d) => hoveredDay === d.day,
  );

  const rule = g.select<SVGLineElement>(".hover-rule");
  if (hoveredDay == null) {
    rule.attr("opacity", 0);
    return;
  }
  const innerW = Number(g.attr("data-inner-w") ?? 0);
  const days = g
    .selectAll<SVGRectElement, DemandForecastRow>(".day-hit")
    .data()
    .map((d) => d.day);
  if (!innerW || !days.length) {
    rule.attr("opacity", 0);
    return;
  }
  const x = salesDemandX(days, innerW, hoveredDay);
  rule.attr("x1", x).attr("x2", x).attr("opacity", 1);
}

/**
 * Known demand distribution — expected μ and p10–p90 over the next few days.
 * Uses Snapshot demand_summary (DOW calendar) + config demand_vm (NB dispersion).
 */
export function renderDemandForecast(
  container: HTMLElement,
  history: Day[],
  summary: DemandSummary | null | undefined,
  episodeDay: number,
  demandVm: number,
  height = 160,
): void {
  const profile = summary ?? FALLBACK_SUMMARY;
  const rows = demandForecastRows(episodeDay, profile, demandVm);
  const dayNums = rows.map((r) => r.day);
  const realized = history.filter((d) => dayNums.includes(d.day));

  const width = container.clientWidth > 60 ? container.clientWidth : 320;
  const margin = { top: 18, right: CHART_MARGIN.right, bottom: 28, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  if (innerW <= 0 || rows.length === 0) return;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr(
      "aria-label",
      "Known demand distribution forecast for the next few days",
    );

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("data-inner-w", String(innerW))
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = padDaysToMinRange(dayNums);
  const step = Math.max(0, innerW / days.length);
  const x = (day: number): number => salesDemandX(days, innerW, day);

  const yMax =
    d3.max([
      d3.max(rows, (r) => r.p90) ?? 0,
      d3.max(realized, (d) => d.demand) ?? 0,
    ]) ?? 1;
  const y = d3.scaleLinear().domain([0, yMax * 1.1]).nice().range([innerH, 0]);

  g.append("g")
    .attr("class", "day-hits")
    .attr("pointer-events", "none")
    .selectAll("rect")
    .data(rows, (d) => String((d as DemandForecastRow).day))
    .join("rect")
    .attr("class", "day-hit")
    .attr("data-day", (d) => d.day)
    .attr("x", (d) => {
      const i = days.indexOf(d.day);
      return i * step;
    })
    .attr("y", 0)
    .attr("width", step)
    .attr("height", innerH);

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
        .tickFormat((d) => {
          const row = rows.find((r) => r.day === d);
          return row ? `${row.weekday}` : `d${d}`;
        })
        .tickValues(pickDayTicks(days, innerW))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  const bandArea = d3
    .area<DemandForecastRow>()
    .x((d) => x(d.day))
    .y0((d) => y(d.p10))
    .y1((d) => y(d.p90))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(rows)
    .attr("class", "forecast-band")
    .attr("fill", "var(--chart-band, rgba(59, 130, 246, 0.18))")
    .attr("stroke", "none")
    .attr("d", bandArea);

  const meanLine = d3
    .line<DemandForecastRow>()
    .x((d) => x(d.day))
    .y((d) => y(d.mean))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(rows)
    .attr("class", "forecast-mean")
    .attr("fill", "none")
    .attr("stroke", "var(--chart-accent, #2563eb)")
    .attr("stroke-width", 2)
    .attr("stroke-dasharray", "5,3")
    .attr("d", meanLine);

  if (realized.length > 0) {
    const realizedLine = d3
      .line<Day>()
      .x((d) => x(d.day))
      .y((d) => y(d.demand))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(realized)
      .attr("class", "forecast-realized")
      .attr("fill", "none")
      .attr("stroke", "var(--chart-ink, #0f172a)")
      .attr("stroke-width", 2)
      .attr("d", realizedLine);

    g.selectAll<SVGCircleElement, Day>(".forecast-realized-dot")
      .data(realized, (d) => String((d as Day).day))
      .join("circle")
      .attr("class", "forecast-realized-dot")
      .attr("cx", (d) => x(d.day))
      .attr("cy", (d) => y(d.demand))
      .attr("r", 3);
  }

  g.append("line")
    .attr("class", "forecast-today")
    .attr("x1", x(episodeDay))
    .attr("x2", x(episodeDay))
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("stroke", "var(--chart-muted, #94a3b8)")
    .attr("stroke-width", 1)
    .attr("stroke-dasharray", "2,2")
    .attr("pointer-events", "none");

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", 0)
    .attr("y", -4)
    .attr("text-anchor", "start")
    .text(`Known demand · next ${rows.length} days (μ + p10–p90)`);

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");
}
