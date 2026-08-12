# FIL-11 Stage C — generative vs day_step (T-012)

Production gate is generative agreement with shared `day_step` kernels (ADR 0088). Soft `tv_vs_exact` is not the gate.

- status: **PASS**
- mode: `generative_day_step`
- tolerance (TV on discrete P1 sales/waste): 0.05
- production divergence: 0.000000
- wrong-physics divergence: 0.495000 (passed=False)
- L=2, K=4
- alphabet: empirical support of day_step (sales, waste) pairs
- figure: /home/oliver/blog/blueberries-voi/figures/m1.5/fil11_stage_c_generative.png
