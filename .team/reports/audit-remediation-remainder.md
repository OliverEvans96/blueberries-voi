# Audit remediation — remainder report

**Tip documented:** `team/audit-remediation-integ` @ `c11d25a88af84a2484dfedd0b848b38a334bd793`  
**Source audit:** four-way review of `main` @ `f4a467f` (stubs / parameters / architecture / realism)  
**Remediation scope:** ADR [0104](../adr/0104-audit-remediation-defaults.md), tickets **T-042**–**T-044**  
**Status:** Straightforward silent-default / dual-semantic fixes landed. This file lists what the audit still leaves open. **Science VOI is not citeable.**

---

## Addressed in T-042 / T-043 / T-044

| Ticket | What closed |
|--------|-------------|
| **T-042** | Single `case_round` semantic: nearest / half-away-from-zero. `sim.episode` no longer ceil-rounds closed-loop orders; public path aligns with `controller.ordering.case_round`. |
| **T-043** | Shared `DEFAULT_PROFIT_COSTS` (still documented as uncalibrated scaffold). Production-facing APIs default shipments to Abdella; cool 1°C traces only via explicit `smoke_cool_shipments()`. Production VOI sweep hard-gates on a tuned α table; smoke may keep α=0.9. |
| **T-044** | Shared `MF_MAX_SWEEPS=5` on production mean-field path (CI-only `2` removed). Bakeoff `SlidingWindowBackend` / `FullJointBackend` marked non-citeable stubs (`is_stub`). Controller / α-tune docstring hygiene; backlog wording that M2+M3 library work is on `main`. |

Reviewer non-blocking residuals from those tickets are listed under **Reviewer non-blocking** below (not claimed fixed).

---

## Remainder (not fixed by this remediation)

### Filter physics and beliefs

- **ResearchParticleFilter lot counts** still follow a **±1 random walk**, not `day_step` inventory physics (`filter/backends.py`). Shelf beliefs that feed survival-weighted / VOI paths therefore use **fake counts**.
- Beliefs derived from those counts inherit the same fiction whenever the live filter (not B-state oracle) is the information source.

### Closed-loop information default

- Default **`run_closed_loop_episode`** still builds beliefs from **oracle ages**, so generic closed-loop / α-tune / ladder callers that omit an explicit filter belief are **not information-limited**.

### α search gaps

- **`tune_alpha_grid` remains `NotImplemented` for rollout and DP ladder arms** — top-of-ladder α must still be hand-filled or skipped.

### Filter honesty / likelihood mismatch

- **Stage A:** under defaults, P0 / P1 / F1 age posteriors **do not contract**; F2 passes mainly via receipt priors, not sales learning.
- **Stage B:** miscalibrated when forced on failing rungs.
- **MF LL vs MC weight mismatch:** production mean-field updates can disagree with the MC observation weights used for particle weighting — honesty / calibration claims stay weak.

### Uncalibrated parameters and species caveat

Still agent-/convention-assumed (keep + sensitivity; do not claim blueberry fit):

| Symbol / knob | Notes |
|---------------|--------|
| **β** | Spoilage shape; sweep axis, not a fitted Weibull |
| **η** (`eta_ref`) | ~14 d @ 0°C scale |
| **Q₁₀** | Convention (~3) |
| **σ** (picking) | Low-confidence veto default |
| **Demand** μ / variance | Veto defaults; need POS |
| **Dollar `ProfitCosts`** | Centralized but still **uncalibrated** scaffold |
| **Strawberry transit** | Thermal paths substitute strawberry loggers for blueberry (ADR [0045](../adr/0045-mod-23-strawberry-logger-to-blueberry-substitution.md)) |

### Production VOI compute (out of this remediation)

- Full-budget / research-scale production VOI wall-clock and speedups are **owned elsewhere** (other agent / M3 compute reports and production blog-results drivers). This remediation does **not** claim citeable overnight results or compute reduction.

### Smoke, ladder, CLI, parked axes

- **Loose smoke β=1 gate** with tolerance ~**50** remains effectively vacuous.
- Ladder **`"dp"` arm** still reports a **toy DP certificate** value, not comparable store profit under MOD-12 physics.
- **CLI** remains help/version-only (no experiment entrypoints).
- **Parked without Oliver reopen:** **ENG-01** (browser / Pyodide), **VOI-02** honesty / misspecification arms, **X-06** cadence / arrival-stagger axes.

### Controller / figures leftovers

- Rollout lookahead still uses delivery age **τ=0** (hardcoded) rather than sampling an arrival prior.
- **Rung 0** age-blind weights still use fixed **0.75** rather than belief-derived E[S].
- **ENG-03** committed figure pipeline largely **missing** on tip (static / blog figures not fully landed as a shipped pipeline).

### Board ⚑ risks and Wave-0 ADR locks

- Board **⚑** risks called out in the audit still stand: order-quantity-only VOI channel (X-04), ResearchParticleFilter-first complexity (FIL-01) compounded by MF + MC LL, fine β grid compute (VOI-04), ENG-01 static-vs-Pyodide tension.
- **Wave-0 ADRs** (especially implementer-filled budgets / package layout / scenario columns around **0094–0096**, and historical “Oliver unavailable” notes such as **0082**) still need **personal Oliver lock** before treating them as board-grade.

### Reviewer non-blocking (T-042 / T-043)

- **Open-loop** `run_episode` still **ceil-rounds inline** (`np.ceil`) and does not call unified `case_round` — residual dual semantic on the M1 open-loop path (outside T-042 AC).
- **`run_voi_crn_cell`** can still omit `alpha_table_path` and fall back to α=0.9; **production fail-closed is on `run_voi_sweep(smoke=False)`** (sweep hard-gated). Direct CRN-cell callers can still get silent 0.9.

---

## Explicit non-claims

- This tip is a **decision-analysis scaffold** with cleaner production defaults — **not** a calibrated blueberry retail VOI study.
- Do **not** cite quantitative store-profit VOI from current defaults as science about blueberries until calibration, filter honesty, and production compute artifacts are separately settled.

---

## Note (2026-08-13) — arrival-only count filter stream

Oliver locked ADRs **0105** / **0106** (tickets **T-067**–**T-069**) to address the
filter-physics remainder above:

- ±1 count RW → `day_step`-consistent count PF (T-068)
- MF age learning + MC weight mismatch → arrival-only ages + exact sequential-WOR weights
- Stage A honesty → re-gate on count calibration + arrival-prior injection (T-069); P0/P1/F1
  no longer claim in-store age contraction

Until T-068/T-069 verify PASS on their tips, the remainder bullets above still describe
`main`. After those tips integrate, strike or rewrite the filter-physics and
MF-vs-MC honesty bullets accordingly.

