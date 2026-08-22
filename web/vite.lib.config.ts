import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import dts from "vite-plugin-dts";

const WEB_ROOT = fileURLToPath(new URL(".", import.meta.url));

/** T-145: publishable `@oliverevans96/blueberries-voi-studio` library build. */
export default defineConfig({
  root: ".",
  base: "./",
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
      external: ["react", "react-dom", "react/jsx-runtime"],
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
