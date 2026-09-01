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

function obsChannels(page: Page) {
  return page.locator("[data-testid='obs-controls-pane']");
}

async function setObsChannels(
  page: Page,
  partial: { scanWaste?: boolean; codeType?: "upc" | "lgtin" },
) {
  if (partial.codeType) {
    await obsChannels(page)
      .locator(`[data-obs-code-type='${partial.codeType}']`)
      .click();
  }
  if (partial.scanWaste != null) {
    await obsChannels(page)
      .locator(`[data-obs-scan-waste='${partial.scanWaste}']`)
      .click();
  }
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

async function openTuningDrawer(page: Page) {
  await page.locator("#tuning-drawer-trigger").click();
  await page.waitForSelector("dialog.tuning-drawer[open]", { state: "visible" });
  await page.waitForTimeout(150);
}

test.describe("T-158 layout v7 — visual QA", () => {
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

  test("1: layout v7 — metrics, belief, sidebar (no tuning row)", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await expect(page.locator(".cockpit-grid[data-layout='v7']")).toBeVisible();
    await expect(page.locator(".cockpit-pane--metrics")).toBeVisible();
    await expect(page.locator(".cockpit-pane--belief")).toBeVisible();
    await expect(page.locator(".cockpit-pane--sidebar")).toBeVisible();
    await expect(page.locator(".cockpit-row--tuning")).toHaveCount(0);
    await expect(page.locator("[data-testid='obs-controls-pane']")).toBeVisible();
    await expect(page.locator("[data-testid='cockpit-events-column']")).toBeVisible();
    await expect(page.locator(".title-bar h1")).toContainText("Blueberry inventory studio");
    await page.screenshot({ path: shotPath("01-full-page-initial"), fullPage: true });
  });

  test("2: metrics column charts and P&L impact totals", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await advanceDays(page, 3);
    const metrics = page.locator(".cockpit-pane--metrics");
    await expect(metrics.locator("#chart-pnl-economics")).toBeVisible();
    await expect(metrics.locator("#chart-sales-demand")).toBeVisible();
    await expect(metrics.locator("#chart-controller-orders")).toBeVisible();
    await expect(metrics.locator("#chart-spoil")).toBeVisible();
    await expect(metrics.locator("#chart-age-comp")).toHaveCount(0);
    await expect(metrics.locator(".pnl-totals-line")).toHaveCount(2);
    await expect(metrics.locator(".pnl-value--service")).toBeVisible();
    await expect(metrics.locator(".pnl-value--waste")).toBeVisible();
  });

  test("3: belief column and truth toggle in obs controls", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await advanceDays(page, 2);
    const belief = page.locator(".cockpit-pane--belief");
    await expect(belief.locator("#chart-belief-lg")).toBeVisible();
    await expect(belief.locator("#chart-age-comp")).toBeVisible();
    await expect(belief.locator("#chart-history")).toBeVisible();

    const truthToggle = page.locator("[data-testid='obs-controls-pane'] .truth-toggle");
    await expect(truthToggle).toHaveAttribute("aria-checked", "false");
    await expect(page.locator(".truth-toggle-label")).toContainText("Omniscience");
    await truthToggle.click();
    await expect(truthToggle).toHaveAttribute("aria-checked", "true");
  });

  test("4: exactly one order-qty control and one advance button", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await expect(page.locator("#order-range")).toHaveCount(1);
    await expect(page.locator("#order-num")).toHaveCount(1);
    await expect(page.locator("#btn-advance")).toHaveCount(1);
    await expect(page.locator("#btn-reset")).toHaveCount(1);
  });


  test("6: events pane 5-day window", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await advanceDays(page, 6);
    const events = page.locator("#events-pane-host");
    await expect(events).toBeVisible();
    await expect(events.locator(".events-day-card")).toHaveCount(5);
    await expect(events.locator("[data-testid='events-columns']").first()).toBeVisible();
    await expect(events.locator(".events-day-card[data-day='7']")).toHaveCount(0);
  });

  test("7: tuning drawer without observation tab", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await openTuningDrawer(page);
    await expect(page.locator('.tuning-dock-tabs [data-section="observation"]')).toHaveCount(0);
    for (const section of ["demand", "arrival", "physics", "logistics", "autopilot"]) {
      const tab = page.locator(`.tuning-dock-tabs [data-section="${section}"]`);
      await expect(tab).toBeVisible();
      await tab.click();
      await page.waitForTimeout(150);
      await expect(tab).toHaveAttribute("aria-selected", "true");
    }
  });

  test("8: obs channel changes keep events pane visible", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await advanceDays(page, 3);
    await setObsChannels(page, { scanWaste: false });
    await expect(page.locator("#events-pane-host")).toBeVisible();
    await setObsChannels(page, { codeType: "lgtin", scanWaste: true });
    await expect(page.locator("#events-pane-host")).toBeVisible();
  });

  test("9: chart host heights stay stable across first advances", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);

    const chartIds = [
      "#chart-pnl-economics",
      "#chart-history",
      "#chart-belief-lg",
          ];

    const heightsBefore = await page.evaluate((ids) => {
      const out: Record<string, number> = {};
      for (const id of ids) {
        const el = document.querySelector(id);
        out[id] = el?.getBoundingClientRect().height ?? 0;
      }
      return out;
    }, chartIds);

    await advanceDays(page, 2);

    const heightsAfter = await page.evaluate((ids) => {
      const out: Record<string, number> = {};
      for (const id of ids) {
        const el = document.querySelector(id);
        out[id] = el?.getBoundingClientRect().height ?? 0;
      }
      return out;
    }, chartIds);

    for (const id of chartIds) {
      const before = heightsBefore[id] ?? 0;
      const after = heightsAfter[id] ?? 0;
      expect(before).toBeGreaterThan(0);
      expect(Math.abs(after - before)).toBeLessThanOrEqual(1);
    }
  });
});
