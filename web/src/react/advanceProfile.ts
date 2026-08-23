/**
 * End-to-end Advance pipeline profiling (click → last paint).
 * Combines engine RPC, remote fetches, and sync D3/React render buckets.
 */

import {
  getRenderProfileReport,
  sumRenderProfilePrefixes,
  type RenderProfileRow,
} from "./renderProfile";
import { getRpcProfileReport, type RpcProfileRow } from "../engine/rpcProfile";

export type AdvancePipelineSample = {
  totalMs: number;
  engineStepNMs: number;
  fetchTradeoffMs: number;
  fetchEventsMs: number;
  syncRenderMs: number;
  remotePaintMs: number;
  otherMs: number;
};

export type AdvancePipelineRow = {
  name: string;
  count: number;
  totalMs: number;
  meanMs: number;
  pct: number;
};

export type AdvancePipelineReport = {
  advances: number;
  samples: AdvancePipelineSample[];
  rows: AdvancePipelineRow[];
  renderRows: RenderProfileRow[];
  rpcRows: RpcProfileRow[];
  categories: {
    engine: { totalMs: number; pct: number };
    fetch: { totalMs: number; pct: number };
    paint: { totalMs: number; pct: number };
    other: { totalMs: number; pct: number };
  };
};

let enabled = false;
const samples: AdvancePipelineSample[] = [];

export function setAdvanceProfiling(on: boolean): void {
  enabled = on;
  if (!on) samples.length = 0;
}

export function clearAdvanceProfile(): void {
  samples.length = 0;
}

export function isAdvanceProfiling(): boolean {
  return enabled;
}

export function recordAdvanceSample(sample: AdvancePipelineSample): void {
  if (!enabled) return;
  samples.push(sample);
}

/** Build a sample from explicit engine timer + render profile snapshot. */
export function buildAdvanceSample(
  totalMs: number,
  engineStepNMs: number,
  renderReport: RenderProfileRow[],
): AdvancePipelineSample {
  const fetchTradeoff = sumRenderProfilePrefixes(renderReport, ["fetchTradeoffForecast"]);
  const fetchEvents = sumRenderProfilePrefixes(renderReport, ["fetchEvents"]);
  const remotePaint = sumRenderProfilePrefixes(renderReport, ["refreshRemotePanes.paint"]);
  // Top-level renderAll only — inner renderStore/render* rows nest inside it.
  const syncRender = sumRenderProfilePrefixes(renderReport, ["renderAll"]);
  const fetchTradeoffMs = fetchTradeoff.totalMs;
  const fetchEventsMs = fetchEvents.totalMs;
  const remotePaintMs = remotePaint.totalMs;
  const syncRenderMs = syncRender.totalMs;
  const accounted =
    engineStepNMs + fetchTradeoffMs + fetchEventsMs + syncRenderMs + remotePaintMs;
  const otherMs = Math.max(0, totalMs - accounted);
  return {
    totalMs,
    engineStepNMs,
    fetchTradeoffMs,
    fetchEventsMs,
    syncRenderMs,
    remotePaintMs,
    otherMs,
  };
}

function aggregateSamples(advanceSamples: AdvancePipelineSample[]): AdvancePipelineRow[] {
  const n = advanceSamples.length;
  if (n === 0) return [];

  const sum = (pick: (s: AdvancePipelineSample) => number) =>
    advanceSamples.reduce((acc, s) => acc + pick(s), 0);

  const engine = sum((s) => s.engineStepNMs);
  const fetchTradeoff = sum((s) => s.fetchTradeoffMs);
  const fetchEvents = sum((s) => s.fetchEventsMs);
  const syncRender = sum((s) => s.syncRenderMs);
  const remotePaint = sum((s) => s.remotePaintMs);
  const other = sum((s) => s.otherMs);
  const total = sum((s) => s.totalMs);

  const rows: AdvancePipelineRow[] = [
    {
      name: "engine.step_n (WASM RPC)",
      count: n,
      totalMs: engine,
      meanMs: engine / n,
      pct: 0,
    },
    {
      name: "fetchTradeoffForecast",
      count: n,
      totalMs: fetchTradeoff,
      meanMs: fetchTradeoff / n,
      pct: 0,
    },
    {
      name: "fetchEvents",
      count: n,
      totalMs: fetchEvents,
      meanMs: fetchEvents / n,
      pct: 0,
    },
    {
      name: "sync render (D3 + React)",
      count: n,
      totalMs: syncRender,
      meanMs: syncRender / n,
      pct: 0,
    },
    {
      name: "remote pane paint",
      count: n,
      totalMs: remotePaint,
      meanMs: remotePaint / n,
      pct: 0,
    },
    {
      name: "other (chrome / unbucketed)",
      count: n,
      totalMs: other,
      meanMs: other / n,
      pct: 0,
    },
    {
      name: "TOTAL wall (click → last paint)",
      count: n,
      totalMs: total,
      meanMs: total / n,
      pct: 100,
    },
  ];

  for (const row of rows) {
    if (row.name.startsWith("TOTAL")) continue;
    row.pct = total > 0 ? (row.totalMs / total) * 100 : 0;
  }
  return rows.sort((a, b) => {
    if (a.name.startsWith("TOTAL")) return 1;
    if (b.name.startsWith("TOTAL")) return -1;
    return b.totalMs - a.totalMs;
  });
}

export function getAdvancePipelineReport(): AdvancePipelineReport {
  const rows = aggregateSamples(samples);
  const totalMs = samples.reduce((sum, s) => sum + s.totalMs, 0);
  const engineMs = samples.reduce((sum, s) => sum + s.engineStepNMs, 0);
  const fetchMs = samples.reduce(
    (sum, s) => sum + s.fetchTradeoffMs + s.fetchEventsMs,
    0,
  );
  const paintMs = samples.reduce(
    (sum, s) => sum + s.syncRenderMs + s.remotePaintMs,
    0,
  );
  const otherMs = samples.reduce((sum, s) => sum + s.otherMs, 0);

  return {
    advances: samples.length,
    samples: [...samples],
    rows,
    renderRows: getRenderProfileReport(),
    rpcRows: getRpcProfileReport(),
    categories: {
      engine: {
        totalMs: engineMs,
        pct: totalMs > 0 ? (engineMs / totalMs) * 100 : 0,
      },
      fetch: {
        totalMs: fetchMs,
        pct: totalMs > 0 ? (fetchMs / totalMs) * 100 : 0,
      },
      paint: {
        totalMs: paintMs,
        pct: totalMs > 0 ? (paintMs / totalMs) * 100 : 0,
      },
      other: {
        totalMs: otherMs,
        pct: totalMs > 0 ? (otherMs / totalMs) * 100 : 0,
      },
    },
  };
}
