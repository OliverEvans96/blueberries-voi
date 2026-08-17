/**
 * T-116 RED: missed-sales store chart — source contracts on StudioLayout +
 * studioLogic + styles.css (stack order, caption, legend chip, hover, shared yMax).
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const LAYOUT_TS = join(HERE, "react/StudioLayout.tsx");
const LOGIC_TS = join(HERE, "react/studioLogic.ts");
const STYLES_CSS = join(HERE, "styles.css");
const SALES_DEMAND_TS = join(HERE, "charts/salesDemand.ts");

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("Store chart-stack missed sales (T-116)", () => {
  const layoutSrc = stripComments(readFileSync(LAYOUT_TS, "utf8"));
  const logicSrc = stripComments(readFileSync(LOGIC_TS, "utf8"));

  it("cockpit layout preserves missed-sales captions and chart hosts (T-127)", () => {
    expect(layoutSrc).toMatch(/Missed sales/);
    expect(layoutSrc).toMatch(/id="chart-stockout"/);
    expect(layoutSrc).toMatch(/id="chart-history"/);
    expect(layoutSrc).toMatch(/id="chart-spoil"/);
    const sold = layoutSrc.indexOf("Units sold");
    const salesId = layoutSrc.indexOf('id="chart-sales"');
    const missed = layoutSrc.indexOf("Missed sales");
    const stockoutId = layoutSrc.indexOf('id="chart-stockout"');
    expect(sold).toBeGreaterThanOrEqual(0);
    expect(salesId).toBeGreaterThan(sold);
    expect(missed).toBeGreaterThan(salesId);
    expect(stockoutId).toBeGreaterThan(missed);
  });

  it('caption text is exactly "Missed sales"', () => {
    expect(layoutSrc).toMatch(
      /className="chart-caption">Missed sales<\/div>/,
    );
    expect(layoutSrc).not.toMatch(
      /className="chart-caption">Stockout<\/div>/,
    );
  });

  it("store legend includes chip-missed alongside Sales / Lots / Spoilage", () => {
    const legend = layoutSrc.match(
      /className="legend-inline store-legend">([\s\S]*?)<\/div>/,
    )?.[1];
    expect(legend, "expected store-legend").toBeDefined();
    expect(legend).toMatch(/chip-sales/);
    expect(legend).toMatch(/>Sales</);
    expect(legend).toMatch(/chip-lots/);
    expect(legend).toMatch(/chip-spoil/);
    expect(legend).toMatch(/Spoilage/);
    expect(legend).toMatch(/chip-missed/);
    expect(legend).toMatch(/>Missed</);
  });

  it("els.stockout binds #chart-stockout", () => {
    expect(logicSrc).toMatch(/stockout:\s*document\.querySelector\(\s*"#chart-stockout"/);
  });

  it("applyHoverStyles calls setMarginalHover(els.stockout, day)", () => {
    const fn = logicSrc.match(
      /function applyHoverStyles\s*\(\s*day[\s\S]*?\n\}/,
    )?.[0];
    expect(fn, "expected applyHoverStyles").toBeDefined();
    expect(fn).toMatch(/setMarginalHover\(\s*els\.sales/);
    expect(fn).toMatch(/setWasteBarsHover\(\s*els\.spoil/);
    expect(fn).toMatch(/setMarginalHover\(\s*els\.stockout\s*,\s*day\s*\)/);
  });

  it("renderStore shares marginalYMax / yMax for sales and stockout", () => {
    const fn = logicSrc.match(/function renderStore\s*\(\s*\)\s*\{[\s\S]*?\n\}/)?.[0];
    expect(fn, "expected renderStore").toBeDefined();
    expect(fn).toMatch(/marginalYMax\s*\(/);
    expect(fn).toMatch(/yMax/);
    expect(fn).toMatch(
      /renderMarginal\(\s*els\.sales[\s\S]*,\s*"sales"[\s\S]*yMax/,
    );
    expect(fn).toMatch(
      /renderMarginal\(\s*els\.stockout[\s\S]*,\s*"stockout"[\s\S]*yMax/,
    );
    expect(fn).toMatch(/renderWasteBars\(\s*els\.spoil/);
  });

  it("Demand Sales vs demand / chart-sales-demand still a line chart module", () => {
    expect(layoutSrc).toMatch(/Sales vs demand/);
    expect(layoutSrc).toMatch(/id="chart-sales-demand"/);
    expect(logicSrc).toMatch(/renderSalesDemand\(\s*els\.salesDemand/);
    expect(existsSync(SALES_DEMAND_TS)).toBe(true);
    const sd = stripComments(readFileSync(SALES_DEMAND_TS, "utf8"));
    expect(sd).toMatch(/export\s+function\s+renderSalesDemand/);
    expect(sd).toMatch(/lineSales|lineDemand/);
    expect(sd).toMatch(/sales-demand-gap/);
    expect(sd).not.toMatch(/bar--stockout/);
  });
});

describe("Cockpit grid responsive shell (T-127 AC-layout)", () => {
  const layoutSrc = stripComments(readFileSync(LAYOUT_TS, "utf8"));
  const css = readFileSync(STYLES_CSS, "utf8");

  it("cockpitGrid.css or styles.css defines cockpit-grid breakpoints at 1100px and 720px", () => {
    const cockpitCssPath = join(HERE, "styles/cockpitGrid.css");
    const cockpitCss = existsSync(cockpitCssPath)
      ? readFileSync(cockpitCssPath, "utf8")
      : css;
    expect(cockpitCss).toMatch(/cockpit-grid/);
    expect(cockpitCss).toMatch(/1100px/);
    expect(cockpitCss).toMatch(/720px/);
  });

  it(".shell.studio scroll not clipped by cockpit rows at narrow widths", () => {
    const cockpitCssPath = join(HERE, "styles/cockpitGrid.css");
    const cockpitCss = existsSync(cockpitCssPath)
      ? readFileSync(cockpitCssPath, "utf8")
      : css;
    expect(cockpitCss).toMatch(/overflow/);
    expect(layoutSrc).toMatch(/cockpit-grid/);
  });
});

describe("Missed-sales CSS tokens (T-116)", () => {
  const css = readFileSync(STYLES_CSS, "utf8");

  it("defines --missed and --missed-strong", () => {
    expect(css).toMatch(/--missed\s*:/);
    expect(css).toMatch(/--missed-strong\s*:/);
  });

  it(".bar--stockout uses --missed; active uses --missed-strong", () => {
    expect(css).toMatch(
      /\.bar--stockout\s*\{[\s\S]*?fill:\s*var\(\s*--missed\s*\)/,
    );
    expect(css).toMatch(
      /\.bar--stockout\.bar--active\s*\{[\s\S]*?fill:\s*var\(\s*--missed-strong\s*\)/,
    );
  });

  it("defines .chip-missed", () => {
    expect(css).toMatch(/\.chip-missed\s*\{/);
  });
});
