<!--
Authority for the *transit temperature / duration generative model* on PR #65
(team/arrival-breaks/integrate). Written 2026-08-26 after design review with Oliver.

Status: **PLAN ONLY — do not treat Stage 1 (deterministic legs + breaks) as the final
thermal design.** Implement this document next (or revise Stage 1 against it) before
accepting Stage 1 as done.

Preserves from the prior plan / ADR 0150:
  - compound-Poisson breaks at fixed T_break (duration severity, not ΔT)
  - trace as generative primitive (Λ from path)
  - filter summaries cached; no meaningful per-day filter runtime increase
  - multi-lot (ADR 0149) unchanged by this doc — see arrival-breaks-multilot.md §2

Supersedes / revises:
  - Deterministic fixed leg shares+setpoints as the sole baseline in
    .team/plans/arrival-breaks-multilot.md §1 and ADR 0150 §2 baseline wording
  - short_haul / long_haul as first-class studio duration modes
  - the unachievable "98.4% duration share at ρ→0" guard under a fully deterministic
    baseline (handoff open issue) — replaced by clean-chain φ̄ moment match + Var(log d)

Related: .team/handoffs/arrival-breaks-multilot.md, ADR 0148/0149/0150, PR #65
-->

# Transit generative model v2 (bottom-up stages + modes + hourly noise + breaks)

**Audience:** next implementing agent on PR #65.  
**Scope:** cold-chain **transit** generative path + filter projection only.  
**Out of scope here:** three-lots wiring (still `.team/plans/arrival-breaks-multilot.md` §2), docs site rewrite (known-red deferred), notebook prose.

**Do not implement other features in the same pass.** Land this thermal/duration redesign (revising Stage 1), then continue Stage 2/3 as in the handoff.

---

## 0. Goals and constraints (binding)

| Goal | Requirement |
|---|---|
| Generative traces | Path first; `Λ = ∫ φ(T(t)) dt` via existing `resolve_arrival_exposure` |
| Informative F3 | Breaks carry real thermal variance a pack date cannot see |
| Semi-realistic charts | Hourly logger-like noise **required**; not flat steps |
| Unified shipments | **No** short/long haul toggle; one duration family |
| Bottom-up duration | Stage times drawn first; total `d = Σ d_k` |
| Match Abdella | Marginal `d` **exactly** matches `abdella_all`; clean-chain `φ̄` mean/SD match by simple metrics |
| Realistic stage variation | Random stage lengths + trip thermal mode (not only tiny OU) |
| Filter tractable | Closed-form / enumerable `Λ` summary; **no hourly latent**; cached prior/F2 |
| Runtime | No meaningful per-day filter increase (`bench_day_timing` within noise of ~5.7 ms/day @ N=200) |
| Few parameters | Prefer assumed knobs + moment match; no MLE theater on n=6 |
| Simplicity | Explainable in one page; avoid black-box MC-fitted `P(Λ\|d)` as primary law |

**Hard rejects**

- Unbounded random break temperature / `ΔT ~ Exp` (Q10 → heavy tails; ADR 0150).
- Hourly OU inside live filter quadrature.
- Decorative bisection traces (old `truth_transit_trace`).
- Reintroducing `mu_T` / `sigma_T` truncated-normal as the generative thermal law.

---

## 1. Generative model (truth, charts, F3 input)

### 1.1 Stages (means, not rigid laws)

Keep three named stages with **mean** shares and **nominal** setpoints (artifact `legs`):

| Stage | Mean share \(w_k\) | Nominal setpoint \(\mu_k\) |
|---|---|---|
| `precool_staging` | 0.15 | 0.5 °C |
| `line_haul` | 0.60 | 2.0 °C |
| `dock_receiving` | 0.25 | 5.0 °C |

### 1.2 Bottom-up durations (exact Abdella match)

Let the pooled Abdella law be the sole duration family (today’s `corridors.abdella_all`):

\[
d = d_{\min} + E,\qquad E\sim\mathrm{Gamma}(a,b)
\]

with committed fit \((d_{\min},a,b) \approx (1.853,\ 3.009,\ 0.974)\).

**Construction** (draw stages first):

\[
e_k \sim \mathrm{Gamma}(w_k\, a,\ b)\ \text{i.i.d. scale }b,\qquad
d_k = w_k\, d_{\min} + e_k,\qquad
d = \sum_k d_k.
\]

Then \(d\) has **exactly** the Abdella pooled law. Short/long trips are outcomes of this draw.

**Product:** demote/remove studio chips `short_haul` / `long_haul` as first-class modes. Default everything through this one family (rename in UI copy to “transit” / keep key `abdella_all` internally if convenient). Advanced overrides may remain in config later; not core UX.

### 1.3 Trip thermal mode (real mean-temperature variation)

Once per trip draw discrete mode \(M \in \{\mathrm{cool},\mathrm{nominal},\mathrm{warm}\}\) with probabilities \((p_c,p_n,p_w)\) (two free probs; rest = 1 − sum).

Fixed offsets \(\delta_c < \delta_n=0 < \delta_w\) (starting suggestion: \(-1,\ 0,\ +1.5\) °C — assumed, tuned under §3).

\[
T_k^{\mathrm{mean}} = \mu_k + \delta_M.
\]

One **trip-wide** mode (not independent per stage) — 3 filter branches, clear story (“this truck ran warm”).

### 1.4 Hourly noise (required on path)

Around \(T_k^{\mathrm{mean}}\), OU / AR(1) noise:

- correlation time **fixed** ≈ 1 hour (not a free knob),
- amplitude \(\sigma_{\mathrm{hour}}\) (one free assumed knob).

Must be visible on Events delivery-temperature charts even when \(\rho=0\).

### 1.5 Breaks (ADR 0150, kept)

\[
N\sim\mathrm{Poisson}(\rho\, d),\qquad
\tau_j\sim\mathrm{Exp}(\bar\tau)\ \text{at fixed }T_{\mathrm{break}}.
\]

Punch rectangular pulses into the path; clamp so total break time ≤ \(d\).  
Defaults remain assumed: e.g. \(T_{\mathrm{break}}=12\) °C, \(\bar\tau=0.5\) d, \(\rho=0.08\) /day (scenario design, **not** fit from six clean traces).

**Inferential choice (locked unless Oliver reopens):** `d` is **total calendar** duration; breaks sit *inside* it. Pack date is not direct evidence of a break. (Alternative “breaks extend the trip” stays rejected for this PR — see handoff.)

### 1.6 Path assembly and exposure

1. Draw \(\{d_k\}\), mode \(M\), OU path, breaks.  
2. Emit `ShipmentTrace` `{times_d, temps_c}` (duplicate knots at discontinuities as today so trapezoid Q10 is exact on piecewise-constant segments; OU may be sampled on an hourly grid with linear/hold segments).  
3. \(\Lambda =\) `resolve_arrival_exposure(...)`.  
4. Per-unit: \(\psi\sim\mathrm{Lognormal}(0,\sigma_{\mathrm{pos}})\), \(D\sim\mathrm{Gamma}(k\cdot\Lambda\psi,\theta)\), \(f=\max(0,1-D)\) — existing birth API.

Optional studio `transit_temp_bias_c`: add a constant offset to all setpoints / path (exploration knob), as today if wired.

---

## 2. Filter projection (closed-form / enumerable summary)

Particles never store paths. Arrival laws stay in `ArrivalModel` caches (`Prior`, `Duration(d)`, `Exposure(Λ)`).

### 2.1 Freshness given exposure (unchanged, closed form)

\[
P(f\mid\Lambda)\ \text{via incomplete gamma (existing `cdf_f_given_lambda`)}.
\]

### 2.2 Building \(\Lambda\) nodes

**Prior**

1. Quadrature over \(d \sim d_{\min}+\mathrm{Gamma}(a,b)\) (existing 8 nodes).  
2. For each \(d\) (or analytically via stage construction — see baseline): mix modes and breaks as below.  
3. Quadrature over \(\psi\).  
4. Average `cdf_f_given_lambda` → grid CDF; cache.

**Pack date (`Duration(d_days)`)**

Fix \(d\); mix modes + stage baseline + breaks + \(\psi\).

**F3 (`Exposure(Λ)`)**

Observed path → one \(\Lambda\); only \(\psi\) quadrature.

### 2.3 Baseline exposure given mode (stage gammas)

With effective rates \(\varphi_{\mathrm{eff}}(T)=E[\varphi(T+X_{\mathrm{OU}})]\) (Jensen fold of hourly noise; no OU latent):

\[
\Lambda_{\mathrm{base}}\mid M
= \sum_k d_k\,\varphi_{\mathrm{eff}}(\mu_k+\delta_M)
= c_M + \sum_k \varphi_{\mathrm{eff}}(\mu_k+\delta_M)\, e_k.
\]

Each \(\varphi_k e_k\) is gamma with scale \(b\varphi_k\). Sum of heteroscedastic gammas:

| Default | Moment-match to one \(\mathrm{Gamma}(a_M^\star,b_M^\star)\) (or shifted) from exact mean/variance of the sum |
|---|---|
| Upgrade if coherence fails | One-time DP/FFT convolution of the three scaled-gamma densities on a fixed \(\Lambda\) grid (repo PB-DP spirit); cache |

### 2.4 Breaks (existing structure)

Enumerate \(N=0..N_{\max}\) (keep 4), Poisson weights on \(\rho d\), for \(n\ge 1\) 8-node quadrature on \(\mathrm{Gamma}(n,m_M)\) with \(m_M=\bar\tau(\varphi_{\mathrm{break}}-\varphi_{\mathrm{eff},M})\), cap by trip.

### 2.5 Mode mix

\[
P(\Lambda\mid d)=\sum_M p_M\, P(\Lambda_{\mathrm{base}}+\Lambda_{\mathrm{break}}\mid d,M).
\]

Node budget order: \(3 \times (1 + N_{\max}\times 8)\) thermal nodes per \(d\), plus duration×position outer quads for prior — still **cached**, milliseconds-class, not per particle-day.

### 2.6 Coherence guard

Monte Carlo the generative model at \(\rho=0\) and at default \(\rho\); compare mean/variance of \(\Lambda\mid d\) (or of \(f\mid d\)) to the filter’s `Duration(d)` law within tolerance. Fail CI if projection drifts.

---

## 3. Calibration from Abdella (n=6 honesty)

### 3.1 Fitted

| Target | Method |
|---|---|
| \((d_{\min},a,b)\) | Existing delayed-gamma moment match on six `d_i` (`scripts/fit_abdella_arrival.py`) |
| Stage split | **Derived** from \((w_k,a,b,d_{\min})\) — not separately fitted |

### 3.2 Anchored (clean-chain \(\rho=0\))

| Target | Method |
|---|---|
| Mean \(\bar\varphi\) | Tune nominal \(\mu_k\) (or global bias) so break-free \(\varphi_{\mathrm{set}}\) ≈ mean of six \(\bar\varphi_i\) (~1.36) |
| SD \(\bar\varphi\) | Tune mode offsets / \(p_M\) / \(\sigma_{\mathrm{hour}}\) so simulated SD(\(\bar\varphi\)) ≈ sample SD of six (~0.07–0.08 in φ-space) |

### 3.3 Assumed (document in artifact provenance)

\(\rho,\bar\tau,T_{\mathrm{break}}\), residual mode probs after SD match, shelf gamma \(k,\theta\), \(\sigma_{\mathrm{pos}}\).

**Do not** fit break rate from these six traces.

### 3.4 Metrics / guards that must pass

1. Simulated mean/SD of \(d\) match Abdella law (and overlay).  
2. At \(\rho=0\): mean/SD of \(\bar\varphi\) (and mean \(\Lambda\)) in ballpark of six shipments; overlay cloud.  
3. At \(\rho=0\): `Var(log d)` matches observed ~0.205 (duration check).  
4. Default \(\rho\): report duration vs break share of \(\mathrm{Var}(\log\Lambda)\) as **design** output (~80% duration target from original plan is OK as scenario, not Abdella measurement).  
5. Ladder: `ac2_11a_empirical_ladder_tracking_mae` still strictly ordered (never relax).  
6. Charts: non-flat traces at \(\rho=0\) (hourly noise present).  
7. Coherence G vs filter (§2.6).

Update `scripts/fit_abdella_arrival.py` / calibration note: drop truncated-normal fit; write legs/modes/breaks provenance; keep duration moment match; add clean-chain φ̄ checks.

---

## 4. Simulator / filter / studio impact

### 4.1 Simulator (`voi_core`)

| File / area | Change |
|---|---|
| `shipments.rs::truth_transit_trace` | Bottom-up \(d_k\), mode, OU, breaks → path |
| `arrival.rs::draw_transit` / `draw_truth_delivery*` | Use new path; Λ from integrator |
| `arrival.rs` thermal nodes / `marginal_cdf_at` | Modes + stage-gamma baseline + breaks |
| `arrival_model.json` | Schema fields for modes, \(\sigma_{\mathrm{hour}}\); retire `mu_T`/`sigma_T` if still present; single duration family emphasis |
| `session.rs` | Default `arrival_product` → unified law; stop requiring haul chips |
| Multi-lot (Stage 2) | Still \(\Lambda_\ell=\Lambda_{\mathrm{upstream},\ell}+\Lambda_{\mathrm{shared}}\); each segment uses this generative model |

In-store day step, PB spoilage, sales LL, policy: **unchanged**.

### 4.2 Filter runtime

- Per-day filter: **no meaningful change** (arrival cached at birth).  
- Configure / pack-date cache rebuild: small constant factor (×3 modes).  
- Measure with `cargo run -p voi_core --release --bin bench_day_timing`.

### 4.3 Studio / web

| Surface | Expected change |
|---|---|
| Arrival chips All/Long/Short | Remove or demote; one unified transit law |
| Events temp charts | Variable stage lengths, hourly wiggle, occasional break spikes |
| Arrival prior chart | Wider / differently shaped prior; still from engine wire |
| `transit_temp_bias_c` | Keep as exploration offset if wired |
| Obs ladder presets | Structure unchanged; **F2→F3 should matter more** than pre-0150 |
| Autopilot `rho` | Unrelated to break \(\rho\) — do not confuse in copy |
| `web/package.json` version | Bump when `voi_core` / publishable paths change (Stage 3) |

### 4.4 Outcomes (expected direction)

- Chart realism ↑  
- Temp-history VOI ↑ vs decorative era  
- Pack date still strong (duration) but less monopolistic when breaks on  
- Mean arrival freshness near calibration if φ̄ centre matched; spread ↑ with modes/breaks  
- Docs job likely red until follow-up (known-red)

---

## 5. ADR / plan document updates (same PR family)

Implementing agent should, in the thermal pass or a tiny docs-ADR commit:

1. Amend **ADR 0150** (or add a short ADR that partially supersedes §2 baseline): deterministic legs → bottom-up stage gammas + trip mode + path OU; filter projection as in §2. Keep break decision.  
2. Note **ADR 0148**: duration fit stays; truncated-normal temp fit remains retired.  
3. Leave **ADR 0149** (multi-lot) intact.  
4. Point `.team/plans/arrival-breaks-multilot.md` header at **this** file as thermal authority.  
5. Update handoff Stage 1 acceptance criteria to this plan.

---

## 6. Implementation sequence (suggested)

**Do not start Stage 2 until Stage 1 matches this plan and tests are green.**

1. **Artifact + fit script** — duration-only fit; provenance for modes/OU/breaks; clean-chain φ̄ anchors.  
2. **Generative path** — `truth_transit_trace` rewrite; unit tests: Abdella `d` marginal; ρ=0 φ̄ moments; OU visible; breaks punch; path integrates to reported Λ.  
3. **Filter projection** — `thermal_nodes` → modes × baseline × breaks; coherence test; prior/F2 cache fingerprint includes new knobs.  
4. **Session / studio** — default unified corridor; demote haul chips; version bump when required.  
5. **Gates** — `cargo test -p voi_core`; focused arrival tests; `bench_day_timing` note in PR; Python verify when wiring touches `src/`.  
6. **Then** Stage 2 multi-lot per original plan §2 / handoff.

### Test checklist (minimum)

- [ ] `d` marginal equals `d_min + Gamma(a,b)` (analytic or MC).  
- [ ] ρ=0: mean/SD `φ̄` vs six shipments within agreed tol.  
- [ ] ρ=0: traces non-constant (OU).  
- [ ] ρ>0: some traces hit ~`T_break`.  
- [ ] Trace Λ ↔ `resolve_arrival_exposure` parity.  
- [ ] Filter `Duration(d)` moments ≈ generative MC.  
- [ ] `ac2_11a` ladder MAE ordering.  
- [ ] Artifact drops truncated-normal fields if not already.  
- [ ] No per-day regress beyond noise on bench.

---

## 7. Parameter budget (reference)

| Parameter | Source |
|---|---|
| \(d_{\min},a,b\) | Fit Abdella durations |
| \(w_k,\mu_k\) | Fixed means; μ tweaked for mean φ̄ |
| \(\delta_M, p_M\) | Assumed; tune under ρ=0 φ̄ SD |
| \(\sigma_{\mathrm{hour}}\) | Assumed; chart + ρ=0 SD |
| \(\rho,\bar\tau,T_{\mathrm{break}}\) | Assumed scenario |
| \(\sigma_{\mathrm{pos}},k,\theta,q_{10},T_{\mathrm{ref}}\) | Existing |

---

## 8. One-sentence contract for implementers

**Draw Abdella-matched stage times, a cool/nominal/warm trip mode, hourly OU, and optional fixed-temperature breaks into a path; integrate Λ for truth/F3; give the filter only a cached mixture of stage-gamma baselines × modes × Poisson–gamma breaks × position — no haul toggles, no decorative traces, no hourly filter nodes.**
