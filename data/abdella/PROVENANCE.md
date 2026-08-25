# Abdella transit traces — provenance

## Source

- Hugging Face dataset: `NifferLi/cold-chain-strawberry-sensors`
- Files: `data/s{1..6}-00000-of-00001.parquet` → vendored as `s{1..6}.parquet`
- Fetched: 2026-08-12
- License: CC BY 4.0 (see `LICENSE`)

## Upstream scientific source

Abdella, A., Brecht, J. K., & Uysal, I. (2021). Statistical and temporal analysis
of a novel multivariate time series data for food engineering. *Journal of Food
Engineering*, 298, 110477. https://doi.org/10.1016/j.jfoodeng.2021.110477
(arXiv:2103.12895)

## Processing in this repo

1. Lot-average temperature across the nine probe positions (NaNs ignored per
   timestamp; small gaps forward-filled).
2. Clip each shipment to the **published harvest→end-of-chain duration** from
   Abdella Table 2 (approx. 2.0–6.6 days). The Hugging Face release spans are
   longer (~14–22 calendar days) and appear to include post-arrival monitoring;
   using the published windows keeps MOD-21 / Gate 0 aligned with the paper mix.
3. Within that window, begin the Arrhenius integral at the **first sample with
   lot-mean T < 10 °C** (start of the refrigerated leg). Warm harvest spikes
   before precool otherwise dominate effective age and push τ far above the
   FIL-15 grid [0, 8].
4. No synthetic temperature paths. If a file is missing, loaders raise
   `FileNotFoundError` and stop.

## Published durations used for clipping (days)

| Shipment | Duration |
| --- | --- |
| S1 | 6d 9h 28m |
| S2 | 2d 1h 9m |
| S3 | 6d 9h 25m |
| S4 | 5d 12h 5m |
| S5 | 6d 14h 53m |
| S6 | 4d 4h 35m |

## `arrival_model.json` (T-150 / ADR 0148)

Offline **fit** from vendored parquet into the hierarchical arrival law (ADR 0144).
Runtime loads only the committed JSON (`include_str!` in Rust); production paths do
**not** read parquet.

| Step | Command |
| --- | --- |
| Fit artifact + report | `uv sync --extra data --extra viz && uv run python scripts/fit_abdella_arrival.py` |
| Overlay only | `uv run python scripts/arrival_calibration_note.py` |

Outputs: `arrival_model.json`, `fit_report.md`, `calibration_note.md`,
`arrival_calibration_overlay.png`.

**Fitted:** corridor duration gammas, `mu_T`, `sigma_T` (moment match on n=6).
**Adjustment knobs (not refit by default):** `gamma_shape`, `gamma_scale`,
`reference_life_days`, `q10`, `T_ref`, `sigma_pos` — see `fit_report.md`.

The six shipments are far too few to **validate** the families; the fit automates
moment matching, not MLE proof. Arrival freshness remains an **upper bound** on the
refrigerated leg (field heat excluded).

| Field | Window / meaning |
| --- | --- |
| `d` (duration) | Refrigerated leg only: first lot-mean **T < 10 °C** through published Table 2 clip. |
| `phi_bar` | Arrhenius mean temperature factor on that same leg. |
| `sigma_pos` | Lognormal within-pallet multiplier (literature default; not probe-temp sd). |

See `data/abdella/fit_report.md` and `data/abdella/calibration_note.md`.
