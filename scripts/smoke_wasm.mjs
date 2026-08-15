#!/usr/bin/env node
/**
 * wasm32 handle_rpc contract for the studio EngineAdapter surface
 * (init / reset / step / step_n / act). Used by ./scripts/smoke-wasm.sh.
 *
 * `"ok": true` is not enough — Snapshot/DayDelta must carry FlatBelief fields
 * the ViewModelProjector reads (lot_counts, age_marginals, tau_grid).
 */
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkg = process.env.VOI_WASM_SMOKE_OUT ?? join(root, "target", "wasm-smoke-pkg");
const js = join(pkg, "voi_wasm.js");

if (!existsSync(js)) {
  throw new Error(`missing ${js}; run ./scripts/smoke-wasm.sh`);
}

async function loadMod() {
  try {
    return createRequire(import.meta.url)(js);
  } catch {
    return await import(pathToFileURL(js).href);
  }
}

const mod = await loadMod();
const handle = mod.handle_rpc ?? mod.default?.handle_rpc;
if (typeof handle !== "function") {
  throw new Error(`handle_rpc not exported from ${pkg}: ${Object.keys(mod).join(",")}`);
}

function parseRpc(raw) {
  return JSON.parse(raw);
}

function rpc(obj) {
  const raw = handle(JSON.stringify(obj));
  const parsed = parseRpc(raw);
  if (parsed.ok !== true) {
    throw new Error(`RPC ${obj.method} not ok: ${raw}`);
  }
  return parsed;
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

function assertFlatBelief(belief, label) {
  assert(belief != null && typeof belief === "object", `${label}: belief missing`);
  assert(Array.isArray(belief.lot_counts), `${label}: belief.lot_counts must be an array`);
  assert(
    Array.isArray(belief.age_marginals),
    `${label}: belief.age_marginals must be an array`,
  );
  assert(Array.isArray(belief.tau_grid), `${label}: belief.tau_grid must be an array`);
  assert(typeof belief.L === "number", `${label}: belief.L`);
  assert(typeof belief.K === "number", `${label}: belief.K`);
  // Same spreads ViewModelProjector.applySnapshot / applyDelta perform.
  const cloned = {
    ...belief,
    lot_counts: [...belief.lot_counts],
    age_marginals: [...belief.age_marginals],
    tau_grid: [...belief.tau_grid],
  };
  assert(cloned.lot_counts.length === belief.lot_counts.length, `${label}: clone`);
}

function assertSnapshot(result, label) {
  assert(typeof result.seq === "number", `${label}: seq`);
  assert(typeof result.episode_day === "number", `${label}: episode_day`);
  assertFlatBelief(result.belief, label);
  assert(Array.isArray(result.live_lots), `${label}: live_lots must be an array`);
  assert(Array.isArray(result.pipeline ?? []), `${label}: pipeline`);
}

function assertDayDelta(result, label) {
  assert(typeof result.seq === "number", `${label}: seq`);
  assert(typeof result.episode_day === "number", `${label}: episode_day`);
  assert(typeof result.drop_oldest === "boolean", `${label}: drop_oldest`);
  assert(result.day != null && typeof result.day === "object", `${label}: day`);
  assert(typeof result.day.day === "number", `${label}: day.day`);
  assert(typeof result.day.order_qty === "number", `${label}: day.order_qty`);
  assert(typeof result.day.sales_total === "number", `${label}: day.sales_total`);
  assertFlatBelief(result.belief, label);
  assert(Array.isArray(result.live_lots), `${label}: live_lots`);
}

const init = rpc({ id: "1", method: "init", params: { seed: 1 } });
assertSnapshot(init.result, "init");
assert(init.result.episode_day === 0, "init episode_day should be 0");
assert(init.result.seq === 0, "init seq should be 0");

const reset = rpc({ id: "2", method: "reset", params: { seed: 2 } });
assertSnapshot(reset.result, "reset");
assert(reset.result.episode_day === 0, "reset episode_day should be 0");

const step = rpc({ id: "3", method: "step", params: { order_qty: 0, order: 0 } });
assertDayDelta(step.result, "step");

const emptyN = rpc({ id: "4", method: "step_n", params: { orders: [] } });
assert(Array.isArray(emptyN.result), "step_n [] must return an array");
assert(emptyN.result.length === 0, `step_n [] length: ${emptyN.result.length}`);

const orders = [0, 8, 0, 16];
const many = rpc({ id: "5", method: "step_n", params: { orders } });
assert(Array.isArray(many.result), "step_n must return an array");
assert(
  many.result.length === orders.length,
  `step_n length ${many.result.length} != ${orders.length}`,
);
for (let i = 0; i < many.result.length; i++) {
  assertDayDelta(many.result[i], `step_n[${i}]`);
}

const actDefault = rpc({ id: "6", method: "act", params: {} });
assertDayDelta(actDefault.result, "act default");

const actRollout = rpc({
  id: "7",
  method: "act",
  params: { policy: "rollout" },
});
assertDayDelta(actRollout.result, "act rollout");

const unknown = parseRpc(handle(JSON.stringify({ id: "8", method: "nope", params: {} })));
assert(unknown.ok === false, "unknown method must set ok:false");
assert(
  unknown.error?.type === "UnknownMethod" || String(unknown.error?.message ?? "").length > 0,
  `unknown envelope: ${JSON.stringify(unknown)}`,
);

let malformed;
try {
  malformed = parseRpc(handle("{not-json"));
} catch (err) {
  throw new Error(`malformed JSON must return an error envelope, not throw: ${err}`);
}
assert(malformed.ok === false, "malformed JSON must set ok:false");
assert(malformed.error?.type, `malformed envelope: ${JSON.stringify(malformed)}`);

console.log(
  "wasm smoke: init/reset/step/step_n/act + error envelopes ok; belief.lot_counts is array (wasm32)",
);
