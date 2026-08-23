import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import dts from "vite-plugin-dts";
import { readWebPackageVersion } from "./vitePackageVersion";

const WEB_ROOT = fileURLToPath(new URL(".", import.meta.url));
const studioVersion = readWebPackageVersion();

/** Peer deps must resolve from the host app, not ship inside embed.js (issue #5). */
function isReactPeerExternal(id: string): boolean {
  return (
    id === "react" ||
    id === "react-dom" ||
    id.startsWith("react/") ||
    id.startsWith("react-dom/")
  );
}

/** T-145: publishable `@oliverevans96/blueberries-voi-studio` library build. */
export default defineConfig({
  root: ".",
  base: "./",
  define: {
    "import.meta.env.VITE_STUDIO_VERSION": JSON.stringify(studioVersion),
  },
  plugins: [
    react(),
    dts({
      entryRoot: "src",
      tsconfigPath: "./tsconfig.lib.json",
      rollupTypes: true,
      outDir: "dist-lib",
      exclude: ["src/**/*.test.ts", "src/main.tsx", "src/main.ts"],
      skipDiagnostics: true,
    }),
  ],
  assetsInclude: ["**/*.wasm"],
  worker: {
    format: "es",
  },
  publicDir: false,
  build: {
    lib: {
      entry: resolve(WEB_ROOT, "src/embed.ts"),
      formats: ["es"],
      fileName: "embed",
    },
    outDir: "dist-lib",
    emptyOutDir: true,
    cssCodeSplit: false,
    copyPublicDir: false,
    rollupOptions: {
      external: isReactPeerExternal,
      output: {
        assetFileNames(assetInfo) {
          if (assetInfo.names.some((n) => n.endsWith(".css"))) {
            return "styles.css";
          }
          return "assets/[name][extname]";
        },
      },
    },
  },
});
