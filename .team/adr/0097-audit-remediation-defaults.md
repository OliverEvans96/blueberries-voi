# 0097. Audit remediation: case_round, Abdella defaults, costs, α gate, MF sweeps, bakeoff stubs

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: *(repo audit)*
GROUP: ENG / SIM / VOI / FIL
PROVENANCE: Oliver lock after four-way audit of `main` @ `f4a467f`
TIER: 1
MILESTONE: Audit remediation (straightforward fixes)

## Context

A post-M3 audit of `main` found several **silent dual semantics and uncalibrated defaults** that
make production-facing entry points disagree with the controller contract or with CTL-03:

1. **`case_round`:** `controller/ordering.py` uses nearest / half-away-from-zero; `sim/episode.py`
   re-applies **ceil** on closed-loop orders. The same policy can emit different quantities on the
   two paths.
2. **Shipments:** VOI CRN, M2 ladder / multi-scenario, and α-tune default to a synthetic **1°C cool**
   fixture when `shipments=None`, while open-loop sim defaults to Abdella parquet.
3. **Profit costs:** The same `ProfitCosts(2.0, 1.5, 3.0)` literals are duplicated as private
   `_DEFAULT_COSTS` in several modules, with no shared documented default and no calibration claim.
4. **VOI α:** Production VOI CRN/sweep still default to a fixed **α=0.9**, while CTL-03=B and M2
   ladder already require a tuned α table for profit claims.
5. **MF sweeps:** `age_likelihood` defaults to **5** sweeps; the production P1 path in
   `filter/backends.py` hard-codes **2** for CI tractability — a silent production under-iteration.
6. **Bakeoff backends:** `SlidingWindowBackend` / `FullJointBackend` still share the factorized
   `_rbpf_update` path and are easy to mistake for citeable production filters after ADR 0091
   settled mean-field.

Oliver locked: **nearest** case rounding everywhere; production shipment defaults **Abdella**; cool
fixtures **smoke/test-only** under an explicit name. Deep science gaps (RBPF count physics, Stage A
honesty, compute reduction) stay out of this ADR and land in a later remainder report.

## Decision

We will:

1. **Unify `case_round`:** The sole semantic is **nearest multiple of `case_size`, ties
   half-away-from-zero**, as already documented in `controller/ordering.py`. `sim/episode.py` must
   **not** keep a ceil implementation; closed-loop and any public `sim.case_round` re-export or thin
   wrapper call the controller function (one definition).
2. **Default shipments to Abdella:** When production-facing APIs leave `shipments=None`, they load
   via `load_abdella_shipments()` (or an equivalent public `default_shipments()` that does so). The
   synthetic 1°C cool path is available only under an explicit smoke/test helper (e.g.
   `smoke_cool_shipments()`), never as a silent default.
3. **Centralize `DEFAULT_PROFIT_COSTS`:** Define
   `DEFAULT_PROFIT_COSTS = ProfitCosts(unit_margin=2.0, waste_cost=1.5, stockout_penalty=3.0)` on
   `sim/profit.py`, document that these dollars are **still uncalibrated** scaffold values, and
   replace duplicated private `_DEFAULT_COSTS` copies in VOI / M2 / α-tune with that constant.
4. **Gate production VOI on CTL-03 α tables:** Production VOI CRN / non-smoke sweep paths must
   obtain α from a tuned table via the existing `require_tuned_alpha_table` (or equivalent), failing
   closed if the artifact is missing or incomplete. **Smoke** may keep a fixed α=0.9.
5. **Share `MF_MAX_SWEEPS = 5`:** Production mean-field updates in `filter/backends.py` use the same
   library default of **5** sweeps as `age_likelihood` (no CI-only hard-coded `2` on the production
   path).
6. **Mark bakeoff stubs non-citeable:** `SlidingWindowBackend` and `FullJointBackend` are retained
   for bakeoff / registry compatibility but are explicitly **non-production, non-citeable stubs**
   (module docstring and a machine-checkable marker such as `is_stub=True` or equivalent).

Tickets **T-042** (case_round), **T-043** (costs / Abdella / α gate), and **T-044** (MF sweeps /
bakeoff markers / backlog–docstring hygiene) implement this decision.

## Alternatives considered

- **Ceil everywhere** — rejected: Oliver locked nearest; controller policies and T-026 fixtures
  already assume nearest / half-away-from-zero.
- **Require explicit `shipments=` (no default)** — rejected: Oliver locked Abdella as the production
  default; failing closed without data is worse UX than loading vendored Abdella when present.
- **Leave cool fixtures as silent defaults; document only** — rejected: silent toy cold-chain ages
  contaminate VOI / M2 / α-tune headline paths.
- **Keep fixed α=0.9 for production VOI** — rejected: CTL-03=B already forbids untuned α for ladder
  profit claims; VOI must match that gate.
- **Keep `max_sweeps=2` on the production P1 path** — rejected: diverges from the library MF default
  and under-iterates production beliefs for CI convenience.
- **Delete SlidingWindow / FullJoint backends** — rejected: bakeoff registry and historical FIL-13
  arms still reference them; marking stubs is enough for this remediation.

## Consequences

**Easy:** One order-rounding rule; production runs that omit `shipments` use Abdella; one named
profit-cost default; VOI production cannot claim dollars without a tuned α table; MF iteration count
matches the likelihood helper; bakeoff backends cannot be mistaken for production filters.

**Hard:** Call sites and tests that relied on ceil or silent cool fixtures must be updated; production
VOI needs a tuned-α artifact in the environment (smoke stays cheap); CI that depended on
`max_sweeps=2` may get slower MF updates unless smoke paths pass an explicit override.

**Locked:** Nearest `case_round`; Abdella production shipment default; uncalibrated
`DEFAULT_PROFIT_COSTS` values as the shared scaffold; CTL-03 α-table gate for production VOI; MF
sweeps default 5; bakeoff SlidingWindow/FullJoint non-citeable.

**Revisit if:** Oliver recalibrates dollar costs or α search; production joint / window backends are
reintroduced under a new ADR (would supersede the stub marking, not ADR 0091’s mean-field settle).
