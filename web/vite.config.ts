import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Connect, Plugin } from "vite";
import { defineConfig } from "vitest/config";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const packagingPyodideDir = path.join(repoRoot, "packaging", "pyodide");
/** Local slim wheels from ``uv run python scripts/build_slim_wheel.py`` (repo dist/). */
const slimWheelDir = path.join(repoRoot, "dist");

/**
 * T-072 / ADR 0108 local dual-mode URL contract:
 * - worker:  /packaging/pyodide/worker.js  (repo packaging/pyodide/)
 * - wheel:   /wheels/*.whl                (repo dist/*.whl from build_slim_wheel)
 */
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
          const filePath = path.join(packagingPyodideDir, rel);
          if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
            next();
            return;
          }
          res.setHeader(
            "Content-Type",
            filePath.endsWith(".js")
              ? "application/javascript; charset=utf-8"
              : "application/octet-stream",
          );
          fs.createReadStream(filePath).pipe(res);
          return;
        }

        if (pathname.startsWith("/wheels/")) {
          const rel = pathname.slice("/wheels/".length);
          if (!rel || rel.includes("..") || !rel.endsWith(".whl")) {
            next();
            return;
          }
          const filePath = path.join(slimWheelDir, rel);
          if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
            next();
            return;
          }
          res.setHeader("Content-Type", "application/octet-stream");
          fs.createReadStream(filePath).pipe(res);
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
  plugins: [servePackagingAndWheels()],
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
    include: ["src/**/*.test.ts"],
  },
});
