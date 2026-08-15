#!/usr/bin/env node
/**
 * Node Pyodide 314.0.4 column for the 1d×90d EngineSession matrix.
 *
 * Same RPC as packaging/pyodide/worker.js: one loadPyodide, micropip slim
 * wheel, one EngineSession; 1 day = one `step` RPC; 90 days = one `step_n`.
 * Cold start is timed separately and is not folded into the 1-day cell.
 */
import { existsSync, readFileSync, writeFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { performance } from "node:perf_hooks";

const PYODIDE_VERSION = "314.0.4";
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPEATS = 3;
const ORDER = 16;
const HORIZON = Number(process.env.BENCH_HORIZON || 90);
const FOOTNOTE_DAYS = Number(process.env.BENCH_FOOTNOTE_DAYS || 14);
const DEADLINE_MS = Number(process.env.BENCH_DEADLINE_MS || 40 * 60 * 1000);
const SEED = 42;

const CONFIG = {
  n_particles: 200,
  H: 7,
  n_rollout_paths: 2,
  candidate_case_radius: 1,
  enable_filter: true,
  lead_time: 1,
  obs_scenario: "P1",
  L: 2,
  K: 4,
};

function findWheel() {
  const dist = join(ROOT, "dist");
  if (!existsSync(dist)) return null;
  const names = readdirSync(dist).filter(
    (n) => n.startsWith("blueberries_voi-") && n.endsWith(".whl"),
  );
  names.sort();
  return names.length ? join(dist, names[names.length - 1]) : null;
}

function stats(xs) {
  const s = [...xs].sort((a, b) => a - b);
  return {
    mean_s: xs.reduce((a, b) => a + b, 0) / xs.length,
    min_s: s[0],
    max_s: s[s.length - 1],
    n: xs.length,
  };
}

async function resolveLoadPyodide() {
  const extra = process.env.NODE_PATH;
  const require = createRequire(
    extra ? pathToFileURL(join(extra, "pyodide/package.json")).href : import.meta.url,
  );
  try {
    const pkg = dirname(require.resolve("pyodide/package.json"));
    const mod = await import(pathToFileURL(join(pkg, "pyodide.mjs")).href);
    return {
      loadPyodide: mod.loadPyodide,
      indexURL: pkg + "/",
      source: pkg,
    };
  } catch (err) {
    const cdn = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/pyodide.mjs`;
    try {
      const mod = await import(cdn);
      return {
        loadPyodide: mod.loadPyodide,
        indexURL: `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`,
        source: cdn,
      };
    } catch (err2) {
      throw new Error(
        `Could not load Pyodide ${PYODIDE_VERSION} from npm (${err}) or CDN (${err2}). ` +
          `Try: npm install pyodide@${PYODIDE_VERSION}`,
      );
    }
  }
}

const WORKER_PY = `
import json
from blueberries_voi.sim.shipments import ensure_demo_shipments
from blueberries_voi.simulator import DEMO_BUDGETS, EngineSession

_SESSION = EngineSession()
_RPC_METHODS = frozenset({"init", "step", "step_n", "reset", "act"})

def dumps_payload(obj):
    return json.dumps(obj)

def _ok(req_id, result):
    return dumps_payload({"id": req_id, "ok": True, "result": result})

def _err(req_id, err_type, message):
    return dumps_payload({
        "id": req_id,
        "ok": False,
        "error": {"type": err_type, "message": message},
    })

def _dispatch(method, params):
    if method == "init":
        config = ensure_demo_shipments(dict(params.get("config") or {}))
        seed = params.get("seed")
        return _SESSION.init(config, seed=None if seed is None else int(seed))
    if method == "step":
        return _SESSION.step(int(params["order_qty"]))
    if method == "step_n":
        orders = list(params.get("orders") or [])
        return _SESSION.step_n([int(q) for q in orders])
    if method == "reset":
        config = params.get("config")
        seed = params.get("seed")
        return _SESSION.reset(
            None if config is None else ensure_demo_shipments(dict(config)),
            seed=None if seed is None else int(seed),
        )
    if method == "act":
        policy = params.get("policy")
        overrides = {k: v for k, v in params.items() if k != "policy"}
        return _SESSION.act(policy=policy, **overrides)
    raise ValueError(f"unknown method {method!r}")

def handle_rpc(request):
    if isinstance(request, str):
        request = json.loads(request)
    req_id = str(request.get("id", ""))
    method = request.get("method")
    params = request.get("params") or {}
    if method not in _RPC_METHODS:
        return _err(req_id, "UnknownMethod", f"unknown method {method!r}")
    try:
        result = _dispatch(method, params)
    except Exception as exc:
        return _err(req_id, type(exc).__name__, str(exc))
    return _ok(req_id, result)
`;

function rpc(pyodide, obj) {
  const payload = JSON.stringify(obj);
  const resultStr = pyodide.runPython(`handle_rpc(${JSON.stringify(payload)})`);
  const parsed = JSON.parse(resultStr);
  if (!parsed.ok) {
    const e = parsed.error || {};
    throw new Error(`${e.type || "rpc"}: ${e.message}`);
  }
  return parsed.result;
}

function timeCalls(fn, repeats) {
  fn();
  const xs = [];
  for (let i = 0; i < repeats; i++) {
    const t0 = performance.now();
    fn();
    xs.push((performance.now() - t0) / 1000);
  }
  return stats(xs);
}

async function main() {
  const wheelPath = findWheel();
  if (!wheelPath) {
    throw new Error("No dist/*.whl — run: uv run python scripts/build_slim_wheel.py");
  }

  const loader = await resolveLoadPyodide();
  const tCold0 = performance.now();
  const pyodide = await loader.loadPyodide({ indexURL: loader.indexURL });
  await pyodide.loadPackage(["micropip", "numpy", "scipy", "pyarrow"]);
  const bytes = readFileSync(wheelPath);
  const wheelName = wheelPath.split("/").pop();
  const emfsPath = `/tmp/${wheelName}`;
  pyodide.FS.writeFile(emfsPath, bytes);
  await pyodide.runPythonAsync(`
import micropip
await micropip.install("emfs:${emfsPath}", deps=False)
`);
  await pyodide.runPythonAsync(WORKER_PY);
  const demandSrc = join(ROOT, "data/freshnet/demand_profile.json");
  if (existsSync(demandSrc)) {
    pyodide.FS.mkdirTree("/lib/python3.14/data/freshnet");
    pyodide.FS.writeFile(
      "/lib/python3.14/data/freshnet/demand_profile.json",
      new Uint8Array(readFileSync(demandSrc)),
    );
  }
  // Filter arrival priors load Abdella parquet from default_abdella_root()
  // (package-relative), even when EngineSession uses smoke_cool_shipments.
  const abdellaGuest = String(
    pyodide.runPython(`
from blueberries_voi.model.abdella import default_abdella_root
str(default_abdella_root())
`),
  ).trim();
  const abdellaDir = join(ROOT, "data/abdella");
  if (existsSync(abdellaDir)) {
    pyodide.FS.mkdirTree(abdellaGuest);
    for (const name of readdirSync(abdellaDir)) {
      if (!name.endsWith(".parquet")) continue;
      pyodide.FS.writeFile(
        `${abdellaGuest.replace(/\/$/, "")}/${name}`,
        new Uint8Array(readFileSync(join(abdellaDir, name))),
      );
    }
  }
  const cold_start_s = (performance.now() - tCold0) / 1000;

  const oneDay = () => {
    rpc(pyodide, {
      id: "init",
      method: "init",
      params: { config: CONFIG, seed: SEED },
    });
    const delta = rpc(pyodide, {
      id: "step",
      method: "step",
      params: { order_qty: ORDER },
    });
    if (!delta || typeof delta !== "object" || !("day" in delta)) {
      throw new Error("step did not return a DayDelta");
    }
  };

  const ninety = () => {
    rpc(pyodide, {
      id: "init90",
      method: "init",
      params: { config: CONFIG, seed: SEED },
    });
    const deltas = rpc(pyodide, {
      id: "stepn",
      method: "step_n",
      params: { orders: Array(HORIZON).fill(ORDER) },
    });
    if (!Array.isArray(deltas) || deltas.length !== HORIZON) {
      throw new Error(`step_n expected ${HORIZON} deltas, got ${deltas?.length}`);
    }
  };

  const oneAct = () => {
    rpc(pyodide, {
      id: "init-act",
      method: "init",
      params: { config: CONFIG, seed: SEED },
    });
    const delta = rpc(pyodide, {
      id: "act",
      method: "act",
      params: { policy: "rollout" },
    });
    if (!delta || typeof delta !== "object" || !("day" in delta)) {
      throw new Error("act did not return a DayDelta");
    }
  };

  const nActs = (n) => {
    rpc(pyodide, {
      id: "init-act-n",
      method: "init",
      params: { config: CONFIG, seed: SEED },
    });
    for (let i = 0; i < n; i++) {
      rpc(pyodide, {
        id: `act-${i}`,
        method: "act",
        params: { policy: "rollout" },
      });
    }
  };

  function timeOrNa(label, fn, repeats) {
    const t0 = performance.now();
    try {
      const timed = timeCalls(fn, repeats);
      timed.elapsed_wall_s = (performance.now() - t0) / 1000;
      return timed;
    } catch (err) {
      return {
        n_a: String(err && err.message ? err.message : err),
        elapsed_wall_s: (performance.now() - t0) / 1000,
        label,
      };
    }
  }

  const deadline = performance.now() + DEADLINE_MS;
  console.error("cold_start_s", cold_start_s.toFixed(2));
  console.error("timing simulator 1d…");
  const sim1 = timeCalls(oneDay, REPEATS);
  console.error("simulator_1d", JSON.stringify(sim1));
  const remaining = () => deadline - performance.now();

  let sim90;
  if (remaining() < 60_000) {
    sim90 = { n_a: "skipped: under 60s left before 40min deadline" };
  } else {
    console.error("timing simulator 90d…");
    sim90 = timeOrNa("simulator_90d", ninety, REPEATS);
    console.error("simulator_90d", JSON.stringify(sim90));
  }

  console.error("timing controller 1d…");
  const ctrl1 = timeCalls(oneAct, REPEATS);
  console.error("controller_1d", JSON.stringify(ctrl1));

  let ctrl90;
  let footnote14 = null;
  if (remaining() < 120_000) {
    ctrl90 = {
      n_a: `skipped: ${Math.round(remaining() / 1000)}s left before 40min deadline`,
    };
    footnote14 = timeOrNa("controller_14d", () => nActs(FOOTNOTE_DAYS), REPEATS);
  } else {
    console.error("timing controller 90d…");
    const t90 = performance.now();
    try {
      ctrl90 = timeCalls(() => nActs(HORIZON), REPEATS);
      ctrl90.note = "90× act(policy=rollout) RPCs; no act_n";
    } catch (err) {
      ctrl90 = {
        n_a: String(err && err.message ? err.message : err),
        elapsed_wall_s: (performance.now() - t90) / 1000,
      };
      footnote14 = timeOrNa("controller_14d", () => nActs(FOOTNOTE_DAYS), 1);
    }
    if (performance.now() > deadline && !ctrl90.mean_s) {
      ctrl90 = {
        n_a: "exceeded ~40 min wall budget",
        elapsed_wall_s: (performance.now() - t90) / 1000,
      };
    }
  }

  const out = {
    meta: {
      pyodide: PYODIDE_VERSION,
      load_source: loader.source,
      wheel: wheelPath,
      fixture: "ensure_demo_shipments → smoke_cool_shipments",
      n_particles: 200,
      enable_filter: true,
      order_qty: ORDER,
      horizon_days: HORIZON,
      repeats: REPEATS,
      warmup: 1,
      deadline_ms: DEADLINE_MS,
      note: "cold start excluded from 1-day / 90-day cells; init is inside each cell",
      policy: "act(policy='rollout')",
    },
    cold_start_s,
    engine_session: {
      simulator_1d_step: sim1,
      simulator_90d_step_n: sim90,
      controller_1d_act_rollout: ctrl1,
      controller_90d_act_rollout: ctrl90,
      footnote_14d_act: footnote14,
    },
  };

  const dest = join(ROOT, "outputs/bench_1d_90d_pyodide.json");
  try {
    writeFileSync(dest, JSON.stringify(out, null, 2) + "\n");
  } catch {
    /* outputs/ may be missing */
  }
  console.log(JSON.stringify(out, null, 2));
  console.log("wrote", dest);
}

try {
  await main();
} catch (err) {
  console.error("PYODIDE_BENCH_FAIL", err && err.message ? err.message : err);
  if (err && err.stack) {
    console.error(String(err.stack).split("\n").slice(0, 20).join("\n"));
  }
  process.exit(1);
}
