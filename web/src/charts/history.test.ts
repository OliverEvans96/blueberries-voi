/**
 * T-115: History lot circles gated by empty lots arrays; filled when drawn.
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
    f_at_receipt: 1,
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
    renderHistory(el, [sampleDay(0, []), sampleDay(1, [])], undefined, [], {
      width: 720,
      height: 220,
    });
    expect(el.querySelectorAll("circle.lot").length).toBe(0);
  });

  it("draws lot circles with age-based fill when lots are nonempty", () => {
    const el = host();
    renderHistory(
      el,
      [
        sampleDay(0, [{ lot_id: 1, n: 8, mean_f: 0.857 }]),
        sampleDay(1, [{ lot_id: 2, n: 4, mean_f: 0.643 }]),
      ],
      undefined,
      [],
      { width: 720, height: 220 },
    );
    const circles = el.querySelectorAll("circle.lot");
    expect(circles.length).toBeGreaterThan(0);
    for (const circle of circles) {
      const fill = circle.getAttribute("fill");
      expect(fill, "history lot circles must have a fill color").toBeTruthy();
      expect(fill).not.toBe("none");
      const fillOpacity = Number(circle.getAttribute("fill-opacity") ?? "1");
      expect(fillOpacity).toBeGreaterThan(0);
    }
  });
});
