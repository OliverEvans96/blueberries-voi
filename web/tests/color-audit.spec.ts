import { test, expect } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = path.join(__dirname, "..", "pr-screenshots", "color-audit");
fs.mkdirSync(SHOT_DIR, { recursive: true });

function shotPath(name: string): string {
  return path.join(SHOT_DIR, `${name}.png`);
}

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
  await page.waitForTimeout(400);
}

async function dismissWelcomeIfOpen(page: import("@playwright/test").Page) {
  const close = page.locator(".welcome-modal-close");
  if (await close.isVisible().catch(() => false)) {
    await close.click();
    await page.waitForTimeout(200);
  }
}

async function advanceDays(page: import("@playwright/test").Page, n: number) {
  for (let i = 0; i < n; i++) {
    await page.locator("#btn-advance").click();
    await page.waitForTimeout(400);
  }
}

test.describe("Studio color audit screenshots", () => {
  test("belief cockpit — Omniscience OFF and ON", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await dismissWelcomeIfOpen(page);
    await advanceDays(page, 3);

    const truthToggle = page.locator("[data-testid='obs-controls-pane'] .truth-toggle");

    await truthToggle.click();
    await expect(truthToggle).toHaveAttribute("aria-checked", "false");
    await page.waitForTimeout(300);
    await page.screenshot({ path: shotPath("01-belief-cockpit-truth-off"), fullPage: true });

    await truthToggle.click();
    await expect(truthToggle).toHaveAttribute("aria-checked", "true");
    await page.waitForTimeout(300);
    await page.screenshot({ path: shotPath("02-belief-cockpit-truth-on"), fullPage: true });
  });

  test("belief pane chart close-ups", async ({ page }) => {
    await page.goto("/");
    await waitForEngine(page);
    await dismissWelcomeIfOpen(page);
    await advanceDays(page, 3);

    const beliefLg = page.locator("#chart-belief-lg");
    await expect(beliefLg).toBeVisible();
    await beliefLg.screenshot({ path: shotPath("03-chart-belief-lg") });

    const history = page.locator("#chart-history");
    if ((await history.count()) > 0) {
      await history.screenshot({ path: shotPath("04-chart-history") });
    }
  });
});
