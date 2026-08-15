/**
 * T-116 RED: missed-sales (stockout) marginal — source contracts on
 * marginals.ts (kind union, shared yMax, upward bars, no x-axis).
 * Node vitest has no jsdom; do not assert D3 pixels.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const MARGINALS_TS = join(HERE, "marginals.ts");

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

function signatureBlock(src: string, name: string): string {
  const re = new RegExp(
    `export\\s+function\\s+${name}\\s*\\(([\\s\\S]*?)\\)\\s*(?::\\s*[^{]+)?\\{`,
  );
  const m = src.match(re);
  expect(m, `expected export function ${name}(...)`).toBeTruthy();
  return m![1] ?? "";
}

describe("MarginalKind stockout (T-116)", () => {
  const src = stripComments(readFileSync(MARGINALS_TS, "utf8"));

  it('exported MarginalKind includes "stockout"', () => {
    const typeBlock = src.match(
      /export\s+type\s+MarginalKind\s*=([\s\S]*?);/,
    )?.[1];
    expect(typeBlock, "expected exported MarginalKind type alias").toBeDefined();
    expect(typeBlock).toMatch(/"sales"/);
    expect(typeBlock).toMatch(/"spoilage"/);
    expect(typeBlock).toMatch(/"stockout"/);
  });

  it("exports marginalYMax(history)", () => {
    expect(src).toMatch(/export\s+function\s+marginalYMax\s*\(/);
    const params = signatureBlock(src, "marginalYMax");
    expect(params).toMatch(/history/);
    expect(params).not.toMatch(/ghost/);
    expect(src).toMatch(/sales_total/);
    expect(src).toMatch(/\.stockout/);
  });

  it("renderMarginal accepts optional yMax", () => {
    const params = signatureBlock(src, "renderMarginal");
    expect(params).toMatch(/\bkind\b/);
    expect(params).not.toMatch(/\bghost\b/);
    expect(params).toMatch(/\byMax\s*\?/);
  });
});

describe("renderMarginal stockout mapping and geometry (T-116)", () => {
  const src = stripComments(readFileSync(MARGINALS_TS, "utf8"));

  it("kind stockout maps d.stockout (not waste_total as the stockout value)", () => {
    expect(src).toMatch(/kind\s*===\s*"stockout"/);
    expect(src).toMatch(/d\.stockout/);
    const valuesBlock = src.match(
      /const\s+values\s*=\s*history\.map\(([\s\S]*?)\);/,
    )?.[1];
    expect(valuesBlock, "expected history.map values selector").toBeDefined();
    expect(valuesBlock).toMatch(/stockout/);
    expect(valuesBlock).not.toMatch(
      /kind\s*===\s*"stockout"[\s\S]{0,40}waste_total/,
    );
  });

  it("stockout bar geometry is upward like sales (yScale(v) / innerH - y), not y=0 like spoilage", () => {
    const barJoin = src.match(
      /selectAll\(\s*"\.bar"\s*\)([\s\S]*?)\.call\(\s*\(sel\)/,
    )?.[1];
    expect(barJoin, "expected .bar data join").toBeDefined();
    expect(barJoin).toMatch(/stockout/);
    expect(barJoin).toMatch(/d\.stockout/);
    expect(barJoin).toMatch(/y\s*\(\s*v\s*\)/);
    expect(barJoin).toMatch(/innerH\s*-\s*y\s*\(\s*v\s*\)/);
    expect(barJoin).toMatch(/kind\s*===\s*"spoilage"|waste_total/);
  });


  it('no .axis-x for stockout; kind === "spoilage" still has x axis', () => {
    expect(src).toMatch(/kind\s*===\s*"stockout"/);
    expect(src).toMatch(/kind\s*===\s*"spoilage"/);
    expect(src).toMatch(/axis-x/);
    const axisGate = src.match(
      /if\s*\(\s*kind\s*===\s*"spoilage"\s*\)\s*\{([\s\S]*?)axis-x([\s\S]*?)\n\}/,
    );
    expect(
      axisGate,
      "expected axis-x only inside kind === spoilage",
    ).toBeTruthy();
    expect(src).not.toMatch(/kind\s*===\s*"stockout"[\s\S]{0,200}axis-x/);
  });

  it("sales and stockout use shared yMax when passed (Math.max(1, yMax))", () => {
    expect(src).toMatch(/yMax/);
    expect(src).toMatch(
      /kind\s*===\s*"sales"[\s\S]{0,120}stockout|kind\s*===\s*"stockout"[\s\S]{0,120}sales/,
    );
    expect(src).toMatch(/Math\.max\s*\(\s*1\s*,\s*yMax\s*\)/);
  });
});
