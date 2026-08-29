/**
 * T-157: first-order visual QA — day-0 init, first Place Order, five orders.
 * Screenshots land under web/tests/__screenshots__/init-audit/ (gitignored).
 */
import { test, expect, type Page, type Locator } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = path.join(__dirname, "__screenshots__", "init-audit");
fs.mkdirSync(SHOT_DIR, { recursive: true });

/** Mirrors MIN_CHART_DAY_SPAN in web/src/charts/axisTicks.ts */
const MIN_CHART_DAY_SPAN = 5;

const CHART_HOSTS = [
  "#chart-pnl-economics",
  "#chart-controller-orders",
  "#chart-spoil",
  "#chart-sales-demand",
  "#chart-history",
  "#chart-age-comp",
  "#chart-belief-lg",
  "#tradeoff-curve-host",
] as const;

const TEXT_HOSTS = ["#pnl-totals-host"] as const;

const LAYOUT_HOSTS = [...TEXT_HOSTS, ...CHART_HOSTS] as const;

type Rect = { x: number; y: number; width: number; height: number };

function shotPath(name: string): string {
  return path.join(SHOT_DIR, `${name}.png`);
}

async function waitForEngine(page: Page): Promise<void> {
  await page.waitForSelector(".cockpit-grid", { state: "visible" });
  await page.waitForFunction(
    () =>
      document.querySelector("#engine-status")?.getAttribute("data-status") !==
      "loading",
    { timeout: 30000 },
  );
  // Allow first paint of charts / totals after engine ready.
  await page.waitForTimeout(500);
}

async function placeOrder(page: Page): Promise<void> {
  await page.locator("#btn-advance").click();
  await page.waitForTimeout(500);
}

async function placeOrders(page: Page, n: number): Promise<void> {
  for (let i = 0; i < n; i++) {
    await placeOrder(page);
  }
}

async function hostRect(locator: Locator): Promise<Rect> {
  const box = await locator.boundingBox();
  if (!box) throw new Error("host missing bounding box");
  return {
    x: box.x,
    y: box.y,
    width: box.width,
    height: box.height,
  };
}

function assertRectStable(before: Rect, after: Rect, label: string): void {
  const keys: (keyof Rect)[] = ["x", "y", "width", "height"];
  for (const k of keys) {
    const delta = Math.abs(after[k] - before[k]);
    expect(delta, `${label}.${k} shifted by ${delta}px`).toBeLessThanOrEqual(1);
  }
}

async function assertChartInitialized(page: Page, sel: string): Promise<void> {
  const host = page.locator(sel);
  await expect(host, `${sel} visible`).toBeVisible();
  const svg = host.locator("svg.chart-svg");
  await expect(svg, `${sel} has svg.chart-svg`).toHaveCount(1);
  // Axes: at least one tick group (x or y). Tradeoff curve may use path/line axes differently.
  if (sel === "#tradeoff-curve-host") {
    const marks = await host.locator("path, line, .axis").count();
    expect(marks, `${sel} has chart marks`).toBeGreaterThan(0);
    return;
  }
  await expect(host.locator(".axis"), `${sel} has .axis`).not.toHaveCount(0);
}

async function xAxisDaySpan(page: Page, sel: string): Promise<number> {
  return page.locator(sel).evaluate((el) => {
    const ticks = [...el.querySelectorAll(".axis-x .tick text")].map((t) =>
      Number(t.textContent?.replace(/[^\d.-]/g, "")),
    );
    const nums = ticks.filter((n) => Number.isFinite(n));
    if (nums.length === 0) return 0;
    return Math.max(...nums) - Math.min(...nums) + 1;
  });
}

async function assertMinDaySpan(page: Page, sel: string): Promise<void> {
  if (sel === "#tradeoff-curve-host" || sel === "#chart-belief-lg") {
    // Tradeoff is candidate-indexed; belief-lg is a freshness histogram (not day-axis).
    return;
  }
  const span = await xAxisDaySpan(page, sel);
  expect(
    span,
    `${sel} x-axis day span ${span} < MIN_CHART_DAY_SPAN=${MIN_CHART_DAY_SPAN}`,
  ).toBeGreaterThanOrEqual(MIN_CHART_DAY_SPAN);
}

async function assertTextInitialized(page: Page): Promise<void> {
  const pnl = page.locator("#pnl-totals-host");
  await expect(pnl.locator(".pnl-totals")).toBeVisible();
  await expect(pnl.locator(".pnl-value--rev")).toContainText("$");
  await expect(pnl.locator(".pnl-value--cost")).toContainText("$");
  await expect(pnl.locator(".pnl-value--profit")).toContainText("$");
  // Day 0: zeros should be zero.
  await expect(pnl.locator(".pnl-value--rev")).toHaveText("$0");
  await expect(pnl.locator(".pnl-value--cost")).toHaveText("$0");
  await expect(pnl.locator(".pnl-value--profit")).toHaveText("$0");
  await expect(pnl.locator(".pnl-value--service")).toHaveText("0");
  await expect(pnl.locator(".pnl-value--waste")).toHaveText("0");
}

test.describe("T-157 first-order init audit", () => {
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

  test("day-0 → 1 order → 5 orders: charts, text, span, layout", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    const errors = (page as unknown as { __errors: string[] }).__errors;

    await page.goto("/");
    await waitForEngine(page);

    // --- Day 0 ---
    await page.screenshot({
      path: shotPath("00-day0-full"),
      fullPage: true,
    });
    await page.locator(".cockpit-pane--metrics").screenshot({
      path: shotPath("00-day0-metrics"),
    });
    await page.locator(".cockpit-pane--belief").screenshot({
      path: shotPath("00-day0-belief"),
    });

    for (const sel of CHART_HOSTS) {
      await assertChartInitialized(page, sel);
      await assertMinDaySpan(page, sel);
    }
    await assertTextInitialized(page);

    const day0Rects: Record<string, Rect> = {};
    for (const sel of LAYOUT_HOSTS) {
      day0Rects[sel] = await hostRect(page.locator(sel));
    }

    const day0Errors = [...errors];

    // --- After 1 Place Order ---
    await placeOrder(page);
    await page.screenshot({
      path: shotPath("01-after-1-order-full"),
      fullPage: true,
    });
    await page.locator(".cockpit-pane--metrics").screenshot({
      path: shotPath("01-after-1-order-metrics"),
    });
    await page.locator(".cockpit-pane--belief").screenshot({
      path: shotPath("01-after-1-order-belief"),
    });

    for (const sel of CHART_HOSTS) {
      await assertChartInitialized(page, sel);
      await assertMinDaySpan(page, sel);
    }
    // Text still populated (values may leave zero after first day).
    await expect(page.locator("#pnl-totals-host .pnl-totals")).toBeVisible();
    await expect(page.locator("#pnl-totals-host .pnl-value--service")).toBeVisible();
    await expect(page.locator("#pnl-totals-host .pnl-value--waste")).toBeVisible();

    for (const sel of LAYOUT_HOSTS) {
      const after = await hostRect(page.locator(sel));
      assertRectStable(day0Rects[sel]!, after, sel);
    }

    // --- After 5 Place Orders total (4 more) ---
    await placeOrders(page, 4);
    await page.screenshot({
      path: shotPath("05-after-5-orders-full"),
      fullPage: true,
    });
    await page.locator(".cockpit-pane--metrics").screenshot({
      path: shotPath("05-after-5-orders-metrics"),
    });
    await page.locator(".cockpit-pane--belief").screenshot({
      path: shotPath("05-after-5-orders-belief"),
    });

    for (const sel of CHART_HOSTS) {
      await assertChartInitialized(page, sel);
      await assertMinDaySpan(page, sel);
    }

    const allErrors = [...errors];
    expect(
      allErrors,
      `console/page errors:\n${allErrors.join("\n")}`,
    ).toEqual([]);
    expect(day0Errors).toEqual([]);
  });
});
