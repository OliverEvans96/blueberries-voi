# M2.5 Stage A — multi-rung (shared CRN)

Library: `blueberries_voi.viz.m25.run_m25_stage_a` (T-016; F2a emit T-019).
Metric: **cohort-from-birth** arrival-age SD on a tracked birth-lot slot after ≥1
post-birth day (avoids oldest-slot-only artifacts). Default contraction margin
5%. Shared `root_seed`; only the observation mask differs by rung.

## Honesty

- **P0/P1 FAIL is allowed** under defaults if documented (optional gate; not an
  M2.5 blocker alone).
- **F2a/F2 should PASS.** If they fail, treat as **needs-human** — do not paper
  over.
- F1/F1s should improve vs P1 when lot-resolved observations identify age
  better than totals.

## Smoke table (`root_seed=0`, library defaults N/horizon)

| rung | prior_sd | posterior_sd | contracted | tight_control | pass/fail |
| --- | --- | --- | --- | --- | --- |
| P0 | 2.0603 | 2.0603 | no | yes | FAIL (allowed) |
| P1 | 2.0603 | 2.0603 | no | yes | FAIL (allowed) |
| F1 | 2.0603 | 2.0603 | no | yes | FAIL (diagnostic) |
| F1s | 2.0603 | 2.0603 | no | yes | FAIL (diagnostic) |
| F2a | 2.0603 | 0.7454 | yes | yes | PASS |
| F2 | 2.0603 | 0.0000 | yes | yes | PASS |

F2 contracts via age-at-receipt Dirac birth prior. F2a contracts via synthetic
ASN `pack_date` on delivery `DayLog` rows (T-019; non-delivery stays `None`).
Does not claim dollar value-of-information.
