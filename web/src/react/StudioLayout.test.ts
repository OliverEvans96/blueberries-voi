/**
 * T-148: Cockpit Grid shell — layout v6.
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
import { OperatorBar } from "./OperatorBar";
import { StudioLayout } from "./StudioLayout";

const HERE = dirname(fileURLToPath(import.meta.url));
const LAYOUT_TS = join(HERE, "StudioLayout.tsx");
const COCKPIT_CSS = join(HERE, "../styles/cockpitGrid.css");

const REQUIRED_CHART_IDS = [
  "chart-sales",
  "chart-stockout",
  "chart-history",
  "chart-sales-demand",
  "chart-demand",
  "chart-inventory",
  "chart-age-comp",
  "chart-arrival-prior",
  "chart-arrival-shift",
  "chart-arrhenius-temp",
  "chart-gamma-path",
  "chart-belief-age-marginal",
  "chart-belief-lg",
  "chart-controller-orders",
  "chart-spoil",
  "chart-inventory-focus",
  "chart-controller-orders-focus",
  "chart-spoil-focus",
] as const;

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("StudioLayout cockpit grid (T-148 v6)", () => {
  const layoutSrc = stripComments(readFileSync(LAYOUT_TS, "utf8"));
  const cockpitCss = readFileSync(COCKPIT_CSS, "utf8");

  it("uses minimal title-bar header without hero chrome", () => {
    expect(layoutSrc).toMatch(/title-bar/);
    expect(layoutSrc).not.toMatch(/className="hero"/);
    expect(layoutSrc).not.toMatch(/insight-strip-host/);
    expect(layoutSrc).not.toMatch(/chapter-tabs-host/);
    expect(layoutSrc).not.toMatch(/guided-paths-host/);
  });

  it("defines layout v6 grid areas in cockpitGrid.css", () => {
    expect(cockpitCss).toMatch(/grid-template-areas/);
    expect(cockpitCss).toMatch(/metrics\s+belief\s+sidebar/);
    expect(cockpitCss).toMatch(/tuning\s+tuning\s+tuning/);
  });

  it("renders v6 data-layout and three column panes", () => {
    const { container } = render(createElement(StudioLayout));
    const grid = container.querySelector(".cockpit-grid[data-layout='v6']");
    expect(grid).not.toBeNull();
    expect(grid!.querySelector(".cockpit-pane--metrics")).not.toBeNull();
    expect(grid!.querySelector(".cockpit-pane--belief")).not.toBeNull();
    expect(grid!.querySelector(".cockpit-pane--sidebar")).not.toBeNull();
    expect(grid!.querySelector("#obs-controls-pane-host")).not.toBeNull();
    expect(grid!.querySelector("#pnl-totals-host")).not.toBeNull();
    expect(grid!.querySelector("#impact-missed-host")).not.toBeNull();
    expect(grid!.querySelector("#impact-waste-host")).not.toBeNull();
    expect(grid!.querySelector("#secondary-chrome-host")).toBeNull();
    expect(grid!.querySelector("#economics-pane-host")).toBeNull();
  });

  it("metrics column stacks P&L, charts, and impact stat hosts", () => {
    const { container } = render(createElement(StudioLayout));
    const metrics = container.querySelector(".cockpit-pane--metrics");
    expect(metrics).not.toBeNull();
    expect(metrics!.querySelector("#chart-pnl-economics")).not.toBeNull();
    expect(metrics!.querySelector("#chart-age-comp")).not.toBeNull();
    expect(metrics!.querySelector("#chart-inventory")).not.toBeNull();
    expect(metrics!.querySelector("#chart-controller-orders")).not.toBeNull();
    expect(metrics!.querySelector("#chart-spoil")).not.toBeNull();
    expect(metrics!.querySelector("#chart-sales-demand")).not.toBeNull();
    const impactRow = metrics!.querySelector(".impact-row");
    expect(impactRow).not.toBeNull();
    const totals = metrics!.querySelector("#pnl-totals-host");
    expect(
      totals!.compareDocumentPosition(impactRow!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      impactRow!.compareDocumentPosition(
        metrics!.querySelector("#chart-pnl-economics")!,
      ) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("belief column hosts tradeoff charts and operator bar", () => {
    const { container } = render(createElement(StudioLayout));
    const belief = container.querySelector(".cockpit-pane--belief");
    expect(belief!.querySelector("#tradeoff-curve-host")).not.toBeNull();
    expect(belief!.querySelector("#tradeoff-histogram-host")).not.toBeNull();
    expect(belief!.querySelector("#chart-history")).not.toBeNull();
    expect(belief!.querySelector("#chart-belief-lg")).not.toBeNull();
    expect(belief!.querySelector("#operator-bar-host")).not.toBeNull();
  });

  it("belief column tradeoff uses Curve/Histogram tab toggle", () => {
    const { container } = render(createElement(StudioLayout));
    const belief = container.querySelector(".cockpit-pane--belief");
    const tablist = belief!.querySelector(
      '.belief-tradeoff-tabs[role="tablist"]',
    );
    expect(tablist).not.toBeNull();
    expect(tablist).toHaveAttribute("aria-label", "Tradeoff view");
    const tabs = tablist!.querySelectorAll('[role="tab"]');
    expect(tabs.length).toBe(2);
    expect(tabs[0]!.textContent).toBe("Curve");
    expect(tabs[1]!.textContent).toBe("Histogram");
    expect(tabs[0]).toHaveAttribute("data-tradeoff-tab", "curve");
    expect(tabs[1]).toHaveAttribute("data-tradeoff-tab", "histogram");
  });

  it("belief column shows only the curve chart by default", () => {
    const { container } = render(createElement(StudioLayout));
    const curve = container.querySelector("#tradeoff-curve-host");
    const hist = container.querySelector("#tradeoff-histogram-host");
    expect(curve?.hasAttribute("hidden")).toBe(false);
    expect(hist?.hasAttribute("hidden")).toBe(true);
  });

  it("tuning dock omits Observation tab", () => {
    const { container } = render(createElement(StudioLayout));
    const observationTab = container.querySelector(
      '.tuning-dock-tabs [data-section="observation"]',
    );
    expect(observationTab).toBeNull();
  });

  it("tuning dock uses side-by-side controls and teaching plots", () => {
    const { container } = render(createElement(StudioLayout));
    const columns = container.querySelector(".tuning-dock-columns");
    expect(columns).not.toBeNull();
    expect(columns!.querySelector("#section-controls.tuning-dock-controls")).not.toBeNull();
    expect(columns!.querySelector(".focus-plots.tuning-plots")).not.toBeNull();
    expect(container.querySelector("#chart-demand-host")).not.toBeNull();
    expect(
      container.querySelector('.focus-plot[data-plot="plot-demand"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('.focus-plot[data-plot="plot-picking-variability"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('.focus-plot[data-plot="plot-logistics-calendar"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('.focus-plot[data-plot="plot-inventory"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('.focus-plot[data-plot="plot-controller-orders"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('.focus-plot[data-plot="plot-spoil"]'),
    ).not.toBeNull();
  });

  it("all D3ChartHost ids appear exactly once", () => {
    const { container } = render(createElement(StudioLayout));
    for (const id of REQUIRED_CHART_IDS) {
      const nodes = container.querySelectorAll(`#${id}`);
      expect(nodes.length, `expected exactly one #${id}`).toBe(1);
    }
  });

  it("renders OperatorBar controls exactly once", () => {
    const { container } = render(createElement(StudioLayout));
    const operatorBarHost = container.querySelector("#operator-bar-host");
    expect(operatorBarHost).not.toBeNull();

    const operatorBarRoot = createRoot(operatorBarHost!);
    flushSync(() => {
      operatorBarRoot.render(
        createElement(OperatorBar, {
          vm: {
            episode_day: 1,
            window_days: 90,
            config: DEFAULT_SIM_CONFIG,
          },
          orderQty: 24,
          onAdvance: () => undefined,
          onReset: () => undefined,
          onAutopilotPlay: () => undefined,
          onAutopilotPause: () => undefined,
          onOrderChange: () => undefined,
        }),
      );
    });

    for (const id of ["order-range", "order-num", "btn-advance", "btn-reset"]) {
      const nodes = container.querySelectorAll(`#${id}`);
      expect(nodes.length, `expected exactly one #${id}`).toBe(1);
    }
    operatorBarRoot.unmount();
  });

  it("mounts reference drawer host in portal root", () => {
    const { container } = render(createElement(StudioLayout));
    expect(
      container.querySelector(
        ".bv-studio-portal-root #reference-drawer-host[data-testid='reference-drawer-host']",
      ),
    ).not.toBeNull();
  });

  it("mounts studio loading dialog host in portal root (T-149)", () => {
    const { container } = render(createElement(StudioLayout));
    expect(
      container.querySelector(
        ".bv-studio-portal-root #studio-loading-host[data-testid='studio-loading-host']",
      ),
    ).not.toBeNull();
  });
});

describe("StudioLayout metrics narration (T-154)", () => {
  const cockpitCss = readFileSync(COCKPIT_CSS, "utf8");

  it("metrics pane has Outcomes panel head and note", () => {
    const { container } = render(createElement(StudioLayout));
    const metrics = container.querySelector(".cockpit-pane--metrics");
    const head = metrics!.querySelector(".panel-head");
    expect(head).not.toBeNull();
    expect(head!.querySelector("h2")?.textContent).toBe("Outcomes");
    expect(head!.querySelector(".panel-note")?.textContent).toBe(
      "Money, stock, and daily flow for this run.",
    );
    const totals = metrics!.querySelector("#pnl-totals-host");
    expect(
      head!.compareDocumentPosition(totals!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("metrics groups show Economics, Inventory, and Flow labels", () => {
    const { container } = render(createElement(StudioLayout));
    const metrics = container.querySelector(".cockpit-pane--metrics");
    expect(
      metrics!.querySelector(
        ".metrics-group--economics .metrics-group-label",
      )?.textContent,
    ).toBe("Economics");
    expect(
      metrics!.querySelector(
        ".metrics-group--inventory .metrics-group-label",
      )?.textContent,
    ).toBe("Inventory");
    expect(
      metrics!.querySelector(".metrics-group--flow .metrics-group-label")
        ?.textContent,
    ).toBe("Flow");
  });

  it("belief panel note links hover to charts", () => {
    const { container } = render(createElement(StudioLayout));
    const note = container.querySelector("#hover-note");
    expect(note?.textContent).toBe(
      "Filter belief over time — hover a day to link charts.",
    );
  });

  it("cockpitGrid.css boldens metrics chart captions only", () => {
    expect(cockpitCss).toMatch(
      /\.cockpit-pane--metrics\s+\.chart-caption\s*\{[^}]*font-weight:\s*700/,
    );
    expect(cockpitCss).toMatch(
      /\.cockpit-pane--metrics\s+\.chart-caption\s*\{[^}]*font-size:\s*0\.8rem/,
    );
    expect(cockpitCss).toMatch(
      /\.cockpit-pane--metrics\s+\.chart-caption\s*\{[^}]*color:\s*var\(--ink-soft\)/,
    );
    expect(cockpitCss).not.toMatch(
      /\.cockpit-pane--belief\s+\.chart-caption\s*\{[^}]*font-weight:\s*700/,
    );
  });

  it("cockpitGrid.css de-emphasizes impact stat weight and Fraunces", () => {
    expect(cockpitCss).toMatch(
      /\.impact-stat-label\s*\{[^}]*font-weight:\s*(400|500)/,
    );
    expect(cockpitCss).toMatch(
      /\.impact-stat-value\s*\{[^}]*font-weight:\s*(400|500)/,
    );
    expect(cockpitCss).not.toMatch(
      /\.impact-stat-value\s*\{[^}]*font-family:\s*var\(--font-display\)/,
    );
    expect(cockpitCss).toMatch(
      /\.impact-stat-value\s*\{[^}]*color:\s*var\(--ink-soft\)/,
    );
  });
});
