/**
 * T-143: studio CSS scoped under .bv-studio + self-hosted fonts.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(HERE, "../..");
const STYLES_CSS = join(HERE, "../styles.css");
const INDEX_HTML = join(WEB_ROOT, "index.html");
const STUDIO_LAYOUT_TS = join(HERE, "../react/StudioLayout.tsx");
const FONTS_DIR = join(WEB_ROOT, "public/fonts");

describe("T-143 studio CSS scoping", () => {
  const stylesCss = readFileSync(STYLES_CSS, "utf8");
  const indexHtml = readFileSync(INDEX_HTML, "utf8");
  const layoutSrc = readFileSync(STUDIO_LAYOUT_TS, "utf8");

  it("wraps studio UI in .bv-studio root class", () => {
    expect(layoutSrc).toMatch(/className="bv-studio"/);
  });

  it("scopes design tokens and page chrome under .bv-studio", () => {
    expect(stylesCss).toMatch(/\.bv-studio\s*\{[\s\S]*--bg:/);
    expect(stylesCss).not.toMatch(/^:root\s*\{/m);
    expect(stylesCss).not.toMatch(/^html,\s*\nbody\s*\{/m);
    expect(stylesCss).toMatch(/\.bv-studio,\s*\n\.bv-studio \*,/);
  });

  it("does not load Google Fonts from index.html", () => {
    expect(indexHtml).not.toMatch(/fonts\.googleapis\.com/);
    expect(indexHtml).not.toMatch(/fonts\.gstatic\.com/);
  });

  it("self-hosts Fraunces and IBM Plex Sans via @font-face", () => {
    expect(stylesCss).toMatch(/@font-face[\s\S]*Fraunces[\s\S]*\/fonts\/fraunces-latin\.woff2/);
    expect(stylesCss).toMatch(
      /@font-face[\s\S]*IBM Plex Sans[\s\S]*\/fonts\/ibm-plex-sans-latin-400\.woff2/,
    );
    expect(existsSync(join(FONTS_DIR, "fraunces-latin.woff2"))).toBe(true);
    expect(existsSync(join(FONTS_DIR, "ibm-plex-sans-latin-400.woff2"))).toBe(true);
  });
});
