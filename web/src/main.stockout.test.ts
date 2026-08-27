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
const PNL_TOTALS_TS = join(HERE, "charts/pnlTotals.ts");

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("Store chart-stack missed sales (T-116)", () => {
  const layoutSrc = stripComments(readFileSync(LAYOUT_TS, "utf8"));
  const logicSrc = stripComments(readFileSync(LOGIC_TS, "utf8"));

  it("cockpit layout preserves chart-stockout host for hover wiring (T-128 hidden)", () => {
    expect(layoutSrc).toMatch(/id="chart-stockout"/);
    expect(layoutSrc).toMatch(/id="chart-history"/);
    expect(layoutSrc).toMatch(/id="chart-controller-orders"/);
    expect(layoutSrc).toMatch(/id="chart-spoil"/);
    expect(layoutSrc).toMatch(/visually-hidden/);
    expect(layoutSrc).toMatch(/ariaLabel="Missed sales by day"/);
  });

  it("missed-sales chart is not in visible Today strip (T-128)", () => {
    expect(layoutSrc).not.toMatch(
      /className="chart-caption">Missed sales<\/div>/,
    );
    expect(layoutSrc).not.toMatch(
      /className="chart-caption">Stockout<\/div>/,
    );
  });

  it("cockpit layout v6 keeps hover hosts in visually-hidden region (T-148)", () => {
    expect(layoutSrc).not.toMatch(/className="legend-inline store-legend"/);
    expect(layoutSrc).toMatch(/visually-hidden/);
    expect(layoutSrc).toMatch(/id="chart-sales"/);
    expect(layoutSrc).toMatch(/id="chart-stockout"/);
  });

  it("els.stockout binds #chart-stockout", () => {
    expect(logicSrc).toMatch(
      /get stockout\(\):\s*HTMLElement[\s\S]*?q<HTMLElement>\("#chart-stockout"\)/,
    );
  });

  it("beliefFreshnessHoverFocus maps spoilage hover source to spoiled focus", () => {
    const fn = logicSrc.match(
      /function beliefFreshnessHoverFocus\s*\([\s\S]*?\n\}/,
    )?.[0];
    expect(fn, "expected beliefFreshnessHoverFocus").toBeDefined();
    expect(fn).toMatch(/source\s*===\s*"spoilage"/);
    expect(fn).toMatch(/return\s+"spoiled"/);
    expect(fn).toMatch(/source\s*===\s*"sales"/);
    expect(fn).toMatch(/return\s+"sales"/);
  });

  it("applyHoverStyles passes beliefFreshnessHoverFocus source to freshness chart", () => {
    const fn = logicSrc.match(
      /function applyHoverStyles\s*\(\s*day[\s\S]*?\n\}/,
    )?.[0];
    expect(fn).toMatch(/beliefFreshnessHoverFocus\s*\(\s*source\s*\)/);
  });

  it("applyHoverStyles calls setMarginalHover(els.stockout, day)", () => {
    const fn = logicSrc.match(
      /function applyHoverStyles\s*\(\s*day[\s\S]*?\n\}/,
    )?.[0];
    expect(fn, "expected applyHoverStyles").toBeDefined();
    expect(fn).toMatch(/setMarginalHover\(\s*els\.sales/);
    expect(fn).toMatch(/setControllerOrdersHover\(\s*els\.controllerOrders/);
    expect(fn).toMatch(/setWasteBarsHover\(\s*els\.spoil/);
    expect(fn).toMatch(/setPnLHover\(\s*els\.pnlEconomics/);
    expect(fn).toMatch(/setFreshnessCompositionHover\(\s*els\.ageComp/);
    expect(fn).toMatch(/setDemandForecastHover\(\s*els\.demandForecast/);
    expect(fn).toMatch(/setMarginalHover\(\s*els\.stockout\s*,\s*day\s*\)/);
  });

  it("renderRunStripCharts renders separate orders and spoilage in metrics column", () => {
    expect(logicSrc).toMatch(/renderControllerOrders\(\s*els\.controllerOrders/);
    expect(logicSrc).toMatch(/renderWasteBars\(\s*els\.spoil/);
    expect(logicSrc).not.toMatch(/renderOrdersSpoilageGroupedBars/);
  });

  it("pnl totals host renders missed sales and waste in second line", () => {
    const pnl = stripComments(readFileSync(PNL_TOTALS_TS, "utf8"));
    expect(pnl).toMatch(/computeImpactTotals/);
    expect(pnl).toMatch(/Missed sales/);
    expect(pnl).toMatch(/Waste/);
    expect(layoutSrc).not.toMatch(/impact-missed-host/);
    expect(logicSrc).not.toMatch(/ImpactStat/);
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
  });

  it("Demand Sales vs demand / chart-sales-demand still a line chart module", () => {
    expect(layoutSrc).toMatch(/Sales &amp; demand|Sales & demand/);
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
