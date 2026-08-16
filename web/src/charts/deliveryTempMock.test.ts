/**
 * T-127 (events implement): delivery temp mock chart — seeded curve + D3 render.
 */
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import {
  generateDeliveryTempHistory,
  renderDeliveryTempHistory,
  renderDeliveryTempHistorySvg,
  seedForDeliveryTemp,
} from "./deliveryTempMock";

describe("deliveryTempMock (T-127 events)", () => {
  it("seedForDeliveryTemp is stable for (day, lot_id)", () => {
    expect(seedForDeliveryTemp(3, 101)).toBe(seedForDeliveryTemp(3, 101));
    expect(seedForDeliveryTemp(3, 101)).not.toBe(seedForDeliveryTemp(4, 101));
    expect(seedForDeliveryTemp(3, 101)).not.toBe(seedForDeliveryTemp(3, 102));
  });

  it("generateDeliveryTempHistory is deterministic and bounded", () => {
    const a = generateDeliveryTempHistory(5, 42);
    const b = generateDeliveryTempHistory(5, 42);
    expect(a).toEqual(b);
    expect(a.length).toBeGreaterThan(3);
    for (const p of a) {
      expect(p.temp).toBeGreaterThanOrEqual(0.5);
      expect(p.temp).toBeLessThanOrEqual(6);
      expect(p.t).toBeGreaterThanOrEqual(0);
      expect(p.t).toBeLessThanOrEqual(1);
    }
  });

  it("renderDeliveryTempHistorySvg draws line path", () => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    const data = generateDeliveryTempHistory(2, 7);
    renderDeliveryTempHistorySvg(svg, data);
    expect(svg.querySelector(".delivery-temp-line, [data-series='temp']")).not.toBeNull();
    expect(svg.querySelector(".delivery-temp-baseline")).not.toBeNull();
  });

  it("renderDeliveryTempHistory mounts into host element", () => {
    const host = document.createElement("div");
    renderDeliveryTempHistory(host, 1, 99);
    expect(host.querySelector("svg")).not.toBeNull();
    expect(host.querySelector(".delivery-temp-line, [data-series='temp']")).not.toBeNull();
  });
});
