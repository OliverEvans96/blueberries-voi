# Backlog

Escalations and items that need a human decision land here.

- **Done — exact LL speedups (T-064–T-066):** Unique-particle MF dedup + NumPy
  sequential-WOR DP on `team/T-064-065/integrate` (ADR
  [0103](./adr/0103-exact-faster-p1-f2a-likelihood.md); report
  [M3-exact-ll-speedup-bench.md](./reports/M3-exact-ll-speedup-bench.md)). Measured
  closed-loop ~8–11× on P1/F2a; density unchanged. Pending human merge to parent.
  Residual: full production VOI grid may still need stagewise design / budget cuts /
  Numba if overnight citeable run is required.
- **M1.5 / T-021 settled:** Production RBPF is mean-field (ADR
  [0091](./adr/0091-fil13-production-mean-field.md), commit `d240414`). FIL-04=C; FIL-13
  production=B; joint / `K^L` production parked. Do not reopen joint production without a **new**
  ADR.
- **Done — M3 (T-035–T-041):** VOI sweep library + smoke gates on
  `team/T-036/implement` (plan [M3-voi-sweep.md](./plans/M3-voi-sweep.md)). Pending human
  merge with M2 tip to `main`. Do not reopen ENG-01 / VOI-02 ⚑ / X-06 axes without Oliver.
- **M2 complete pending human merge to main:** Waves 0–7 (T-022–T-034) are tip-green on
  the M2 verify/implement line; landing on `main` is a human decision. M3 branched from the
  M2 tip without waiting for that merge.
- **Done — M2 Wave 7:** **T-034** (M2 close-out: DoD checklist, client-voice summary,
  non-goal locks) gate-green on `team/T-022/verify` (verifier PASS).
- **Done — M2 Wave 6:** **T-033** (multi-scenario closed-loop + L remeasure) integrated
  and gate-green on `team/T-022/verify`.
- **Done — M2 Wave 5:** **T-032** (CTL-05 five-point ladder + ENG-04 M2 gates: β=1,
  CRN desync, DP certificate) integrated and gate-green on `team/T-022/verify`.
- **Done — M2 Wave 4:** Parallel **T-030 ∥ T-031** (one-step rollout + salvage; toy exact DP
  certificate) integrated and gate-green on `team/T-022/verify`.
- **Done — M2 Wave 3:** **T-029** α fractile tuning (CTL-03=B) integrated and gate-green on
  `team/T-022/verify`.
- **Done — M2 Wave 2:** Parallel base policies **T-027 ∥ T-028** (age-blind Rung 0 and CTL-01
  damped survival-weighted base-stock) integrated and gate-green on `team/T-022/verify`.
- **Done — M2 Wave 0 / Wave 1:** ADRs
  [0092](./adr/0092-controller-belief-api.md)–[0093](./adr/0093-day-profit-helper.md) and specs
  [T-022](./specs/T-022.md)–[T-034](./specs/T-034.md); Wave 1 implement tips integrated and
  gate-green (T-023–T-026).
- **Historical — M1.5 Wave 0 / T-011:** Architecture lock and honest MC LL are done; do not treat
  “Next: Wave 2 / T-011” as current work.
- **Resolved — experiments lint:** `experiments/fil11_a_scenarios.py` RUF001
  (`sigma`/`x` ASCII) + E501/format wrap fixed; `uv run ruff check experiments/`
  and `uv run ruff format experiments/` pass.
- **Do not reopen without Oliver:** ⚑ cards (FIL-01, FIL-08, MOD-14/15/17, SCN-P2/F3/B-clair, …).
  **Exception / settle (ADR [0091](./adr/0091-fil13-production-mean-field.md), 2026-08-12):** production
  FIL-13 = **B (`mean_field`)**; FIL-04 → **C**; FIL-12 (ADR 0057) is **historical** — joint /
  `full_joint` is no longer the production default (bakeoff arm E retained). Do not reopen joint
  production without a **new** ADR; T-021 wires the settle.
- **M2 non-goals (binding):** no browser packaging in M2; no new runtime deps without
  ADR; do not reopen T-021 / joint production.
- **Eventual — Pyodide / browser A′ (compat notes only):** when implementing the controller, keep
  library shape handoff-ready — see
  [`.team/plans/M2-controller-agent-brief.md`](./plans/M2-controller-agent-brief.md)
  (pure library, JSON-friendly belief, compute budgets, no FS/viz/pyarrow in `controller/`).
  **Not** an M2 deliverable; packaging stays parked below.
- **Parked — browser A′ (Pyodide) deployment (needs Oliver to reopen ENG-01 / ADR 0073):**
  Intent: run sim/filter/(later) controller live in-browser via Pyodide on the
  Astro site (separate repo). Locked preferences (2026-08-12 chat), not ticketed:
  (1) ship **derived Abdella product** (e.g. arrival-age mix / arrays), not
  parquet/pyarrow in the browser path; (2) distribute wheel + assets via
  **CI → GitHub Release** (not PyPI); Astro `micropip.install` from release URL;
  (3) **no matplotlib in-browser** — static preloaded images and/or JS interactive
  figures from Python summaries; (4) slim import graph / browser façade;
  (5) thin JSON-friendly JS↔Python API, Pyodide in a worker; (6) demo numerics /
  perf deferred; (7) design CTL/VOI for dual runtime when built; (8) process:
  reopen ENG-01, write ADR + export contract, Pyodide smoke later. Do not start
  packaging under M2; park until explicit reopen.
- **Resolved — F2a Stage A pack_date emit (T-019):** Sim now emits synthetic ASN
  `pack_date` on delivery `DayLog` rows (non-delivery stays `None`). Stage A F2a
  contracts under smoke defaults; needs-human from T-016 is cleared.
