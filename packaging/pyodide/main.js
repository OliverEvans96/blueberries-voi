/**
 * Main-thread smoke harness for the Pyodide EngineSession worker (T-047).
 *
 * Physics stays in the worker: this page only postMessages RPC requests and
 * never calls pyodide.runPython / runPythonAsync for per-click steps.
 *
 * Protocol: { id, method, params } → { id, ok, result | error }
 */

const WORKER_URL = new URL("./worker.js", import.meta.url);

/**
 * @param {Worker} worker
 * @param {{ id: string, method: string, params?: object }} request
 * @returns {Promise<object>}
 */
function rpc(worker, request) {
  return new Promise((resolve, reject) => {
    const onMessage = (event) => {
      worker.removeEventListener("message", onMessage);
      worker.removeEventListener("error", onError);
      try {
        const raw = event.data;
        const resp = typeof raw === "string" ? JSON.parse(raw) : raw;
        resolve(resp);
      } catch (err) {
        reject(err);
      }
    };
    const onError = (err) => {
      worker.removeEventListener("message", onMessage);
      worker.removeEventListener("error", onError);
      reject(err);
    };
    worker.addEventListener("message", onMessage);
    worker.addEventListener("error", onError);
    // JSON string payload — structured-clone safe, no PyProxy on main thread.
    worker.postMessage(JSON.stringify(request));
  });
}

/**
 * Demo budget smoke: init + step + step_n (≥2 orders) under dialed caps.
 * @returns {Promise<void>}
 */
export async function runDemoBudgetSmoke() {
  const worker = new Worker(WORKER_URL, { type: "classic" });
  try {
    // DEMO_BUDGETS: n_particles ≤ 200 (not full production particle count). Shipments are
    // injected by the worker/session_rpc prepare path in full hosts; smoke
    // passes dialed numeric knobs only when the worker already has fixtures.
    const config = {
      n_particles: 200,
      H: 7,
      n_rollout_paths: 2,
      candidate_case_radius: 1,
      L: 2,
      K: 4,
      enable_filter: true,
    };

    const initResp = await rpc(worker, {
      id: "main-init",
      method: "init",
      params: { config, seed: 47 },
    });
    if (!initResp.ok) throw new Error(JSON.stringify(initResp.error));

    const stepResp = await rpc(worker, {
      id: "main-step",
      method: "step",
      params: { order_qty: 1 },
    });
    if (!stepResp.ok) throw new Error(JSON.stringify(stepResp.error));

    const stepNResp = await rpc(worker, {
      id: "main-stepn",
      method: "step_n",
      params: { orders: [1, 0] },
    });
    if (!stepNResp.ok) throw new Error(JSON.stringify(stepNResp.error));

    return { initResp, stepResp, stepNResp };
  } finally {
    worker.terminate();
  }
}

// Browser entry: expose for manual smoke pages.
if (typeof window !== "undefined") {
  window.runDemoBudgetSmoke = runDemoBudgetSmoke;
}
