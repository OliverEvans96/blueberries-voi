/**
 * Studio render cost profiler — mock adapter, advance steps, per-function breakdown.
 *
 * Run from web/: `npm run profile:render`
 */
// @vitest-environment jsdom
import { fireEvent, render } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearRenderProfile,
  getRenderProfileReport,
  initStudio,
  setRenderProfiling,
  type RenderProfileRow,
} from "../src/react/studioLogic";
import { sumRenderProfilePrefixes } from "../src/react/renderProfile";
import { StudioLayout } from "../src/react/StudioLayout";

const ADVANCE_STEPS = 5;
const BOOTSTRAP_TIMEOUT_MS = 10_000;

async function waitForEngineReady(app: HTMLElement): Promise<void> {
  const start = performance.now();
  while (performance.now() - start < BOOTSTRAP_TIMEOUT_MS) {
    const status = app.querySelector("#engine-status")?.getAttribute("data-status");
    const advanceBtn = app.querySelector("#btn-advance");
    if (status === "ready" && advanceBtn) return;
    if (status === "error") {
      throw new Error("studio bootstrap failed (engine-status=error)");
    }
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  throw new Error("timed out waiting for engine ready + operator bar");
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

  const tradeoff = sumRenderProfilePrefixes(report, [
    "renderTradeoff",
    "fetchTradeoffForecast",
  ]);
  const belief = sumRenderProfilePrefixes(report, [
    "renderStore.belief",
    "renderStore.renderMarginal",
    "renderCockpitBelief",
    "renderStore.beliefFreshnessTime",
    "renderStore.salesDemand",
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
  const fetchTotal = sumRenderProfilePrefixes(report, ["fetchTradeoffForecast", "fetchEvents"]);
  const paintTotal = { totalMs: grandTotal - fetchTotal.totalMs, pct: 0 };
  paintTotal.pct =
    grandTotal > 0 ? (paintTotal.totalMs / grandTotal) * 100 : 0;

  console.log("\n=== Category rollup ===");
  console.log(
    `Tradeoff (fetch + paint): ${tradeoff.totalMs.toFixed(1)} ms (${tradeoff.pct.toFixed(1)}%)`,
  );
  console.log(`Belief charts:          ${belief.totalMs.toFixed(1)} ms (${belief.pct.toFixed(1)}%)`);
  console.log(`Events (fetch + pane):  ${events.totalMs.toFixed(1)} ms (${events.pct.toFixed(1)}%)`);
  console.log(`Metrics pane:           ${metrics.totalMs.toFixed(1)} ms (${metrics.pct.toFixed(1)}%)`);
  console.log(`React chrome panes:     ${reactChrome.totalMs.toFixed(1)} ms (${reactChrome.pct.toFixed(1)}%)`);
  console.log("\n=== Fetch vs sync paint (approx) ===");
  console.log(
    `Async fetch (tradeoff + events RPC): ${fetchTotal.totalMs.toFixed(1)} ms (${fetchTotal.pct.toFixed(1)}%)`,
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
    render(createElement(StudioLayout), { container: app });
    initStudio(app);

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

    const tradeoff = sumRenderProfilePrefixes(report, [
      "renderTradeoff",
      "fetchTradeoffForecast",
    ]);
    const belief = sumRenderProfilePrefixes(report, [
      "renderStore.belief",
      "renderStore.renderMarginal",
      "renderCockpitBelief",
      "renderStore.beliefFreshnessTime",
      "renderStore.salesDemand",
    ]);

    expect(tradeoff.totalMs).toBeGreaterThan(0);
    expect(belief.totalMs).toBeGreaterThan(0);
    },
    15_000,
  );
});
