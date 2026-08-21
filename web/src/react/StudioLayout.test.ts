/**
 * T-127 / T-128: Cockpit Grid shell — layout v4 → v5.
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
  "chart-spoil",
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
] as const;

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("StudioLayout cockpit grid (T-127 AC-layout, T-128 v5)", () => {
  const layoutSrc = stripComments(readFileSync(LAYOUT_TS, "utf8"));
  const cockpitCss = readFileSync(COCKPIT_CSS, "utf8");

  it("uses cockpit-grid shell — not T-126 two-pane / focus-column", () => {
    expect(layoutSrc).toMatch(/cockpit-grid/);
    expect(layoutSrc).not.toMatch(/studio-layout--two-pane/);
    expect(layoutSrc).not.toMatch(/focus-column/);
  });

  it("defines layout v5 3-column grid areas in cockpitGrid.css", () => {
    expect(cockpitCss).toMatch(/grid-template-areas/);
    expect(cockpitCss).toMatch(/economics\s+today\s+events/);
    expect(cockpitCss).toMatch(/minmax\(280px,\s*380px\)/);
  });

  it("renders charts and tuning row regions in DOM order", () => {
    const { container } = render(createElement(StudioLayout));
    const rows = container.querySelectorAll(
      ".cockpit-grid > .cockpit-row, .cockpit-grid > [data-cockpit-row]",
    );
    expect(rows.length).toBeGreaterThanOrEqual(2);
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

  it("row 2 hosts Economics, Today center pane, and Events column (v5)", () => {
    const { container } = render(createElement(StudioLayout));
    const grid = container.querySelector(".cockpit-grid");
    expect(grid).not.toBeNull();
    expect(
      grid!.querySelector("#economics-pane-host, [data-pane='economics']"),
    ).not.toBeNull();
    expect(
      grid!.querySelector(
        ".cockpit-pane--today, [data-testid='cockpit-today']",
      ),
    ).not.toBeNull();
    expect(
      grid!.querySelector("#events-pane-host, [data-pane='events']"),
    ).not.toBeNull();
    expect(grid!.querySelector("#decision-rail-host")).toBeNull();
    expect(grid!.querySelector(".cockpit-pane--run")).toBeNull();
    expect(grid!.querySelector("[data-testid='cockpit-sidebar-run']")).toBeNull();
  });

  it("retires Run sidebar — no decision-rail-host in layout source", () => {
    expect(layoutSrc).not.toMatch(/decision-rail-host/);
    expect(layoutSrc).not.toMatch(/cockpit-pane--run/);
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

  it("all D3ChartHost ids appear exactly once", () => {
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

  it("renders OperatorBar controls exactly once (no hidden PlayChrome duplicate)", () => {
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

    expect(container.querySelector("#play-chrome")).toBeNull();
    operatorBarRoot.unmount();
  });

  it("mounts #secondary-chrome-host above #operator-bar-host in Secondary (v5)", () => {
    const { container } = render(createElement(StudioLayout));
    const secondary = container.querySelector(".cockpit-pane--secondary");
    expect(secondary).not.toBeNull();
    const chromeHost = secondary!.querySelector("#secondary-chrome-host");
    const operatorBarHost = secondary!.querySelector("#operator-bar-host");
    expect(chromeHost).not.toBeNull();
    expect(operatorBarHost).not.toBeNull();
    expect(operatorBarHost).toBe(secondary!.lastElementChild);
    expect(chromeHost!.compareDocumentPosition(operatorBarHost!) &
      Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
  });
});
