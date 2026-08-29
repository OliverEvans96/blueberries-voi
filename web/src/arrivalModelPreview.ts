/**
 * Closed-form arrival Λ helpers for Preview-tier lottery charts.
 * Constants mirror `data/abdella/arrival_model.json` (schema 3).
 */
import type { ArrivalProduct } from "./types";

const Q10 = 2.0;
const T_REF = 0.0;
const T_BREAK = 12.0;
const TAU_BAR = 0.5;
const LAMBDA_FLOOR = 1e-6;

const LEGS = [
  { weight: 0.15, setpoint_c: 0.35 },
  { weight: 0.6, setpoint_c: 2.58 },
  { weight: 0.25, setpoint_c: 4.32 },
] as const;

const THERMAL_MODES = {
  cool: { offset_c: -0.12, p: 0.1 },
  nominal: { offset_c: 0.0, p: 0.8 },
  warm: { offset_c: 0.22, p: 0.1 },
} as const;

type CorridorKey = "abdella_all" | "short_haul" | "long_haul";

const CORRIDORS: Record<
  CorridorKey,
  { d_min: number; delay_shape: number; delay_scale: number }
> = {
  short_haul: { d_min: 1.802778, delay_shape: 2.0, delay_scale: 0.05 },
  long_haul: { d_min: 4.033333, delay_shape: 1.628384, delay_scale: 0.81369 },
  abdella_all: { d_min: 1.852778, delay_shape: 3.008681, delay_scale: 0.973726 },
};

const ABDELLA_MIX = [
  { corridor: "short_haul" as const, weight: 0.627 },
  { corridor: "long_haul" as const, weight: 0.373 },
];

const INTEGER_DAYS = [2, 3, 4, 5, 6, 7] as const;

export function phi(tC: number, q10 = Q10, tRef = T_REF): number {
  return Math.pow(q10, (tC - tRef) / 10);
}

export function phiSetFromLegs(biasC = 0, q10 = Q10, tRef = T_REF): number {
  return LEGS.reduce((acc, leg) => acc + leg.weight * phi(leg.setpoint_c + biasC, q10, tRef), 0);
}

export function phiSetForThermalMode(
  mode: keyof typeof THERMAL_MODES,
  biasC = 0,
  q10 = Q10,
  tRef = T_REF,
): number {
  return phiSetFromLegs(biasC + THERMAL_MODES[mode].offset_c, q10, tRef);
}

export function phiBreak(q10 = Q10, tRef = T_REF): number {
  return phi(T_BREAK, q10, tRef);
}

export function breakExposureRate(phiSet: number, phiBrk: number): number {
  return Math.max(phiBrk - phiSet, 0);
}

export function lambdaClean(d: number, phiSet: number): number {
  return Math.max(d * phiSet, LAMBDA_FLOOR);
}

export function lambdaBreakDelta(
  nBreaks: number,
  tauBar: number,
  phiSet: number,
  phiBrk: number,
): number {
  return nBreaks * tauBar * breakExposureRate(phiSet, phiBrk);
}

function lnGamma(x: number): number {
  if (x <= 0) return NaN;
  const cof = [
    76.18009172947146, -86.50532032941677, 24.01409824083091,
    -1.231739572450155, 0.001208650973866179, -0.000005395239385495,
  ];
  let y = x;
  let tmp = x + 5.5;
  tmp -= (x + 0.5) * Math.log(tmp);
  let ser = 1.000000000190015;
  for (let j = 0; j < cof.length; j += 1) {
    y += 1;
    ser += cof[j]! / y;
  }
  return -tmp + Math.log((2.506628274631 * ser) / x);
}

function gammaPdf(x: number, shape: number, scale: number): number {
  if (x <= 0) return 0;
  const logNorm = shape * Math.log(scale) + lnGamma(shape);
  return Math.exp((shape - 1) * Math.log(x) - x / scale - logNorm);
}

function gammaCdf(x: number, shape: number, scale: number): number {
  if (x <= 0) return 0;
  const steps = 128;
  const hi = Math.max(x, shape * scale * 6);
  const dx = hi / steps;
  let acc = 0;
  for (let i = 1; i <= steps; i += 1) {
    const t = i * dx;
    if (t > x) break;
    const w = i === steps || t + dx > x ? (x - (i - 1) * dx) / dx : 1;
    acc += gammaPdf(t, shape, scale) * dx * w;
  }
  return Math.min(1, Math.max(0, acc));
}

export function durationPmfIntegerDays(corridorKey: CorridorKey): Record<number, number> {
  const corridor = CORRIDORS[corridorKey];
  const probs: Record<number, number> = {};
  for (const k of INTEGER_DAYS) {
    const lo = Math.max(k - 0.5 - corridor.d_min, 0);
    const hi = k + 0.5 - corridor.d_min;
    probs[k] =
      gammaCdf(hi, corridor.delay_shape, corridor.delay_scale) -
      gammaCdf(lo, corridor.delay_shape, corridor.delay_scale);
  }
  const total = INTEGER_DAYS.reduce((s, k) => s + (probs[k] ?? 0), 0);
  const out: Record<number, number> = {};
  for (const k of INTEGER_DAYS) {
    out[k] = total > 0 ? (probs[k] ?? 0) / total : 0;
  }
  return out;
}

function blendPmfs(
  a: Record<number, number>,
  b: Record<number, number>,
  wA: number,
  wB: number,
): Record<number, number> {
  const out: Record<number, number> = {};
  for (const k of INTEGER_DAYS) {
    out[k] = wA * (a[k] ?? 0) + wB * (b[k] ?? 0);
  }
  return out;
}

export function durationPmfForProduct(product: ArrivalProduct): Record<number, number> {
  if (product === "abdella_mix") {
    return blendPmfs(
      durationPmfIntegerDays("short_haul"),
      durationPmfIntegerDays("long_haul"),
      ABDELLA_MIX[0]!.weight,
      ABDELLA_MIX[1]!.weight,
    );
  }
  if (product === "short_haul") return durationPmfIntegerDays("short_haul");
  if (product === "long_haul") return durationPmfIntegerDays("long_haul");
  return durationPmfIntegerDays("abdella_all");
}

export function expectedDurationDays(product: ArrivalProduct): number {
  const pmf = durationPmfForProduct(product);
  return INTEGER_DAYS.reduce((s, k) => s + k * (pmf[k] ?? 0), 0);
}

export function poissonPmf(mu: number, maxN = 4): number[] {
  const out: number[] = [];
  for (let n = 0; n <= maxN; n += 1) {
    if (n === 0) {
      out.push(Math.exp(-mu));
      continue;
    }
    out.push((out[n - 1]! * mu) / n);
  }
  const tail = 1 - out.reduce((a, b) => a + b, 0);
  if (tail > 1e-9) out[maxN] = (out[maxN] ?? 0) + tail;
  return out;
}

export const ARRIVAL_PREVIEW_DEFAULTS = {
  q10: Q10,
  tRef: T_REF,
  tauBar: TAU_BAR,
  integerDays: INTEGER_DAYS,
  thermalModes: THERMAL_MODES,
} as const;
