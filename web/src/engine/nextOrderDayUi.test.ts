/**
 * T-086 RED: studio play chrome advances to next order day via step_n,
 * shows weekday + pipeline chrome, and mock mode shares the same semantics.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import { MockAdapter } from "../mock/adapter";
import type { ScheduleWire } from "./types";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(HERE, "../..");
const REPO_ROOT = join(WEB_ROOT, "..");
const MAIN_TS = join(WEB_ROOT, "src/main.ts");
const CONTROLS_TS = join(WEB_ROOT, "src/controls.ts");

const DEFAULT_SCHEDULE: ScheduleWire = {
  delivery_weekdays: [0, 2, 4],
  order_weekdays: [6, 1, 3],
  lead_time_days: 1,
  epoch: "2024-01-01",
};

describe("T-086 primary play advances via step_n to next order day", () => {
  it("main.ts primary onAdvance calls adapter.step_n (not only single-day step)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    const advance = src.match(/onAdvance\s*\([^)]*\)\s*\{[\s\S]*?\n\s*\},/);
    expect(advance, "expected onAdvance handler in main.ts").toBeTruthy();
    const body = advance![0]!;
    expect(body).toMatch(/adapter\.step_n\s*\(/);
    // Primary path must not be a lone single-day step.
    expect(body).not.toMatch(/^\s*onAdvance[\s\S]*?await\s+adapter\.step\s*\(/m);
    expect(body).not.toMatch(/const\s+delta\s*=\s*await\s+adapter\.step\s*\(/);
  });

  it("play chrome primary button labels next-order-day advance (not plain Advance day)", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).toMatch(/btn-advance|onAdvance/);
    // Prefer explicit next-order copy; reject the pre-CAL-C2 single-day label alone.
    expect(src).not.toMatch(/>\s*Advance day\s*</);
    expect(src).toMatch(/next\s*order|order\s*day|Advance to|Skip to/i);
  });

  it("optional single-day step remains available or is documented as omitted", () => {
    const controls = readFileSync(CONTROLS_TS, "utf8");
    const main = readFileSync(MAIN_TS, "utf8");
    const smokePath = join(REPO_ROOT, ".team/qa/T-086-smoke.md");
    const hasDebugControl = /btn-step-day|Advance one day|single-day|step one day/i.test(
      controls + main,
    );
    // Primary onAdvance must use step_n; a leftover adapter.step outside that
    // handler can count as the debug single-day path.
    const advance = main.match(/onAdvance\s*\([^)]*\)\s*\{[\s\S]*?\n\s*\},/);
    const advanceBody = advance?.[0] ?? "";
    const stepOutsideAdvance =
      /adapter\.step\s*\(/.test(main) && !/adapter\.step\s*\(/.test(advanceBody);
    const docsOmission =
      existsSync(smokePath) &&
      /single-day|one-day|optional.*step|omitted|debug/i.test(
        readFileSync(smokePath, "utf8"),
      );
    expect(
      hasDebugControl || stepOutsideAdvance || docsOmission,
      "keep a cheap single-day step control, or document why it was omitted in T-086-smoke.md",
    ).toBe(true);
  });
});

describe("T-086 weekday labels + pipeline hint in studio chrome", () => {
  it("play chrome / main surfaces weekday labels from schedule epoch", () => {
    const controls = readFileSync(CONTROLS_TS, "utf8");
    const main = readFileSync(MAIN_TS, "utf8");
    const blob = controls + main;
    // Avoid matching incidental substrings like ArrowDown's "dow".
    expect(blob).toMatch(/\bweekdayLabel\b|\bweekday_label\b|\bformatWeekday\b|\bday-label\b|\bweekday\b/i);
    expect(blob).toMatch(/2024-01-01|schedule\.epoch|epoch.*weekday|weekday.*epoch/i);
  });

  it("UI surfaces next delivery / pipeline hint consistent with LT=1", () => {
    const controls = readFileSync(CONTROLS_TS, "utf8");
    const main = readFileSync(MAIN_TS, "utf8");
    const blob = controls + main;
    expect(blob).toMatch(
      /pipeline|deliver|arrival|inbound|LT\s*=?\s*1|lead_time/i,
    );
    expect(blob).toMatch(
      /pipelineDeliveryHint|pipeline.?hint|delivery.?hint|next.?deliver/i,
    );
  });
});

describe("T-086 mock mode shares next-order advance semantics", () => {
  it("MockAdapter init exposes schedule stubs used to size step_n jumps", async () => {
    const adapter = new MockAdapter(42);
    const snap = await adapter.init({});
    expect(snap.schedule).toBeTruthy();
    expect(new Set(snap.schedule!.order_weekdays)).toEqual(
      new Set(DEFAULT_SCHEDULE.order_weekdays),
    );
    expect(snap.schedule!.lead_time_days).toBe(1);
    expect(String(snap.schedule!.epoch).startsWith("2024-01-01")).toBe(true);
  });

  it("mock adapter step_n with zeros-then-qty advances episode_day across skip days", async () => {
    const adapter = new MockAdapter(42);
    const snap = await adapter.init({});
    const start = snap.episode_day;
    const schedule = snap.schedule ?? {
      delivery_weekdays: [0, 2, 4],
      order_weekdays: [6, 1, 3],
      lead_time_days: 1,
      epoch: "2024-01-01",
    };
    const helperPath = existsSync(join(WEB_ROOT, "src/calendar/nextOrderAdvance.ts"))
      ? "../calendar/nextOrderAdvance.ts"
      : null;
    expect(helperPath).toBeTruthy();
    const mod = (await import(helperPath!)) as {
      buildStepNOrders: (
        day: number,
        qty: number,
        schedule: typeof schedule,
      ) => number[];
    };
    const orders = mod.buildStepNOrders(start, 16, schedule);
    const deltas = await adapter.step_n(orders);
    expect(deltas).toHaveLength(orders.length);
    const end = deltas[deltas.length - 1]!.episode_day;
    // DayDelta.episode_day is the completed day (EngineSession parity).
    expect(end).toBe(start + orders.length - 1);
    // Last day must be an order weekday under the mock schedule.
    const epoch = new Date(`${schedule.epoch}T00:00:00Z`);
    const endDate = new Date(epoch);
    endDate.setUTCDate(epoch.getUTCDate() + end);
    const weekday = (endDate.getUTCDay() + 6) % 7; // JS Sun=0 → monday0
    expect(schedule.order_weekdays).toContain(weekday);
  });

  it("studio mock path builds step_n orders (main wires helper or inline schedule math)", () => {
    const main = readFileSync(MAIN_TS, "utf8");
    expect(main).toMatch(/step_n\s*\(/);
    expect(main).toMatch(
      /buildStepNOrders|nextOrderDay|order_weekdays|schedule/,
    );
  });
});

describe("T-086 smoke: advance skips non-order days", () => {
  it("records a dedicated smoke note proving advance skips non-order days", () => {
    // Automated unit coverage lives in nextOrderAdvance.test.ts; this AC also
    // wants an explicit recorded check (screenshot note or checklist).
    const smokePath = join(REPO_ROOT, ".team/qa/T-086-smoke.md");
    expect(
      existsSync(smokePath),
      "expected .team/qa/T-086-smoke.md (screenshot note or playwright/unit checklist)",
    ).toBe(true);
    const text = readFileSync(smokePath, "utf8");
    expect(text).toMatch(/step_n|next order/i);
    expect(text).toMatch(/non-order|skip|intervening/i);
  });

  it("does not redefine OrderSchedule math in JS beyond consuming Snapshot fields", () => {
    // Scan studio UI sources — calendar helpers may consume order_weekdays+epoch,
    // but must not invent a second protection_days / frozen schedule type.
    const roots = [
      CONTROLS_TS,
      MAIN_TS,
      join(WEB_ROOT, "src/calendar"),
      join(WEB_ROOT, "src/engine"),
    ];
    const files: string[] = [];
    for (const root of roots) {
      if (!existsSync(root)) continue;
      // file or shallow dir listing via known test patterns
      if (root.endsWith(".ts")) files.push(root);
    }
    // Explicit helper candidates
    for (const rel of [
      "src/calendar/nextOrderAdvance.ts",
      "src/calendar/index.ts",
      "src/engine/nextOrderAdvance.ts",
    ]) {
      const p = join(WEB_ROOT, rel);
      if (existsSync(p)) files.push(p);
    }
    expect(
      files.length,
      "UI sources must exist for ADR 0111 no-redefine scan",
    ).toBeGreaterThan(0);

    const blob = files.map((f) => readFileSync(f, "utf8")).join("\n");
    // Hard ban: inventing protection interval formula in the studio path.
    expect(blob).not.toMatch(/protection_days\s*[:=]/);
    // Must not hardcode Sun/Tue/Thu without reading schedule wire fields.
    const hardcodedOrderSet =
      /order_weekdays\s*=\s*\[\s*6\s*,\s*1\s*,\s*3\s*\]/.test(blob) &&
      !/schedule\.order_weekdays|MOCK_SCHEDULE|ScheduleWire/.test(blob);
    expect(hardcodedOrderSet).toBe(false);
  });
});

describe("T-086 mock integration: spy proves zeros-on-skip + order-on-target", () => {
  it("advance helper + MockAdapter.step_n receives padded orders from schedule", async () => {
    // Prefer the real helper when implement lands it; until then this stays RED.
    const helperPath = [
      join(WEB_ROOT, "src/calendar/nextOrderAdvance.ts"),
      join(WEB_ROOT, "src/engine/nextOrderAdvance.ts"),
    ].find((p) => existsSync(p));
    expect(
      helperPath,
      "nextOrderAdvance helper required to build mock-mode step_n vectors",
    ).toBeTruthy();

    const mod = (await import(helperPath!)) as {
      buildStepNOrders: (
        day: number,
        qty: number,
        schedule: ScheduleWire,
      ) => number[];
    };
    const adapter = new MockAdapter(42);
    const snap = await adapter.init({});
    const spy = vi.spyOn(adapter, "step_n");
    const qty = 16;
    const orders = mod.buildStepNOrders(
      snap.episode_day,
      qty,
      snap.schedule ?? DEFAULT_SCHEDULE,
    );
    expect(orders.length).toBeGreaterThanOrEqual(1);
    expect(orders[orders.length - 1]).toBe(qty);
    expect(orders.slice(0, -1).every((q) => q === 0)).toBe(true);

    await adapter.step_n(orders);
    expect(spy).toHaveBeenCalledWith(orders);
    spy.mockRestore();
  });
});
