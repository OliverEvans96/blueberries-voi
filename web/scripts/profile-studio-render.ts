/**
 * Studio render cost profiler — mock adapter, advance steps, per-function breakdown.
 *
 * Run from web/: `npm run profile:render`
 */
// @vitest-environment jsdom
import { act, fireEvent, render, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import {
  clearRenderProfile,
  getRenderProfileReport,
  setRenderProfiling,
  type RenderProfileRow,
} from "../src/react/studioLogic";
import { sumRenderProfilePrefixes } from "../src/react/renderProfile";

const ADVANCE_STEPS = 5;
const BOOTSTRAP_TIMEOUT_MS = 10_000;

async function waitForEngineReady(root: HTMLElement): Promise<void> {
  await waitFor(
    () => {
      const status = root.querySelector("#engine-status")?.getAttribute("data-status");
      if (status === "error") {
        throw new Error("studio bootstrap failed (engine-status=error)");
      }
      expect(status).toBe("ready");
      expect(root.querySelector("#btn-advance")).not.toBeNull();
    },
    { timeout: BOOTSTRAP_TIMEOUT_MS },
  );
}

function formatRow(row: RenderProfileRow): string {
  return `${row.name.padEnd(42)} ${row.meanMs.toFixed(2).padStart(7)} ms/call  ${row.totalMs
    .toFixed(1)
    .padStart(8)} ms total  ${row.pct.toFixed(1).padStart(5)}%  (n=${row.count})`;
}

function printReport(report: RenderProfileRow[]): void {
  const grandTotal = report.reduce((sum, row) => sum + row.totalMs, 0);
  console.log("\n=== Studio render profile (mock adapter) ===");
  console.log(`Grand total sampled time: ${grandTotal.toFixed(1)} ms`);
  console.log("Ranked breakdown:");
  for (const row of report) {
    console.log(formatRow(row));
  }

  const outcomes = sumRenderProfilePrefixes(report, [
    "renderMetricsPane",
    "renderRunStripCharts",
    "renderStore.salesDemand",
  ]);
  const belief = sumRenderProfilePrefixes(report, [
    "renderStore.belief",
    "renderStore.renderMarginal",
    "renderCockpitBelief",
    "renderStore.beliefFreshnessTime",
  ]);
  const events = sumRenderProfilePrefixes(report, ["fetchEvents", "renderEventsPane"]);
  const metrics = sumRenderProfilePrefixes(report, ["renderMetricsPane"]);
  const reactChrome = sumRenderProfilePrefixes(report, [
    "renderOperatorBar",
    "renderObsControlsPane",
    "renderDayInspector",
    "renderReferenceDrawer",
    "sectionControlsApi.update",
  ]);
  const fetchTotal = sumRenderProfilePrefixes(report, ["fetchEvents"]);
  const paintTotal = { totalMs: grandTotal - fetchTotal.totalMs, pct: 0 };
  paintTotal.pct =
    grandTotal > 0 ? (paintTotal.totalMs / grandTotal) * 100 : 0;

  console.log("\n=== Category rollup ===");
  console.log(
    `Outcomes strip (metrics + flow): ${outcomes.totalMs.toFixed(1)} ms (${outcomes.pct.toFixed(1)}%)`,
  );
  console.log(`Belief charts:          ${belief.totalMs.toFixed(1)} ms (${belief.pct.toFixed(1)}%)`);
  console.log(`Events (fetch + pane):  ${events.totalMs.toFixed(1)} ms (${events.pct.toFixed(1)}%)`);
  console.log(`Metrics pane:           ${metrics.totalMs.toFixed(1)} ms (${metrics.pct.toFixed(1)}%)`);
  console.log(`React chrome panes:     ${reactChrome.totalMs.toFixed(1)} ms (${reactChrome.pct.toFixed(1)}%)`);
  console.log("\n=== Fetch vs sync paint (approx) ===");
  console.log(
    `Async fetch (events RPC): ${fetchTotal.totalMs.toFixed(1)} ms (${fetchTotal.pct.toFixed(1)}%)`,
  );
  console.log(
    `Sync paint / React / D3:             ${paintTotal.totalMs.toFixed(1)} ms (${paintTotal.pct.toFixed(1)}%)`,
  );
}

describe("studio render profile harness", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_ENGINE_ADAPTER", "mock");
    setRenderProfiling(true);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    setRenderProfiling(false);
    document.body.innerHTML = "";
  });

  it(
    `profiles ${ADVANCE_STEPS} advance steps on mock adapter`,
    async () => {
    const app = document.createElement("div");
    app.id = "app";
    document.body.appendChild(app);
    await act(async () => {
      render(createElement(App), { container: app });
    });

    await waitForEngineReady(app);
    clearRenderProfile();

    const advanceBtn = app.querySelector("#btn-advance") as HTMLButtonElement;
    expect(advanceBtn).toBeTruthy();

    for (let i = 0; i < ADVANCE_STEPS; i++) {
      fireEvent.click(advanceBtn);
      await new Promise((resolve) => setTimeout(resolve, 0));
      await new Promise((resolve) => setTimeout(resolve, 50));
    }

    const report = getRenderProfileReport();
    expect(report.length).toBeGreaterThan(0);

    printReport(report);

    const outcomes = sumRenderProfilePrefixes(report, [
      "renderMetricsPane",
      "renderRunStripCharts",
      "renderStore.salesDemand",
    ]);
    const belief = sumRenderProfilePrefixes(report, [
      "renderStore.belief",
      "renderStore.renderMarginal",
      "renderCockpitBelief",
      "renderStore.beliefFreshnessTime",
    ]);

    expect(outcomes.totalMs).toBeGreaterThan(0);
    expect(belief.totalMs).toBeGreaterThan(0);
    },
    15_000,
  );
});
