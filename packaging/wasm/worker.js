/**
 * WASM worker host for EngineSession (ADR 0120).
 * Same JSON RPC envelope as packaging/pyodide/worker.js:
 *   init | step | step_n | reset | act
 *
 * Load voi_wasm from VITE_WASM_PKG_URL (default /wasm/) or sibling ./pkg/.
 */
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
