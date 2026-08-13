import { loadPyodide } from "pyodide";
import { createRequire } from "module";
import { dirname } from "path";
import { readFileSync } from "fs";

const require = createRequire(import.meta.url);
const pyodidePkg = dirname(require.resolve("pyodide/package.json"));
const wheelName = "blueberries_voi-0.1.0-py3-none-any.whl";
const wheelPath =
  `/home/oliver/blog/blueberries-voi/.worktrees/T-075-implement/dist/${wheelName}`;
const wheelUrl = `http://127.0.0.1:5173/wheels/${wheelName}`;

const head = await fetch(wheelUrl, { method: "HEAD" });
if (!head.ok) throw new Error(`Vite wheel URL failed: ${head.status} ${wheelUrl}`);
console.log("VITE_WHEEL_URL_OK", wheelUrl, head.status);

const worker = await fetch("http://127.0.0.1:5173/packaging/pyodide/worker.js");
if (!worker.ok) throw new Error(`worker.js failed: ${worker.status}`);
const workerText = await worker.text();
if (!/wheelUrl|URLSearchParams/.test(workerText)) {
  throw new Error("worker.js missing wheelUrl honor");
}
console.log("VITE_WORKER_OK", worker.status);

console.log("Loading Pyodide 314.0.4 from", pyodidePkg);
const pyodide = await loadPyodide({ indexURL: pyodidePkg + "/" });
await pyodide.loadPackage(["micropip", "numpy", "scipy", "pyarrow"]);

const bytes = readFileSync(wheelPath);
const emfsPath = `/tmp/${wheelName}`;
pyodide.FS.writeFile(emfsPath, bytes);
console.log("micropip.install(emfs path, deps=False)");
await pyodide.runPythonAsync(`
import micropip
await micropip.install("emfs:${emfsPath}", deps=False)
`);

const raw = await pyodide.runPythonAsync(`
from blueberries_voi.simulator import EngineSession, DEMO_BUDGETS
from blueberries_voi.sim.shipments import ensure_demo_shipments
import json
session = EngineSession()
cfg = ensure_demo_shipments({
    "n_particles": int(DEMO_BUDGETS["n_particles"]),
    "H": int(DEMO_BUDGETS["H"]),
})
snap = session.init(cfg, seed=0)
delta = session.step(8)
json.dumps({
    "seq": snap["seq"],
    "episode_day": delta.get("episode_day"),
    "belief_L": snap["belief"]["L"],
})
`);
console.log("PYODIDE_RESULT", raw);
console.log("PYODIDE_LIVE_SMOKE_PASS");
