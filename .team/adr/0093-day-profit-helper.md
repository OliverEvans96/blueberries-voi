# 0093. Day profit helper lives in sim/profit.py (SIM-01 extract for CTL)

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SIM-01 (M2 extract) / CTL objective
GROUP: SIM
PROVENANCE: M2 Wave 0 lock
TIER: 1
MILESTONE: M2 — controller and multi-scenario

## Context

CTL-03 α tuning, CTL-02/04 rollout scoring, and the CTL-05 ladder all need a day-level profit
number before M3’s VOI package exists. SIM-01 (ADR 0064) already locked accounting as **B —
margin + waste cost + explicit stockout penalty** (no holding). Physics already logs
`DayLog.sales_total`, `waste_total`, and `demand` (lost sales = `demand - sales_total` under
MOD-10). There is no profit implementation yet; putting P&L inside `controller/` or `voi/` would
either couple economics to policies or invent VOI aggregation too early.

## Decision

We will:

1. Extract a pure numeric **day profit helper** into **`sim/profit.py`** (package path
   `blueberries_voi.sim.profit`) implementing SIM-01=B:
   \(\mathrm{day\_profit} = m\cdot\mathrm{sales} - c_w\cdot\mathrm{waste} - c_s\cdot\mathrm{lost}\),
   where lost sales = \(\max(0, \mathrm{demand} - \mathrm{sales})\).
2. Accept a small frozen **cost/params** object (unit margin, waste cost, stockout penalty) passed
   into the helper — not matplotlib, not filesystem, not experiment writers.
3. Keep the helper **I/O-free**: inputs are numbers / `DayLog` (or equivalent scored day fields);
   output is a float and/or a small named components dict — no figure or markdown writes.
4. Allow an episode aggregator over **scored** days (after SIM-03 burn-in) that sums day profits —
   still not VOI.
5. Leave **M3 / `voi/`** as the owner of VOI aggregation (differences across information scenarios,
   sweeps, misspecification arms). M2 may *use* day/episode profit; it must not claim VOI tables.

## Alternatives considered

- **Inline profit inside controller rollout only** — rejected: duplicates accounting; violates
  “one economics path” shared with closed-loop eval and α tuning.
- **Put helper under `voi/` now** — rejected: VOI is a difference of profits and a later milestone;
  would pressure M2 into VOI scope.
- **Full P&L with holding cost (SIM-01=C)** — rejected: ADR 0064 already chose B; M2 must not
  reopen holding cost without a new ADR.
- **Margin and waste only (SIM-01=A)** — rejected: ADR 0064 chose B; X-12 stockout-penalty
  sensitivity requires the explicit stockout term.

## Consequences

**Easy:** T-025 / T-029 / T-030 / T-032 share one tested formula; closed-loop and rollout cannot
drift on economics.

**Hard / cost:** default dollar parameters for margin / waste / stockout must be chosen for
fixtures (and later documented for experiments); until M3, “profit” must not be mislabelled as VOI
in changelogs or figure captions.

**Locked in:** `sim/profit.py` owns SIM-01=B day (and scored-episode) profit; no I/O; M3 owns VOI;
no holding cost in M2.

**Revisit if:** X-12 sensitivity shows the stockout penalty dominates headlines and needs a better-
grounded estimate — still a parameter change, not a move out of `sim/profit.py`.
