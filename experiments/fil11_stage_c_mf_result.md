# FIL-11 Stage C - exact joint vs mean-field (FIL-04 check)

**Verdict:** PASS

**Recommendation:** Pass on P1 base + mild path - recommend reopening FIL-04 toward mean-field (C) and parking FIL-12/13 joint machinery (FIL-13 option B). Do not flip ⚑ ADRs until Oliver confirms. (base marg_tv median=0.0050 p95_max=0.0105; joint_tv median=0.0435; action_agree=1.000; stress_fail=False)

Likelihood: named `sequential_wor_pmf` (ADR 0090). Production soft `_rbpf_update` left unchanged. ADR 0049 / 0057 statuses not flipped.

Findings report: `.team/reports/FIL-11-stage-c-mf-findings.md`

## Stage 1 - one-step synthetic

| case | L | K | sigma | joint TV | marg TV max | marg KL max | max MI | SW rel delta | action agree |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| balanced_mild_sigma | 2 | 6 | 0.50 | 0.0455 | 0.0080 | 0.0002 | 0.0104 | 0.0014 | True |
| age_gap_lifo | 2 | 6 | 0.20 | 0.0977 | 0.0112 | 0.0004 | 0.0380 | 0.0001 | True |
| near_dead_cohort | 2 | 6 | 0.50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | True |
| large_waste | 2 | 6 | 0.50 | 0.0185 | 0.0012 | 0.0000 | 0.0019 | 0.0001 | True |
| weak_info | 2 | 6 | 0.50 | 0.0007 | 0.0002 | 0.0000 | 0.0000 | 0.0000 | True |
| L3_base_P1 | 3 | 6 | 0.50 | 0.0496 | 0.0051 | 0.0001 | 0.0031 | 0.0009 | True |
| L3_stress_lifo_rich | 3 | 6 | 0.20 | 0.1324 | 0.0136 | 0.0005 | 0.0190 | 0.0004 | True |

## Stage 2 - multi-day accumulation (L=3, K=6, T≈12)

| case | L | K | sigma | joint TV | marg TV max | marg KL max | max MI | SW rel delta | action agree |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| multiday_t0 | 3 | 6 | 0.50 | 0.0500 | 0.0064 | 0.0001 | 0.0057 | 0.0007 | True |
| multiday_t2 | 3 | 6 | 0.50 | 0.0495 | 0.0072 | 0.0001 | 0.0055 | 0.0005 | True |
| multiday_t4 | 3 | 6 | 0.50 | 0.0435 | 0.0107 | 0.0003 | 0.0051 | 0.0004 | True |
| multiday_t6 | 3 | 6 | 0.50 | 0.0353 | 0.0100 | 0.0003 | 0.0037 | 0.0003 | True |
| multiday_t8 | 3 | 6 | 0.50 | 0.0128 | 0.0060 | 0.0002 | 0.0015 | 0.0001 | True |
| multiday_t10 | 3 | 6 | 0.50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | True |

## Stage 3 - frozen RBPF count path replay

| case | L | K | sigma | joint TV | marg TV max | marg KL max | max MI | SW rel delta | action agree |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| particle_t0 | 3 | 6 | 0.50 | 0.0340 | 0.0050 | 0.0001 | 0.0019 | 0.0008 | True |
| particle_t1 | 3 | 6 | 0.50 | 0.0523 | 0.0054 | 0.0001 | 0.0044 | 0.0002 | True |
| particle_t2 | 3 | 6 | 0.50 | 0.0644 | 0.0150 | 0.0007 | 0.0069 | 0.0015 | True |
| particle_t3 | 3 | 6 | 0.50 | 0.0732 | 0.0233 | 0.0017 | 0.0079 | 0.0026 | True |
| particle_t4 | 3 | 6 | 0.50 | 0.0818 | 0.0254 | 0.0022 | 0.0072 | 0.0036 | True |
| particle_t5 | 3 | 6 | 0.50 | 0.0897 | 0.0321 | 0.0033 | 0.0092 | 0.0041 | True |
| particle_t6 | 3 | 6 | 0.50 | 0.0956 | 0.0383 | 0.0046 | 0.0105 | 0.0046 | True |
| particle_t7 | 3 | 6 | 0.50 | 0.1025 | 0.0393 | 0.0050 | 0.0107 | 0.0054 | True |
| particle_t8 | 3 | 6 | 0.50 | 0.1093 | 0.0406 | 0.0055 | 0.0108 | 0.0057 | True |
| particle_t9 | 3 | 6 | 0.50 | 0.1155 | 0.0421 | 0.0060 | 0.0109 | 0.0060 | True |

## Stage 4 - decision metric

Embedded in tables: `SW rel delta` = |E_exact - E_MF| / stock; `action agree` on order grid {0,8,16,24}.

## Marginal TV vs sigma (L=3)

| sigma | mean marginal TV |
| --- | --- |
| 0.2 | 0.0050 |
| 0.5 | 0.0051 |
| 1.0 | 0.0057 |

Figure: `figures/m1/fil11_stage_c_mf_tv_vs_sigma.png`

## Gates (ADR 0090)

- Marginal TV: median < 0.02, p95 < 0.05
- Joint TV median < 0.05 or action agree >= 0.95
- Stress LIFO+rich with action flips => fail MF for production

