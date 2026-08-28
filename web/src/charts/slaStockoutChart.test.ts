/**
 * T-164: SLA stockout belief chart.
 */
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { ORDER_Q_SLIDER_MIN_MAX } from "../react/studioShellDefaults";
import {
  SLA_STOCKOUT_X_MAX,
  renderSlaStockoutChart,
  refreshSlaStockoutMarker,
} from "./slaStockoutChart";

describe("slaStockoutChart", () => {
  it("renders dual-axis chart with demand bars and stockout line", () => {
    const host = document.createElement("div");
    Object.defineProperty(host, "clientWidth", { value: 320, configurable: true });
    renderSlaStockoutChart(host, {
      curve: {
        candidates: [
          { q: 0, p_no_stockout: 0.2, p_stockout: 0.8 },
          { q: 8, p_no_stockout: 0.6, p_stockout: 0.4 },
          { q: 16, p_no_stockout: 0.9, p_stockout: 0.1 },
        ],
      },
      orderQty: 8,
      demandVm: 2.5,
      demandSummary: {
        scale_mu: 30,
        dow_means: [30, 30, 30, 30, 30, 30, 30],
      },
      schedule: {
        delivery_weekdays: [0, 2, 4],
        order_weekdays: [6, 1, 3],
        lead_time_days: 1,
        epoch: "2024-01-01",
      },
      episodeDay: 2,
      height: 130,
    });
    expect(host.querySelector("svg.sla-stockout-chart")).not.toBeNull();
    expect(host.querySelectorAll(".sla-demand-bar").length).toBeGreaterThan(0);
    expect(host.querySelector(".sla-stockout-line")).not.toBeNull();
    expect(host.querySelector(".sla-order-q-marker")).not.toBeNull();
    expect(host.querySelector(".axis-y-left")).not.toBeNull();
    expect(host.querySelector(".axis-y-right")).not.toBeNull();
    expect(host.querySelector(".sla-stockout-legend")).not.toBeNull();
  });

  it("uses fixed x domain [0, 160] matching the order slider range", () => {
    expect(SLA_STOCKOUT_X_MAX).toBe(ORDER_Q_SLIDER_MIN_MAX);
    expect(SLA_STOCKOUT_X_MAX).toBe(160);

    const host = document.createElement("div");
    Object.defineProperty(host, "clientWidth", { value: 400, configurable: true });
    renderSlaStockoutChart(host, {
      curve: {
        candidates: [
          { q: 0, p_no_stockout: 0.1, p_stockout: 0.9 },
          { q: 200, p_no_stockout: 0.99, p_stockout: 0.01 },
        ],
      },
      orderQty: 80,
      demandVm: 2.5,
      demandSummary: null,
      schedule: null,
      episodeDay: 0,
    });

    const svg = host.querySelector("svg.sla-stockout-chart")!;
    expect(svg.getAttribute("data-x-max")).toBe("160");

    const tickTexts = [...svg.querySelectorAll(".axis-x text")].map(
      (el) => el.textContent,
    );
    expect(tickTexts).toContain("0");
    expect(tickTexts).toContain("160");

    const marker = svg.querySelector(".sla-order-q-marker")!;
    const x1 = Number(marker.getAttribute("x1"));
    const x2 = Number(marker.getAttribute("x2"));
    expect(x1).toBeCloseTo(x2, 5);
    // q=80 is midpoint of [0, 160] → marker near plot center (margin.left ≈ 40).
    expect(x1).toBeGreaterThan(130);
    expect(x1).toBeLessThan(210);
  });

  it("refreshSlaStockoutMarker moves marker without rebuilding chart", () => {
    const host = document.createElement("div");
    Object.defineProperty(host, "clientWidth", { value: 320, configurable: true });
    const curve = {
      candidates: [
        { q: 0, p_no_stockout: 0.1, p_stockout: 0.9 },
        { q: 24, p_no_stockout: 0.95, p_stockout: 0.05 },
      ],
    };
    renderSlaStockoutChart(host, {
      curve,
      orderQty: 8,
      demandVm: 2.5,
      demandSummary: null,
      schedule: null,
      episodeDay: 0,
    });
    const svg = host.querySelector("svg.sla-stockout-chart")!;
    const xBefore = svg.querySelector(".sla-order-q-marker")?.getAttribute("x1");
    refreshSlaStockoutMarker(host, 16, curve);
    expect(svg.querySelector(".sla-order-q-marker")?.getAttribute("data-order-q")).toBe(
      "16",
    );
    const xAfter = svg.querySelector(".sla-order-q-marker")?.getAttribute("x1");
    expect(Number(xAfter)).toBeGreaterThan(Number(xBefore));
  });
});
