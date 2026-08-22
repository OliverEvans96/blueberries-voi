/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENGINE_ADAPTER?: string;
  readonly VITE_ENGINE_API_BASE_URL?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_PYODIDE_WORKER_URL?: string;
  readonly VITE_PYODIDE_WHEEL_URL?: string;
  readonly VITE_WASM_WORKER_URL?: string;
  readonly VITE_WASM_PKG_URL?: string;
  readonly VITE_WASM_ASSET_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
