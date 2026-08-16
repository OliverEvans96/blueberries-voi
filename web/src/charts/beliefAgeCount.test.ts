/**
 * T-115: Belief heatmap truth overlay nodes only when lots are passed.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { BeliefGrid, Lot } from "../types";
import { renderBeliefAgeCount } from "./beliefAgeCount";

const BELIEF: BeliefGrid = {
  f_edges: [0, 0.25, 0.5, 0.75, 1], freshness_edges: [0, 0.25, 0.5, 0.75, 1],
  count_edges: [0, 5, 10, 15],
  density: [
    [0.1, 0.05, 0.01],
    [0.08, 0.2, 0.04],
    [0.02, 0.1, 0.15],
  ],
};

const LOTS: Lot[] = [{ lot_id: 1, n: 8, mean_f: 0.857 }];

function host(): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { configurable: true, value: 400 });
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("beliefAgeCount truth overlay (T-115)", () => {
  it("draws zero .truth-cross / .truth-lot when truthLots is empty", () => {
    const el = host();
    renderBeliefAgeCount(el, BELIEF, []);
    expect(el.querySelectorAll(".truth-cross").length).toBe(0);
    expect(el.querySelectorAll(".truth-lot").length).toBe(0);
  });

  it("draws .truth-cross and .truth-lot when lots are passed", () => {
    const el = host();
    renderBeliefAgeCount(el, BELIEF, LOTS);
    expect(el.querySelectorAll(".truth-lot").length).toBeGreaterThan(0);
    expect(el.querySelectorAll(".truth-cross").length).toBeGreaterThan(0);
  });
});
