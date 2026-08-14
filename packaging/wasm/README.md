# WASM studio kernel

Build (requires rustc + wasm-pack):

```bash
./scripts/build-wasm.sh
```

Vite should serve `packaging/wasm/pkg/` at `/wasm/` (`VITE_WASM_PKG_URL=/wasm/`).
The worker is `packaging/wasm/worker.js` (`VITE_WASM_WORKER_URL`).
