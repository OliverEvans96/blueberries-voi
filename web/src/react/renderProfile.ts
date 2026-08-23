/** Dev-only sync/async render timing (studioLogic renderAll breakdown). */
export type RenderProfileRow = {
  name: string;
  count: number;
  totalMs: number;
  meanMs: number;
  pct: number;
};

let enabled = false;
const samples = new Map<string, number[]>();

export function setRenderProfiling(on: boolean): void {
  enabled = on;
  if (!on) samples.clear();
}

export function clearRenderProfile(): void {
  samples.clear();
}

export function isRenderProfiling(): boolean {
  return enabled;
}

function record(name: string, ms: number): void {
  const arr = samples.get(name) ?? [];
  arr.push(ms);
  samples.set(name, arr);
}

export function profileSync<T>(name: string, fn: () => T): T {
  if (!enabled) return fn();
  const t0 = performance.now();
  try {
    return fn();
  } finally {
    record(name, performance.now() - t0);
  }
}

export async function profileAsync<T>(name: string, fn: () => Promise<T>): Promise<T> {
  if (!enabled) return fn();
  const t0 = performance.now();
  try {
    return await fn();
  } finally {
    record(name, performance.now() - t0);
  }
}

export function getRenderProfileReport(): RenderProfileRow[] {
  const rows = Array.from(samples.entries()).map(([name, arr]) => {
    const totalMs = arr.reduce((sum, ms) => sum + ms, 0);
    return {
      name,
      count: arr.length,
      totalMs,
      meanMs: totalMs / arr.length,
      pct: 0,
    };
  });
  const grandTotal = rows.reduce((sum, row) => sum + row.totalMs, 0);
  for (const row of rows) {
    row.pct = grandTotal > 0 ? (row.totalMs / grandTotal) * 100 : 0;
  }
  return rows.sort((a, b) => b.totalMs - a.totalMs);
}

/** Sum rows whose names match any prefix (for grouped report lines). */
export function sumRenderProfilePrefixes(
  report: RenderProfileRow[],
  prefixes: string[],
): { totalMs: number; pct: number } {
  const grandTotal = report.reduce((sum, row) => sum + row.totalMs, 0);
  const totalMs = report
    .filter((row) => prefixes.some((p) => row.name.startsWith(p)))
    .reduce((sum, row) => sum + row.totalMs, 0);
  return {
    totalMs,
    pct: grandTotal > 0 ? (totalMs / grandTotal) * 100 : 0,
  };
}
