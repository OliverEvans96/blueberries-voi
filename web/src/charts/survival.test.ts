/**
 * T-115: Survival lot rug gated off when lots=[]; .truth-* when present.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { DEFAULT_SIM_CONFIG } from "../mock/generate";
import type { Lot } from "../types";
import { renderSurvival } from "./survival";

const LOTS: Lot[] = [
  { lot_id: 1, n: 8, tau: 2 },
  { lot_id: 2, n: 4, tau: 5 },
];

function host(): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { configurable: true, value: 400 });
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("survival lot rug (T-115)", () => {
  it("draws zero rug marks when lots is empty", () => {
    const el = host();
    renderSurvival(el, DEFAULT_SIM_CONFIG, []);
    expect(el.querySelectorAll(".lot-rug").length).toBe(0);
    expect(el.querySelectorAll("[class*='truth']").length).toBe(0);
  });

  it("draws rug marks with a .truth-* class when lots are passed", () => {
    const el = host();
    renderSurvival(el, DEFAULT_SIM_CONFIG, LOTS);
    const rugs = el.querySelectorAll(".lot-rug, [class*='truth']");
    expect(rugs.length).toBeGreaterThan(0);
    const truthClassed = el.querySelectorAll(
      ".truth-circle, .truth-cross, .lot-rug.truth-circle, [class~='truth-circle'], [class*='truth-']",
    );
    expect(
      truthClassed.length,
      "survival rug marks must use a .truth-* class",
    ).toBeGreaterThan(0);
  });
});
