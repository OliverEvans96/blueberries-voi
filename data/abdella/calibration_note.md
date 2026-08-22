# Abdella arrival calibration note (T-150)

This note is **reporting only**. Parameters in `arrival_model.json` are **assumed**
parametric families roughly consistent with the **six** Abdella cold-chain shipments.
The data **does not validate** these families; with only six corridors, MLE or other
fitting would be misleading. This script performs **no fitting**.

## Window consistency

Both duration `d` and `phi_bar` are measured over the **same refrigerated leg**:
from the first lot-mean sample below **10 °C** through the published Table 2
harvest→end-of-chain clip. Warm harvest spikes and field heat are excluded. Arrival
freshness from the model is therefore an **upper bound** on store-relevant quality.

## Position spread (`sigma_pos`)

The lognormal within-pallet multiplier `sigma_pos` in the artifact was set with **S4**
suspect position probes excluded from spread calibration.

## Empirical overlay (six shipments)

| shipment | d_days | phi_bar |
| --- | --- | --- |
| S1 | 4.604 | 1.318 |
| S2 | 1.903 | 1.287 |
| S3 | 6.243 | 1.355 |
| S4 | 5.347 | 1.433 |
| S5 | 6.514 | 1.286 |
| S6 | 4.083 | 1.478 |

Overlay figure: `data/abdella/arrival_calibration_overlay.png`.

Committed artifact schema version: 1.
