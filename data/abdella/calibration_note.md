# Abdella arrival calibration note

Parameters in `arrival_model.json` are **fitted offline** from six Abdella shipments
(`scripts/fit_abdella_arrival.py`). The data **does not validate** the assumed families;
with only six corridors, treat numbers as defensible starting points, not MLE proof.

## Window consistency

Both duration `d` and `phi_bar` are measured over the **same refrigerated leg**:
from the first lot-mean sample below **10 °C** through the published Table 2 clip.
Warm harvest spikes and **field heat** are excluded. Arrival freshness is an
**upper bound** on store-relevant quality.

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
