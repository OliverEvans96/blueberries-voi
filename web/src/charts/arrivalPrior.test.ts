/**
 * T-115: Arrival-prior receipt-age rug gated off without samples; .truth-* when on.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { DEFAULT_SIM_CONFIG } from "../mock/generate";
import type { Day } from "../types";
import { renderArrivalPrior } from "./arrivalPrior";

function day(partial: Partial<Day> & { day: number }): Day {
  return {
    lots: [],
    sales_total: 0,
    waste_total: 0,
    demand: 0,
    order_qty: 0,
    arrivals: 0,
    stockout: 0,
    f_at_receipt: null,
    ...partial,
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

describe("arrival prior receipt-age rug (T-115)", () => {
  it("draws zero rug marks when history has no f_at_receipt / arrivals", () => {
    const el = host();
    renderArrivalPrior(el, DEFAULT_SIM_CONFIG, [
      day({ day: 0, arrivals: 0, f_at_receipt: null }),
      day({ day: 1, arrivals: 0, f_at_receipt: 0.786 }),
    ]);
    expect(el.querySelectorAll(".arrival-rug").length).toBe(0);
    expect(el.querySelectorAll("[class*='truth']").length).toBe(0);
  });

  it("draws rug marks with a .truth-* class when receipt-age samples exist", () => {
    const el = host();
    renderArrivalPrior(el, DEFAULT_SIM_CONFIG, [
      day({ day: 0, arrivals: 8, f_at_receipt: 0.821 }),
      day({ day: 1, arrivals: 8, f_at_receipt: 0.714 }),
    ]);
    expect(el.querySelectorAll(".arrival-rug").length).toBeGreaterThan(0);
    const truthClassed = el.querySelectorAll(
      ".arrival-rug.truth-cross, .arrival-rug.truth-circle, [class*='truth-']",
    );
    expect(
      truthClassed.length,
      "arrival rug marks must use a .truth-* class",
    ).toBeGreaterThan(0);
  });
});
