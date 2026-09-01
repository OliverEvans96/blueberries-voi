# 0140. F3 count-bias guard and contrast-sensitive spoilage scoring (Stage B)

STATUS: PROPOSED
DATE: 2026-08-21
TICKET: T-139
RELATED: [0137](./0137-observed-lot-segmentation-and-exact-spoilage-likelihood.md),
[0139](./0139-heterogeneous-arrivals-within-lot-dispersion.md) (Stage A dispersion),
T-138 AC-12 drift guard (P1/F2a pass; F3 deferred)

## Context

Stage A (T-138) added within-lot aleatoric birth dispersion while keeping ADR 0137
shared-decrement spoilage scoring. Homogeneous-fleet diagnostics show **P1** and **F2a**
alive-count bias stable when `arrival_dispersion_sd` increases from 0 to 0.05, but **F3**
(temperature-history observation channel) exhibits ~0.36 absolute count bias drift — violating
the conservation contract in ADR 0139 consequences.

ADR 0139 explicitly deferred **cross-lot sales allocation and contrast weighting** to Stage B
once heterogeneous births are baseline.

## Decision

**Stage B (T-139)** will:

1. **Fix F3 count bias under dispersion** — audit the F3 mask path, filter birth row
   extension, and belief export so expected alive mass matches truth after dispersed births;
   restore F3 in AC-12 drift guard with the same relative bound as P1/F2a.

2. **Introduce a documented contrast hook** — add `contrast_spoilage_weight` (name provisional)
   in `unit_ll` / `unit_pf` that scales per-lot decrement evidence by within-lot freshness
   spread when `arrival_dispersion_sd > 0`, defaulting to **1.0** (no effect) at sd=0 and for
   channels that do not use spoilage intervals.

3. **Preserve sd=0 parity** — VOI CRN seven-scenario profits at seed `1` remain within `1e-6` of
   T-138 baseline when `arrival_dispersion_sd = 0`.

4. **Close coverage gap** — raise Python package coverage to ≥80% with targeted tests on
   filter/belief paths uncovered after T-138 (79.45% remediate tip).

## Alternatives considered

- **Relax AC-12 for F3 only** — rejected. F3 is a production observation channel; drift
  indicates a structural mismatch, not acceptable aleatoric noise.

- **Disable dispersion when F3 active** — rejected. Breaks scenario orthogonality (ADR 0133).

- **Rewrite spoilage likelihood (full Stage B from 0137 roadmap)** — deferred. Stage B starts
  with count conservation + hook; full contrast form change needs measured LGTIN gains first.

## Consequences

- F3 re-enters AC-12 guard; T-138 spec footnote on F3 deferral superseded.
- Contrast hook is public Rust API — Python/tests may grep export name; behaviour off at sd=0.
- Possible small ESS shift when contrast weighting enabled; monitor in `lgtin_upc_diag`.
- T-140 (multi-lot delivery) remains blocked until Stage B count bias is green.
