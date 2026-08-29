/**
 * T-163 — lazy arrival_summary load (init omits wire; section-open fetch).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const WEB_SRC = fileURLToPath(new URL(".", import.meta.url));

function read(rel: string): string {
  return readFileSync(join(WEB_SRC, rel), "utf8");
}

describe("T-163 arrival lottery charts", () => {
  it("wasmAdapter still exposes fetchArrivalSummary RPC for diagnostics", () => {
    const src = read("engine/wasmAdapter.ts");
    expect(src).toMatch(/fetchArrivalSummary/);
    expect(src).toMatch(/arrival_summary/);
  });

  it("studioLogic renders production-keyed arrival lottery charts", () => {
    const src = read("react/studioLogic.ts");
    expect(src).toMatch(/renderArrivalLotteryCharts/);
    expect(src).toMatch(/renderDurationLottery/);
    expect(src).toMatch(/renderBreakLottery/);
    expect(src).toMatch(/chart-arrival-duration-lottery/);
  });

  it("controls pair lottery charts with production knobs only", () => {
    const src = read("controls.ts");
    expect(src).toMatch(/plot-arrival-duration-lottery/);
    expect(src).toMatch(/break_rho/);
    expect(src).toMatch(/transit_temp_bias_c/);
    expect(src).not.toMatch(/preview_transit_days/);
  });
});
