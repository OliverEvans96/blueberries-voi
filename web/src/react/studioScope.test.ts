/**
 * T-142: studio mount de-globalized for Astro embed.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { SECTION_STORAGE_KEY } from "../sections";
import { SHOW_TRUTH_STORAGE_KEY } from "../showTruth";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP_TS = join(HERE, "../App.tsx");
const STUDIO_LOGIC_TS = join(HERE, "studioLogic.ts");
const STUDIO_PROVIDER_TS = join(HERE, "StudioProvider.tsx");
const STUDIO_LAYOUT_TS = join(HERE, "StudioLayout.tsx");
const REFERENCE_DRAWER_TS = join(HERE, "ReferenceDrawer.tsx");
const STUDIO_ADAPTER_TS = join(HERE, "../engine/studioAdapter.ts");

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("T-142 studio mount scoping", () => {
  const appSrc = stripComments(readFileSync(APP_TS, "utf8"));
  const logicSrc = stripComments(readFileSync(STUDIO_LOGIC_TS, "utf8"));
  const providerSrc = stripComments(readFileSync(STUDIO_PROVIDER_TS, "utf8"));
  const layoutSrc = stripComments(readFileSync(STUDIO_LAYOUT_TS, "utf8"));
  const drawerSrc = stripComments(readFileSync(REFERENCE_DRAWER_TS, "utf8"));
  const adapterSrc = stripComments(readFileSync(STUDIO_ADAPTER_TS, "utf8"));

  it("studioLogic.ts queries DOM via app root, not document", () => {
    expect(logicSrc).toMatch(/app\.querySelector/);
    expect(logicSrc).not.toMatch(/document\.querySelector/);
    expect(logicSrc).toMatch(/app\.addEventListener\("keydown"/);
    expect(logicSrc).not.toMatch(/window\.addEventListener\("keydown"/);
    expect(logicSrc).toMatch(/app\.removeEventListener\("keydown"/);
  });

  it("studioLogic.ts mounts day-inspector portal under #day-inspector-host", () => {
    expect(logicSrc).toMatch(/#day-inspector-host/);
    expect(logicSrc).not.toMatch(/app\.appendChild\(dayInspectorPortal\)/);
    expect(logicSrc).not.toMatch(/document\.body\.appendChild\(dayInspectorPortal\)/);
  });

  it("StudioProvider accepts optional containerRef for embed mounts", () => {
    expect(providerSrc).toMatch(/containerRef\?: RefObject/);
    expect(providerSrc).toMatch(/containerRef\?\.current \?\? document\.getElementById\("app"\)/);
  });

  it("App.tsx passes containerRef to StudioProvider (T-160)", () => {
    expect(appSrc).toMatch(/useRef<HTMLDivElement>/);
    expect(appSrc).toMatch(/<StudioProvider containerRef=\{containerRef\}>/);
  });

  it("TuningDrawer portals into scoped host under .bv-studio", () => {
    expect(drawerSrc).toMatch(/portalContainerRef/);
    expect(drawerSrc).not.toMatch(/createPortal\([\s\S]*document\.body/);
    expect(layoutSrc).toMatch(/bv-studio-portal-root/);
    expect(layoutSrc).toMatch(/reference-drawer-host/);
    expect(layoutSrc).toMatch(/day-inspector-host/);
  });

  it("TuningDrawer host is scoped under .bv-studio portal root", () => {
    expect(layoutSrc).toMatch(/tuning-drawer-host/);
  });

  it("localStorage keys are namespaced under bv-studio:", () => {
    expect(SECTION_STORAGE_KEY).toBe("bv-studio:section");
    expect(SHOW_TRUTH_STORAGE_KEY).toBe("bv-studio:show-truth");
  });

  it("reportStudioAdapterError can resolve #studio-error from optional root", () => {
    expect(adapterSrc).toMatch(/root\?\.querySelector\("#studio-error"\)/);
  });
});
