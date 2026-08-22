import type { HoverDay } from "./types";

export const CHART_MARGIN = {
  top: 12,
  right: 16,
  bottom: 28,
  left: 44,
} as const;

function marginFromSvgAttr(
  svg: SVGSVGElement,
  attr: string,
  fallback: number,
): number {
  const raw = svg.getAttribute(attr);
  if (raw == null) return fallback;
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

export type ChartPlotMargins = {
  top: number;
  right: number;
  bottom: number;
  left: number;
};

function plotMarginsFromSvg(
  svg: SVGSVGElement,
  fallback: ChartPlotMargins = CHART_MARGIN,
): ChartPlotMargins {
  return {
    top: marginFromSvgAttr(svg, "data-margin-top", fallback.top),
    right: marginFromSvgAttr(svg, "data-margin-right", fallback.right),
    bottom: marginFromSvgAttr(svg, "data-margin-bottom", fallback.bottom),
    left: marginFromSvgAttr(svg, "data-margin-left", fallback.left),
  };
}

/** Map pointer position over a chart SVG to a day index within the inner plot. */
export function dayFromPointer(
  svg: SVGSVGElement,
  clientX: number,
  clientY: number,
  days: readonly number[],
  marginFallback: ChartPlotMargins = CHART_MARGIN,
): number | null {
  if (days.length === 0) return null;

  const margin = plotMarginsFromSvg(svg, marginFallback);

  const rect = svg.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return null;

  const viewBox = svg.viewBox.baseVal;
  const svgWidth = viewBox.width > 0 ? viewBox.width : rect.width;
  const svgHeight = viewBox.height > 0 ? viewBox.height : rect.height;
  const localX = ((clientX - rect.left) / rect.width) * svgWidth;
  const localY = ((clientY - rect.top) / rect.height) * svgHeight;
  const innerX = localX - margin.left;
  const innerY = localY - margin.top;
  const innerW = svgWidth - margin.left - margin.right;
  const innerH = svgHeight - margin.top - margin.bottom;
  if (innerX < 0 || innerX > innerW || innerY < 0 || innerY > innerH) return null;

  const i = Math.min(
    days.length - 1,
    Math.max(0, Math.floor((innerX / innerW) * days.length)),
  );
  return days[i] ?? null;
}

/** @deprecated Prefer {@link dayFromPointer} for y-aware hit testing. */
export function dayFromClientX(
  svg: SVGSVGElement,
  clientX: number,
  days: readonly number[],
  marginLeft = CHART_MARGIN.left,
  marginRight = CHART_MARGIN.right,
): number | null {
  const rect = svg.getBoundingClientRect();
  const viewBox = svg.viewBox.baseVal;
  const svgHeight = viewBox.height > 0 ? viewBox.height : rect.height;
  const marginTop = marginFromSvgAttr(svg, "data-margin-top", CHART_MARGIN.top);
  const marginBottom = marginFromSvgAttr(
    svg,
    "data-margin-bottom",
    CHART_MARGIN.bottom,
  );
  const midY =
    rect.top + ((marginTop + (svgHeight - marginBottom)) / 2 / svgHeight) * rect.height;
  return dayFromPointer(svg, clientX, midY, days, {
    ...CHART_MARGIN,
    left: marginLeft,
    right: marginRight,
  });
}

export type HoverPoint = { clientX: number; clientY: number } | null;

/** Which linked chart initiated the hover (null when cleared). */
export type HoverChartSource =
  | "sales"
  | "spoilage"
  | "stockout"
  | "freshness"
  | "other"
  | null;

export function hoverChartSourceFromSvg(svg: SVGSVGElement): HoverChartSource {
  const host =
    svg.parentElement instanceof HTMLElement &&
    svg.parentElement.id.startsWith("chart-")
      ? svg.parentElement
      : (svg.closest("[id^='chart-']") as HTMLElement | null);
  if (!host) return "other";
  switch (host.id) {
    case "chart-sales":
    case "chart-sales-demand":
      return "sales";
    case "chart-spoil":
      return "spoilage";
    case "chart-stockout":
      return "stockout";
    case "chart-history":
      return "freshness";
    default:
      return "other";
  }
}

export type LinkedHoverHandlers = {
  onDay: (day: HoverDay, point: HoverPoint, source: HoverChartSource) => void;
};

/**
 * One shared hover controller for stacked/linked charts.
 * Uses pointermove + day-from-xy; clears when leaving the plot band or
 * non-chart gaps inside the linked region.
 */
export function attachLinkedHover(
  root: HTMLElement,
  getDays: () => readonly number[],
  handlers: LinkedHoverHandlers,
): () => void {
  const onMove = (event: PointerEvent): void => {
    const target = event.target as Element | null;
    if (!target) {
      handlers.onDay(null, null, null);
      return;
    }

    const svg = target.closest("svg.chart-svg") as SVGSVGElement | null;
    if (!svg || !root.contains(svg)) {
      handlers.onDay(null, null, null);
      return;
    }

    const source = hoverChartSourceFromSvg(svg);
    const day = dayFromPointer(svg, event.clientX, event.clientY, getDays());
    if (day != null) {
      handlers.onDay(
        day,
        {
          clientX: event.clientX,
          clientY: event.clientY,
        },
        source,
      );
    } else {
      handlers.onDay(null, null, null);
    }
  };

  const onLeave = (event: PointerEvent): void => {
    const next = event.relatedTarget as Node | null;
    if (next && root.contains(next)) return;
    handlers.onDay(null, null, null);
  };

  root.addEventListener("pointermove", onMove);
  root.addEventListener("pointerleave", onLeave);

  return () => {
    root.removeEventListener("pointermove", onMove);
    root.removeEventListener("pointerleave", onLeave);
  };
}
