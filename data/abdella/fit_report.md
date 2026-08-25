# Abdella arrival model fit report (ADR 0148)

Generated: 2026-08-25T20:16:00Z

## Source

- Vendored parquet: `data/abdella/s{1..6}.parquet`
- Upstream: Abdella et al. 2021 / HF `NifferLi/cold-chain-strawberry-sensors`
- Fit script: `scripts/fit_abdella_arrival.py`
- Shipments in fit: **6**

## Fitted parameters

| Field | Value | Method |
| --- | --- | --- |
| `mu_T` | 2.781762 | mean T from shipment phi_bar via Q10 |
| `sigma_T` | 0.527213 | sd T across six shipments |
| `sigma_pos` | 0.08 | keep 0.08 (lognormal psi scale; not identified from n=6; probe temperature sd is not sigma_pos) |
| `abdella_all.d_min` | 1.852778 | delayed-gamma moments on six d |
| `abdella_all.delay_shape` | 3.008681 | delayed-gamma moments |
| `abdella_all.delay_scale` | 0.973726 | delayed-gamma moments |

## Adjustment knobs (not refit by default)

| Knob | Committed | Decision |
| --- | --- | --- |
| `gamma_shape` | 2.0 | keep gamma_shape=2.0, gamma_scale=0.03571428571428571 (MOD eta_ref=14.0 continuity; not identified from n=6) |
| `gamma_scale` | 0.03571428571428571 | tied to MOD shelf-life invariant |
| `reference_life_days` | 14.0 | literature eta_ref continuity |
| `q10` | 3.0 | ModelParams / ADR 0008 default |
| `T_ref` | 0.0 | ADR 0041 convention |

## Honesty

- n=6 shipments **do not validate** the parametric families; fit automates moment
  matching, not proof of model correctness.
- Strawberry logger substitution; refrigerated-leg-only window; arrival f is an
  **upper bound** (field heat excluded).

## Empirical summaries

| shipment | d_days | phi_bar |
| --- | --- | --- |
| S1 | 4.604 | 1.318 |
| S2 | 1.903 | 1.287 |
| S3 | 6.243 | 1.355 |
| S4 | 5.347 | 1.433 |
| S5 | 6.514 | 1.286 |
| S6 | 4.083 | 1.478 |

Overlay: `data/abdella/arrival_calibration_overlay.png`

Re-run: `uv sync --extra data --extra viz && uv run python scripts/fit_abdella_arrival.py`
