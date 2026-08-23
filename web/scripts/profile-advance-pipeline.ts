/**
 * Studio Advance pipeline profiler — mock adapter in jsdom; WASM via browser console.
 *
 * Run from web/: `npm run profile:advance`
 *
 * WASM note: vitest/jsdom cannot load the bundled WASM worker. For real engine
 * timings, open the studio in a browser and run:
 *   await window.__studioProfileAdvance(5)
 */
// @vitest-environment jsdom
import { fireEvent, render } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getAdvancePipelineReport,
  initStudio,
  setAdvanceProfiling,
  setRenderProfiling,
  setRpcProfiling,
  studioProfileAdvanceSteps,
  type AdvancePipelineReport,
} from "../src/react/studioLogic";
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

function formatPipelineRow(row: { name: string; meanMs: number; totalMs: number; pct: number; count: number }): string {
  return `${row.name.padEnd(42)} ${row.meanMs.toFixed(2).padStart(7)} ms/step  ${row.totalMs
    .toFixed(1)
    .padStart(8)} ms total  ${row.pct.toFixed(1).padStart(5)}%  (n=${row.count})`;
}

function printPipelineReport(report: AdvancePipelineReport, adapterKind: string): void {
  const { categories } = report;
  console.log(`\n=== Studio Advance pipeline (${adapterKind} adapter) ===`);
  console.log(`Advances profiled: ${report.advances}`);
  console.log("\nRanked breakdown (wall-clock, click → last paint):");
  for (const row of report.rows) {
    console.log(formatPipelineRow(row));
  }

  console.log("\n=== Category rollup (engine vs fetch vs paint) ===");
  console.log(
    `Engine / WASM RPC:  ${categories.engine.totalMs.toFixed(1)} ms (${categories.engine.pct.toFixed(1)}%)`,
  );
  console.log(
    `Remote fetches:     ${categories.fetch.totalMs.toFixed(1)} ms (${categories.fetch.pct.toFixed(1)}%)`,
  );
  console.log(
    `Sync paint (D3):    ${categories.paint.totalMs.toFixed(1)} ms (${categories.paint.pct.toFixed(1)}%)`,
  );
  console.log(
    `Other / chrome:     ${categories.other.totalMs.toFixed(1)} ms (${categories.other.pct.toFixed(1)}%)`,
  );

  if (report.rpcRows.length > 0) {
    console.log("\n=== WASM RPC methods (worker round-trip) ===");
    for (const row of report.rpcRows) {
      console.log(
        `${row.method.padEnd(24)} ${row.meanMs.toFixed(2).padStart(7)} ms/call  ${row.totalMs
          .toFixed(1)
          .padStart(8)} ms total  ${row.pct.toFixed(1).padStart(5)}%  (n=${row.count})`,
      );
    }
  } else if (adapterKind === "mock") {
    console.log(
      "\n(WASM RPC breakdown unavailable — mock adapter; use browser __studioProfileAdvance for WASM)",
    );
  }

  const ranked = [
    { label: "engine", pct: categories.engine.pct },
    { label: "fetch", pct: categories.fetch.pct },
    { label: "paint", pct: categories.paint.pct },
    { label: "other", pct: categories.other.pct },
  ].sort((a, b) => b.pct - a.pct);
  console.log(`\nBottleneck: ${ranked[0]!.label} (${ranked[0]!.pct.toFixed(1)}% of wall time)`);
}

describe("studio advance pipeline profile harness", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_ENGINE_ADAPTER", "mock");
    setAdvanceProfiling(false);
    setRenderProfiling(false);
    setRpcProfiling(false);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    setAdvanceProfiling(false);
    setRenderProfiling(false);
    setRpcProfiling(false);
    document.body.innerHTML = "";
  });

  it(
    `profiles ${ADVANCE_STEPS} advance steps end-to-end on mock adapter`,
    async () => {
      const app = document.createElement("div");
      app.id = "app";
      document.body.appendChild(app);
      render(createElement(StudioLayout), { container: app });
      initStudio(app);

      await waitForEngineReady(app);

      const report = await studioProfileAdvanceSteps(ADVANCE_STEPS);
      expect(report.advances).toBe(ADVANCE_STEPS);
      expect(report.rows.length).toBeGreaterThan(0);

      const totalRow = report.rows.find((r) => r.name.startsWith("TOTAL"));
      expect(totalRow?.totalMs).toBeGreaterThan(0);

      printPipelineReport(report, "mock");

      expect(report.categories.paint.totalMs).toBeGreaterThan(0);
    },
    30_000,
  );
});
