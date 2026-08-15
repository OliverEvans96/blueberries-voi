/**
 * T-115: History lot circles gated by empty lots arrays; .truth-* when drawn.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { Day } from "../types";
import { renderHistory } from "./history";

function sampleDay(day: number, lots: Day["lots"]): Day {
  return {
    day,
    lots,
    sales_total: 10,
    waste_total: 1,
    demand: 12,
    order_qty: 8,
    arrivals: 8,
    stockout: 2,
    age_at_receipt: 1,
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

describe("history lot circles (T-115)", () => {
  it("draws zero .lot circles when history days have empty lots arrays", () => {
    const el = host();
    renderHistory(el, [sampleDay(0, []), sampleDay(1, [])], {
      width: 720,
      height: 220,
    });
    expect(el.querySelectorAll("circle.lot").length).toBe(0);
  });

  it("draws lot circles with a truth stroke class when lots are nonempty", () => {
    const el = host();
    renderHistory(
      el,
      [
        sampleDay(0, [{ lot_id: 1, n: 8, tau: 2 }]),
        sampleDay(1, [{ lot_id: 2, n: 4, tau: 5 }]),
      ],
      { width: 720, height: 220 },
    );
    const circles = el.querySelectorAll("circle.lot");
    expect(circles.length).toBeGreaterThan(0);
    const truthStroke = el.querySelectorAll(
      "circle.lot.truth-circle, circle.truth-circle, .lot.truth-circle",
    );
    expect(
      truthStroke.length,
      "history lot circles must carry .truth-circle (or .lot.truth-circle)",
    ).toBeGreaterThan(0);
  });
});
