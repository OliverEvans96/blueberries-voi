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

function obsPresetSelect(page: Page) {
  return page.locator(".secondary-chrome #obs-preset-select");
}

async function setObsPreset(page: Page, scenario: string) {
  await obsPresetSelect(page).selectOption(scenario);
  await page.waitForTimeout(250);
}

async function waitForEngine(page: Page) {
  await page.waitForSelector(".cockpit-grid", { state: "visible" });
  await page
    .waitForFunction(
      () => document.querySelector("#engine-status")?.getAttribute("data-status") !== "loading",
      { timeout: 15000 },
    )
    .catch(() => {
      /* fall through */
    });
  await page.waitForTimeout(300);
}

async function advanceDays(page: Page, n: number) {
  for (let i = 0; i < n; i++) {
    await page.locator("#btn-advance").click();
    await page.waitForTimeout(400);
  }
}

test.describe("T-130 layout v5 — visual QA", () => {
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

  test("1: layout v5 — Primary, Secondary chrome, Today center, Events column", async ({
    page,
  }) => {
    await page.goto("/");
    await waitForEngine(page);
    await expect(page.locator(".cockpit-grid[data-layout='v5']")).toBeVisible();
    await expect(page.locator(".cockpit-pane--primary")).toBeVisible();
    await expect(page.locator(".cockpit-pane--secondary")).toBeVisible();
    await expect(page.locator("[data-testid='cockpit-today']")).toBeVisible();
    await expect(page.locator("[data-testid='cockpit-events-column']")).toBeVisible();
    await expect(page.locator("#decision-rail-host")).toHaveCount(0);
    await expect(page.locator("#play-chrome")).toHaveCount(0);
    await page.screenshot({ path: shotPath("01-full-page-initial"), fullPage: true });
  });

  test("2: primary pane 3-chart stack + truth overlay toggle", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await advanceDays(page, 3);
    const primary = page.locator(".cockpit-pane--primary");
    await expect(primary).toContainText("Freshness × time");
    await expect(primary).toContainText("Sales vs demand");
    await expect(primary).toContainText("Units spoiled");
    await expect(page.locator("#chart-history")).toBeVisible();
    await expect(page.locator("#chart-sales-demand")).toBeVisible();
    await expect(page.locator("#chart-spoil")).toBeVisible();

    const truthToggle = page.locator(".secondary-chrome .truth-toggle");
    await expect(truthToggle).toHaveAttribute("aria-checked", "true");
    await primary.screenshot({ path: shotPath("02b-primary-truth-on") });
    const dotsOn = await page.locator("#chart-history circle").count();
    expect(dotsOn).toBeGreaterThan(0);

    await truthToggle.click();
    await expect(truthToggle).toHaveAttribute("aria-checked", "false");
    await page.waitForTimeout(200);
    const dotsOff = await page.locator("#chart-history circle").count();
    expect(dotsOff).toBe(0);

    const salesDemandSvgHtml = await page.locator("#chart-sales-demand svg").innerHTML();
    fs.writeFileSync(path.join(SHOT_DIR, "chart-sales-demand.svg.html"), salesDemandSvgHtml);

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

  test("3: secondary pane — histogram + chrome, truth bars", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await advanceDays(page, 2);
    const secondary = page.locator(".cockpit-pane--secondary");
    await expect(secondary).toContainText(/freshness histogram/i);
    await expect(page.locator("#chart-belief-lg")).toBeVisible();
    await expect(page.locator("[data-testid='secondary-chrome']")).toBeVisible();
    await secondary.screenshot({ path: shotPath("03a-secondary-truth-on") });

    const truthBarCountOn = await page.locator("#chart-belief-lg .truth-bar").count();
    expect(truthBarCountOn).toBeGreaterThan(0);

    await page.locator(".secondary-chrome .truth-toggle").click();
    await page.waitForTimeout(200);
    const truthBarCountOff = await page.locator("#chart-belief-lg .truth-bar").count();
    expect(truthBarCountOff).toBe(0);
  });

  test("4: exactly one order-qty control and one advance button", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await expect(page.locator("#order-range")).toHaveCount(1);
    await expect(page.locator("#order-num")).toHaveCount(1);
    await expect(page.locator("#btn-advance")).toHaveCount(1);
    await expect(page.locator("#btn-reset")).toHaveCount(1);
    await expect(page.locator("#play-chrome")).toHaveCount(0);
  });

  test("5: tradeoff tab toggle — curve then histogram", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    const chrome = page.locator("[data-testid='secondary-chrome']");
    await expect(chrome).toBeVisible();

    const curvePaths = await page.locator("#tradeoff-curve-host path, #tradeoff-curve-host line").count();
    expect(curvePaths).toBeGreaterThan(0);
    await expect(page.locator("#tradeoff-histogram-host")).toHaveCount(0);

    await chrome.getByRole("tab", { name: "Histogram" }).click();
    await page.waitForTimeout(200);
    const histRects = await page.locator("#tradeoff-histogram-host rect").count();
    expect(histRects).toBeGreaterThan(0);
    await expect(page.locator("#tradeoff-curve-host")).toHaveCount(0);
    await chrome.screenshot({ path: shotPath("05-tradeoff-histogram-tab") });
  });

  test("6: economics pane — no dead pnl-spark/series", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await expect(page.locator("#chart-pnl-spark")).toHaveCount(0);
    await expect(page.locator("#chart-pnl-series")).toHaveCount(0);
    const econ = page.locator("#economics-pane-host");
    await expect(econ).toBeVisible();
    await econ.screenshot({ path: shotPath("06-economics-pane") });
  });

  test("7: events pane changes per observation preset", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await advanceDays(page, 3);
    const events = page.locator("#events-pane-host");
    await expect(events).toBeVisible();

    for (const scenario of ["P0", "P1", "F1", "F1s", "F2a", "F2"]) {
      await setObsPreset(page, scenario);
      await events.screenshot({ path: shotPath(`07-events-${scenario}`) });
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
    }

    await setObsPreset(page, "P0");
    await dockTab("arrival").click();
    await page.waitForTimeout(150);

    await setObsPreset(page, "F2a");
    await dockTab("arrival").click();
    await page.waitForTimeout(150);

    await setObsPreset(page, "F2");
    await page.waitForTimeout(150);
    await dockTab("arrival").click();
    await page.waitForTimeout(150);

    await dockTab("autopilot").click();
    await page.waitForTimeout(150);
    const pad = page.locator("#alpha-rho-pad, [data-testid='alpha-rho-pad']").first();
    if (await pad.count() > 0) {
      const box = await pad.boundingBox();
      if (box) {
        await page.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.2);
        await page.mouse.down();
        await page.mouse.move(box.x + box.width * 0.8, box.y + box.height * 0.8, { steps: 5 });
        await page.mouse.up();
      }
    }
    await page.locator(".tuning-dock").screenshot({ path: shotPath("08e-autopilot-after-drag") });
  });

  test("9: general polish — layout at two viewports", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await waitForEngine(page);
    await advanceDays(page, 3);
    await page.screenshot({ path: shotPath("09a-desktop-1440"), fullPage: true });

    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForTimeout(200);
    await page.screenshot({ path: shotPath("09b-narrow-1024"), fullPage: true });
  });
});
