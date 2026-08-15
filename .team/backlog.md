# Backlog

Escalations and items that need a human decision land here.

## In-flight ID reservations (do not collide)

See [ticket-adr-reservations-2026-08-13.md](./plans/ticket-adr-reservations-2026-08-13.md).

- **Arrival-only filter:** **T-067–T-069**, ADR **0105–0106** (`team/T-067/architect`). Leave alone.
- **ENG-01 dual-mode readiness follow-on:** **T-070–T-075**, ADR **0107–0108** — **Done / complete pending human merge.** Tip ready: `team/ENG-01-readiness/wave2` (= `team/T-075/implement`); verified close-out @ `a75fc10` (plan [ENG-01-readiness.md](./plans/ENG-01-readiness.md); smoke [T-075-smoke.md](./qa/T-075-smoke.md); verify [T-075.md](./qa/T-075.md)). Agents did not merge to `main`. Do **not** reuse T-067–T-069 / 0105–0106 for readiness.
- **CAL-01 calendar realism:** **T-076–T-088**, ADR **0112–0116** — **Done / complete pending human merge.** Close-out tip: `team/T-088/integrate-main` (DoD [CAL-01.md](./reviews/CAL-01.md); plan [CAL-01-calendar-realism.md](./plans/CAL-01-calendar-realism.md); smoke [T-088.md](./qa/T-088.md); FIL-13 remotesure [CAL-01-fil13-remeasure-L.md](./reports/CAL-01-fil13-remeasure-L.md)). Agents did not merge to `main`. CAL-01 ADRs renumbered past ENG-01 0109–0111 on integrate tip. **Not** Studio Autopilot — do not repurpose these ids.
- **Pyodide module-worker:** **T-092** (+ ADR **0111**) — landed on local `main` with CAL-01 integrate. **Not** Autopilot — do not claim T-092–T-096 for Autopilot.
- **Studio Autopilot Mode:** **T-091 + T-097–T-101**, ADR **0117** — **Done / complete pending human merge.** Tip: `team/studio-autopilot/wave` (merged with local `main`; verify was `9a1d482`); plan [studio-autopilot.md](./plans/studio-autopilot.md); ADR [0117](./adr/0117-studio-autopilot-mode.md). User plan T-076–T-081 collided with CAL-01 → actual ids **T-091, T-097–T-101**; provisional Autopilot ADR **0112** renumbered to **0117** at merge with CAL-01 (CAL-01 keeps 0112–0116). Void first Autopilot draft that used T-092–T-096 / ADR 0111.
- **Next free after Autopilot + CAL-01:** **T-102+**, ADR **0118+**.

## Needs human now

- **T-102 deferred semantics (notes only — do not unify in this milestone):** VOI/m2 still omit some order-gate / `day=` wiring that closed-loop episode has; ceil vs nearest case-rounding owners stay split (day_driver/open-loop vs episode/m2/voi); `ess_fraction` remains unused vs hardcoded `0.5 * N` resample; `sim/` vs `simulator/` naming debt stays. See ADR [0118](./adr/0118-behavior-frozen-module-splits.md).
- **needs-human — CAL-01 merge:** Human merge of `team/T-088/integrate-main` (CAL-01 close-out + main; ADRs 0112–0116) into parent when ready (agents must not merge to `main`). Citeable VOI regen after land; remotesure FIL-13 L before citing L-dependent filter claims.
- **needs-human — T-071 xdist flake:** `tests/test_t071_demo_hydrate_edges.py` intermittently returns 422 `shipments[0] must be an object` under full `pytest -n auto` (reproduces on `main`; file-alone xdist passes). Related residual: VOI/CRN `isinstance` dual-import flakes under xdist (see T-087 verify). Blocks clean verify retries occasionally; not a CAL-01 product defect.
- **Frontend controls/plots audit:** Review UI controls and plots so that (1) no controls are redundant, (2) every control affects a plot, (3) every plot is relevant, (4) all relevant concepts are illustrated, and (5) no plots are redundant.
- **needs-human — T-115 studio show-truth toggle:** **Done / complete pending human merge.** Implement `team/T-115/implement` @ `4517eab`; review APPROVED `team/T-115/review` @ `0e8476f`; verify PASS `team/T-115/verify` @ `a6d4c35` (ADR [0125](./adr/0125-studio-show-truth-js-only.md), renumbered from 0122 at merge with main). Changelog and `.team/qa/T-115.md` live on the verify tip — merge implement + review + verify together. Agents must not merge to `main`. Keep `.worktrees/T-115-implement` until then.
- **Frontend knowledge-scenario UI audit:** Review whether the UI should differ across knowledge scenarios. Prefer one consistent layout throughout; if some charts only make sense in certain scenarios, keep the shell the same and show or hide those charts (or mark them unavailable) rather than forking the whole UI.
- **needs-human — ENG-01 readiness merge:** Human merge of `team/ENG-01-readiness/wave2` / `team/T-075/implement` (verify tip `a75fc10`; tip includes post-handoff chore) into parent when ready (agents must not merge to `main`).
- **needs-human — Studio Autopilot merge:** Human merge of `team/studio-autopilot/wave` (T-091 / T-097–T-101, ADR 0117) into parent when ready (agents must not merge to `main`). Keep implement worktrees until then.
- **Optional — lazy-import pyarrow:** Consider deferring `pyarrow` import so dual-mode / slim paths avoid a hard runtime dependency unless parquet paths are used (non-blocking polish).
- **Intake open questions → [GitHub issue #1](https://github.com/OliverEvans96/blueberries-voi/issues/1):** Confirm production β grid upper bound / knot placement, default `ProfitCosts` for headline VOI, and whether F1/F1s closed-loop must fully score lot-resolved masks in M3v1 (see `.team/intake.md`).
- **M3 overnight production regen:** Keep tip `team/T-060/implement` (worktree `.worktrees/T-060-implement`) for citeable overnight VOI grid regeneration. Library M3 is on `main`; this tip is still needed for the production run. **Note:** CAL-01 will invalidate daily/i.i.d. citeable numbers again once landed — regen after CAL-01 closeout.
- **Optional — push `main`:** Local `main` is ahead of `origin/main` after integrate landings; push when ready (human).
- **Optional later — ADR / ticket-id collision:** Audit remediation used ticket ids T-042–T-044 under `*-audit-remediation*` paths while ENG-01 also used T-042–T-058; ADR [0104](./adr/0104-audit-remediation-defaults.md) landed. Rename/clarify artifacts only if it confuses readers — not blocking.

## Landed on `main`

- **T-046 workflows:** Live `.github/workflows/ci.yml` and `release-slim-wheel.yml` match `packaging/github-workflows/`. Quality CI is Python 3.11 only; Pyodide/CPython 3.14 remain documented env pins, not a CI matrix. No human copy/symlink remaining.
- **Done — ENG-01** dual-runtime / live simulator: complete pending human merge to `main` for any tip still off the integration branch (library path already landed).
 (tip `d376852`)

- **testmon LFS cache** and **chore/agent-gate-ladder** merged.
- **ENG-01 dual-runtime (T-042–T-058)** Done — complete pending human merge of any remaining tip notes; landed on `main` via `team/ENG-01/integrate`. ADRs [0099](./adr/0099-eng-01-dual-runtime-ap.md)–[0102](./adr/0102-eng-01-api-asgi-session.md) (0073 superseded). DoD: [ENG-01.md](./reviews/ENG-01.md). Binding prefs remain in ADRs 0100–0101 and plan [ENG-01-dual-runtime.md](./plans/ENG-01-dual-runtime.md).
- **Exact LL speedups (T-064–T-065)** on `main` via `team/T-064-065/integrate` — ADR [0103](./adr/0103-exact-faster-p1-f2a-likelihood.md); report [M3-exact-ll-speedup-bench.md](./reports/M3-exact-ll-speedup-bench.md). Measured closed-loop ~8–11× on P1/F2a; density unchanged. Residual: full production VOI grid may still need stagewise design / budget cuts / Numba if overnight citeable run requires more.
- **Audit remediation** on `main` via `team/audit-remediation-integ` — ADR [0104](./adr/0104-audit-remediation-defaults.md); artifacts under `*-audit-remediation*` paths. **Science VOI is not citeable** until production regen. Remainder pointers: [audit-remediation-remainder.md](./reports/audit-remediation-remainder.md).
- **M2+M3 library work is on `main`** (M2 T-022–T-034 and M3 T-035–T-041; plan [M3-voi-sweep.md](./plans/M3-voi-sweep.md)). Do not reopen VOI-02 ⚑ / X-06 axes without Oliver.

## Settled / historical (do not reopen lightly)

- **M1.5 / T-021 historical; superseded for production by ADR [0105](./adr/0105-arrival-only-age-counts-only-exact-wor.md):** Production filter is arrival-only age + counts-only PF (exact WOR). ADR [0091](./adr/0091-fil13-production-mean-field.md) mean-field age path is no longer the live settle. Do not reopen joint / MF age production without a **new** ADR.
- **X-11 / MOD-09:** Previously “do not reopen without Oliver.” **Oliver reopened both for CAL-01** (2026-08-13). Daily cadence (0011) and i.i.d. demand (0031) are **SUPERSEDED** by [0112](./adr/0112-x-11-mwf-delivery-base-case.md) and [0113](./adr/0113-mod-09-calendar-demand.md). Further cadence/demand changes still need Oliver; X-06 remains parked.
- **Do not reopen without Oliver:** other ⚑ cards (FIL-01, FIL-08, MOD-14/15/17, SCN-P2/F3/B-clair, X-06 cadence-as-axis, VOI-02, …). Exception / settle as ADR 0105 above; X-11/MOD-09 exception is CAL-01.
- **M2 non-goals (binding):** no browser packaging **in M2**; no new runtime deps without ADR; do not reopen T-021 / joint production. ENG-01 packaging was a **separate** milestone and is now landed on `main`. T-046 live `.github/workflows/` already matches `packaging/github-workflows/` (no copy remaining).
- **Handoff notes (still useful):** [`.team/plans/M2-controller-agent-brief.md`](./plans/M2-controller-agent-brief.md) (pure library, JSON-friendly belief, compute budgets, no FS/viz/pyarrow in `controller/`).
- **Resolved — F2a Stage A pack_date emit (T-019):** Sim emits synthetic ASN `pack_date` on delivery `DayLog` rows; Stage A F2a contracts under smoke defaults.
- **Resolved — experiments lint:** `experiments/fil11_a_scenarios.py` RUF001 + E501/format fixed.
- **Historical — M2 wave tips / ENG-01 A′ prefs:** Prior wave-by-wave “pending merge” and board Active wording are superseded by the landings above; keep ADRs/plans as the source of truth.
