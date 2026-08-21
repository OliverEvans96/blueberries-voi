/**
 * T-139: clamp day-band widths when plot area is narrower than margins.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { Day } from "../types";
import { renderMarginal, renderWasteBars } from "./marginals";

function sampleDay(day: number): Day {
  return {
    day,
    lots: [],
    sales_total: 8,
    waste_total: 2,
    demand: 10,
    order_qty: 0,
    arrivals: 0,
    stockout: 2,
    f_at_receipt: null,
  };
}

function narrowHost(width: number): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { configurable: true, value: width });
  document.body.appendChild(el);
  return el;
}

function assertNonNegativeWidths(el: HTMLElement): void {
  for (const rect of el.querySelectorAll("rect")) {
    const w = Number(rect.getAttribute("width"));
    expect(w, rect.outerHTML).toBeGreaterThanOrEqual(0);
  }
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("marginals narrow plot (T-139)", () => {
  it("renderMarginal skips draw when innerW <= 0", () => {
    const el = narrowHost(40);
    renderMarginal(el, [sampleDay(0), sampleDay(1)], "sales");
    expect(el.querySelector("svg.chart-svg")).toBeNull();
  });

  it("renderMarginal uses non-negative day-hit and bar widths when squeezed", () => {
    const el = narrowHost(80);
    renderMarginal(el, [sampleDay(0), sampleDay(1), sampleDay(2)], "sales");
    assertNonNegativeWidths(el);
    const bar = el.querySelector(".bar");
    expect(Number(bar?.getAttribute("width"))).toBeGreaterThanOrEqual(1);
  });

  it("renderWasteBars skips draw when innerW <= 0", () => {
    const el = narrowHost(40);
    renderWasteBars(el, [sampleDay(0), sampleDay(1)]);
    expect(el.querySelector("svg.chart-svg")).toBeNull();
  });

  it("renderWasteBars uses non-negative day-hit and bar widths when squeezed", () => {
    const el = narrowHost(80);
    renderWasteBars(el, [sampleDay(0), sampleDay(1), sampleDay(2)]);
    assertNonNegativeWidths(el);
    const bar = el.querySelector(".bar--spoilage");
    expect(Number(bar?.getAttribute("width"))).toBeGreaterThanOrEqual(1);
  });
});
