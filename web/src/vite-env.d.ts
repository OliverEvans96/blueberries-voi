/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENGINE_ADAPTER?: string;
  readonly VITE_ENGINE_API_BASE_URL?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_PYODIDE_WORKER_URL?: string;
  readonly VITE_PYODIDE_WHEEL_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
