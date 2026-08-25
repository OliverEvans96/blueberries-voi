/**
 * Freshness×time chart palette — OKLab-informed, hue-partitioned for the full stack.
 *
 * ## Layers
 * 1. **Belief heatmap** — green sequential (hue 144–165°), encodes mass density.
 * 2. **Truth trajectories** — warm orange (hue ~41°), continuous alive paths.
 * 3. **Terminal dots** — categorical exits on hue arc outside the green band:
 *    sold cyan (~222°), spoiled fuchsia (~323°).
 *
 * ## Design constraints (grid-searched on OKLab approx ΔE ×100)
 * - sold↔spoiled was ΔE≈13 / Δhue≈29° (#1d4ed8 vs #7c3aed) → confusable at r≈1.25px.
 * - Chosen triple min pairwise ΔE≈29.7, min Δhue≈84.7° on #f97316 / #0891b2 / #c026d3.
 * - Trajectory orange kept off red/spoil axis (>80° from fuchsia).
 * - Sold cyan separates from heatmap dark green (ΔE≈19 vs #2f5d4a) and truth orange (#f97316).
 *
 * Paper reference: Björn Ottosson OKLab (2020); hues verified with in-repo OKLab helper + pytest/vitest.
 */

/** Belief bar / UI accent (matches --belief). */
export const BELIEF_BAR_COLOR = "#2f5d4a";

/** Soft belief fill (matches --belief-soft). */
export const BELIEF_BAR_SOFT = "#9bbf9a";

/** Truth histogram / overlay bar (matches --truth). */
export const TRUTH_BAR_COLOR = "#f97316";

/** Strong truth UI chrome (matches --truth-strong). */
export const TRUTH_UI_STRONG = "#c2410c";

/** Belief mass heatmap stops (light → dark, green sequential). */
export const BELIEF_HEATMAP_STOPS = [
  "#f3efe6",
  "#9bbf9a",
  "#2f5d4a",
  "#17362c",
] as const;

/** Studio paper background (for contrast checks). */
export const CHART_PAPER = "#f7f2e8";

/** Alive unit trajectory stroke (orange-500, OKLCH ≈ L0.68 C0.19 h41°). */
export const TRUTH_TRAJECTORY_STROKE = "#f97316";

/** Unit sold terminal (cyan-600, OKLCH ≈ L0.61 C0.11 h222°). */
export const UNIT_TERMINAL_SOLD = "#0891b2";

/** Unit spoiled terminal (fuchsia-600, OKLCH ≈ L0.59 C0.26 h323°). */
export const UNIT_TERMINAL_SPOILED = "#c026d3";

/** Subtle ring so 1.25px terminals survive on dark heatmap cells. */
export const TERMINAL_DOT_STROKE = "rgba(28, 36, 32, 0.45)";

export const TRUTH_OVERLAY_PALETTE = {
  alive: TRUTH_TRAJECTORY_STROKE,
  sold: UNIT_TERMINAL_SOLD,
  spoiled: UNIT_TERMINAL_SPOILED,
} as const;

export type TruthOverlayRole = keyof typeof TRUTH_OVERLAY_PALETTE;

/** sRGB hex → OKLab (Björn Ottosson, 2020). */
export function hexToOklab(hex: string): { L: number; a: number; b: number } {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  const lin = (c: number) =>
    c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  const lr = lin(r);
  const lg = lin(g);
  const lb = lin(b);
  const l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb;
  const m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb;
  const s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb;
  const l_ = l > 0 ? l ** (1 / 3) : 0;
  const m_ = m > 0 ? m ** (1 / 3) : 0;
  const s_ = s > 0 ? s ** (1 / 3) : 0;
  const L = 0.2104542553 * l_ + 0.793617785 * m_ - 0.0040720468 * s_;
  const a = 1.9779984951 * l_ - 2.428592205 * m_ + 0.4505937099 * s_;
  const b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.808675766 * s_;
  return { L, a, b: b2 };
}

/** Approximate OKLab distance (×100, comparable to rough ΔE scale). */
export function oklabDistance(hexA: string, hexB: string): number {
  const a = hexToOklab(hexA);
  const b = hexToOklab(hexB);
  return Math.hypot(a.L - b.L, a.a - b.a, a.b - b.b) * 100;
}

export function oklabHueDegrees(hex: string): number {
  const { a, b } = hexToOklab(hex);
  const h = (Math.atan2(b, a) * 180) / Math.PI;
  return h < 0 ? h + 360 : h;
}

export function minHueSeparationDegrees(hexes: readonly string[]): number {
  const hues = hexes.map(oklabHueDegrees);
  let min = 360;
  for (let i = 0; i < hues.length; i++) {
    for (let j = i + 1; j < hues.length; j++) {
      const d = Math.abs(hues[i]! - hues[j]!);
      min = Math.min(min, d, 360 - d);
    }
  }
  return min;
}

export function minOklabDistance(hexes: readonly string[]): number {
  let min = Infinity;
  for (let i = 0; i < hexes.length; i++) {
    for (let j = i + 1; j < hexes.length; j++) {
      min = Math.min(min, oklabDistance(hexes[i]!, hexes[j]!));
    }
  }
  return min;
}
