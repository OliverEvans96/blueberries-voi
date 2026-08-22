import { test, expect } from "@playwright/test";

test.describe("studio cockpit smoke (T-148 layout v6)", () => {
  test("loads shell with key panes and chart hosts", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".cockpit-grid[data-layout='v6']")).toBeVisible();
    await expect(page.locator("[data-testid='cockpit-metrics']")).toBeVisible();
    await expect(page.locator("[data-testid='cockpit-belief']")).toBeVisible();
    await expect(page.locator("[data-testid='cockpit-sidebar']")).toBeVisible();
    await expect(page.locator("#chart-history")).toBeVisible();
    await expect(page.locator("#chart-sales-demand")).toBeVisible();
    await expect(page.locator("#chart-controller-orders")).toBeVisible();
    await expect(page.locator("#chart-belief-lg")).toBeVisible();
    await expect(page.locator("#pnl-totals-host")).toHaveCount(1);
    await expect(page.locator("#obs-controls-pane-host")).toHaveCount(1);
    await expect(page.locator("#events-pane-host")).toHaveCount(1);
    await expect(page.locator("#economics-pane-host")).toHaveCount(0);
    await expect(page.locator("[data-testid='cockpit-today']")).toHaveCount(0);
    await expect(page.locator("#secondary-chrome-host")).toHaveCount(0);
    await expect(page.locator("#decision-rail-host")).toHaveCount(0);
    await expect(page.locator(".tuning-dock")).toBeVisible();
    await expect(page.locator("#chart-pnl-spark")).toHaveCount(0);
    await expect(page.locator("#chart-pnl-series")).toHaveCount(0);
  });
});
