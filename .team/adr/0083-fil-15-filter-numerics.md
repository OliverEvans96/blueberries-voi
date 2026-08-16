# 0083. FIL-15: Filter numerics — production grid / N / ESS

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-15
GROUP: FIL
PROVENANCE: newly-raised; settled with FIL-13=E at measured L
TIER: 3
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

FIL-03=A specifies a fixed uniform grid over a truncated age range without truncation points or K.
FIL-05=A specifies a fixed particle count and ESS-triggered systematic resampling without numeric N
or threshold. FIL-13 settled on **full joint (E)** because empirical L≤3 makes `K^L` cheap.

## Decision

Production numerics for M1 ResearchParticleFilter (full_joint at measured L):

| Parameter | Production value | Note |
| --- | --- | --- |
| Arrival-age grid range | **[0, 8]** effective days | Covers MOD-21 ~2–6.6 d bootstrap with headroom |
| Grid points **K** | **8** | `8^3·2000 ≈ 1e6` floats ≪ budget |
| Particle count **N** | **2000** | Ratified interim proposal |
| ESS resample threshold | **N/2** | FIL-05=A |

If L grows and the memory guard fires, revisit toward sliding_window and possibly smaller K.

## Alternatives considered

- **K=4** — rejected as production default; bakeoff still probes K∈{4,8}.
- **N=500** — rejected for production calibration thickness.
- **Keep PROPOSED** — rejected once FIL-13 settled.

## Consequences

- `blueberries_voi.filter.constants` exports matching `PRODUCTION_*` constants.
- Boundary-pile tests should watch mass at 0 and 8.

**Depends on:** `FIL-03`, `FIL-05`, `FIL-13`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
