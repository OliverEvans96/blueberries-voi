# Abdella arrival calibration note

Parameters in `arrival_model.json` are **fitted offline** from six Abdella shipments
(`scripts/fit_abdella_arrival.py`). The data **does not validate** the assumed families;
with only six corridors, treat numbers as defensible starting points, not MLE proof.

Duration corridors are moment-matched on six `d_i`. **thermal_modes**, **sigma_hour**,
**legs**, and break knobs (**T_break**, **rho**, **tau_bar**) are **ASSUMED** scenario
design — not fit from the six clean-chain traces.

## Window consistency

Both duration `d` and `phi_bar` are measured over the **same refrigerated leg**:
from the first lot-mean sample below **10 °C** through the published Table 2 clip.
Warm harvest spikes and **field heat** are excluded. Arrival freshness is an
**upper bound** on store-relevant quality.

## Design variance decomposition (Var(log Λ))

At default **rho** = 0.08 (scenario design, not Abdella measurement):

- **Duration** share of Var(log Λ): ~82%
- **Break** share of Var(log Λ): ~18%

At **rho** = 0, duration accounts for 100% of Var(log Λ) (no break pulses).

## Assumed thermal knobs

Trip-wide cool/nominal/warm mode mix and offset_c values are ASSUMED (p_c=0.25, p_n=0.5, p_w=0.25; offsets -1.0/0.0/1.5 C). Tuned under rho=0 for phi_bar SD, not fit from six traces.

Hourly OU amplitude (0.35 C) is ASSUMED for chart realism and rho=0 phi_bar scatter; not fit from six traces.

rho (breaks per transit-day), tau_bar (mean break duration, days), and T_break are ASSUMED, NOT FITTED. All six Abdella shipments are clean chains with no cold-chain break, so a break frequency is not estimable from this data at any confidence. rho=0.08 / tau_bar=0.5 / T_break=12 put a typical break at ~1.2 reference-days and the duration share of Var(log Lambda) at ~82%, versus 100% at rho=0. Treat these numbers as a documented modelling regime, not a measurement.

## Position spread (`sigma_pos`)

keep 0.08 (lognormal psi scale; not identified from n=6; probe temperature sd is not sigma_pos)
**S4** suspect position probes excluded when estimating spread.

## Empirical overlay (six shipments)

| shipment | d_days | phi_bar |
| --- | --- | --- |
| S1 | 4.604 | 1.318 |
| S2 | 1.903 | 1.287 |
| S3 | 6.243 | 1.355 |
| S4 | 5.347 | 1.433 |
| S5 | 6.514 | 1.286 |
| S6 | 4.083 | 1.478 |

See also `data/abdella/fit_report.md` (fit_utc: 2026-08-25T20:16:00Z).
