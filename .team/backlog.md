# Backlog

Escalations and items that need a human decision land here.

- **M1.5 / T-021 settled:** Production RBPF is mean-field (ADR
  [0091](./adr/0091-fil13-production-mean-field.md), commit `d240414`). FIL-04=C; FIL-13
  production=B; joint / `K^L` production parked. Do not reopen joint production without a **new**
  ADR.
- **Next — M2 Wave 0 / Wave 1:** Team plan
  [`.team/plans/M2-controller.md`](./plans/M2-controller.md). Wave 0 locks ADRs
  [0092](./adr/0092-controller-belief-api.md)–[0093](./adr/0093-day-profit-helper.md) and specs
  [T-022](./specs/T-022.md)–[T-034](./specs/T-034.md). After Wave 0 freeze → Wave 1 parallel
  T-023–T-026.
- **Historical — M1.5 Wave 0 / T-011:** Architecture lock and honest MC LL are done; do not treat
  “Next: Wave 2 / T-011” as current work.
- **Resolved — experiments lint:** `experiments/fil11_a_scenarios.py` RUF001
  (`sigma`/`x` ASCII) + E501/format wrap fixed; `uv run ruff check experiments/`
  and `uv run ruff format experiments/` pass.
- **Do not reopen without Oliver:** ⚑ cards (FIL-01, FIL-08, MOD-14/15/17, SCN-P2/F3/B-clair, …).
  **Exception / settle (ADR [0091](./adr/0091-fil13-production-mean-field.md), 2026-08-12):** production
  FIL-13 = **B (`mean_field`)**; FIL-04 → **C**; FIL-12 (ADR 0057) is **historical** — joint /
  `full_joint` is no longer the production default (bakeoff arm E retained).
- **M2 non-goals (binding):** no VOI sweep; no browser packaging in M2; no new runtime deps without
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
