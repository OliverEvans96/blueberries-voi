/**
 * T-148: ImpactStat displays absolute and percent caption.
 */
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { ImpactStat } from "./ImpactStat";

describe("ImpactStat", () => {
  it("renders label, absolute count, and percent caption", () => {
    render(
      createElement(ImpactStat, {
        label: "Total missed sales",
        absolute: 12,
        percent: 0.125,
        percentCaption: "12.5% of cumulative demand",
      }),
    );
    expect(screen.getByText("Total missed sales")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("12.5% of cumulative demand")).toBeInTheDocument();
  });
});
