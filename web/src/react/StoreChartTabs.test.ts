/**
 * T-126 RED (qa-storetabs): StoreChartTabs — tabbed store chart panels.
 */
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { StoreChartTabs, type StoreChartView } from "./StoreChartTabs";

const SALES_MOCK = createElement("div", {
  "data-testid": "sales-mock",
  children: [
    createElement("div", { id: "chart-sales" }),
    createElement("div", { id: "chart-stockout" }),
  ],
});

const AGE_MOCK = createElement("div", {
  "data-testid": "age-mock",
  children: [
    createElement("div", { id: "chart-history" }),
    createElement("div", { id: "chart-spoil" }),
  ],
});

function viewPanelFor(testId: string): HTMLElement {
  const node = screen.getByTestId(testId);
  const panel = node.parentElement;
  expect(panel).not.toBeNull();
  return panel!;
}

describe("StoreChartTabs (T-126 AC-storetabs)", () => {
  it("renders both tab labels in a tablist", () => {
    render(
      createElement(StoreChartTabs, {
        salesView: SALES_MOCK,
        ageView: AGE_MOCK,
      }),
    );

    const tablist = screen.getByRole("tablist");
    expect(tablist).toBeInTheDocument();

    expect(
      screen.getByRole("tab", { name: "Sales & stockouts" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Freshness & spoilage" }),
    ).toBeInTheDocument();
  });

  it("keeps both view subtrees mounted with all four chart host ids", () => {
    render(
      createElement(StoreChartTabs, {
        salesView: SALES_MOCK,
        ageView: AGE_MOCK,
      }),
    );

    expect(screen.getByTestId("sales-mock")).toBeInTheDocument();
    expect(screen.getByTestId("age-mock")).toBeInTheDocument();
    expect(document.getElementById("chart-sales")).not.toBeNull();
    expect(document.getElementById("chart-stockout")).not.toBeNull();
    expect(document.getElementById("chart-history")).not.toBeNull();
    expect(document.getElementById("chart-spoil")).not.toBeNull();
  });

  it("controlled: sales-stockouts active shows sales panel and hides age panel", () => {
    render(
      createElement(StoreChartTabs, {
        salesView: SALES_MOCK,
        ageView: AGE_MOCK,
        activeView: "sales-stockouts",
      }),
    );

    expect(
      screen.getByRole("tab", { name: "Sales & stockouts" }),
    ).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByRole("tab", { name: "Freshness & spoilage" }),
    ).toHaveAttribute("aria-selected", "false");

    expect(viewPanelFor("sales-mock").hasAttribute("hidden")).toBe(false);
    expect(viewPanelFor("age-mock").hasAttribute("hidden")).toBe(true);
  });

  it("controlled: freshness-spoilage active shows age panel and hides sales panel", () => {
    render(
      createElement(StoreChartTabs, {
        salesView: SALES_MOCK,
        ageView: AGE_MOCK,
        activeView: "freshness-spoilage",
      }),
    );

    expect(
      screen.getByRole("tab", { name: "Sales & stockouts" }),
    ).toHaveAttribute("aria-selected", "false");
    expect(
      screen.getByRole("tab", { name: "Freshness & spoilage" }),
    ).toHaveAttribute("aria-selected", "true");

    expect(viewPanelFor("sales-mock").hasAttribute("hidden")).toBe(true);
    expect(viewPanelFor("age-mock").hasAttribute("hidden")).toBe(false);
  });

  it("calls onSelectView with the clicked tab id (controlled)", () => {
    const onSelectView = vi.fn();
    render(
      createElement(StoreChartTabs, {
        salesView: SALES_MOCK,
        ageView: AGE_MOCK,
        activeView: "sales-stockouts",
        onSelectView,
      }),
    );

    fireEvent.click(screen.getByRole("tab", { name: "Freshness & spoilage" }));
    expect(onSelectView).toHaveBeenCalledTimes(1);
    expect(onSelectView).toHaveBeenCalledWith("freshness-spoilage");

    fireEvent.click(screen.getByRole("tab", { name: "Sales & stockouts" }));
    expect(onSelectView).toHaveBeenCalledTimes(2);
    expect(onSelectView).toHaveBeenLastCalledWith("sales-stockouts");
  });

  it("uncontrolled: defaults to sales-stockouts and toggles hidden on click", () => {
    const onSelectView = vi.fn();
    render(
      createElement(StoreChartTabs, {
        salesView: SALES_MOCK,
        ageView: AGE_MOCK,
        onSelectView,
      }),
    );

    expect(viewPanelFor("sales-mock").hasAttribute("hidden")).toBe(false);
    expect(viewPanelFor("age-mock").hasAttribute("hidden")).toBe(true);

    fireEvent.click(screen.getByRole("tab", { name: "Freshness & spoilage" }));
    expect(onSelectView).toHaveBeenCalledWith("freshness-spoilage");
    expect(viewPanelFor("sales-mock").hasAttribute("hidden")).toBe(true);
    expect(viewPanelFor("age-mock").hasAttribute("hidden")).toBe(false);

    fireEvent.click(screen.getByRole("tab", { name: "Sales & stockouts" }));
    expect(onSelectView).toHaveBeenLastCalledWith("sales-stockouts");
    expect(viewPanelFor("sales-mock").hasAttribute("hidden")).toBe(false);
    expect(viewPanelFor("age-mock").hasAttribute("hidden")).toBe(true);
  });

  it("uncontrolled: defaultView selects the initial active panel", () => {
    render(
      createElement(StoreChartTabs, {
        salesView: SALES_MOCK,
        ageView: AGE_MOCK,
        defaultView: "freshness-spoilage" satisfies StoreChartView,
      }),
    );

    expect(viewPanelFor("sales-mock").hasAttribute("hidden")).toBe(true);
    expect(viewPanelFor("age-mock").hasAttribute("hidden")).toBe(false);
    expect(
      screen.getByRole("tab", { name: "Freshness & spoilage" }),
    ).toHaveAttribute("aria-selected", "true");
  });
});
