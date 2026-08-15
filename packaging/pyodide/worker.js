/**
 * Pyodide worker host for EngineSession (T-047 / ADR 0099–0101).
 *
 * Loads Pyodide 314.0.4 via ESM ``pyodide.mjs`` in a **module** worker (ADR 0111),
 * installs the Release/slim wheel via micropip,
 * binds one EngineSession, and answers RPC methods:
 *   init | step | step_n | reset | act
 *
 * Wire protocol (JSON strings / structured-clone-safe objects):
 *   request:  { id, method, params }
 *   response: { id, ok: true, result } | { id, ok: false, error: { type, message } }
 *
 * Payloads are serialised with JSON.stringify / Python json.dumps — never deep
 * toJs (depth=-1) of nested EngineSession trees. Demo budgets use DEMO_BUDGETS
 * (n_particles ≤ 200), not the full production particle count.
 */

import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.4/full/pyodide.mjs";

const PYODIDE_VERSION = "314.0.4";
const PYODIDE_INDEX = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

/** GitHub Release URL for the slim / browser wheel (replace tag/asset as published). */
const SLIM_WHEEL_URL =
  "https://github.com/oliver/blueberries-voi/releases/download/v0.1.0/" +
  "blueberries_voi-0.1.0-py3-none-any.whl";

/**
 * Resolve wheel URL for micropip (ADR 0108 / T-072).
 * Prefer ``?wheelUrl=`` on the worker script URL; Release URL is fallback only.
 */
function resolveWheelUrl() {
  try {
    const params = new URLSearchParams(self.location.search);
    const fromQuery = params.get("wheelUrl");
    if (fromQuery) return fromQuery;
  } catch (_err) {
    /* ignore malformed location */
  }
  return SLIM_WHEEL_URL;
}

let pyodide = null;
let ready = null;

/**
 * Bootstrap Pyodide + micropip.install(slim wheel) + one EngineSession.
 * Python-side handle_rpc mirrors packaging/pyodide/session_rpc.py.
 */
async function ensureReady() {
  if (ready) return ready;
  ready = (async () => {
    // Module-worker ESM bootstrap (ADR 0111); classic worker loaders rejected on 314.0.4.
    pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX });
    // Reuse Pyodide 314.0.4 wasm builds (numpy 2.4.3, scipy, pyarrow). Do not
    // micropip.install(..., reinstall=True) CPython wheels over these.
    // pyarrow: sim.shipments → model.abdella imports it at module load.
    await pyodide.loadPackage(["micropip", "numpy", "scipy", "pyarrow"]);
    const micropip = pyodide.pyimport("micropip");
    // Local override via ?wheelUrl=; Release/slim URL is fallback only (ADR 0108).
    const wheelUrl = resolveWheelUrl();
    await micropip.install(wheelUrl);

    await pyodide.runPythonAsync(`
import json
from blueberries_voi.sim.shipments import ensure_demo_shipments
from blueberries_voi.simulator import DEMO_BUDGETS, EngineSession

_SESSION = EngineSession()
_RPC_METHODS = frozenset({"init", "step", "step_n", "reset", "act", "set_obs_scenario"})

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
    if method == "set_obs_scenario":
        return _SESSION.set_obs_scenario(params["obs_scenario"])
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
`);
    return pyodide;
  })();
  return ready;
}

self.onmessage = async (event) => {
  const data = event.data;
  let request;
  try {
    request = typeof data === "string" ? JSON.parse(data) : data;
  } catch (err) {
    self.postMessage(
      JSON.stringify({
        id: "",
        ok: false,
        error: { type: "JSONDecodeError", message: String(err) },
      }),
    );
    return;
  }

  const reqId = request && request.id != null ? String(request.id) : "";
  try {
    await ensureReady();
    // Pass a JSON string into Python; receive a JSON string back (no deep toJs).
    const payload = JSON.stringify(request);
    const resultStr = pyodide.runPython(
      `handle_rpc(${JSON.stringify(payload)})`,
    );
    // Always post a string (structured-clone safe); main thread JSON.parses.
    self.postMessage(
      typeof resultStr === "string" ? resultStr : JSON.stringify(resultStr),
    );
  } catch (err) {
    self.postMessage(
      JSON.stringify({
        id: reqId,
        ok: false,
        error: { type: "WorkerError", message: String(err) },
      }),
    );
  }
};
