import { test, expect } from "@playwright/test";

async function waitForEngine(page: import("@playwright/test").Page) {
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

async function dismissWelcomeIfOpen(page: import("@playwright/test").Page) {
  const close = page.locator(".welcome-modal-close");
  if (await close.isVisible().catch(() => false)) {
    await close.click();
    await page.waitForTimeout(200);
  }
}

test.describe("studio cockpit smoke (T-158 layout v7)", () => {
  test("loads shell with key panes and chart hosts", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".cockpit-grid[data-layout='v7']")).toBeVisible();
    await expect(page.locator("[data-testid='cockpit-metrics']")).toBeVisible();
    await expect(page.locator("[data-testid='cockpit-belief']")).toBeVisible();
    await expect(page.locator("[data-testid='cockpit-sidebar']")).toBeVisible();
    await expect(page.locator("#chart-history")).toBeVisible();
    await expect(page.locator("#chart-sales-demand")).toBeVisible();
    await expect(page.locator("#chart-controller-orders")).toBeVisible();
    await expect(page.locator("#chart-spoil")).toBeVisible();
    await expect(page.locator("#chart-belief-lg")).toBeVisible();
    await expect(page.locator("#pnl-totals-host")).toHaveCount(1);
    await expect(page.locator("#obs-controls-pane-host")).toHaveCount(1);
    await expect(page.locator("#events-pane-host")).toHaveCount(1);
    await expect(page.locator("#economics-pane-host")).toHaveCount(0);
    await expect(page.locator("[data-testid='cockpit-today']")).toHaveCount(0);
    await expect(page.locator("#secondary-chrome-host")).toHaveCount(0);
    await expect(page.locator("#decision-rail-host")).toHaveCount(0);
    await expect(page.locator(".cockpit-row--tuning")).toHaveCount(0);
    await expect(page.locator("#tuning-drawer-trigger")).toBeVisible();
    await expect(page.locator("#chart-pnl-spark")).toHaveCount(0);
    await expect(page.locator("#chart-pnl-series")).toHaveCount(0);
  });

  test("tuning drawer info-tip bubble is visible on hover", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await dismissWelcomeIfOpen(page);
    await page.locator("#tuning-drawer-trigger").click();
    await page.waitForSelector("dialog.tuning-drawer[open]", { state: "visible" });

    const trigger = page
      .locator(
        "dialog.tuning-drawer[open] .controls-block:not([hidden]) .info-tip-trigger",
      )
      .first();
    await expect(trigger).toBeVisible();
    await trigger.hover();

    const bubble = page.locator(
      "dialog.tuning-drawer[open] .info-tip-bubble--portaled",
    );
    await expect(bubble).toBeVisible();
  });
});
