# Abdella arrival model fit report (ADR 0148)

Generated: 2026-08-25T20:16:00Z

## Source

- Vendored parquet: `data/abdella/s{1..6}.parquet`
- Upstream: Abdella et al. 2021 / HF `NifferLi/cold-chain-strawberry-sensors`
- Fit script: `scripts/fit_abdella_arrival.py`
- Shipments in fit: **6**

## Fitted parameters (duration only)

| Field | Value | Method |
| --- | --- | --- |
| `abdella_all.d_min` | 1.852778 | delayed-gamma moments on six d |
| `abdella_all.delay_shape` | 3.008681 | delayed-gamma moments |
| `abdella_all.delay_scale` | 0.973726 | delayed-gamma moments |

Truncated-normal temperature fit is **retired** (v2 generative uses trip modes + hourly OU).

## Assumed thermal and break knobs (not fitted)

| Field | Value | Decision |
| --- | --- | --- |
| `thermal_modes` | cool/nominal/warm | Trip-wide cool/nominal/warm mode mix and offset_c values are ASSUMED (p_c=0.25, p_n=0.5, p_w=0.25; offsets -1.0/0.0/1.5 C). Tuned under rho=0 for phi_bar SD, not fit from six traces. |
| `sigma_hour` | 0.35 | Hourly OU amplitude (0.35 C) is ASSUMED for chart realism and rho=0 phi_bar scatter; not fit from six traces. |
| `T_break` | 12.0 | rho (breaks per transit-day), tau_bar (mean break duration, days), and T_break are ASSUMED, NOT FITTED. All six Abdella shipments are clean chains with no cold-chain break, so a break frequency is not estimable from this data at any confidence. rho=0.08 / tau_bar=0.5 / T_break=12 put a typical break at ~1.2 reference-days and the duration share of Var(log Lambda) at ~82%, versus 100% at rho=0. Treat these numbers as a documented modelling regime, not a measurement. |
| `rho` | 0.08 | assumed break rate (see breaks note) |
| `tau_bar` | 0.5 | assumed mean break duration (see breaks note) |
| `legs` | three named stages | Nominal stage setpoints and mean shares (w_k). ASSUMED anchors for clean-chain phi_bar centre (~1.36); not separately MLE-fit from n=6. |

Mode probabilities committed: cool p=0.25, nominal p=0.5, warm p=0.25.

## Other adjustment knobs (not refit by default)

| Knob | Committed | Decision |
| --- | --- | --- |
| `sigma_pos` | 0.08 | keep 0.08 (lognormal psi scale; not identified from n=6; probe temperature sd is not sigma_pos) |
| `gamma_shape` | 2.0 | keep gamma_shape=2.0, gamma_scale=0.03571428571428571 (MOD eta_ref=14.0 continuity; not identified from n=6) |
| `gamma_scale` | 0.03571428571428571 | tied to MOD shelf-life invariant |
| `reference_life_days` | 14.0 | literature eta_ref |
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
