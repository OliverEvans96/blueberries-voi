/**
 * Info-tip portal positioning — keep bubbles inside the viewport.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { positionInfoTipBubble } from "./infoTipPortal";

function mockRect(
  element: Element,
  rect: Partial<DOMRect>,
): void {
  vi.spyOn(element, "getBoundingClientRect").mockReturnValue({
    x: rect.left ?? 0,
    y: rect.top ?? 0,
    width: rect.width ?? 0,
    height: rect.height ?? 0,
    top: rect.top ?? 0,
    left: rect.left ?? 0,
    right: (rect.left ?? 0) + (rect.width ?? 0),
    bottom: (rect.top ?? 0) + (rect.height ?? 0),
    toJSON: () => ({}),
  });
}

describe("positionInfoTipBubble", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("clamps a bubble that would extend past the right viewport edge", () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 320,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 640,
    });

    const trigger = document.createElement("button");
    const bubble = document.createElement("span");
    document.body.append(trigger, bubble);

    mockRect(trigger, { left: 280, top: 40, width: 24, height: 24, bottom: 64 });
    mockRect(bubble, { width: 200, height: 80 });

    positionInfoTipBubble(trigger, bubble);

    expect(Number.parseInt(bubble.style.left, 10)).toBeLessThanOrEqual(320 - 200 - 8);
    expect(Number.parseInt(bubble.style.top, 10)).toBeGreaterThanOrEqual(8);
  });

  it("shrinks max-width on narrow viewports", () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 200,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 640,
    });

    const trigger = document.createElement("button");
    const bubble = document.createElement("span");
    document.body.append(trigger, bubble);

    mockRect(trigger, { left: 10, top: 40, width: 24, height: 24, bottom: 64 });
    mockRect(bubble, { width: 184, height: 60 });

    positionInfoTipBubble(trigger, bubble);

    expect(bubble.style.maxWidth).toBe("184px");
  });
});
