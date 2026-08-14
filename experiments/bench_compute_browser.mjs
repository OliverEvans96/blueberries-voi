#!/usr/bin/env node
/**
 * Browser-column harness (T-109): wasm init/step/step_n(7)/act.
 * Pyodide: n/a unless PYODIDE_BENCH=1 (full loadPyodide is optional).
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { performance } from "node:perf_hooks";

const root = join(dirname(new URL(import.meta.url).pathname), "..");
const pkgJs = join(root, "packaging/wasm/pkg/voi_wasm.js");

function stats(xs) {
  const s = [...xs].sort((a, b) => a - b);
  return {
    mean: xs.reduce((a, b) => a + b, 0) / xs.length,
    p50: s[Math.floor(s.length / 2)],
    p95: s[Math.floor(0.95 * (s.length - 1))],
    n: xs.length,
    crossings: 1,
  };
}

async function benchWasm() {
  if (!existsSync(pkgJs)) {
    return { n_a: "run ./scripts/build-wasm.sh (packaging/wasm/pkg missing)" };
  }
  const mod = await import(pathToFileURL(pkgJs).href);
  const wasmPath = join(root, "packaging/wasm/pkg/voi_wasm_bg.wasm");
  const t0 = performance.now();
  // Node has no file:// fetch; pass bytes so wasm-pack init skips `fetch`.
  await mod.default({ module_or_path: readFileSync(wasmPath) });
  const cold_ms = performance.now() - t0;
  const rpc = (obj) => JSON.parse(mod.handle_rpc(JSON.stringify(obj)));
  rpc({ id: "0", method: "init", params: { seed: 1 } });
  const step = [];
  for (let i = 0; i < 5; i++) {
    const a = performance.now();
    rpc({ id: String(i), method: "step", params: { order: 8 } });
    step.push((performance.now() - a) / 1000);
  }
  const stepn = [];
  for (let i = 0; i < 5; i++) {
    const a = performance.now();
    rpc({
      id: "n" + i,
      method: "step_n",
      params: { orders: [8, 0, 8, 0, 8, 0, 8] },
    });
    stepn.push((performance.now() - a) / 1000);
  }
  const act = [];
  for (let i = 0; i < 3; i++) {
    const a = performance.now();
    rpc({ id: "a" + i, method: "act", params: { policy: "rollout" } });
    act.push((performance.now() - a) / 1000);
  }
  return {
    cold_start_s: cold_ms / 1000,
    step: stats(step),
    step_n_7: stats(stepn),
    act_rollout: stats(act),
  };
}

const out = {
  wasm: await benchWasm(),
  pyodide: process.env.PYODIDE_BENCH
    ? { n_a: "set PYODIDE_BENCH but harness does not embed loadPyodide yet" }
    : { n_a: "no Node Pyodide; studio worker remains the prod path" },
};
const dest = join(root, "outputs/bench_compute_browser.json");
try {
  writeFileSync(dest, JSON.stringify(out, null, 2));
} catch {
  /* outputs/ may be gitignored / missing */
}
console.log(JSON.stringify(out, null, 2));
