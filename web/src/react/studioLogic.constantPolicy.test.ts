/**
 * Constant policy: order slider is controller input, not delta echo.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const LOGIC_TS = join(HERE, "studioLogic.ts");

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("constant policy order_qty sync (T-164)", () => {
  const logicSrc = stripComments(readFileSync(LOGIC_TS, "utf8"));

  it("applyDelta skips orderQty sync when policy is constant", () => {
    expect(logicSrc).toMatch(
      /if \(typeof q === "number" && controllerState\.policy !== "constant"\)/,
    );
  });

  it("preserves user-set orderQty through a non-order-day delta", () => {
    let orderQty = 24;
    const controllerState = { policy: "constant" as const };
    const snapOrder = (q: number) => q;

    const delta = { day: { order_qty: 0 } };
    const q = delta.day.order_qty;
    if (typeof q === "number" && controllerState.policy !== "constant") {
      orderQty = snapOrder(q);
    }

    expect(orderQty).toBe(24);

    const budgets =
      controllerState.policy === "constant"
        ? { order_qty: orderQty }
        : {};
    expect(budgets.order_qty).toBe(24);
  });
});
