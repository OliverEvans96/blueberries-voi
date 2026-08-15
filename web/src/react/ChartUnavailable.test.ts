/**
 * T-124 RED (qa-charts): unavailable chart placeholder — P0 spoilage gate.
 */
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import type { ScenarioId } from "../types";
import { ChartUnavailable } from "./ChartUnavailable";
import { resolveStoreSpoilageSlot } from "./chartSlots";

describe("ChartUnavailable (T-124 AC-avail spoilage placeholder)", () => {
  it("renders role=img, muted hatch, and unavailable caption", () => {
    render(
      createElement(ChartUnavailable, {
        plotId: "store-spoilage",
        caption: "Daily waste is not observed at this knowledge rung.",
      }),
    );
    const host = screen.getByRole("img", {
      name: /not observed|unavailable/i,
    });
    expect(host.className).toMatch(/chart-unavailable/);
    expect(
      host.querySelector(".chart-unavailable-hatch") ??
        document.querySelector("[data-unavailable-hatch]"),
    ).not.toBeNull();
    expect(screen.getByText(/not observed|unavailable/i)).toBeInTheDocument();
  });

  it("does not render a D3 svg series for unavailable spoilage", () => {
    const { container } = render(
      createElement(ChartUnavailable, {
        plotId: "store-spoilage",
        caption: "Daily waste is not observed at this knowledge rung.",
      }),
    );
    expect(container.querySelector("svg.d3-series")).toBeNull();
    expect(container.querySelector("[data-waste-series]")).toBeNull();
  });
});

describe("store spoilage slot gating (T-124)", () => {
  it("P0 resolves to unavailable placeholder instead of waste_total series", () => {
    const p0 = resolveStoreSpoilageSlot({
      scenario: "P0" satisfies ScenarioId,
      showTruth: false,
    });
    expect(p0.kind).toBe("unavailable");
    expect(p0.component).toBe(ChartUnavailable);
  });

  it("P1+ resolves to live spoilage series rendering", () => {
    for (const scenario of ["P1", "F1", "F1s", "F2a", "F2"] as const) {
      const slot = resolveStoreSpoilageSlot({ scenario, showTruth: false });
      expect(slot.kind, scenario).toBe("series");
    }
  });
});
