/**
 * T-153: Events pane CSS lives only in eventsPane.css (not cockpitGrid.css).
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const EVENTS_PANE_CSS = join(HERE, "eventsPane.css");
const COCKPIT_GRID_CSS = join(HERE, "cockpitGrid.css");

describe("T-153 events pane CSS ownership", () => {
  const eventsCss = readFileSync(EVENTS_PANE_CSS, "utf8");
  const cockpitCss = readFileSync(COCKPIT_GRID_CSS, "utf8");

  it("defines events typography in eventsPane.css", () => {
    expect(eventsCss).toMatch(/\.events-day-heading[\s\S]*font-size:\s*1\.0[58]rem/);
    expect(eventsCss).toMatch(/\.events-col-title[\s\S]*text-transform:\s*uppercase/);
    expect(eventsCss).toMatch(/\.events-table-lot[\s\S]*font-size:\s*0\.72rem/);
    expect(eventsCss).toMatch(/\.events-table-total[\s\S]*font-weight:\s*700/);
  });

  it("does not duplicate events rules in cockpitGrid.css", () => {
    expect(cockpitCss).not.toMatch(/\.events-day-heading/);
    expect(cockpitCss).not.toMatch(/\.events-col-title/);
    expect(cockpitCss).not.toMatch(/\.events-table/);
    expect(cockpitCss).not.toMatch(/\.events-columns/);
  });

  it("keeps P&L totals second-line spacing in cockpitGrid.css", () => {
    expect(cockpitCss).toMatch(/\.pnl-totals-line \+ \.pnl-totals-line/);
  });

  it("stacks P&L total lines vertically in styles.css", () => {
    const stylesCss = readFileSync(join(HERE, "..", "styles.css"), "utf8");
    expect(stylesCss).toMatch(/\.pnl-totals[\s\S]*flex-direction:\s*column/);
  });
});
