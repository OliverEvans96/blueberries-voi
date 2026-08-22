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

  it("exports renderOrdersWaste for combined order + spoilage chart", async () => {
    const container = document.createElement("div");
    Object.defineProperty(container, "clientWidth", {
      value: 320,
      configurable: true,
    });
    const { renderOrdersWaste } = await import("./controllerOrders");
    renderOrdersWaste(
      container,
      [
        { day: 1, order_qty: 16, waste_total: 2 },
        { day: 2, order_qty: 0, waste_total: 5 },
        { day: 3, order_qty: 24, waste_total: 1 },
      ],
      130,
    );
    expect(container.querySelector("path.order-line")).not.toBeNull();
    expect(container.querySelector("path.waste-line")).not.toBeNull();
    expect(container.querySelector("svg.chart-svg")).not.toBeNull();
  });

  it("setOrdersWasteHover toggles hover rule for hovered day", async () => {
    const container = document.createElement("div");
    Object.defineProperty(container, "clientWidth", {
      value: 320,
      configurable: true,
    });
    document.body.appendChild(container);
    const { renderOrdersWaste, setOrdersWasteHover } = await import(
      "./controllerOrders"
    );
    renderOrdersWaste(
      container,
      [
        { day: 1, order_qty: 16, waste_total: 2 },
        { day: 2, order_qty: 0, waste_total: 5 },
      ],
      100,
    );
    setOrdersWasteHover(container, 2);
    const rule = container.querySelector(".hover-rule");
    expect(rule?.getAttribute("opacity")).toBe("1");
    expect(Number(rule?.getAttribute("x1"))).toBeGreaterThan(0);
    setOrdersWasteHover(container, null);
    expect(rule?.getAttribute("opacity")).toBe("0");
    container.remove();
  });
});
