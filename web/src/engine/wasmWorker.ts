/**
 * WASM worker host for EngineSession (ADR 0139 / T-144).
 * Bundled via Vite; imports wasm-pack output from ../wasm/voi_wasm.js.
 *
 * Same JSON RPC envelope as legacy packaging/wasm/worker.js:
 *   init | step | step_n | reset | act | set_obs_scenario | set_obs_channels |
 *   tradeoff_forecast | events
 */

import init, { handle_rpc as wasmHandleRpc } from "../wasm/voi_wasm.js";

/** ADR 0099 dialed browser demo preset (≤ production defaults). */
const DEMO_BUDGETS = {
  n_particles: 200,
  H: 7,
  n_rollout_paths: 2,
  candidate_case_radius: 1,
} as const;

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
function ensureDemoShipments(config: Record<string, unknown>) {
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
function prepareDemoConfig(
  config: Record<string, unknown>,
  shipments: unknown[] | undefined = undefined,
) {
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
function hydrateRpcRequest(request: Record<string, unknown> | null) {
  if (!request || typeof request !== "object") return request;
  const method = request.method;
  if (method !== "init" && method !== "reset") return request;

  const params =
    request.params && typeof request.params === "object"
      ? { ...(request.params as Record<string, unknown>) }
      : {};

  if (method === "init") {
    const raw =
      params.config && typeof params.config === "object"
        ? (params.config as Record<string, unknown>)
        : {};
    params.config = prepareDemoConfig(raw);
    return { ...request, params };
  }

  if ("config" in params && params.config != null) {
    const raw =
      typeof params.config === "object"
        ? (params.config as Record<string, unknown>)
        : {};
    params.config = prepareDemoConfig(raw);
    return { ...request, params };
  }

  return request;
}

type RpcHandler = (requestJson: string) => string;

let handleRpc: RpcHandler | null = null;
let ready: Promise<void> | null = null;

function resolveAssetBaseUrl(): string | undefined {
  const params = new URLSearchParams(self.location.search);
  const fromQuery = params.get("assetBaseUrl") ?? params.get("pkgUrl");
  const fromEnv = import.meta.env.VITE_WASM_ASSET_BASE_URL ?? import.meta.env.VITE_WASM_PKG_URL;
  const raw = fromQuery ?? fromEnv;
  if (!raw || raw === "bundled") return undefined;
  return raw.replace(/\/?$/, "/");
}

async function ensureReady(): Promise<void> {
  if (ready) return ready;
  ready = (async () => {
    const assetBase = resolveAssetBaseUrl();
    if (assetBase) {
      const mod = (await import(/* @vite-ignore */ `${assetBase}voi_wasm.js`)) as {
        default: () => Promise<unknown>;
        handle_rpc: RpcHandler;
      };
      await mod.default();
      handleRpc = mod.handle_rpc;
      return;
    }
    await init();
    handleRpc = wasmHandleRpc;
  })();
  return ready;
}

self.onmessage = async (ev: MessageEvent) => {
  const msg = ev.data;
  try {
    await ensureReady();
    if (!handleRpc) {
      throw new Error("voi_wasm handle_rpc not initialized");
    }
    let request: Record<string, unknown> =
      typeof msg === "string" ? (JSON.parse(msg) as Record<string, unknown>) : msg;
    request = hydrateRpcRequest(request) as Record<string, unknown>;
    const out = handleRpc(JSON.stringify(request));
    const parsed = JSON.parse(out) as unknown;
    self.postMessage(parsed);
  } catch (err) {
    const id =
      msg && typeof msg === "object" && msg !== null && "id" in msg
        ? (msg as { id?: unknown }).id
        : undefined;
    self.postMessage({
      id,
      ok: false,
      error: { type: "WorkerError", message: String(err) },
    });
  }
};
