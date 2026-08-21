/**
 * T-124 RED (qa-charts): unavailable chart placeholder — P0 spoilage gate.
 * T-126 RED (qa-hatch): hatch overlay containment — position + pointer-events CSS.
 */
// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import type { ScenarioId } from "../types";
import { ChartUnavailable } from "./ChartUnavailable";
import { resolveStoreSpoilageSlot } from "./chartSlots";

const STYLES_CSS = join(dirname(fileURLToPath(import.meta.url)), "../styles.css");

/** Extract the declaration block for a simple top-level CSS rule (no nested braces). */
function cssRuleBlock(selector: string, css: string): string | undefined {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))?.[1];
}

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

  it("custom channels with temperature_history resolve via channels, not scenario preset", () => {
    const slot = resolveStoreSpoilageSlot({
      channels: {
        code_type: "upc",
        scan_waste: true,
        delivery_history: "temperature_history",
      },
      showTruth: false,
    });
    expect(slot.kind).toBe("series");
  });
});

describe("ChartUnavailable hatch containment (T-126 AC-hatch)", () => {
  const css = readFileSync(STYLES_CSS, "utf8");

  it("renders unchanged DOM markers for chartSlots consumers", () => {
    render(
      createElement(ChartUnavailable, {
        plotId: "store-spoilage",
        caption: "Daily waste is not observed at this knowledge rung.",
      }),
    );
    const host = screen.getByRole("img", {
      name: /not observed|unavailable/i,
    });
    expect(host).toHaveAttribute("data-plot-id", "store-spoilage");
    expect(host).toHaveAttribute("data-unavailable", "true");
    expect(host).toHaveAttribute("aria-label", "Daily waste is not observed at this knowledge rung.");
    const hatch = host.querySelector("[data-unavailable-hatch]");
    expect(hatch).not.toBeNull();
    expect(hatch).toHaveAttribute("aria-hidden", "true");
    expect(hatch?.className).toBe("chart-unavailable-hatch");
  });

  it(".chart-unavailable rule declares position: relative so hatch absolute inset is scoped", () => {
    const block = cssRuleBlock(".chart-unavailable", css);
    expect(block, "expected .chart-unavailable rule in styles.css").toBeDefined();
    expect(block).toMatch(/position\s*:\s*relative\b/);
  });

  it(".chart-unavailable-hatch rule declares pointer-events: none so overlay cannot intercept clicks", () => {
    const block = cssRuleBlock(".chart-unavailable-hatch", css);
    expect(block, "expected .chart-unavailable-hatch rule in styles.css").toBeDefined();
    expect(block).toMatch(/pointer-events\s*:\s*none\b/);
  });
});
