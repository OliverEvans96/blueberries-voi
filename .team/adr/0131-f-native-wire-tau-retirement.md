# 0131. F-native wire completion — retire τ / Weibull from production

STATUS: PROPOSED
DATE: 2026-08-16
BOARD-ID: FIL-01 / CTL-01 / ENG-01
GROUP: FIL / CTL / ENG
PROVENANCE: T-TAU-RETIRE — f-native unit PF completion on `team/feature-c2-a-f-native`
TIER: 1
MILESTONE: C2 f-native belief wire
SUPERSEDES (partial): [0105](./0105-arrival-only-age-counts-only-exact-wor.md) (τ wire exports),
[0106](./0106-shelfbelief-arrival-prior-age-exports.md) (τ `ShelfBelief` as production wire),
[0126](./0126-wasm-rich-filterobs-particle-belief.md) (τ birth / `age_at_receipt` on wire)
RELATED: [0130](./0130-f-native-unit-pf-wire.md) (unit grid + flat f belief),
[0024](./0024-mod-02-effective-age-dynamics.md) (MOD-02 clock — now expressed as gamma aging on `f`),
[0058](./0058-ctl-01-base-policy-family.md) (damped-SW ordering)

## Context

ADR 0130 landed the **f-native unit particle filter**: internal state is `L×U` freshness
values; the wire exports `lot_counts`, `f_marginals`, and `f_grid`. Production ordering already
has an f-path — `effective_inventory_f_belief` / `damped_sw_order_f_belief` in Rust,
`FreshShelfBelief.effective_inventory_f_belief` in Python, and
`effectiveInventoryFromFlatBelief` in the web charts layer.

Despite that, the codebase still carries a **parallel τ / Weibull stack**:

- Legacy **cohort count filter** (`particle_filter`, `exact_ll`, `day_step_legacy`) with
  `age_marginals` / `tau_grid` wire flatteners.
- **Weibull survival integrals** for effective inventory (`effective_inventory_belief`,
  `survival_weighted_on_hand`, mock `survivalWeightedInventory` on belief-driven paths).
- Wire fields **`age_at_receipt`** and **`live_lots[].tau`** that leak effective-age coordinates
  the filter no longer learns.
- **F2/F2a driver bug**: session / VOI paths still birth τ then map to `f`, while the unit PF
  expects native birth `f` from `shipments::delivery_birth_f` with Q10 private inside the
  shipment cache only.

Oliver locked: **complete f-native birth end-to-end**, **remove Weibull from UI and legacy
modules**, and **keep effective inventory defined from freshness** — not τ survival integrals.

Removing τ does **not** remove effective inventory. It replaces the old Weibull-over-τ-bins
path with a freshness-native definition aligned to the same gamma aging used in truth and the
filter (see §Effective inventory below and explainer §8).

## Decision

We will:

### 1. Wire renames and truth overlay

1. **Receipt field:** rename observed receipt freshness on the wire from `age_at_receipt`
   (τ days) to **`f_at_receipt`** (`f ∈ [0, 1]`). Internal shipment helpers may still use
   τ days privately (`birth_f_f2_dirac(age_at_receipt, η_ref)`); only the **exported**
   observation / snapshot field becomes f-native. Scenario masks follow the rename
   (`ObsMask.f_at_receipt`).
2. **`live_lots` truth overlay:** replace per-lot **`tau`** with **`mean_f`** — the mean
   freshness of alive units in that ground-truth lot (`session::live_lots_value`). Truth overlay
   stays physics-only; the filter wire remains `f_marginals`.
3. **Belief wire:** export **`f_grid` / `f_marginals` / `lot_counts` only**. Delete τ wire
   flatteners (`age_marginals`, `tau_grid`) from production `belief_flat` paths.

### 2. F-native arrival birth

Birth freshness **`f`** is drawn **once per delivery** via `shipments::delivery_birth_f`:

| Scenario | Birth rule |
|----------|------------|
| **F2** | Dirac: `f_at_receipt` on wire (or private τ → `age_to_f`) |
| **F2a** | Gaussian on pack-date transit age (τ days) → `f`; SD = `f2a_transit_uncertainty_sd` (default **0.75** τ-days) |
| **P0** / default | Mixed shipment prior; Q10 integration stays **private** in `shipments.rs` |

Fix F2/F2a session / VOI drivers so births call `delivery_birth_f` (or equivalent) instead of
cohort τ=0 / mis-wired τ paths. After birth, only **gamma aging on `f`** advances inventory
(MOD-02 in freshness coordinates).

**F2a uncertainty (documented formula):** draw transit age
\(\tilde\tau \sim \mathcal{N}(\mu_{\mathrm{pack}}, \sigma_{\mathrm{F2a}})\) with
\(\mu_{\mathrm{pack}}\) from calendar pack-date transit and \(\sigma_{\mathrm{F2a}} = 0.75\)
τ-days (clamped ≥ 0), then \(f = \mathrm{age\_to\_f}(\tilde\tau, \eta_{\mathrm{ref}})\).

### 3. Effective inventory — MVP (production)

Per unit with freshness \(f\), define a **quality weight**:

\[
w(f) = \frac{\mathbb{E}[T_{\mathrm{rem}} \mid f]}{T_{\mathrm{nom}}}
\]

where \(T_{\mathrm{rem}}(f)\) is time until spoil (first day \(f \le 0\)) under production
gamma aging, and \(T_{\mathrm{nom}} = \mathbb{E}[T_{\mathrm{rem}} \mid f{=}1]\).

**Effective inventory:**

\[
\tilde I = \sum_{\ell=1}^{L} n_\ell \, \mathbb{E}[w(f) \mid \ell] + q_{\mathrm{pipeline}} \, f_{\mathrm{pipe}}
\]

(\(n_\ell\) = expected alive units in virtual lot slot \(\ell\) from `lot_counts`; expectation
over `f_marginals`.)

**MVP (ship now):** treat bin centers on `f_grid` as \(w(f_k) = f_k\) — i.e.
**\(\mathbb{E}[f]\) weighting**:

\[
\tilde I = \sum_\ell n_\ell \sum_k p_{\ell k} f_k + q_{\mathrm{pipe}} f_{\mathrm{pipe}}
\]

Implemented as `effective_inventory_f_belief` (Rust `policy.rs`), Python
`effective_inventory_f_belief`, web `effectiveInventoryFromFlatBelief`. This is the correct
“pristine-equivalent units” count when \(f\) is a **linear remaining-life fraction**
(birth convention \(f = 1 - \tau/\eta_{\mathrm{ref}}\) kept private inside shipment cache).

| Regime | \(w(f)\) | Notes |
|--------|----------|-------|
| **Deterministic** \(\Delta \equiv \delta\) | \(w(f) = f\) | \(T_{\mathrm{rem}} = f/\delta\); ratio cancels \(\delta\) |
| **Stochastic gamma** | \(w(f) \approx f\) first-order; exact \(w(f_k)\) tabulatable | Jensen / first-passage makes \(\mathbb{E}[T_{\mathrm{rem}}\mid f] \neq f \cdot T_{\mathrm{nom}}\) in general |

**Production ordering** uses **`effective_inventory_f_belief` / `damped_sw_order_f_belief` /
`effectiveInventoryFromFlatBelief` only**. Delete τ/Weibull policy helpers
(`effective_inventory_belief`, `damped_sw_order_belief`) and mock
`survivalWeightedInventory` on **belief-driven** `effective_inv` paths.

**Optional v2 (not blocking MVP):** precompute \(w(f_k)\) on `f_grid` from
`(gamma_shape, gamma_scale, store Q10)` via short Monte Carlo or analytic first-passage
approximation; horizon-aligned variant \(w_H(f)\) for protection window \(H\) in damped-SW.

### 4. Unit likelihood picking weights

When removing `f_to_age` from the unit likelihood kernel, switch
`sequential_kernel_path_logprob` to **`picking_weights_f`** on raw `f` (orthogonal to
\(\tilde I\) but same f-native coordinate). Ground-truth `pick_units_f` already uses this path.

### 5. Module and API deletion

**Rust (`voi_core`):** delete `particle_filter`, `day_step_legacy`, `exact_ll`; remove τ
flatteners from `belief_flat`; trim τ/Weibull exports from `physics` / `policy` used only by
deleted paths; update `lib.rs` and `voi_py` re-exports.

**Python:** promote **`FreshShelfBelief`** as the production belief type; delete τ production
paths in `age_likelihood`, `particle/`, `arrival_priors` tied to `ShelfBelief` /
`age_marginals`; migrate `sim/`, bakeoff, and `viz/` imports; rewrite failing tests.

**Web:** remove survival / β UI, legacy projector shims, τ mock sim paths; f-only charts,
types, and tests; `projector.effective_inv` from flat f belief only.

Diagnostic τ code may remain **only** under `experiments/` or explicitly marked non-production
imports — not on closed-loop / studio / VOI paths.

## Alternatives considered

- **Keep τ wire fields alongside f** — rejected: dual coordinates confuse studio masks, goldens,
  and policy; τ is derivable privately where needed (`f_to_age` for legacy viz only).
- **Drop effective inventory when dropping Weibull** — rejected: damped-SW still needs a
  quality-weighted on-hand scalar; MVP \(\mathbb{E}[f]\) preserves interpretability and matches
  deterministic-gamma physics.
- **Ship gamma-derived \(w(f_k)\) lookup in the same ticket** — deferred: MVP \(w=f\) is already
  implemented and tested; v2 lookup documented here for a follow-up.
- **Keep legacy count filter for bakeoff** — rejected for production paths; bakeoff arms migrate
  to unit PF or stay in Python experiments without τ wire exports.

## Consequences

**Easy:** single belief coordinate on wire; ordering / charts / Python host share one effective
inventory definition; grep-clean hot paths (`effective_inventory_belief`,
`survivalWeightedInventory` on belief `effective_inv` absent).

**Hard / cost:** golden wire snapshots regenerate; broad test rewrites; studio control audit
(removes β slider and Weibull survival chart); F2/F2a birth + receipt field rename touches obs
masks across Rust, Python, and web.

**Locked in:** f-native birth; `f_at_receipt` / `mean_f` wire; MVP \(\tilde I = \sum n_\ell
\mathbb{E}[f_\ell] + \text{pipeline}\); legacy τ filter modules deleted from production.

**Revisit if:** stochastic-gamma bias in \(\tilde I\) materially shifts order quantities vs
tabulated \(w(f_k)\), or horizon-aligned \(w_H\) is needed for damped-SW calibration.
