/**
 * Pre-WASM chart hatch shells — fixed slot geometry before D3 render.
 */
// @vitest-environment jsdom
import { render } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { ChartLoadingShell } from "./ChartLoadingShell";

describe("ChartLoadingShell", () => {
  it("renders hatch overlay without caption text", () => {
    const { container } = render(
      createElement(ChartLoadingShell, {
        className: "chart-pnl-economics",
      }),
    );
    const shell = container.querySelector("[data-testid='chart-loading-shell']");
    expect(shell).not.toBeNull();
    expect(shell?.querySelector("[data-loading-hatch]")).not.toBeNull();
    expect(shell?.className).toMatch(/chart-unavailable/);
    expect(shell?.className).toMatch(/chart-pnl-economics/);
    expect(shell?.textContent?.trim()).toBe("");
    expect(shell?.getAttribute("aria-hidden")).toBe("true");
  });
});
