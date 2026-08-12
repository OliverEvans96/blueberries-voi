# Backlog

Escalations and items that need a human decision land here.

- **M1.5 Wave 0 done:** Architecture locked in ADRs
  [0086](./adr/0086-m15-richobs-unobserved-masks.md)–[0089](./adr/0089-m15-dynamic-l-sliding-window-fallback.md)
  and specs [T-008](./specs/T-008.md)–[T-018](./specs/T-018.md). Plan:
  [`.team/plans/M1.5-filter-complete.md`](./plans/M1.5-filter-complete.md).
  **Next:** Wave 2 / T-011 (honest MC LL) — Wave 1 behaviour verified; full-repo
  gates may still be red on T-011 RED until that ticket lands.
- **Resolved — experiments lint:** `experiments/fil11_a_scenarios.py` RUF001
  (`sigma`/`x` ASCII) + E501/format wrap fixed; `uv run ruff check experiments/`
  and `uv run ruff format experiments/` pass.
- **Do not reopen without Oliver:** ⚑ cards (FIL-01, FIL-08, MOD-14/15/17, SCN-P2/F3/B-clair, …).
  **Exception / settle (ADR [0091](./adr/0091-fil13-production-mean-field.md), 2026-08-12):** production
  FIL-13 = **B (`mean_field`)**; FIL-04 → **C**; FIL-12 (ADR 0057) is **historical** — joint /
  `full_joint` is no longer the production default (bakeoff arm E retained). Do not reopen joint
  production without a **new** ADR; T-021 wires the settle.
- **M1.5 non-goals (binding):** no CTL, no VOI sweep, no browser, no new runtime deps without ADR.
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
  implementation under M1.5; park until post–M1.5 / explicit reopen.
- **Resolved — F2a Stage A pack_date emit (T-019):** Sim now emits synthetic ASN
  `pack_date` on delivery `DayLog` rows (non-delivery stays `None`). Stage A F2a
  contracts under smoke defaults; needs-human from T-016 is cleared.
