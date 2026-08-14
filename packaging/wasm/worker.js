/**
 * WASM worker host for EngineSession (ADR 0120).
 * Same JSON RPC envelope as packaging/pyodide/worker.js:
 *   init | step | step_n | reset | act
 */
import init, { handle_rpc } from "/wasm/voi_wasm.js";

let ready = null;

async function ensureReady() {
  if (ready) return ready;
  ready = init();
  return ready;
}

self.onmessage = async (ev) => {
  const msg = ev.data;
  try {
    await ensureReady();
    const raw = typeof msg === "string" ? msg : JSON.stringify(msg);
    const out = handle_rpc(raw);
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
