/**
 * T-127 Primary: waste line for Primary chart stack.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { Day } from "../types";
import {
  renderWasteBars,
  setWasteBarsHover,
  wasteBarYMax,
} from "./marginals";

function sampleDay(day: number, waste: number): Day {
  return {
    day,
    lots: [],
    sales_total: 10,
    waste_total: waste,
    demand: 12,
    order_qty: 0,
    arrivals: 0,
    stockout: 0,
    f_at_receipt: null,
  };
}

function host(): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { configurable: true, value: 720 });
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("renderWasteBars (T-127)", () => {
  it("exports wasteBarYMax from waste_total", () => {
    expect(wasteBarYMax([sampleDay(0, 3), sampleDay(1, 9)])).toBe(9);
    expect(wasteBarYMax([])).toBe(1);
  });

  it("renders chart-svg spoilage bars with x-axis", () => {
    const el = host();
    renderWasteBars(el, [sampleDay(0, 2), sampleDay(1, 5), sampleDay(2, 1)]);
    expect(el.querySelector("svg.chart-svg")).not.toBeNull();
    expect(el.querySelector("path.waste-line")).toBeNull();
    expect(el.querySelector(".bar--spoilage")).not.toBeNull();
    expect(el.querySelector(".axis-x")).not.toBeNull();
  });

  it("setWasteBarsHover activates hover rule", () => {
    const el = host();
    renderWasteBars(el, [sampleDay(0, 2), sampleDay(1, 5)]);
    setWasteBarsHover(el, 1);
    expect(el.querySelector(".hover-rule")?.getAttribute("opacity")).toBe("1");
    setWasteBarsHover(el, null);
    expect(el.querySelector(".hover-rule")?.getAttribute("opacity")).toBe("0");
  });
});
