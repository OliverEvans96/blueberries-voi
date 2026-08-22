#!/usr/bin/env node
/**
 * Post-process dist-lib after `vite build --mode lib`:
 * - copy self-hosted fonts next to styles.css
 * - rewrite absolute /fonts/ URLs for tarball consumers
 */
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(HERE, "..");
const DIST = join(WEB_ROOT, "dist-lib");
const STYLES = join(DIST, "styles.css");
const FONTS_SRC = join(WEB_ROOT, "public/fonts");
const FONTS_DST = join(DIST, "fonts");

if (!existsSync(STYLES)) {
  console.error("copy-lib-assets: missing dist-lib/styles.css — run build:lib first");
  process.exit(1);
}

mkdirSync(FONTS_DST, { recursive: true });
cpSync(FONTS_SRC, FONTS_DST, { recursive: true });

const css = readFileSync(STYLES, "utf8");
writeFileSync(STYLES, css.replaceAll('url("/fonts/', 'url("./fonts/'));

const embedJs = join(DIST, "embed.js");
if (existsSync(embedJs)) {
  const js = readFileSync(embedJs, "utf8");
  writeFileSync(
    embedJs,
    js.replaceAll('"/assets/wasmWorker-', '"./assets/wasmWorker-'),
  );
}

console.log("copy-lib-assets: fonts copied and CSS/worker URLs rewritten for tarball consumers");
