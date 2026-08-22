/**
 * Regression: .obs-controls-pane shares .panel; padding shorthand must not zero inline padding.
 *
 * jsdom does not apply imported stylesheets to getComputedStyle, so we assert on the
 * authored rule (same pattern as studioCssScope.test.ts).
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const OBS_CONTROLS_CSS = join(HERE, "obsControls.css");
const OBS_CONTROLS_PANE_TS = join(HERE, "../react/ObsControlsPane.tsx");

function obsControlsPaneRootRule(): string {
  const css = readFileSync(OBS_CONTROLS_CSS, "utf8");
  const match = css.match(/\.obs-controls-pane\s*\{([^}]+)\}/);
  return match?.[1] ?? "";
}

describe("obsControls.css panel padding", () => {
  it("uses padding-block on .obs-controls-pane so .panel keeps horizontal padding", () => {
    const rootRule = obsControlsPaneRootRule();
    expect(rootRule).toMatch(/padding-block:\s*0\.35rem\s+0\.75rem/);
    expect(rootRule).not.toMatch(/padding:\s*[^;]*\s0\s/);
  });

  it("ObsControlsPane retains .panel class for shared chrome padding", () => {
    const src = readFileSync(OBS_CONTROLS_PANE_TS, "utf8");
    expect(src).toMatch(/className="obs-controls-pane panel"/);
  });
});
