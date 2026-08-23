/**
 * WASM worker host for EngineSession (ADR 0139 / T-144).
 * Bundled via Vite; imports wasm-pack output from ../wasm/voi_wasm.js.
 *
 * Same JSON RPC envelope as legacy packaging/wasm/worker.js:
 *   init | step | step_n | reset | act | set_obs_scenario | set_obs_channels |
 *   tradeoff_forecast | events
 */

import init, { handle_rpc as wasmHandleRpc } from "../wasm/voi_wasm.js";
import { hydrateRpcRequest } from "./demoConfig";

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
