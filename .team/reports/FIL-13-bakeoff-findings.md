# FIL-13 bakeoff findings — agent handoff

**Date:** 2026-08-12  
**Purpose:** Self-contained handoff for another agent with general `blueberries-voi` context but not this chat. Settles what FIL-13 measured, what was locked, what stubs do *not* prove, and what not to redo.

---

## 1. Executive summary

- Board worry was **L ≈ 12–20** under MOD-13=C + daily delivery, which would make FIL-12=B’s joint `K^L` infeasible. FIL-13 ran an in-repo bakeoff before locking production RBPF shape.
- Under **M1 open-loop defaults** (σ=0.5, S=60, MOD-26 demand/case, FIL-14 extinction), empirical live-cohort count **L is small**: roughly **p50≈2, p90≈3, max≈3–4**. Fast ~2-day inventory turn explains why.
- Per settle rule (prefer **A** if L large; **E** if L small enough), production locks **E — `full_joint`** (ADR **0082** ACCEPTED). Code: `PRODUCTION_BACKEND = "full_joint"`.
- FIL-15 locks production numerics (ADR **0083**): age grid **[0, 8]**, **K=8**, **N=2000**, ESS threshold **N/2**.
- At production **K=8, N=2000**, `full_joint` stays under the `K^L·N` budget for measured L≤3–4; the in-process **memory guard** trips near **L≈6** (`8^6·2000 ≈ 5.2e7` vs budget `5e7`). That “OOM” is the **guard**, not OS kill.
- **A — `sliding_window`** remains implemented as bakeoff/fallback if a future policy regime raises L and trips the guard.
- **Critical caveat:** bakeoff backends currently share a **factorized per-cohort update stub**; `full_joint` mainly enforces the **`K^L·N` guard** (dense joint tensor is not materialized). Near-zero TV among backends is **not** evidence of joint accuracy.
- Slow-turn **combo** (μ=15, σ=0.2, S=120) pushes empirical L to **max≈13** — enough that full joint must skip; sliding_window / mean_field still run on memory formulas.
- Stage A relevance to L only: long-dwell knobs that can help Stage A contraction also raise L (e.g. μ=15+S=120 → L≈7–8), while production still hard-codes `PRODUCTION_L=3`. Do not treat Stage A as a FIL-13 accuracy bakeoff.

---

## 2. Problem statement

### FIL-12 = B (coarse joint)

ADR **0057** (FIL-12) chose **B — coarse age grid, joint** against the card’s recommendation (sliding window). Motivation: FIL-01 RBPF + FIL-04 joint age + FIL-03 fixed grid + MOD-13=C (no live-cohort bound) make `K^L` per particle per day explode unless K is small. Worked example assumed **L ≈ 4**.

### Board worry: L ≈ 12–20

Earlier board numbers suggested **L ≈ 12–20** under MOD-13=C + daily delivery. At that L, even coarse K makes joint storage infeasible → FIL-13 required an empirical bakeoff before locking production.

### FIL-13 options A–E

| Key | Option | Role in bakeoff |
| --- | --- | --- |
| **A** | Sliding window + factorised tail | Preferred if L large; fallback |
| **B** | Mean-field | Diagnostic / speed |
| **C** | Bound live cohort count (`bound_L`) | Stress / capped state — not production |
| **D** | Bootstrap PF (age in particle) | Ablation arm |
| **E** | Full joint (FIL-12=B) | Chosen if measured L small enough |

Settle rule (user/board): **prefer A if L large; choose E when empirical L is small enough.**

---

## 3. M1 store parameters + grocery interpretation

### Parameter table (interim M1 defaults used for L measurement)

| Knob | Value | Grocery read |
| --- | --- | --- |
| Demand μ | ~30 punnets/day | ~3.8 cases/day at case size 8; V/M≈2.0 (jumpy) |
| Base-stock S | 60 punnets | ~7.5 cases on-shelf target (~2 days of mean demand) |
| Delivery | Daily, 1-day lead | New lot when reordering |
| Picking σ | 0.5 | Mild fresh bias (not pure LIFO; strong LIFO would be σ≪1) |
| Spoilage | Weibull β=2.0, η=14 d @ 0°C; T_store=4°C, Q10=3 | Effective age ~1.55× calendar → ~9 calendar days characteristic life on shelf |
| Extinction | FIL-14 | Extinct lots (count→0) drop out of live L |
| Case / demand | MOD-26 | Case-rounded demand path used in scored runs |

### Why baseline L is low

With ~30 sold/day from ~60 on hand, inventory **turns in about two days**. Daily deliveries add cohorts, but older lots empty quickly through sales; mild fresh-bias still lets older stock move; extinct lots leave. Result: typically **only a couple of overlapping delivery lots** — not 12–20.

**“Ceiling of 6” is filter memory, not store reality.** `full_joint` budgets `K^L·N` floats; at K=8, N=2000 the guard trips near L~6. Under M1 defaults the store typically has **2–4** live lots.

What would push L toward 6–15: slower sales (↓μ), fatter stock (↑S), stronger LIFO (↓σ), colder store (slower death), less frequent larger deliveries — especially combined.

---

## 4. Empirical L results

Scored windows typically **20 burn + 90 score** (see `experiments/fil13_scaling.md`). Slight run-to-run variation appears across write-ups (max 3 vs 4); treat as **same regime**.

### Baseline (M1 defaults)

| Source | p50 | p90 | max | mean |
| --- | --- | --- | --- | --- |
| `fil13_bakeoff.md` (interim M1) | 2.00 | 3.00 | 3 | 1.73 |
| `fil13_scaling.md` Part A | 2.00 | 3.00 | 4 | 2.02 |
| Slow-turn table “baseline” row | 2.00 | 3.00 | 4 | 1.87 |

**Bottom line:** L ≈ **2–3 typical**, max about **3–4** under open-loop M1 defaults.

### Slow-turn regimes

| regime | p50 | p90 | max | mean |
| --- | --- | --- | --- | --- |
| baseline μ=30 S=60 σ=0.5 daily | 2.00 | 3.00 | 4 | 1.87 |
| slow sales μ=15 | 4.00 | 5.00 | 7 | 3.78 |
| fat stock S=120 | 4.00 | 6.00 | 7 | 4.07 |
| strong LIFO σ=0.2 | 2.00 | 3.00 | 4 | 1.71 |
| delivery every 2d (S=90) | 1.00 | 1.00 | 2 | 1.04 |
| **combo μ=15 σ=0.2 S=120** | **8.00** | **9.10** | **13** | **7.78** |

Highest max L among regimes: **combo → max=13**. At forced L=13, K=8, N=200: `full_joint` **skips** (floats ~1.1e14); `sliding_window` / `mean_field` / `bootstrap_pf` still **ok** on proxies.

### Stage A link (only as it touches L)

FIL-11 Stage A failed under defaults (posterior did not contract). Scenario sweeps show **long dwell** (μ=15 + S=120) can restore contraction under the soft-LL Stage A metric, but those cells push empirical **L≈7–8** while the production RBPF still tracks **`PRODUCTION_L=3`** slots and reports `age_posterior(0)` (oldest fixed slot). That is a **verification / dynamic-L** issue for later work — not a reason to reopen FIL-13’s E-at-measured-L lock without new L evidence under the intended controller.

---

## 5. Bakeoff protocol

### Backends

`sliding_window`, `mean_field`, `bound_L`, `bootstrap_pf`, `full_joint` — one predict/update interface in `src/blueberries_voi/filter/backends.py`.

### Matrix

- **L** probed: {2,3,4,6,8,10,12,15} (and optional forced L=13 for slow-turn).
- **K** ∈ {4,6,8,10}; **N** ∈ {200,500,2000} in scaling microbench; primary bakeoff sample rows often **K=8, N=200**.
- Soft skip if floats proxy > `2e8`; per-cell timeout ~8 s; typically **3** predict/update steps for timing.
- Memory proxies (×8 bytes for peak MB reporting):

| backend | floats proxy |
| --- | --- |
| `full_joint` | `K^L · N` (guarded; budget `MAX_JOINT_FLOATS = 5e7`) |
| `sliding_window` W | `(K^W + max(0,L−W)·K) · N` |
| `mean_field` | `L · K · N` |
| `bound_L` (max_L=4) | `K^{min(L,4)} · N` |
| `bootstrap_pf` | `N · L` (age indices; no grid posterior) |

### Metrics

- Wall time, peak MB / floats proxy, skip/oom flag, TV vs exact one-step (where computed), pairwise TV between backends.
- Empirical L distribution under open-loop sim (separate from microbench cells).

---

## 6. Runtime / memory results

### Sample rows (K=8, N=200) — from bakeoff + scaling

| backend | L | wall_s (order) | flag | floats_proxy (scaling) |
| --- | --- | --- | --- | --- |
| sliding_window | 2–15 | ~0.01–0.04 | ok | ~1.0e5–1.2e5 |
| mean_field | 2–15 | ~0.01–0.03 | ok | L·K·N (small) |
| bound_L | 2–15 | ~0.01 | ok | capped at K^4·N |
| bootstrap_pf | 2–15 | ~0.002 | ok | N·L |
| full_joint | 2–4 | ~0.01–0.016 | ok | 1.28e4 … 8.19e5 |
| full_joint | ≥6 | 0 | **skip/oom (guard)** | ≥5.24e7 |

Runtime differences among RBPF-style stubs are **small**; **memory formulas** are the decision surface.

### Production frontier (K=8, N=2000)

| K | N | max L ok | first fail L | reason |
| --- | --- | --- | --- | --- |
| 8 | 2000 | **4** | **6** | joint guard `K^L·N=5.24e8 > 5e7` |

At measured L≤3: `8^3·2000 ≈ 1.0e6 ≪ 5e7` → **E feasible**.

Other K/N highlights (first fail): K=4 N=2000 fails at L=8; K=6 N=2000 fails at L=6; K=10 same L=6 fail pattern as K=8 at N≥200.

### Memory guard vs OS OOM

- Code: `guard_joint_memory(K, L, N)` in `filter/types.py` raises **`MemoryError`** if `K^L·N > 5e7`, with message to escalate FIL-13 — **no silent L truncation**.
- Bakeoff/scaling “oom” / `skip` flags mean **this guard or the soft floats-proxy skip**, not the Linux OOM killer.
- `FullJointBackend.predict_update` calls the guard; production `RBPF.__post_init__` / `initialize` also call it.
- Do **not** interpret “OOM at L≥6” as “the process blew RAM allocating a dense `K^L` tensor” — the dense joint is **not** materialized in the current stub.

---

## 7. Accuracy / effectiveness + critical stub caveats

### Reported TV (stub world)

TV vs exact one-step and pairwise TV among `full_joint` / `sliding_window` / `mean_field` at K=4, L∈{2,3,4} are all **0.000** in write-ups.

### Critical stub caveats (do not ignore)

1. **Shared factorized update:** RBPF-style backends store `age_post` as shape `(N, L, K)` and share essentially the same **per-cohort** predict/update (`_rbpf_update`). They do **not** currently implement distinct joint vs window vs mean-field *inference* semantics.
2. **`full_joint` distinction today:** mainly the **`K^L·N` memory guard**. True dense joint tensor is **not** allocated.
3. **`sliding_window.window`:** accepted on the backend object but **not yet used** to change the update (W=2 vs W=3 timing cells note “window unused in stub”).
4. **Near-zero TV is expected and uninformative** under a shared stub — it does **not** prove joint fidelity, window approximation quality, or mean-field error.
5. **Bootstrap PF:** age in the particle needs **much larger N** for comparable marginal age accuracy; ESS smoke at N=200/2000/10000 stays high on the toy path but that is not a bakeoff win for production age posteriors.

### When each backend is appropriate (decision table)

| Backend | Use when | Avoid when |
| --- | --- | --- |
| **full_joint (E)** | Empirical L ≤3–4 at K=8, N~2e3; want joint *budget* semantics + production lock | Guard near/over `5e7`; regimes that raise L |
| **sliding_window (A)** | L grows; need fallback without full `K^L` | Need proven joint accuracy on long LIFO tails (**implement W semantics first**) |
| **mean_field (B)** | Diagnostics / speed | Allocation coupling matters |
| **bound_L (C)** | Stress with capped state | Production (silently wrong if true L > cap) |
| **bootstrap_pf (D)** | Ablation | Production age posterior at modest N |

---

## 8. Decision locked

| ADR / code | Decision |
| --- | --- |
| **ADR 0082** (ACCEPTED) | FIL-13 = **E — full_joint** at measured L |
| **ADR 0083** (ACCEPTED) | FIL-15 numerics: grid **[0,8]**, **K=8**, **N=2000**, ESS **N/2** |
| Fallback | **A — sliding_window** kept implemented; reopen 0082 toward A if guard trips under a new policy regime |
| Code constants | `PRODUCTION_BACKEND="full_joint"`, `PRODUCTION_K=8`, `PRODUCTION_N=2000`, `PRODUCTION_ESS_FRACTION=0.5`, `PRODUCTION_L=3` in `src/blueberries_voi/filter/rbpf.py` |
| FIL-12 (ADR 0057) | Still **B — coarse joint**; FIL-13 confirmed that choice is tractable at *measured* L, not at the old 12–20 estimate |

---

## 9. How to evaluate approaches going forward

Once a **real** joint (and real W / mean-field) update exists, do **not** reuse stub TV≈0 as a pass. Recommended metrics:

1. **Memory / feasibility:** `K^L·N` (or window formula) vs `MAX_JOINT_FLOATS`; wall time at production N; guard trip rate under empirical L trajectories.
2. **Marginal age accuracy:** TV or KL of each cohort’s age marginal vs a trusted exact/reference one-step (or small-K brute joint) under **coupled** allocation likelihoods.
3. **Joint / dependence fidelity:** metrics that detect allocation coupling (e.g. pairwise cohort age dependence, or TV on the full joint when L and K are tiny enough to materialize).
4. **Sliding-window error:** TV vs full joint as W and L vary; confirm W semantics actually change the update.
5. **Downstream task metrics:** Stage A–style contraction / calibration **only after** honest likelihood — and with **cohort-from-birth** (not oldest-slot-only) when comparing window vs joint.
6. **Regime stress:** remeasure empirical L under the **controller / cadence / LIFO** actually used; include slow-turn combo as a must-pass memory path for A.

---

## 10. Open risks / next work

1. **Implement real W (and true joint) semantics** — current stubs cannot settle approximation quality.
2. **Remeasure L under the intended controller** (and delivery cadence); open-loop S=60 is not the final policy world. Combo μ=15/σ=0.2/S=120 already reaches max L=13.
3. **Do not trust TV≈0** from the bakeoff as accuracy evidence.
4. **Dynamic L vs `PRODUCTION_L=3`:** long-dwell cells hit L≈7–8 while the filter still tracks 3 slots — escalate toward dynamic L + guard→sliding_window fallback (related ADRs/plans exist under M2.5; do not weaken the guard).
5. **Stage A / FIL-11** remains a separate honesty/verification track; P1 Stage A fail under defaults is documented and not a FIL-13 reopen by itself.
6. If guard trips in production-like regimes → **reopen ADR 0082 toward A**, possibly with smaller K per ADR 0083 note.

---

## 11. Artifact index

| Path | What |
| --- | --- |
| `experiments/fil13_bakeoff.md` | Short bakeoff write-up + recommendation |
| `experiments/fil13_bakeoff.py` | Bakeoff runner |
| `experiments/fil13_scaling.md` | Deep-dive: grocery L, microbench, slow-turn, effectiveness |
| `experiments/fil13_scaling.py` | Scaling / slow-turn runner |
| `.team/adr/0082-fil-13-tractability-bakeoff.md` | **E** locked |
| `.team/adr/0083-fil-15-filter-numerics.md` | K/N/ESS locked |
| `.team/adr/0057-fil-12-making-the-joint-age-posterior-tractable.md` | FIL-12=B coarse joint |
| `figures/m1/fil13_runtime.png` | Bakeoff runtime figure |
| `figures/m1/fil13_scaling.png` | Scaling figure |
| `figures/m1/README.md` | Figure regen map |
| `src/blueberries_voi/filter/rbpf.py` | `PRODUCTION_BACKEND` / K / N / L / ESS |
| `src/blueberries_voi/filter/types.py` | `MAX_JOINT_FLOATS`, `guard_joint_memory` |
| `src/blueberries_voi/filter/backends.py` | Bakeoff backends + shared update stub |
| `tests/test_filter.py` | Asserts `PRODUCTION_BACKEND == "full_joint"` |
| This file | `.team/reports/FIL-13-bakeoff-findings.md` |

---

## 12. What another agent should not redo / should not assume

Do not re-litigate FIL-13 options A–E from a blank board: **E is locked** at measured open-loop L, with **A retained as fallback**, and FIL-15 numerics already set. Do not assume the old board **L≈12–20** still applies under M1 defaults — measured L is ~2–3. Do not treat bakeoff **TV≈0** or similar wall times as proof that joint, window, and mean-field are equally accurate: they share a **factorized stub**, and **`full_joint` primarily enforces the `K^L·N` guard** rather than materializing a dense joint. Do not confuse that **in-process memory guard** with OS OOM. Do not lower `MAX_JOINT_FLOATS`, silently truncate L, or drop coverage/type gates to “make joint fit.” Before changing production backend, **remeasure empirical L under the real controller** and implement real W/joint update semantics; then re-run accuracy metrics that can actually distinguish approaches.
