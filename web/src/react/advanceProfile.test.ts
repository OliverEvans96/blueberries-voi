import { describe, expect, it } from "vitest";
import {
  buildAdvanceSample,
  clearAdvanceProfile,
  getAdvancePipelineReport,
  recordAdvanceSample,
  setAdvanceProfiling,
} from "./advanceProfile";

describe("advanceProfile", () => {
  it("aggregates engine, fetch, and paint buckets", () => {
    setAdvanceProfiling(true);
    clearAdvanceProfile();

    recordAdvanceSample(
      buildAdvanceSample(100, 10, [
        { name: "fetchTradeoffForecast", count: 1, totalMs: 20, meanMs: 20, pct: 0 },
        { name: "fetchEvents", count: 1, totalMs: 5, meanMs: 5, pct: 0 },
        { name: "renderAll", count: 1, totalMs: 50, meanMs: 50, pct: 0 },
        { name: "refreshRemotePanes.paint", count: 1, totalMs: 10, meanMs: 10, pct: 0 },
      ]),
    );

    const report = getAdvancePipelineReport();
    expect(report.advances).toBe(1);
    expect(report.categories.engine.totalMs).toBe(10);
    expect(report.categories.fetch.totalMs).toBe(25);
    expect(report.categories.paint.totalMs).toBe(60); // renderAll 50 + remote paint 10

    const total = report.rows.find((r) => r.name.startsWith("TOTAL"));
    expect(total?.totalMs).toBe(100);
    setAdvanceProfiling(false);
  });
});
