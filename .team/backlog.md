# Backlog

Escalations and items that need a human decision land here.

- **needs-human — T-046 workflows:** Canonical CI (3.11/3.12/3.14) and slim-wheel Release YAML live under `packaging/github-workflows/`. A human must copy/symlink them into the live GitHub Actions workflows directory before CI/Release jobs run on GitHub (agents must not write there).
- **M1.5 / T-021 settled:** Production RBPF is mean-field (ADR
  [0091](./adr/0091-fil13-production-mean-field.md), commit `d240414`). FIL-04=C; FIL-13
  production=B; joint / `K^L` production parked. Do not reopen joint production without a **new**
  ADR.
- **Done — M3 (T-035–T-041):** VOI sweep library + smoke gates on
  `team/T-036/implement` (plan [M3-voi-sweep.md](./plans/M3-voi-sweep.md)). Pending human
  merge with M2 tip to `main`. Do not reopen VOI-02 ⚑ / X-06 axes without Oliver.
- **Done — ENG-01 dual-runtime (T-042–T-058):** Slice 1–3 complete on integrate tip
  `team/ENG-01/integrate` (plan [ENG-01-dual-runtime.md](./plans/ENG-01-dual-runtime.md)).
  Pending human merge to `main` — agents did not merge to `main`. ADRs
  [0099](./adr/0099-eng-01-dual-runtime-ap.md)–[0102](./adr/0102-eng-01-api-asgi-session.md)
  (0073 superseded). DoD / non-goals: [ENG-01.md](./reviews/ENG-01.md).
  Slice tips: T-048 / T-052 / T-058 implement.
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
- **M2 non-goals (binding):** no browser packaging **in M2**; no new runtime deps without
  ADR; do not reopen T-021 / joint production. ENG-01 packaging is a **separate** milestone
  (T-042+), not an M2 deliverable.
- **Handoff notes (still useful):** [`.team/plans/M2-controller-agent-brief.md`](./plans/M2-controller-agent-brief.md)
  (pure library, JSON-friendly belief, compute budgets, no FS/viz/pyarrow in `controller/`).
- **Historical — ENG-01 A′ prefs (closed with T-058):** Dual runtime per ADR
  [0099](./adr/0099-eng-01-dual-runtime-ap.md). Binding prefs remain in ADR
  [0100](./adr/0100-simulator-export-contract.md)–[0101](./adr/0101-eng-01-packaging-pyodide-wheels.md)
  and plan [ENG-01-dual-runtime.md](./plans/ENG-01-dual-runtime.md): derived Abdella; CI→GH
  Release wheels; no matplotlib in-browser; worker-only Pyodide; Snapshot/DayDelta; flat belief;
  sim+filter+controller under dialed budgets; Pyodide 314.0.4 / CPython 3.14.2; CI 3.11+3.12+3.14.
  Board item is Done pending human merge (see above), not Active.
- **Resolved — F2a Stage A pack_date emit (T-019):** Sim now emits synthetic ASN
  `pack_date` on delivery `DayLog` rows (non-delivery stays `None`). Stage A F2a
  contracts under smoke defaults; needs-human from T-016 is cleared.
