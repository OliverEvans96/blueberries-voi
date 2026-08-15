/**
 * T-126 RED (qa-dayinspector): attachLinkedHover passes cursor position with day index.
 */
// @vitest-environment jsdom
import { fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { attachLinkedHover, CHART_MARGIN, type LinkedHoverHandlers } from "./hoverLink";
import type { HoverDay } from "./types";

/** Contract from AC-dayinspector / spec interfaces table. */
type HoverPoint = { clientX: number; clientY: number } | null;

function makeChartRoot(): { root: HTMLDivElement; svg: SVGSVGElement } {
  const root = document.createElement("div");
  root.className = "linked-charts";

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("chart-svg");
  svg.setAttribute("viewBox", "0 0 200 100");
  Object.defineProperty(svg, "getBoundingClientRect", {
    configurable: true,
    value: () =>
      ({
        left: 100,
        top: 50,
        width: 200,
        height: 100,
        right: 300,
        bottom: 150,
        x: 100,
        y: 50,
        toJSON: () => ({}),
      }) as DOMRect,
  });

  root.appendChild(svg);
  document.body.appendChild(root);
  return { root, svg };
}

describe("attachLinkedHover (T-126 AC-dayinspector)", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("invokes onDay with resolved day and { clientX, clientY } on pointermove over a chart svg", () => {
    const { root, svg } = makeChartRoot();
    const days = [1, 2, 3, 4, 5] as const;
    const onDay = vi.fn<(day: HoverDay, point: HoverPoint) => void>();

    const detach = attachLinkedHover(root, () => days, {
      onDay,
    } as LinkedHoverHandlers);

    // Inner plot starts at marginLeft; pick X in the first day band.
    const clientX = 100 + CHART_MARGIN.left + 4;
    const clientY = 120;
    fireEvent.pointerMove(svg, { clientX, clientY, bubbles: true });

    expect(onDay).toHaveBeenCalledWith(1, { clientX, clientY });

    detach();
  });

  it("invokes onDay with (null, null) when pointer leaves the linked region", () => {
    const { root, svg } = makeChartRoot();
    const onDay = vi.fn<(day: HoverDay, point: HoverPoint) => void>();

    const detach = attachLinkedHover(root, () => [1, 2, 3], {
      onDay,
    } as LinkedHoverHandlers);

    fireEvent.pointerMove(svg, { clientX: 160, clientY: 90, bubbles: true });
    onDay.mockClear();

    fireEvent.pointerLeave(root, {
      relatedTarget: document.body,
      bubbles: true,
    });

    expect(onDay).toHaveBeenCalledTimes(1);
    expect(onDay).toHaveBeenCalledWith(null, null);

    detach();
  });
});
