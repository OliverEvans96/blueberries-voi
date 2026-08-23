/**
 * T-148: ImpactStat displays absolute and percent caption.
 */
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { ImpactStat } from "./ImpactStat";

describe("ImpactStat", () => {
  it("renders a single-line units and percent caption", () => {
    render(
      createElement(ImpactStat, {
        label: "Total missed sales",
        absolute: 180,
        percent: 0.18,
        percentCaption: "18% of cumulative demand",
      }),
    );
    const stat = screen.getByTestId("impact-stat");
    expect(stat.textContent).toBe(
      "Total missed sales: 180 units (18% of cumulative demand)",
    );
    expect(stat.querySelector(".impact-stat-label")).not.toBeNull();
    expect(stat.querySelector(".impact-stat-value")).not.toBeNull();
  });
});
