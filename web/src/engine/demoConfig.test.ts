import { describe, expect, it } from "vitest";
import {
  ensureDemoShipments,
  hydrateRpcRequest,
  prepareDemoConfig,
  smokeCoolShipments,
} from "./demoConfig";

describe("demoConfig shipment hydrate", () => {
  it("defers to Rust mod21 when arrival_product is set and shipments absent", () => {
    const out = ensureDemoShipments({ arrival_product: "abdella_all" });
    expect(out.shipments).toBeUndefined();
    expect(out.arrival_product).toBe("abdella_all");
  });

  it("defers to Rust mod21 when arrival_product is set and shipments empty", () => {
    const out = ensureDemoShipments({
      arrival_product: "long_haul",
      shipments: [],
    });
    expect(out.shipments).toBeUndefined();
  });

  it("injects smoke cool only when neither shipments nor arrival_product", () => {
    const out = ensureDemoShipments({});
    expect(out.shipments).toEqual(smokeCoolShipments());
  });

  it("preserves explicit non-empty shipments", () => {
    const explicit = [{ times_d: [0, 1], temps_c: [2, 2] }];
    const out = ensureDemoShipments({
      arrival_product: "abdella_all",
      shipments: explicit,
    });
    expect(out.shipments).toEqual(explicit);
  });

  it("hydrateRpcRequest init leaves shipments unset for studio default config", () => {
    const req = hydrateRpcRequest({
      method: "init",
      params: {
        config: prepareDemoConfig({
          arrival_product: "abdella_all",
          obs_scenario: "P1",
        }),
      },
    }) as { params: { config: Record<string, unknown> } };
    expect(req.params.config.arrival_product).toBe("abdella_all");
    expect(req.params.config.shipments).toBeUndefined();
  });
});
