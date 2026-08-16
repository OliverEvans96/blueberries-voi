/**
 * T-127 secondary: stacked freshness histogram with truth overlay.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { FlatBelief } from "../engine/types";
import type { Lot } from "../types";
import {
  freshnessHistogramDataFromFlat,
  renderFreshnessHistogram,
  type FreshnessHistogramData,
} from "./freshnessHistogram";

const TRUTH_LOTS: Lot[] = [
  { lot_id: 1, n: 10, mean_f: 0.85 },
  { lot_id: 2, n: 6, mean_f: 0.55 },
  { lot_id: 3, n: 4, mean_f: 0.35 },
];

const FLAT: FlatBelief = {
  L: 3,
  K: 4,
  lot_counts: [10, 6, 4],
  f_grid: [0.125, 0.375, 0.625, 0.875],
  f_marginals: [
    1, 0, 0, 0,
    0, 1, 0, 0,
    0, 0, 0, 1,
  ],
};

function host(): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { configurable: true, value: 420 });
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("freshnessHistogramDataFromFlat", () => {
  it("maps flat belief into per-lot bin masses and picks newest lot_id", () => {
    const data = freshnessHistogramDataFromFlat(FLAT, TRUTH_LOTS);
    expect(data.f_edges).toHaveLength(FLAT.K + 1);
    expect(data.segments).toHaveLength(3);
    expect(data.segments[0]!.masses[0]).toBeCloseTo(10);
    expect(data.segments[1]!.masses[1]).toBeCloseTo(6);
    expect(data.segments[2]!.masses[3]).toBeCloseTo(4);
    expect(data.highlight_lot_id).toBe(3);
  });
});

describe("renderFreshnessHistogram", () => {
  it("renders stacked segments per freshness bin (not floating bars)", () => {
    const el = host();
    const data = freshnessHistogramDataFromFlat(FLAT, TRUTH_LOTS);
    renderFreshnessHistogram(el, data, false);

    const svg = el.querySelector("svg");
    expect(svg).not.toBeNull();
    const segments = el.querySelectorAll(".freshness-stack-segment");
    expect(segments.length).toBeGreaterThan(0);

    const bin0Rects = [...segments].filter((node) => {
      const height = Number(node.getAttribute("height"));
      const title = node.querySelector("title")?.textContent ?? "";
      return height > 0 && title.includes("freshness 0.00–0.25");
    });
    expect(bin0Rects.length).toBe(1);
    expect(bin0Rects[0]?.getAttribute("height")).not.toBe("0");
  });

  it("marks the newest delivery lot with highlight class", () => {
    const el = host();
    const data = freshnessHistogramDataFromFlat(FLAT, TRUTH_LOTS);
    renderFreshnessHistogram(el, data, false);
    expect(el.querySelectorAll(".freshness-stack-series--highlight").length).toBe(1);
  });

  it("stacks the highlight lot underneath other lots in the same bin", () => {
    const el = host();
    const data: FreshnessHistogramData = {
      f_edges: [0, 0.5, 1],
      segments: [
        { lot_index: 0, lot_id: 1, masses: [5, 0] },
        { lot_index: 1, lot_id: 2, masses: [3, 0] },
      ],
      truth_lots: [
        { lot_id: 1, n: 5, mean_f: 0.2 },
        { lot_id: 2, n: 3, mean_f: 0.2 },
      ],
      highlight_lot_id: 2,
    };
    renderFreshnessHistogram(el, data, false);

    const rects = [...el.querySelectorAll<SVGRectElement>(".freshness-stack-segment")].filter(
      (node) => (node.querySelector("title")?.textContent ?? "").includes("freshness 0.00–0.50"),
    );
    expect(rects).toHaveLength(2);

    const highlight = el.querySelector<SVGRectElement>(
      ".freshness-stack-series--highlight .freshness-stack-segment",
    );
    const other = rects.find((r) => !highlight?.isEqualNode(r));
    expect(highlight).not.toBeNull();
    expect(other).not.toBeUndefined();
    const yHighlight = Number(highlight!.getAttribute("y"));
    const yOther = Number(other!.getAttribute("y"));
    expect(yHighlight).toBeGreaterThan(yOther);
  });

  it("draws truth bars only when showTruth is true", () => {
    const elOff = host();
    const elOn = host();
    const data = freshnessHistogramDataFromFlat(FLAT, TRUTH_LOTS);

    renderFreshnessHistogram(elOff, data, false);
    renderFreshnessHistogram(elOn, data, true);

    expect(elOff.querySelectorAll(".truth-bar").length).toBe(0);
    expect(elOn.querySelectorAll(".truth-bar").length).toBe(TRUTH_LOTS.length);
  });

  it("truth bar height scales with Lot.n", () => {
    const el = host();
    const data = freshnessHistogramDataFromFlat(FLAT, TRUTH_LOTS);
    renderFreshnessHistogram(el, data, true);

    const bars = [...el.querySelectorAll<SVGRectElement>(".truth-bar")];
    const heights = bars.map((b) => Number(b.getAttribute("height")));
    expect(Math.max(...heights)).toBeGreaterThan(Math.min(...heights));
  });
});
