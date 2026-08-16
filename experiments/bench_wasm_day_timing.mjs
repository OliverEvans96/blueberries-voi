#!/usr/bin/env node
/**
 * WASM day-advance timing under DEMO_BUDGETS (Node loads wasm-pack pkg).
 * Run after ./scripts/build-wasm.sh
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { performance } from "node:perf_hooks";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkgJs = join(root, "packaging/wasm/pkg/voi_wasm.js");
const wasmPath = join(root, "packaging/wasm/pkg/voi_wasm_bg.wasm");

const N_PARTICLES = 200;
const H = 7;
const N_PATHS = 2;
const RADIUS = 1;
const SEED = 42;
const ORDER = 16;
const WARM_DAYS = 7;
const REPS = 100;
const WARMUP = 20;

function stats(xs) {
  const s = [...xs].sort((a, b) => a - b);
  const n = s.length;
  const mean = xs.reduce((a, b) => a + b, 0) / n;
  return {
    mean_ms: mean * 1000,
    p50_ms: s[Math.floor(n / 2)] * 1000,
    p95_ms: s[Math.floor(0.95 * (n - 1))] * 1000,
    min_ms: s[0] * 1000,
    max_ms: s[n - 1] * 1000,
    n,
  };
}

function initPayload() {
  return {
    id: "init",
    method: "init",
    params: {
      seed: SEED,
      config: {
        n_particles: N_PARTICLES,
        H,
        n_rollout_paths: N_PATHS,
        candidate_case_radius: RADIUS,
        enable_filter: true,
        lead_time: 1,
        obs_scenario: "P1",
        L: 2,
        K: 4,
        shipments: [{ times_d: [0, 1, 2], temps_c: [1, 1, 1] }],
      },
    },
  };
}

function timeOne(rpc, method, params) {
  const xs = [];
  const total = REPS + WARMUP;
  for (let i = 0; i < total; i++) {
    const initOut = rpc(initPayload());
    if (initOut.ok !== true) throw new Error(`init failed: ${JSON.stringify(initOut)}`);
    for (let d = 0; d < WARM_DAYS; d++) {
      const w = rpc({ id: `w${d}`, method: "step", params: { order: ORDER } });
      if (w.ok !== true) throw new Error(`warm step failed: ${JSON.stringify(w)}`);
    }
    const t0 = performance.now();
    const out = rpc({ id: "t", method, params });
    if (out.ok !== true) throw new Error(`${method} failed: ${JSON.stringify(out)}`);
    xs.push((performance.now() - t0) / 1000);
  }
  return stats(xs.slice(WARMUP));
}

async function main() {
  if (!existsSync(pkgJs)) {
    console.error(`missing ${pkgJs}; run ./scripts/build-wasm.sh`);
    process.exit(1);
  }
  const mod = await import(new URL(`file://${pkgJs}`).href);
  const coldT0 = performance.now();
  await mod.default({ module_or_path: readFileSync(wasmPath) });
  const cold_ms = performance.now() - coldT0;
  const rpc = (obj) => JSON.parse(mod.handle_rpc(JSON.stringify(obj)));

  const step = timeOne(rpc, "step", { order: ORDER });
  const damped = timeOne(rpc, "act", { policy: "damped_sw" });
  const rollout = timeOne(rpc, "act", { policy: "rollout" });

  const out = {
    meta: {
      target: "wasm32-unknown-unknown",
      pkg: pkgJs,
      warm_days: WARM_DAYS,
      reps: REPS,
      warmup: WARMUP,
      timer: "one advance after warm; includes JSON parse/stringify in handle_rpc",
    },
    cold_start_ms: cold_ms,
    step,
    act_damped_sw: damped,
    act_rollout: rollout,
  };
  console.log(JSON.stringify(out, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
