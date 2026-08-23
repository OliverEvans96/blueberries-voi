/**
 * Issue #5: embed.js must not bundle react-dom — host provides peer deps.
 * Requires `pnpm build:lib` (or vite lib build) before this file runs.
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const WEB_ROOT = fileURLToPath(new URL(".", import.meta.url));
const EMBED_JS = join(WEB_ROOT, "../dist-lib/embed.js");

describe("embed lib bundle", () => {
  it("keeps react peers external instead of bundling react-dom/client", () => {
    if (!existsSync(EMBED_JS)) {
      throw new Error("dist-lib/embed.js missing — run pnpm build:lib first");
    }
    const js = readFileSync(EMBED_JS, "utf8");

    expect(js).not.toContain("react-dom-client.production.js");
    expect(js).not.toContain("Incompatible React versions");
    expect(js).toMatch(/from\s+["']react-dom\/client["']/);
    expect(js).toMatch(/from\s+["']react-dom["']/);
    expect(js).toMatch(/from\s+["']react["']/);
    expect(js).toMatch(/from\s+["']react\/jsx-runtime["']/);
  });
});
