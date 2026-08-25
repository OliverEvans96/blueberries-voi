import { test, expect, type Page } from "@playwright/test";

async function waitForEngine(page: Page) {
  await page.waitForSelector(".cockpit-grid", { state: "visible" });
  await page
    .waitForFunction(
      () =>
        document.querySelector("#engine-status")?.getAttribute("data-status") !==
        "loading",
      { timeout: 15000 },
    )
    .catch(() => {
      /* fall through */
    });
  await page.waitForTimeout(300);
}

async function dismissWelcomeIfOpen(page: Page) {
  const close = page.locator(".welcome-modal-close");
  if (await close.isVisible().catch(() => false)) {
    await close.click();
    await page.waitForTimeout(200);
  }
}

async function advanceDays(page: Page, n: number) {
  for (let i = 0; i < n; i++) {
    await page.locator("#btn-advance").click();
    await page.waitForTimeout(400);
  }
}

async function selectMobileTab(page: Page, tab: "results" | "run" | "observe") {
  await page.locator(`#cockpit-mobile-tab-${tab}`).click();
}

test.describe("mobile layout and touch (iPhone 13)", () => {
  test("welcome modal fits the viewport on first load", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);

    const welcome = page.locator("dialog.welcome-modal[open]");
    await expect(welcome).toBeVisible();
    const welcomeBox = await welcome.boundingBox();
    const viewport = page.viewportSize();
    expect(welcomeBox).not.toBeNull();
    if (welcomeBox && viewport) {
      expect(welcomeBox.width).toBeLessThanOrEqual(viewport.width);
      expect(welcomeBox.x).toBeGreaterThanOrEqual(0);
    }
  });

  test("no horizontal page overflow at phone width", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await dismissWelcomeIfOpen(page);

    const overflow = await page.evaluate(() => {
      const doc = document.documentElement;
      return doc.scrollWidth - doc.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("mobile cockpit tabs default to Run and switch panes", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await dismissWelcomeIfOpen(page);

    const grid = page.locator(".cockpit-grid[data-layout='v7']");
    await expect(grid).toHaveAttribute("data-mobile-tab", "run");

    const runPane = page.locator("#cockpit-center-pane");
    const resultsPane = page.locator("#cockpit-metrics-pane");
    const observePane = page.locator("#cockpit-sidebar-pane");

    await expect(runPane).toBeVisible();
    await expect(resultsPane).toBeHidden();
    await expect(observePane).toBeHidden();

    await page.locator("#cockpit-mobile-tab-results").click();
    await expect(grid).toHaveAttribute("data-mobile-tab", "results");
    await expect(resultsPane).toBeVisible();
    await expect(runPane).toBeHidden();

    await page.locator("#cockpit-mobile-tab-observe").click();
    await expect(grid).toHaveAttribute("data-mobile-tab", "observe");
    await expect(observePane).toBeVisible();
    await expect(resultsPane).toBeHidden();
  });

  test("title bar heading and actions fit without overlapping", async ({
    page,
  }) => {
    await page.goto("/");
    await waitForEngine(page);
    await dismissWelcomeIfOpen(page);

    const heading = page.locator(".title-bar-heading");
    const actions = page.locator(".title-bar-actions");
    await expect(heading).toBeVisible();
    await expect(actions).toBeVisible();

    const headingBox = await heading.boundingBox();
    const actionsBox = await actions.boundingBox();
    expect(headingBox).not.toBeNull();
    expect(actionsBox).not.toBeNull();
    if (headingBox && actionsBox) {
      expect(actionsBox.y).toBeGreaterThanOrEqual(headingBox.y);
      expect(actionsBox.x + actionsBox.width).toBeLessThanOrEqual(395);
    }
  });

  test("tuning drawer fits the viewport and closes via Done", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await dismissWelcomeIfOpen(page);

    await page.locator("#tuning-drawer-trigger").click();
    const drawer = page.locator("dialog.tuning-drawer[open]");
    await expect(drawer).toBeVisible();
    const drawerBox = await drawer.boundingBox();
    const viewport = page.viewportSize();
    expect(drawerBox).not.toBeNull();
    if (drawerBox && viewport) {
      expect(drawerBox.width).toBeLessThanOrEqual(viewport.width);
      expect(drawerBox.x).toBeGreaterThanOrEqual(0);
    }

    await drawer.locator(".tuning-drawer-done").click();
    await expect(drawer).toBeHidden();
  });

  test("chart tap pins the day inspector on touch", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await dismissWelcomeIfOpen(page);
    await advanceDays(page, 3);
    await selectMobileTab(page, "results");

    const chart = page.locator("#chart-sales-demand svg.chart-svg").first();
    await chart.scrollIntoViewIfNeeded();
    await chart.tap();

    await expect(page.locator("#hover-note")).toContainText(/Day \d+ highlighted/);
    await expect(page.locator(".day-inspector-tooltip")).toHaveCount(1);
  });

  test("info-tip glyph opens on tap", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await dismissWelcomeIfOpen(page);
    await selectMobileTab(page, "results");

    const trigger = page.locator(
      "#cockpit-metrics-pane .info-tip-trigger",
    ).first();
    await trigger.scrollIntoViewIfNeeded();
    await trigger.tap();

    const portal = page.locator(".bv-studio-portal-root");
    await expect(portal.locator(".info-tip-bubble--portaled")).toHaveCount(1);
  });
});
