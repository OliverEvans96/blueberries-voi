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

  it("chart-stack order: Units sold, sales, Missed sales, stockout, Lots, history, Units spoiled, spoil", () => {
    const storeSection = layoutSrc.match(
      /id="linked-charts">([\s\S]*?)<\/main>/,
    )?.[1];
    expect(storeSection, "expected #linked-charts section in StudioLayout.tsx").toBeDefined();

    const sold = storeSection!.indexOf("Units sold");
    const salesId = storeSection!.indexOf('id="chart-sales"');
    const missed = storeSection!.indexOf("Missed sales");
    const stockoutId = storeSection!.indexOf('id="chart-stockout"');
    const lots = storeSection!.indexOf("Lots · day × age");
    const historyId = storeSection!.indexOf('id="chart-history"');
    const spoiled = storeSection!.indexOf("Units spoiled");
    const spoilId = storeSection!.indexOf('id="chart-spoil"');

    expect(sold).toBeGreaterThanOrEqual(0);
    expect(salesId).toBeGreaterThan(sold);
    expect(missed).toBeGreaterThan(salesId);
    expect(stockoutId).toBeGreaterThan(missed);
    expect(lots).toBeGreaterThan(stockoutId);
    expect(historyId).toBeGreaterThan(lots);
    expect(spoiled).toBeGreaterThan(historyId);
    expect(spoilId).toBeGreaterThan(spoiled);
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
    expect(fn).toMatch(/setMarginalHover\(\s*els\.spoil/);
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
    expect(fn).toMatch(
      /renderMarginal\(\s*els\.spoil[\s\S]*,\s*"spoilage"/,
    );
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
