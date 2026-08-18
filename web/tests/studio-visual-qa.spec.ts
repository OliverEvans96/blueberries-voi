import { test, expect, type Page } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = path.join(__dirname, "__screenshots__");
fs.mkdirSync(SHOT_DIR, { recursive: true });

function shotPath(name: string): string {
  return path.join(SHOT_DIR, `${name}.png`);
}

async function waitForEngine(page: Page) {
  await page.waitForSelector(".cockpit-grid", { state: "visible" });
  // Wait for the engine to leave "loading" status so charts have real data.
  await page
    .waitForFunction(
      () => document.querySelector("#engine-status")?.getAttribute("data-status") !== "loading",
      { timeout: 15000 },
    )
    .catch(() => {
      /* fall through — some builds may not toggle this attribute */
    });
  await page.waitForTimeout(300);
}

/** Day 0 has no belief/lot history yet — advance a few days so charts have real data. */
async function advanceDays(page: Page, n: number) {
  for (let i = 0; i < n; i++) {
    await page.locator("#btn-advance").click();
    await page.waitForTimeout(400);
  }
}

test.describe("T-127 round 2 — thorough visual QA", () => {
  test.beforeEach(async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(`console.error: ${msg.text()}`);
    });
    (page as unknown as { __errors: string[] }).__errors = errors;
  });

  test.afterEach(async ({ page }) => {
    const errors = (page as unknown as { __errors: string[] }).__errors ?? [];
    if (errors.length > 0) {
      console.log("Console/page errors observed:\n" + errors.join("\n"));
    }
  });

  test("1: no Play tab — Primary and Secondary always visible", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await expect(page.locator(".cockpit-pane--primary")).toBeVisible();
    await expect(page.locator(".cockpit-pane--secondary")).toBeVisible();
    // No leftover "Play" tab/chrome mount point, and no chapter/section literally named "Play".
    await expect(page.locator("#play-chrome")).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "Play", exact: true })).toHaveCount(0);
    await page.screenshot({ path: shotPath("01-full-page-initial"), fullPage: true });
  });

  test("2: primary pane 3-chart stack + truth overlay toggle", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await advanceDays(page, 3); // day 0 has no belief/lot history to plot yet
    const primary = page.locator(".cockpit-pane--primary");
    await expect(primary).toContainText("Freshness × time");
    await expect(primary).toContainText("Sales vs demand");
    await expect(primary).toContainText("Units spoiled");
    await expect(page.locator("#chart-history")).toBeVisible();
    await expect(page.locator("#chart-sales-demand")).toBeVisible();
    await expect(page.locator("#chart-spoil")).toBeVisible();

    // Truth overlay defaults ON for the cockpit grid (intentional, see showTruth.ts).
    const truthToggle = page.locator(".truth-toggle");
    await expect(truthToggle).toHaveAttribute("aria-checked", "true");
    await primary.screenshot({ path: shotPath("02b-primary-truth-on") });
    const dotsOn = await page.locator("#chart-history circle").count();
    console.log(`chart-history truth-overlay circle count (truth ON): ${dotsOn}`);
    expect(dotsOn).toBeGreaterThan(0);

    await truthToggle.click();
    await expect(truthToggle).toHaveAttribute("aria-checked", "false");
    await page.waitForTimeout(200);
    await primary.screenshot({ path: shotPath("02a-primary-truth-off") });
    const dotsOff = await page.locator("#chart-history circle").count();
    console.log(`chart-history truth-overlay circle count (truth OFF): ${dotsOff}`);
    expect(dotsOff).toBe(0);

    // Stockout gap area should exist in the sales-demand chart svg.
    const salesDemandSvgHtml = await page.locator("#chart-sales-demand svg").innerHTML();
    fs.writeFileSync(path.join(SHOT_DIR, "chart-sales-demand.svg.html"), salesDemandSvgHtml);

    // Spoil bars.
    const spoilBars = await page.locator("#chart-spoil rect").count();
    console.log(`chart-spoil rect count: ${spoilBars}`);

    await page.locator("#chart-history").screenshot({
      path: shotPath("chart-history-after-3-days"),
    });
    const chartLayout = await page.evaluate(() => {
      const svg = document.querySelector("#chart-history svg.chart-svg");
      const clip = document.querySelector("#chart-history clipPath");
      const colorbar = document.querySelector(
        "#chart-history .belief-freshness-colorbar",
      );
      const yLabel = document.querySelector("#chart-history .axis-label");
      return {
        marginLeft: svg?.getAttribute("data-margin-left"),
        marginRight: svg?.getAttribute("data-margin-right"),
        hasClip: clip != null,
        hasColorbar: colorbar != null,
        yLabelY: yLabel?.getAttribute("y"),
        unitsLabel: document.querySelector(
          "#chart-history .belief-freshness-colorbar-label",
        )?.textContent,
      };
    });
    console.log("chart-history layout:", JSON.stringify(chartLayout));
    expect(chartLayout.hasClip).toBe(true);
    expect(chartLayout.hasColorbar).toBe(true);
    expect(chartLayout.unitsLabel).toBe("Units");
    expect(chartLayout.marginLeft).toBe("48");
    expect(chartLayout.marginRight).toBe("48");
  });

  test("3: secondary pane — freshness histogram only, with truth bars", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    // 2 days (not 3): enough for a delivery to land, before random daily demand
    // has a chance to fully sell through the lot in this stochastic sim.
    await advanceDays(page, 2);
    const secondary = page.locator(".cockpit-pane--secondary");
    await expect(secondary).toContainText("Stacked freshness histogram");
    await expect(page.locator("#chart-belief-lg")).toBeVisible();
    // Truth defaults ON for the cockpit grid.
    await secondary.screenshot({ path: shotPath("03a-secondary-truth-on") });

    const bgMarginal = page.locator("#chart-belief-age-marginal");
    await expect(bgMarginal).toBeHidden();

    const truthBarCountOn = await page.locator("#chart-belief-lg .truth-bar").count();
    console.log(`chart-belief-lg truth bar count (truth ON): ${truthBarCountOn}`);
    expect(truthBarCountOn).toBeGreaterThan(0);

    const truthToggle = page.locator(".truth-toggle");
    await truthToggle.click();
    await page.waitForTimeout(200);
    await secondary.screenshot({ path: shotPath("03b-secondary-truth-off") });
    const truthBarCountOff = await page.locator("#chart-belief-lg .truth-bar").count();
    console.log(`chart-belief-lg truth bar count (truth OFF): ${truthBarCountOff}`);
    expect(truthBarCountOff).toBe(0);
  });

  test("4: exactly one order-qty control and one advance button", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await expect(page.locator("#order-range")).toHaveCount(1);
    await expect(page.locator("#order-num")).toHaveCount(1);
    await expect(page.locator("#btn-advance")).toHaveCount(1);
    await expect(page.locator("#btn-reset")).toHaveCount(1);
    // No leftover PlayChrome remnants.
    await expect(page.locator("#play-chrome")).toHaveCount(0);
  });

  test("5: tradeoff charts render with real data", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    const rail = page.locator(".tradeoff-charts");
    await expect(rail).toBeVisible();
    await rail.screenshot({ path: shotPath("05-tradeoff-charts") });
    const curvePaths = await page.locator("#tradeoff-curve-host path, #tradeoff-curve-host line").count();
    const histRects = await page.locator("#tradeoff-histogram-host rect").count();
    console.log(`tradeoff-curve-host paths/lines: ${curvePaths}, tradeoff-histogram-host rects: ${histRects}`);
    expect(curvePaths).toBeGreaterThan(0);
    expect(histRects).toBeGreaterThan(0);
  });

  test("6: economics pane — no dead pnl-spark/series, has cumulative chart", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await expect(page.locator("#chart-pnl-spark")).toHaveCount(0);
    await expect(page.locator("#chart-pnl-series")).toHaveCount(0);
    const econ = page.locator("#economics-pane-host");
    await expect(econ).toBeVisible();
    await econ.screenshot({ path: shotPath("06-economics-pane") });
  });

  test("7: events pane changes per observation scenario", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await advanceDays(page, 3);
    const events = page.locator("#events-pane-host");
    await expect(events).toBeVisible();

    for (const scenario of ["P0", "P1", "F1", "F1s", "F2a", "F2"]) {
      await page.locator(`[data-obs="${scenario}"]`).click();
      await page.waitForTimeout(250);
      await events.screenshot({ path: shotPath(`07-events-${scenario}`) });
      const text = await events.innerText();
      fs.writeFileSync(path.join(SHOT_DIR, `07-events-${scenario}.txt`), text);
    }
  });

  test("8: tuning dock — all tabs reveal correct content", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    const dockTab = (section: string) =>
      page.locator(`.tuning-dock-tabs [data-section="${section}"]`);
    const dockContent = (section: string) =>
      page.locator(`.section-controls > [data-section="${section}"]`);

    for (const section of ["demand", "observation", "arrival", "physics", "logistics", "autopilot"]) {
      const tab = dockTab(section);
      await expect(tab).toBeVisible();
      await tab.click();
      await page.waitForTimeout(200);
      await expect(tab).toHaveAttribute("aria-selected", "true");
      await expect(dockContent(section)).toBeVisible();
      const dock = page.locator(".tuning-dock");
      await dock.screenshot({ path: shotPath(`08-tuning-${section}`) });
    }

    // Arrival scenario-dim check for f2a_transit_sd / sensor_sigma
    await page.locator('[data-obs="P0"]').click();
    await page.waitForTimeout(150);
    await dockTab("arrival").click();
    await page.waitForTimeout(150);
    await page.locator(".cockpit-row--tuning").screenshot({ path: shotPath("08b-arrival-P0") });

    await page.locator('[data-obs="F2a"]').click();
    await page.waitForTimeout(150);
    await dockTab("arrival").click();
    await page.waitForTimeout(150);
    await page.locator(".cockpit-row--tuning").screenshot({ path: shotPath("08c-arrival-F2a") });

    await page.locator('[data-obs="F2"]').click();
    await page.waitForTimeout(150);
    await dockTab("arrival").click();
    await page.waitForTimeout(150);
    await page.locator(".cockpit-row--tuning").screenshot({ path: shotPath("08d-arrival-F2") });

    // Autopilot alpha/rho drag pad
    await dockTab("autopilot").click();
    await page.waitForTimeout(150);
    const pad = page.locator("#alpha-rho-pad, [data-testid='alpha-rho-pad']").first();
    const padCount = await pad.count();
    console.log(`alpha-rho pad elements found: ${padCount}`);
    if (padCount > 0) {
      const box = await pad.boundingBox();
      if (box) {
        await page.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.2);
        await page.mouse.down();
        await page.mouse.move(box.x + box.width * 0.8, box.y + box.height * 0.8, { steps: 5 });
        await page.mouse.up();
        await page.waitForTimeout(150);
      }
    }
    await page.locator(".tuning-dock").screenshot({ path: shotPath("08e-autopilot-after-drag") });
  });

  test("9: general polish — layout at two viewports, console errors", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await waitForEngine(page);
    await advanceDays(page, 3);
    await page.screenshot({ path: shotPath("09a-desktop-1440"), fullPage: true });

    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForTimeout(200);
    await page.screenshot({ path: shotPath("09b-narrow-1024"), fullPage: true });

    const errors = (page as unknown as { __errors: string[] }).__errors ?? [];
    fs.writeFileSync(path.join(SHOT_DIR, "09-console-errors.txt"), errors.join("\n") || "(none)");
  });
});
