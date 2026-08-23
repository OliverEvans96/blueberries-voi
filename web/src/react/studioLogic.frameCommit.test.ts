/**
 * Atomic UI frame commits — generation guard and simulation-path wiring.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const LOGIC_TS = join(HERE, "studioLogic.ts");
const EVENTS_PANE_TS = join(HERE, "EventsPane.tsx");
const AUTOPILOT_LOOP_TS = join(HERE, "..", "autopilotLoop.ts");

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("commitFrame generation guard (atomic UI frames)", () => {
  const logicSrc = stripComments(readFileSync(LOGIC_TS, "utf8"));

  it("defines frameGen counter and commitFrame with stale-generation bail", () => {
    expect(logicSrc).toMatch(/let frameGen\s*=\s*0/);
    expect(logicSrc).toMatch(/async function commitFrame/);
    expect(logicSrc).toMatch(/const gen = \+\+frameGen/);
    expect(logicSrc).toMatch(/gen !== frameGen/);
    expect(logicSrc).toMatch(/fetchTradeoffForecast\(gen\)/);
    expect(logicSrc).toMatch(/fetchEvents\(gen\)/);
  });

  it("simulation paths coalesce into commitFrame (no refreshRemotePanes)", () => {
    expect(logicSrc).not.toMatch(/refreshRemotePanes/);
    expect(logicSrc).toMatch(/await commitFrame\(\)/);
  });

  it("fetchEvents does not paint mid-fetch", () => {
    const fetchEventsBody = logicSrc.match(
      /async function fetchEvents\(gen: number\)[^{]*\{([\s\S]*?)\n  \}/,
    )?.[1];
    expect(fetchEventsBody).toBeDefined();
    expect(fetchEventsBody).not.toMatch(/renderEventsPane/);
  });

  it("remote fetch helpers bail before mutating state when generation is stale", () => {
    expect(logicSrc).toMatch(
      /async function fetchTradeoffForecast\(gen: number\)[\s\S]*?if \(gen !== frameGen\) return;[\s\S]*?tradeoffForecasts/,
    );
    expect(logicSrc).toMatch(
      /async function fetchEvents\(gen: number\)[\s\S]*?if \(gen !== frameGen\) return;[\s\S]*?eventDays/,
    );
  });
});

describe("autopilot loop awaits async applyDelta", () => {
  const autopilotSrc = stripComments(readFileSync(AUTOPILOT_LOOP_TS, "utf8"));

  it("applyDelta may return a Promise and tick awaits it", () => {
    expect(autopilotSrc).toMatch(
      /applyDelta:\s*\(delta: DayDelta\)\s*=>\s*void \| Promise<void>/,
    );
    expect(autopilotSrc).toMatch(/await deps\.applyDelta\(delta\)/);
  });
});

describe("EventsPane temp chart layout timing", () => {
  const eventsPaneSrc = stripComments(readFileSync(EVENTS_PANE_TS, "utf8"));

  it("DeliveryTempChart uses useLayoutEffect for D3 paint", () => {
    expect(eventsPaneSrc).toMatch(/useLayoutEffect/);
    expect(eventsPaneSrc).not.toMatch(/useEffect\(\(\) => \{[\s\S]*?renderDeliveryTempMultiLot/);
  });
});
