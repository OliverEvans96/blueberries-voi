/**
 * T-127 Primary: sales vs demand stockout gap shading.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { Day } from "../types";
import { renderSalesDemand, setSalesDemandHover } from "./salesDemand";

function sampleDay(
  day: number,
  sales: number,
  demand: number,
): Day {
  return {
    day,
    lots: [],
    sales_total: sales,
    waste_total: 0,
    demand,
    order_qty: 0,
    arrivals: 0,
    stockout: Math.max(0, demand - sales),
    f_at_receipt: null,
  };
}

function host(): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { configurable: true, value: 400 });
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("renderSalesDemand stockout gap (T-127)", () => {
  it("renders chart-svg with sales and demand lines", () => {
    const el = host();
    renderSalesDemand(el, [
      sampleDay(0, 8, 10),
      sampleDay(1, 12, 12),
    ]);
    expect(el.querySelector("svg.chart-svg")).not.toBeNull();
    expect(el.querySelector(".sd-sales")).not.toBeNull();
    expect(el.querySelector(".sd-demand")).not.toBeNull();
  });

  it("shades red gap area when demand exceeds sales", () => {
    const el = host();
    renderSalesDemand(el, [
      sampleDay(0, 5, 10),
      sampleDay(1, 12, 12),
      sampleDay(2, 3, 9),
    ]);
    const gap = el.querySelector(".sales-demand-gap");
    expect(gap).not.toBeNull();
    expect(gap?.getAttribute("fill")).toMatch(/rgba?\(.*\)/);
    expect(gap?.getAttribute("d")).toBeTruthy();
  });

  it("omits gap path when demand never exceeds sales", () => {
    const el = host();
    renderSalesDemand(el, [
      sampleDay(0, 10, 8),
      sampleDay(1, 12, 12),
    ]);
    expect(el.querySelector(".sales-demand-gap")).toBeNull();
  });

  it("setSalesDemandHover shows vertical rule for hovered day", () => {
    const el = host();
    renderSalesDemand(el, [sampleDay(0, 5, 10), sampleDay(1, 8, 8)]);
    setSalesDemandHover(el, 0);
    expect(el.querySelector(".hover-rule")?.getAttribute("opacity")).toBe("1");
    setSalesDemandHover(el, null);
    expect(el.querySelector(".hover-rule")?.getAttribute("opacity")).toBe("0");
  });
});
