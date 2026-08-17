/**
 * WASM worker host for EngineSession (ADR 0120).
 * Same JSON RPC envelope as packaging/pyodide/worker.js:
 *   init | step | step_n | reset | act | set_obs_scenario | set_obs_channels | tradeoff_forecast | events
 *
 * Demo budgets use DEMO_BUDGETS (n_particles ≤ 200), not full production N.
 * init / reset hydrate missing shipments + clamp budgets (T-071 / session_rpc parity).
 *
 * Load voi_wasm from VITE_WASM_PKG_URL (default /wasm/) or sibling ./pkg/.
 */

/** ADR 0099 dialed browser demo preset (≤ production defaults). */
const DEMO_BUDGETS = {
  n_particles: 200,
  H: 7,
  n_rollout_paths: 2,
  candidate_case_radius: 1,
};

/** Parquet-free smoke fixture (mirrors Python smoke_cool_shipments). */
function smokeCoolShipments() {
  return [
    {
      shipment_id: "SMOKE-COOL",
      times_d: [0.0, 1.0, 2.0],
      temps_c: [1.0, 1.0, 1.0],
      duration_d: 2.0,
    },
  ];
}

/** Fill missing/empty shipments with smokeCoolShipments (ADR 0107). */
function ensureDemoShipments(config) {
  const out = { ...config };
  const ships = out.shipments;
  if (!ships || (Array.isArray(ships) && ships.length === 0)) {
    out.shipments = smokeCoolShipments();
  }
  return out;
}

/**
 * Attach injectable shipments and clamp dialed demo budgets into config.
 * Mirrors packaging/pyodide/session_rpc.py prepare_demo_config.
 */
function prepareDemoConfig(config, shipments = undefined) {
  const out = { ...config };
  if (shipments !== undefined) {
    out.shipments = [...shipments];
  }
  const hydrated = ensureDemoShipments(out);
  for (const [key, cap] of Object.entries(DEMO_BUDGETS)) {
    if (!(key in hydrated)) {
      hydrated[key] = cap;
    } else {
      hydrated[key] = Math.min(Number(hydrated[key]), cap);
    }
  }
  return hydrated;
}

/** Apply demo hydrate on init / reset before Rust handle_rpc (T-121 A3). */
function hydrateRpcRequest(request) {
  if (!request || typeof request !== "object") return request;
  const method = request.method;
  if (method !== "init" && method !== "reset") return request;

  const params =
    request.params && typeof request.params === "object"
      ? { ...request.params }
      : {};

  if (method === "init") {
    const raw =
      params.config && typeof params.config === "object" ? params.config : {};
    params.config = prepareDemoConfig(raw);
    return { ...request, params };
  }

  if ("config" in params && params.config != null) {
    const raw = typeof params.config === "object" ? params.config : {};
    params.config = prepareDemoConfig(raw);
    return { ...request, params };
  }

  return request;
}

let handle_rpc = null;
let ready = null;

async function ensureReady() {
  if (ready) return ready;
  ready = (async () => {
    const params = new URLSearchParams(self.location.search);
    const pkg = (params.get("pkgUrl") || "/wasm/").replace(/\/?$/, "/");
    const candidates = [`${pkg}voi_wasm.js`, new URL("./pkg/voi_wasm.js", import.meta.url).href];
    let lastErr = null;
    for (const href of candidates) {
      try {
        const mod = await import(href);
        await mod.default();
        handle_rpc = mod.handle_rpc;
        return;
      } catch (e) {
        lastErr = e;
      }
    }
    throw lastErr || new Error("voi_wasm module not found");
  })();
  return ready;
}

self.onmessage = async (ev) => {
  const msg = ev.data;
  try {
    await ensureReady();
    let request = typeof msg === "string" ? JSON.parse(msg) : msg;
    request = hydrateRpcRequest(request);
    const out = handle_rpc(JSON.stringify(request));
    const parsed = JSON.parse(out);
    self.postMessage(parsed);
  } catch (err) {
    const id = msg && msg.id;
    self.postMessage({
      id,
      ok: false,
      error: { type: "WorkerError", message: String(err) },
    });
  }
};
