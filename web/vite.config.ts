import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Connect, Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const packagingPyodideDir = path.join(repoRoot, "packaging", "pyodide");
const packagingWasmDir = path.join(repoRoot, "packaging", "wasm");
const wasmPkgDir = path.join(packagingWasmDir, "pkg");
/** Local slim wheels from ``uv run python scripts/build_slim_wheel.py`` (repo dist/). */
const slimWheelDir = path.join(repoRoot, "dist");

/**
 * T-072 / ADR 0108 / ADR 0120 local URL contract:
 * - pyodide worker: /packaging/pyodide/worker.js
 * - wasm worker:    /packaging/wasm/worker.js
 * - wasm pkg:       /wasm/* (packaging/wasm/pkg from wasm-pack)
 * - wheel:          /wheels/*.whl (repo dist/*.whl from build_slim_wheel)
 */
function contentTypeFor(filePath: string): string {
  if (filePath.endsWith(".js") || filePath.endsWith(".mjs")) {
    return "application/javascript; charset=utf-8";
  }
  if (filePath.endsWith(".wasm")) return "application/wasm";
  if (filePath.endsWith(".json")) return "application/json";
  return "application/octet-stream";
}

function tryServeFile(res: Connect.ServerResponse, filePath: string): boolean {
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    return false;
  }
  res.setHeader("Content-Type", contentTypeFor(filePath));
  fs.createReadStream(filePath).pipe(res);
  return true;
}

function servePackagingAndWheels(): Plugin {
  return {
    name: "serve-packaging-and-wheels",
    configureServer(server) {
      const middleware: Connect.NextHandleFunction = (req, res, next) => {
        const rawUrl = req.url ?? "";
        const pathname = rawUrl.split("?")[0] ?? "";

        if (pathname.startsWith("/packaging/pyodide/")) {
          const rel = pathname.slice("/packaging/pyodide/".length);
          if (!rel || rel.includes("..")) {
            next();
            return;
          }
          if (tryServeFile(res, path.join(packagingPyodideDir, rel))) return;
          next();
          return;
        }

        if (pathname.startsWith("/packaging/wasm/")) {
          const rel = pathname.slice("/packaging/wasm/".length);
          if (!rel || rel.includes("..")) {
            next();
            return;
          }
          if (tryServeFile(res, path.join(packagingWasmDir, rel))) return;
          next();
          return;
        }

        if (pathname.startsWith("/wasm/")) {
          const rel = pathname.slice("/wasm/".length);
          if (!rel || rel.includes("..")) {
            next();
            return;
          }
          if (tryServeFile(res, path.join(wasmPkgDir, rel))) return;
          next();
          return;
        }

        if (pathname.startsWith("/wheels/")) {
          const rel = pathname.slice("/wheels/".length);
          if (!rel || rel.includes("..") || !rel.endsWith(".whl")) {
            next();
            return;
          }
          if (tryServeFile(res, path.join(slimWheelDir, rel))) return;
          next();
          return;
        }

        next();
      };
      server.middlewares.use(middleware);
    },
  };
}

export default defineConfig({
  root: ".",
  plugins: [react(), servePackagingAndWheels()],
  server: {
    port: 5173,
    open: false,
    fs: {
      // Allow Vite to read packaging/ + dist/ outside web/ when needed.
      allow: [repoRoot],
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "scripts/smoke-autopilot-mock.ts"],
    setupFiles: ["./src/testSetup.ts"],
  },
});
