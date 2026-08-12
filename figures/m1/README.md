# M1 figures

Committed static figures for Gate 0, simulator diagnostics, FIL-13 bakeoff, and FIL-11
validation (ENG-03 / X-10).

## How to regenerate

```bash
uv sync --all-extras
uv run python experiments/gate0.py
uv run python experiments/cohort_count.py
uv run python experiments/fil13_bakeoff.py
uv run python experiments/fil11_a.py
# Stage A failed; B/C below are diagnostic-only (Oliver requested post-A-fail):
uv run python experiments/fil11_b.py
uv run python experiments/fil11_c.py
```

## Map

| Figure | Decision / ticket |
| --- | --- |
| `gate0_variance.png` | X-13 Gate 0a / T-003 |
| `gate0_caseround.png` | X-13 Gate 0b / T-003 |
| `cohort_count.png` | T-004 / SIM-04 |
| `fil13_runtime.png` | FIL-13 / T-005 |
| `fil11_contraction.png` | FIL-11 Stage A / T-007 (**FAIL**) |
| `fil11_calibration.png` | FIL-11 Stage B / T-007 (diagnostic after A fail) |
| `fil11_exact.png` | FIL-11 Stage C / T-007 (diagnostic after A fail) |
