/**
 * Browser demo config hydration for WASM init/reset (T-071 / T-125 / T-134).
 *
 * When `arrival_product` is set and shipments are absent, leave shipments unset so
 * Rust `apply_rpc_configure` can hydrate `mod21_demo_shipments` (T-150).
 */

/** Parquet-free smoke fixture (mirrors Python smoke_cool_shipments). */
export function smokeCoolShipments() {
  return [
    {
      shipment_id: "SMOKE-COOL",
      times_d: [0.0, 1.0, 2.0],
      temps_c: [1.0, 1.0, 1.0],
      duration_d: 2.0,
    },
  ];
}

function hasArrivalProduct(config: Record<string, unknown>): boolean {
  const product = config.arrival_product;
  return typeof product === "string" && product.length > 0;
}

function shipmentsMissing(config: Record<string, unknown>): boolean {
  const ships = config.shipments;
  return !ships || (Array.isArray(ships) && ships.length === 0);
}

/**
 * Fill missing shipments for browser demos.
 * Defer to Rust mod21 when `arrival_product` is present; otherwise smoke cool.
 */
export function ensureDemoShipments(config: Record<string, unknown>) {
  const out = { ...config };
  if (!shipmentsMissing(out)) {
    return out;
  }
  if (hasArrivalProduct(out)) {
    delete out.shipments;
    return out;
  }
  out.shipments = smokeCoolShipments();
  return out;
}

/** ADR 0099 dialed browser demo preset (≤ production defaults). */
export const DEMO_BUDGETS = {
  n_particles: 200,
  H: 7,
  n_rollout_paths: 2,
  candidate_case_radius: 1,
} as const;

/**
 * Attach injectable shipments and clamp dialed demo budgets into config.
 * Mirrors packaging/pyodide/session_rpc.py prepare_demo_config.
 */
export function prepareDemoConfig(
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
export function hydrateRpcRequest(request: Record<string, unknown> | null) {
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
