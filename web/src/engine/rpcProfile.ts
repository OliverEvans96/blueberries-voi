/** Dev-only WASM worker RPC round-trip timings (postMessage → response). */

export type RpcProfileRow = {
  method: string;
  count: number;
  totalMs: number;
  meanMs: number;
  pct: number;
};

let enabled = false;
const samples = new Map<string, number[]>();

export function setRpcProfiling(on: boolean): void {
  enabled = on;
  if (!on) samples.clear();
}

export function clearRpcProfile(): void {
  samples.clear();
}

export function isRpcProfiling(): boolean {
  return enabled;
}

export function recordRpc(method: string, ms: number): void {
  if (!enabled) return;
  const arr = samples.get(method) ?? [];
  arr.push(ms);
  samples.set(method, arr);
}

export function getRpcProfileReport(): RpcProfileRow[] {
  const rows = Array.from(samples.entries()).map(([method, arr]) => {
    const totalMs = arr.reduce((sum, ms) => sum + ms, 0);
    return {
      method,
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
