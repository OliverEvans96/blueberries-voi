/**
 * T-158: Cockpit Grid shell — layout v7 (tuning drawer).
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
  "chart-age-comp",
  "chart-arrival-prior",
  "chart-arrhenius-temp",
  "chart-gamma-path",
  "chart-belief-age-marginal",
  "chart-belief-lg",
  "chart-controller-orders",
  "chart-spoil",
  "chart-controller-orders-focus",
  "chart-spoil-focus",
] as const;

/** Tuning-drawer chart ids validated in TuningDrawer.test.ts */
export type TuningChartIds = typeof REQUIRED_CHART_IDS;

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("StudioLayout cockpit grid (T-158 v7)", () => {
  const layoutSrc = stripComments(readFileSync(LAYOUT_TS, "utf8"));
  const cockpitCss = readFileSync(COCKPIT_CSS, "utf8");

  it("uses minimal title-bar header without hero chrome", () => {
    expect(layoutSrc).toMatch(/title-bar/);
    expect(layoutSrc).not.toMatch(/className="hero"/);
    expect(layoutSrc).not.toMatch(/insight-strip-host/);
    expect(layoutSrc).not.toMatch(/chapter-tabs-host/);
    expect(layoutSrc).not.toMatch(/guided-paths-host/);
  });

  it("defines layout v7 single-row grid areas in cockpitGrid.css", () => {
    expect(cockpitCss).toMatch(/grid-template-areas/);
    expect(cockpitCss).toMatch(/metrics\s+belief\s+sidebar/);
    expect(cockpitCss).not.toMatch(/tuning\s+tuning\s+tuning/);
  });

  it("renders v7 data-layout and three column panes without tuning row", () => {
    const { container } = render(createElement(StudioLayout));
    const grid = container.querySelector(".cockpit-grid[data-layout='v7']");
    expect(grid).not.toBeNull();
    expect(grid!.querySelector(".cockpit-pane--metrics")).not.toBeNull();
    expect(grid!.querySelector(".cockpit-column--center")).not.toBeNull();
    expect(grid!.querySelector(".cockpit-pane--run")).not.toBeNull();
    expect(grid!.querySelector(".cockpit-pane--belief")).not.toBeNull();
    expect(grid!.querySelector(".cockpit-pane--sidebar")).not.toBeNull();
    expect(grid!.querySelector("#obs-controls-pane-host")).not.toBeNull();
    expect(grid!.querySelector("#pnl-totals-host")).not.toBeNull();
    expect(grid!.querySelector("#impact-missed-host")).toBeNull();
    expect(grid!.querySelector("#impact-waste-host")).toBeNull();
    expect(grid!.querySelector("#secondary-chrome-host")).toBeNull();
    expect(grid!.querySelector("#economics-pane-host")).toBeNull();
    expect(container.querySelector(".cockpit-row--tuning")).toBeNull();
    expect(container.querySelector(".tuning-dock")).toBeNull();
  });

  it("renders mobile cockpit tabs defaulting to Run", () => {
    const { container } = render(createElement(StudioLayout));
    const tabs = container.querySelector(
      "[data-testid='cockpit-mobile-tabs']",
    );
    expect(tabs).not.toBeNull();
    expect(tabs!.querySelectorAll(".cockpit-mobile-tab")).toHaveLength(3);
    const grid = container.querySelector(".cockpit-grid[data-layout='v7']");
    expect(grid).toHaveAttribute("data-mobile-tab", "run");
    expect(
      tabs!.querySelector("#cockpit-mobile-tab-run")?.getAttribute("aria-selected"),
    ).toBe("true");
  });

  it("renders pre-WASM shell placeholders in imperative mount hosts", () => {
    const { container } = render(createElement(StudioLayout));
    expect(
      container.querySelector("#pnl-totals-host [data-testid='pnl-totals-placeholder']"),
    ).not.toBeNull();
    expect(
      container.querySelector("#operator-bar-host .operator-bar[aria-busy='true']"),
    ).not.toBeNull();
    expect(
      container.querySelector(
        "#obs-controls-pane-host [data-testid='obs-controls-pane']",
      ),
    ).not.toBeNull();
    expect(
      container.querySelector("#events-pane-host [data-loading='true']"),
    ).not.toBeNull();
    expect(
      container.querySelector(
        "#events-pane-host [data-testid='events-loading-placeholder']",
      ),
    ).not.toBeNull();
    expect(
      container.querySelector(
        "#obs-controls-pane-host [data-booting='true']",
      ),
    ).not.toBeNull();
    const shells = container.querySelectorAll("[data-testid='chart-loading-shell']");
    expect(shells.length).toBeGreaterThanOrEqual(7);
  });

  it("title bar has gear trigger left of engine status", () => {
    const { container } = render(createElement(StudioLayout));
    const actions = container.querySelector(".title-bar-actions");
    expect(actions).not.toBeNull();
    const docs = actions!.querySelector("a.title-bar-action--docs");
    const github = actions!.querySelector("a.title-bar-action--github");
    const trigger = actions!.querySelector("#tuning-drawer-trigger");
    const status = actions!.querySelector("#engine-status");
    expect(docs).not.toBeNull();
    expect(github).not.toBeNull();
    expect(trigger).not.toBeNull();
    expect(status).not.toBeNull();
    expect(
      github!.compareDocumentPosition(trigger!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      trigger!.compareDocumentPosition(status!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("title bar shows blog link beside the heading", () => {
    const { container } = render(createElement(StudioLayout));
    const heading = container.querySelector(".title-bar-heading");
    expect(heading).not.toBeNull();
    expect(heading!.querySelector("h1")?.textContent).toBe(
      "Blueberry inventory studio",
    );
    const blog = heading!.querySelector("a.title-bar-blog-link");
    expect(blog).not.toBeNull();
    expect(blog?.textContent).toBe("Read the blog post");
  });

  it("metrics column stacks P&L, revenue chart, sales demand, orders, and spoilage", () => {
    const { container } = render(createElement(StudioLayout));
    const metrics = container.querySelector(".cockpit-pane--metrics");
    expect(metrics).not.toBeNull();
    expect(metrics!.querySelector("#chart-pnl-economics")).not.toBeNull();
    expect(metrics!.querySelector("#chart-sales-demand")).not.toBeNull();
    expect(metrics!.querySelector("#chart-controller-orders")).not.toBeNull();
    expect(metrics!.querySelector("#chart-spoil")).not.toBeNull();
    expect(metrics!.querySelector("#chart-age-comp")).toBeNull();
    expect(metrics!.querySelector("#chart-inventory")).toBeNull();
    expect(metrics!.querySelector(".impact-row")).toBeNull();
    const totals = metrics!.querySelector("#pnl-totals-host");
    const pnlChart = metrics!.querySelector("#chart-pnl-economics");
    expect(
      totals!.compareDocumentPosition(pnlChart!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      pnlChart!.compareDocumentPosition(
        metrics!.querySelector("#chart-sales-demand")!,
      ) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      metrics!
        .querySelector("#chart-sales-demand")!
        .compareDocumentPosition(metrics!.querySelector("#chart-controller-orders")!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      metrics!
        .querySelector("#chart-controller-orders")!
        .compareDocumentPosition(metrics!.querySelector("#chart-spoil")!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("belief pane orders today's histogram, summary, then history", () => {
    const { container } = render(createElement(StudioLayout));
    const belief = container.querySelector(".cockpit-pane--belief")!;
    const beliefLg = belief.querySelector("#chart-belief-lg")!;
    const ageComp = belief.querySelector("#chart-age-comp")!;
    const history = belief.querySelector("#chart-history")!;
    expect(belief.querySelector("#chart-sla-stockout")).toBeNull();
    expect(
      beliefLg.compareDocumentPosition(ageComp) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      ageComp.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("run pane hosts operator bar; belief pane hosts freshness charts only", () => {
    const { container } = render(createElement(StudioLayout));
    const run = container.querySelector(".cockpit-pane--run");
    const belief = container.querySelector(".cockpit-pane--belief");
    expect(run!.querySelector("#operator-bar-host")).not.toBeNull();
    expect(belief!.querySelector("#operator-bar-host")).toBeNull();
    expect(belief!.querySelector("#chart-history")).not.toBeNull();
    expect(belief!.querySelector("#chart-belief-lg")).not.toBeNull();
    expect(belief!.querySelector("#chart-age-comp")).not.toBeNull();
    expect(belief!.querySelector("#tradeoff-curve-host")).toBeNull();
    expect(belief!.querySelector("#tradeoff-histogram-host")).toBeNull();
    const runOperator = run!.querySelector("#operator-bar-host");
    const beliefHead = belief!.querySelector(".panel-head");
    const beliefLg = belief!.querySelector("#chart-belief-lg");
    expect(
      runOperator!.compareDocumentPosition(beliefHead!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      beliefHead!.compareDocumentPosition(beliefLg!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("belief pane chart captions use renamed freshness titles", () => {
    const { container } = render(createElement(StudioLayout));
    const belief = container.querySelector(".cockpit-pane--belief")!;
    expect(
      belief.querySelector('[data-truth-caption="lots"] [data-truth-caption-label]')
        ?.textContent,
    ).toBe("Historical Freshness Distribution");
    expect(belief.querySelector('[data-truth-caption="age-comp"] [data-truth-caption-label]')
      ?.textContent,
    ).toBe("Historical Freshness Summary");
    expect(
      belief.querySelector('[data-truth-caption="belief-lg"] [data-truth-caption-label]')
        ?.textContent,
    ).toBe("Today's Freshness Distribution");
    expect(
      belief.querySelector("#chart-belief-lg")?.getAttribute("aria-label"),
    ).toBe("Today's Freshness Distribution");
  });

  it("belief column does not mount runtime tradeoff chrome", () => {
    const { container } = render(createElement(StudioLayout));
    expect(container.querySelector(".belief-tradeoff-panel")).toBeNull();
    expect(container.querySelector("#tradeoff-curve-host")).toBeNull();
    expect(container.querySelector("#tradeoff-histogram-host")).toBeNull();
  });

  it("mounts tuning drawer host in portal root", () => {
    const { container } = render(createElement(StudioLayout));
    expect(
      container.querySelector(
        ".bv-studio-portal-root #tuning-drawer-host[data-testid='tuning-drawer-host']",
      ),
    ).not.toBeNull();
  });

  it("cockpit grid hosts metrics and belief charts (tuning charts live in drawer)", () => {
    const { container } = render(createElement(StudioLayout));
    const cockpitIds = [
      "chart-sales",
      "chart-stockout",
      "chart-history",
      "chart-sales-demand",
      "chart-age-comp",
          "chart-belief-age-marginal",
      "chart-belief-lg",
      "chart-controller-orders",
      "chart-spoil",
    ] as const;
    for (const id of cockpitIds) {
      const nodes = container.querySelectorAll(`#${id}`);
      expect(nodes.length, `expected exactly one #${id}`).toBe(1);
    }
    expect(container.querySelector("#chart-demand-host")).toBeNull();
    expect(container.querySelector("#chart-demand")).toBeNull();
    expect(container.querySelector("#chart-inventory")).toBeNull();
    expect(container.querySelector("#chart-orders-spoilage")).toBeNull();
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

  it("mounts day inspector host in portal root", () => {
    const { container } = render(createElement(StudioLayout));
    expect(
      container.querySelector(
        ".bv-studio-portal-root #day-inspector-host[data-testid='day-inspector-host']",
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

  it("shows the welcome modal open on load, outside the aria-hidden portal root", () => {
    const { container } = render(createElement(StudioLayout));
    const dialog = container.querySelector("dialog.welcome-modal");
    expect(dialog).not.toBeNull();
    expect(dialog!.closest(".bv-studio-portal-root")).toBeNull();
    expect(dialog!.closest(".bv-studio")).not.toBeNull();
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

  it("metrics stack omits Economics, Inventory, and Flow section labels", () => {
    const { container } = render(createElement(StudioLayout));
    const metrics = container.querySelector(".cockpit-pane--metrics");
    expect(metrics!.querySelector(".metrics-group-label")).toBeNull();
    expect(metrics!.querySelector(".metrics-group--economics")).toBeNull();
    expect(metrics!.querySelector(".metrics-group--inventory")).toBeNull();
    expect(metrics!.querySelector(".metrics-group--flow")).toBeNull();
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
});
