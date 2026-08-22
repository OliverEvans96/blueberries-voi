import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/** Minimal consumer smoke for `@oliverevans96/blueberries-voi-studio` (T-147). */
export default defineConfig({
  plugins: [react()],
  server: { port: 5174 },
  build: { outDir: "dist" },
});
