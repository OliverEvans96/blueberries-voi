/**
 * T-127 RED (qa-layout): Cockpit Grid 3-row shell — always-on panes.
 */
// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { render } from "@testing-library/react";
import { createElement } from "react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";
import { DEFAULT_SIM_CONFIG } from "../mock/generate";
import { DecisionRail } from "./DecisionRail";
import { StudioLayout } from "./StudioLayout";

const HERE = dirname(fileURLToPath(import.meta.url));
const LAYOUT_TS = join(HERE, "StudioLayout.tsx");

const REQUIRED_CHART_IDS = [
  "chart-sales",
  "chart-stockout",
  "chart-history",
  "chart-spoil",
  "chart-sales-demand",
  "chart-demand",
  "chart-inventory",
  "chart-age-comp",
  "chart-arrival-prior",
  "chart-arrival-shift",
  "chart-belief-age-marginal",
  "chart-belief-lg",
  "chart-controller-orders",
] as const;

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("StudioLayout cockpit grid (T-127 AC-layout)", () => {
  const layoutSrc = stripComments(readFileSync(LAYOUT_TS, "utf8"));

  it("uses cockpit-grid 3-row shell — not T-126 two-pane / focus-column", () => {
    expect(layoutSrc).toMatch(/cockpit-grid/);
    expect(layoutSrc).not.toMatch(/studio-layout--two-pane/);
    expect(layoutSrc).not.toMatch(/focus-column/);
  });

  it("renders three distinct row regions in DOM order", () => {
    const { container } = render(createElement(StudioLayout));
    const rows = container.querySelectorAll(
      ".cockpit-grid > .cockpit-row, .cockpit-grid > [data-cockpit-row]",
    );
    expect(rows.length).toBeGreaterThanOrEqual(3);
    const indices = Array.from(rows).map((el) =>
      Array.from(container.querySelectorAll(".cockpit-grid *")).indexOf(el),
    );
    for (let i = 1; i < indices.length; i++) {
      expect(indices[i]!).toBeGreaterThan(indices[i - 1]!);
    }
  });

  it("row 1 always shows Primary (#chart-history) and Secondary belief charts", () => {
    const { container } = render(createElement(StudioLayout));
    const history = container.querySelector("#chart-history");
    const beliefLg = container.querySelector("#chart-belief-lg");
    const beliefMarginal = container.querySelector("#chart-belief-age-marginal");
    expect(history).not.toBeNull();
    expect(beliefLg ?? beliefMarginal).not.toBeNull();
    const hiddenAncestor = history?.closest("[hidden]");
    expect(hiddenAncestor).toBeNull();
  });

  it("row 2 hosts Economics, Events, and Run panes", () => {
    const { container } = render(createElement(StudioLayout));
    expect(
      container.querySelector("#events-pane-host, [data-pane='events']"),
    ).not.toBeNull();
    expect(container.querySelector("#decision-rail-host")).not.toBeNull();
    expect(
      container.querySelector(
        "#economics-pane-host, [data-pane='economics'], .economics-pane",
      ),
    ).not.toBeNull();
  });

  it("row 3 tuning dock has tablist with 3 clusters and disabled Future chip", () => {
    const { container } = render(createElement(StudioLayout));
    const tablist = container.querySelector(
      '.tuning-dock [role="tablist"], [data-tuning-dock] [role="tablist"]',
    );
    expect(tablist).not.toBeNull();
    const clusters = tablist!.querySelectorAll(
      '[data-cluster], .tuning-cluster, [role="tab"]',
    );
    expect(clusters.length).toBeGreaterThanOrEqual(3);
    const future = container.querySelector(
      '[data-chip="future"], .future-chip, button[disabled][aria-disabled="true"]',
    );
    expect(future).not.toBeNull();
    expect(
      (future as HTMLButtonElement).disabled ||
        future?.getAttribute("aria-disabled") === "true",
    ).toBe(true);
  });

  it("all 13 D3ChartHost ids appear exactly once", () => {
    const { container } = render(createElement(StudioLayout));
    for (const id of REQUIRED_CHART_IDS) {
      const nodes = container.querySelectorAll(`#${id}`);
      expect(nodes.length, `expected exactly one #${id}`).toBe(1);
    }
    const idsInSource = REQUIRED_CHART_IDS.filter((id) =>
      layoutSrc.includes(`id="${id}"`),
    );
    expect(idsInSource.length).toBe(REQUIRED_CHART_IDS.length);
  });

  it("does not mount StoreChartTabs for always-on Primary/Secondary", () => {
    expect(layoutSrc).not.toMatch(/StoreChartTabs/);
  });

  it("renders run controls exactly once (no hidden PlayChrome duplicate)", () => {
    const { container } = render(createElement(StudioLayout));
    const host = container.querySelector("#decision-rail-host");
    expect(host).not.toBeNull();
    const root = createRoot(host!);
    flushSync(() => {
      root.render(
        createElement(DecisionRail, {
          vm: {
            episode_day: 1,
            window_days: 90,
            config: DEFAULT_SIM_CONFIG,
          },
          showTruth: false,
          orderQty: 24,
          activeSection: "demand",
          onAdvance: () => undefined,
          onReset: () => undefined,
          onAutopilotPlay: () => undefined,
          onAutopilotPause: () => undefined,
          onSetObsScenario: () => undefined,
          onShowTruthChange: () => undefined,
          onOrderChange: () => undefined,
        }),
      );
    });

    for (const id of ["order-range", "order-num", "btn-advance", "btn-reset"]) {
      const nodes = container.querySelectorAll(`#${id}`);
      expect(nodes.length, `expected exactly one #${id}`).toBe(1);
    }

    expect(container.querySelector("#play-chrome")).toBeNull();
    root.unmount();
  });
});
