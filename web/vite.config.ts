import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * T-144: WASM worker + pkg resolve through the Vite graph (dev and production).
 * T-145 library build: `npm run build:lib` uses `vite.lib.config.ts`.
 * Run `./scripts/build-wasm.sh` so `web/src/wasm/` exists before dev/build.
 */
export default defineConfig({
  root: ".",
  plugins: [react()],
  assetsInclude: ["**/*.wasm"],
  worker: {
    format: "es",
  },
  server: {
    port: 5173,
    open: false,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  test: {
    environment: "node",
    include: [
      "src/**/*.test.ts",
      "src/**/*.test.tsx",
      "scripts/smoke-autopilot-mock.ts",
    ],
    setupFiles: ["./src/testSetup.ts"],
  },
});
