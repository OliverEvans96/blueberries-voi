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

/** Map pointer X over a chart SVG to a day index using equal-width day bands. */
export function dayFromClientX(
  svg: SVGSVGElement,
  clientX: number,
  days: readonly number[],
  marginLeft = CHART_MARGIN.left,
  marginRight = CHART_MARGIN.right,
): number | null {
  if (days.length === 0) return null;

  const resolvedLeft = marginFromSvgAttr(svg, "data-margin-left", marginLeft);
  const resolvedRight = marginFromSvgAttr(svg, "data-margin-right", marginRight);

  const rect = svg.getBoundingClientRect();
  if (rect.width <= 0) return null;

  const viewBox = svg.viewBox.baseVal;
  const svgWidth = viewBox.width > 0 ? viewBox.width : rect.width;
  const localX = ((clientX - rect.left) / rect.width) * svgWidth;
  const innerX = localX - resolvedLeft;
  const innerW = svgWidth - resolvedLeft - resolvedRight;
  if (innerX < 0 || innerX > innerW) return null;

  const i = Math.min(
    days.length - 1,
    Math.max(0, Math.floor((innerX / innerW) * days.length)),
  );
  return days[i] ?? null;
}

export type HoverPoint = { clientX: number; clientY: number } | null;

export type LinkedHoverHandlers = {
  onDay: (day: HoverDay, point: HoverPoint) => void;
};

/**
 * One shared hover controller for stacked/linked charts.
 * Uses pointermove + day-from-x; only clears when leaving the whole region
 * (not when crossing captions / chart gaps).
 */
export function attachLinkedHover(
  root: HTMLElement,
  getDays: () => readonly number[],
  handlers: LinkedHoverHandlers,
): () => void {
  const onMove = (event: PointerEvent): void => {
    const target = event.target as Element | null;
    if (!target) return;
    const svg = target.closest("svg.chart-svg") as SVGSVGElement | null;
    if (!svg || !root.contains(svg)) return;

    const day = dayFromClientX(svg, event.clientX, getDays());
    // Keep prior day while over y-axis gutter / legend; only set when resolved
    if (day != null) {
      handlers.onDay(day, {
        clientX: event.clientX,
        clientY: event.clientY,
      });
    }
  };

  const onLeave = (event: PointerEvent): void => {
    const next = event.relatedTarget as Node | null;
    if (next && root.contains(next)) return;
    handlers.onDay(null, null);
  };

  root.addEventListener("pointermove", onMove);
  root.addEventListener("pointerleave", onLeave);

  return () => {
    root.removeEventListener("pointermove", onMove);
    root.removeEventListener("pointerleave", onLeave);
  };
}
