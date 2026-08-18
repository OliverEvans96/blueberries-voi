/**
 * T-099 RED: controllerOrders series helper from sample day history.
 */
// @vitest-environment jsdom
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const CONTROLLER_ORDERS_TS = join(HERE, "controllerOrders.ts");

describe("controllerOrders series helper (T-099)", () => {
  it("controllerOrdersSeries maps day.order_qty from sample history", async () => {
    expect(
      existsSync(CONTROLLER_ORDERS_TS),
      "expected web/src/charts/controllerOrders.ts",
    ).toBe(true);

    const mod = await import("./controllerOrders");
    const seriesFn = (
      mod as {
        controllerOrdersSeries?: (
          history: ReadonlyArray<{ day: number; order_qty: number }>,
        ) => ReadonlyArray<{ day: number; order_qty: number }>;
      }
    ).controllerOrdersSeries;

    expect(
      typeof seriesFn,
      "expected export controllerOrdersSeries (mirrors inventorySeries)",
    ).toBe("function");

    const history = [
      { day: 1, order_qty: 16 },
      { day: 2, order_qty: 0 },
      { day: 3, order_qty: 24 },
    ];
    expect(seriesFn!(history)).toEqual([
      { day: 1, order_qty: 16 },
      { day: 2, order_qty: 0 },
      { day: 3, order_qty: 24 },
    ]);
  });

  it("exports renderControllerOrders for plot mount", async () => {
    expect(existsSync(CONTROLLER_ORDERS_TS)).toBe(true);
    const mod = await import("./controllerOrders");
    expect(typeof mod.renderControllerOrders).toBe("function");
  });

  it("renderControllerOrders draws vertical bars not a line (T-130)", async () => {
    const container = document.createElement("div");
    Object.defineProperty(container, "clientWidth", {
      value: 320,
      configurable: true,
    });
    const { renderControllerOrders } = await import("./controllerOrders");
    renderControllerOrders(
      container,
      [
        { day: 1, order_qty: 16 },
        { day: 2, order_qty: 0 },
        { day: 3, order_qty: 24 },
      ],
      80,
    );
    const bars = container.querySelectorAll(".order-bar, rect.order-bar");
    expect(bars.length).toBeGreaterThan(0);
    expect(container.querySelector(".order-line, path.order-line")).toBeNull();
  });
});
