# M2.5 figures

Generative FIL-11 Stage C (ADR 0088 / T-012), multi-rung Stage A (T-016), and
Stage B / oracle ladder (T-017) publication figures.

## Stage A multi-rung (FIL-11) — figure → rung map

Shared-CRN Stage A contraction across data-availability rungs. Metric is
**cohort-from-birth** arrival-age SD (newest birth slot), not oldest-slot-only.
P0/P1 FAIL is allowed if documented; F2a/F2 are expected to PASS (F2a contracts
under smoke once sim emits `pack_date` — T-019).

| Figure | Rung(s) | FIL-11 role |
| --- | --- | --- |
| `m25_stage_a_rung_map.png` | P0, P1, F1, F1s, F2a, F2 (all six) | Stage A prior vs posterior SD bar map |
| (optional per-rung exports) | P0 | Stage A books-only |
| (optional per-rung exports) | P1 | Stage A shrink-gun totals |
| (optional per-rung exports) | F1 | Stage A lot-resolved sales |
| (optional per-rung exports) | F1s | Stage A lot-resolved shrink |
| (optional per-rung exports) | F2a | Stage A ASN pack-date prior |
| (optional per-rung exports) | F2 | Stage A age-at-receipt prior |

Regenerate the Stage A rung map:

```bash
uv sync --all-extras
uv run python -c "from blueberries_voi.viz.m25 import run_m25_stage_a; run_m25_stage_a()"
```

Short result MD: `experiments/m25_stage_a_result.md`.

## Stage B multi-rung + oracle ladder (FIL-11) — figure → rung map

Shared-CRN Stage B calibration (90% CI coverage + rank histograms) per
data-availability rung. A-failing rungs are **diagnostic only**. The oracle
ladder plots mean abs age error vs the B-state ceiling (belief ≡ true `(n, τ)`).

| Figure | Rung(s) | FIL-11 role |
| --- | --- | --- |
| `m25_stage_b_P0_rank.png` | P0 | Stage B rank hist (diagnostic if A fail) |
| `m25_stage_b_P1_rank.png` | P1 | Stage B rank hist (diagnostic if A fail) |
| `m25_stage_b_F1_rank.png` | F1 | Stage B calibration ranks |
| `m25_stage_b_F1s_rank.png` | F1s | Stage B calibration ranks |
| `m25_stage_b_F2a_rank.png` | F2a | Stage B calibration ranks |
| `m25_stage_b_F2_rank.png` | F2 | Stage B calibration ranks |
| `m25_oracle_ladder_gap.png` | P1, F2 (default compare) | Oracle ladder vs B-state |

Regenerate Stage B + oracle smoke artifacts:

```bash
uv sync --all-extras
uv run python -c "
from blueberries_voi.viz.m25 import run_m25_stage_b, run_m25_oracle_ladder
run_m25_stage_b(
    root_seed=0,
    stage_a_pass={'F2a': True, 'F2': True},
    write_md=True,
)
run_m25_oracle_ladder(root_seed=0, write_figure=True)
"
```

Short result MD (coverage + diagnostic labels + gap table):
`experiments/m25_stage_b_result.md`.

## How to regenerate Stage C

```bash
uv sync --all-extras
uv run python experiments/fil11_c.py
```

Writes:

| Artifact | Path |
| --- | --- |
| Stage C figure | `figures/m2.5/fil11_stage_c_generative.png` |
| Short result MD | `experiments/fil11_stage_c_result.md` |

## Stage C gate (generative)

Pass means the production observation model (shared `day_step` kernels used by
the MC LL) matches simulator `day_step` under paired CRN within documented TV
tolerance (default `0.05`) on discrete P1 sales/waste pairs. Support must be
non-degenerate (`n_support > 1`). Injected wrong physics (soft powers /
hazard*dt) must fail. The M1 soft `tv_vs_exact` self-check is **not** the
production gate.
