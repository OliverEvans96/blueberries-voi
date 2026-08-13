# Backlog

Escalations and items that need a human decision land here.

## In-flight ID reservations (do not collide)

See [ticket-adr-reservations-2026-08-13.md](./plans/ticket-adr-reservations-2026-08-13.md).

- **Arrival-only filter:** **T-067–T-069**, ADR **0105–0106** (`team/T-067/architect`). Leave alone.
- **ENG-01 dual-mode readiness:** **T-070–T-075**, ADR **0107–0108** — **Active** Wave 0 lock on `team/T-070/architect` (plan [ENG-01-readiness.md](./plans/ENG-01-readiness.md)). Next: qa/implement **T-071 ∥ T-072 ∥ T-073**, then T-074, T-075. Do **not** reuse T-067–T-069 / 0105–0106 for readiness.
- **Next free after both:** **T-076+**, ADR **0109+**.

## Needs human now

- **Intake open questions → [GitHub issue #1](https://github.com/OliverEvans96/blueberries-voi/issues/1):** Confirm production β grid upper bound / knot placement, default `ProfitCosts` for headline VOI, and whether F1/F1s closed-loop must fully score lot-resolved masks in M3v1 (see `.team/intake.md`).
- **M3 overnight production regen:** Keep tip `team/T-060/implement` (worktree `.worktrees/T-060-implement`) for citeable overnight VOI grid regeneration. Library M3 is on `main`; this tip is still needed for the production run.
- **needs-human — T-046 workflows:** Canonical CI (3.11/3.12/3.14) and slim-wheel Release YAML live under `packaging/github-workflows/`. A human must copy/symlink them into the live GitHub Actions workflows directory before CI/Release jobs run on GitHub (agents must not write there).
- **Optional — push `main`:** Local `main` is ahead of `origin/main` after integrate landings; push when ready (human).
- **Optional later — ADR / ticket-id collision:** Audit remediation used ticket ids T-042–T-044 under `*-audit-remediation*` paths while ENG-01 also used T-042–T-058; ADR [0104](./adr/0104-audit-remediation-defaults.md) landed. Rename/clarify artifacts only if it confuses readers — not blocking.

## Landed on `main` (tip `d376852`)

- **testmon LFS cache** and **chore/agent-gate-ladder** merged.
- **ENG-01 dual-runtime (T-042–T-058)** on `main` via `team/ENG-01/integrate` — ADRs [0099](./adr/0099-eng-01-dual-runtime-ap.md)–[0102](./adr/0102-eng-01-api-asgi-session.md) (0073 superseded). DoD: [ENG-01.md](./reviews/ENG-01.md). Binding prefs remain in ADRs 0100–0101 and plan [ENG-01-dual-runtime.md](./plans/ENG-01-dual-runtime.md).
- **Exact LL speedups (T-064–T-065)** on `main` via `team/T-064-065/integrate` — ADR [0103](./adr/0103-exact-faster-p1-f2a-likelihood.md); report [M3-exact-ll-speedup-bench.md](./reports/M3-exact-ll-speedup-bench.md). Measured closed-loop ~8–11× on P1/F2a; density unchanged. Residual: full production VOI grid may still need stagewise design / budget cuts / Numba if overnight citeable run requires more.
- **Audit remediation** on `main` via `team/audit-remediation-integ` — ADR [0104](./adr/0104-audit-remediation-defaults.md); artifacts under `*-audit-remediation*` paths. **Science VOI is not citeable** until production regen. Remainder pointers: [audit-remediation-remainder.md](./reports/audit-remediation-remainder.md).
- **M2 (T-022–T-034) and M3 library (T-035–T-041)** already on `main` (plan [M3-voi-sweep.md](./plans/M3-voi-sweep.md)). Do not reopen VOI-02 ⚑ / X-06 axes without Oliver.

## Settled / historical (do not reopen lightly)

- **M1.5 / T-021 settled:** Production RBPF is mean-field (ADR [0091](./adr/0091-fil13-production-mean-field.md)). FIL-04=C; FIL-13 production=B; joint / `K^L` production parked. Do not reopen joint production without a **new** ADR.
- **Do not reopen without Oliver:** ⚑ cards (FIL-01, FIL-08, MOD-14/15/17, SCN-P2/F3/B-clair, …). Exception / settle as ADR 0091 above.
- **M2 non-goals (binding):** no browser packaging **in M2**; no new runtime deps without ADR; do not reopen T-021 / joint production. ENG-01 packaging was a **separate** milestone and is now landed on `main` (see above); T-046 workflow install remains needs-human.
- **Handoff notes (still useful):** [`.team/plans/M2-controller-agent-brief.md`](./plans/M2-controller-agent-brief.md) (pure library, JSON-friendly belief, compute budgets, no FS/viz/pyarrow in `controller/`).
- **Resolved — F2a Stage A pack_date emit (T-019):** Sim emits synthetic ASN `pack_date` on delivery `DayLog` rows; Stage A F2a contracts under smoke defaults.
- **Resolved — experiments lint:** `experiments/fil11_a_scenarios.py` RUF001 + E501/format fixed.
- **Historical — M2 wave tips / ENG-01 A′ prefs:** Prior wave-by-wave “pending merge” and board Active wording are superseded by the landings above; keep ADRs/plans as the source of truth.
