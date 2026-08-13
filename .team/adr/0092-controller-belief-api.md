# 0092. Controller belief API is ShelfBelief over MF marginals and oracle

STATUS: SUPERSEDED BY 0106
DATE: 2026-08-12
BOARD-ID: CTL / M2 belief surface
GROUP: CTL
PROVENANCE: M2 Wave 0 lock (post–T-021)
TIER: 1
MILESTONE: M2 — controller and multi-scenario

## Context

M2 policies (CTL-01 damped survival-weighted base-stock and CTL-02 rollout) need an explicit
effective inventory \(\tilde I_t\) built from on-hand survival-weighted stock plus a pipeline term.
Production RBPF (ADR 0091) exposes mean-field age marginals in private `ParticleState.age_post` of
shape `(N, L, K)` and a thin public `age_posterior(lot)` — not a controller-ready summary.
`viz/m15.OracleBelief` is a B-state verification stub `(n, τ)` that must not stay the CTL contract.
Letting policies read `RBPF._state` would couple CTL to filter internals and block any later
list/float export (see parked [M2-controller-agent-brief.md](../plans/M2-controller-agent-brief.md)).

## Decision

We will:

1. Introduce a frozen public type **`ShelfBelief`** (module `filter/belief.py`, re-exported for
   `controller/`) that summarises shelf state for ordering: lot counts, age marginals usable as
   `(L, K)` (or equivalent list-of-lists of floats), and enough metadata to compute \(\tilde I_t\).
2. Provide **`shelf_belief_from_rbpf(rbpf, ...)`** that builds `ShelfBelief` from a production
   mean-field `RBPF` using weight-averaged counts and MF `age_post` marginals — **never** requiring
   joint `K^L` tensors and **never** returning or exposing `RBPF._state` / `ParticleState`.
3. Provide **`shelf_belief_from_oracle(...)`** that builds the same `ShelfBelief` shape from B-state /
   true lot `(n, τ)` (promote/adapt the viz stub into this filter/controller-facing constructor).
4. Provide **`effective_inventory(belief, *, pending_orders, params, ...)`** that computes
   \(\tilde I_t = \sum_\ell w(\tau_\ell)n_\ell + \sum_j q_{t-j}\mathbb E_g[w_j]\) using
   `survival_weighted_on_hand(..., from_marginals=True)` for the on-hand term plus an explicit
   pipeline term from recent order quantities.
5. Prefer **list/float-friendly fields** on `ShelfBelief` (or a documented `to_export()` /
   round-trip) so a future browser façade can serialise belief without a second API — this is a
   compatibility preference, **not** a Pyodide deliverable.
6. Require all CTL policies to consume **`ShelfBelief` only**; reading `RBPF._state` is forbidden.

## Alternatives considered

- **Policies read `RBPF._state` / `ParticleState` directly** — rejected: private coupling; blocks
  B-state parity; paints CTL into filter-internal shapes.
- **Joint age posterior API for CTL** — rejected: production is mean-field (ADR 0091); joint /
  `K^L` production is parked; M2 must not reopen that path.
- **Keep `OracleBelief` only in `viz/m15` and dual-path policies** — rejected: two belief contracts
  would fork CTL-01 math and invite silent divergence between P1 and B-state eval.
- **Put belief types under `controller/` only** — rejected: filter owns posterior construction;
  controller should import a stable export, not own RBPF adapters.

## Consequences

**Easy:** one belief contract for P1 filter belief and B-state ceiling; CTL unit tests can fixture
`ShelfBelief` without spinning a full particle cloud; eventual JSON round-trip stays cheap.

**Hard / cost:** factories must carefully weight-average MF particles without leaking `_state`;
oracle multi-lot representation must be lifted from today’s single-`(n, τ)` viz stub; pipeline
term needs a clear pending-order convention shared with the closed-loop driver.

**Locked in:** MF-marginal `ShelfBelief`; `from_rbpf` / `from_oracle` / `effective_inventory`;
no joint production belief for CTL; no policy access to `RBPF._state`.

**Revisit if:** a future ADR reopens joint production age belief — then belief factories would need
a new path; do not silently add joint tensors under this ADR.
