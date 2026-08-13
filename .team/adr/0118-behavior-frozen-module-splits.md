# 0118. Behavior-frozen internal module splits behind re-export façades

STATUS: PROPOSED
DATE: 2026-08-13
BOARD-ID: *(refactor)*
GROUP: ENG
PROVENANCE: Post-TDD structure refactor (T-102)
TIER: 1
MILESTONE: Behavior-frozen structure refactor

## Context

TDD left the suite green but the package with **fat modules**
(`filter/backends.py` ~975 LOC, `filter/age_likelihood.py`, `viz/m15.py`,
`controller/rollout.py`, duplicated day loops / belief+protection helpers) and
**intentional semantic forks** (ceil vs nearest case rounding; dual
`Policy.order` signatures; call-site-specific τ grids; some VOI/m2 paths omitting
MWF order gates). Existing tests — including AST hygiene scanners that load
`filter.backends.__file__` and require a top-level `def _rbpf_update(` in that
file — are the safety net.

We need a structure-only cleanup that does **not** change scores, freezes, or
locked import paths, and does **not** edit `tests/`. Production semantics from
ADR [0105](./0105-arrival-only-age-counts-only-exact-wor.md) (counts-only +
exact WOR; MF/MC remain diagnostic), ADR [0104](./0104-audit-remediation-defaults.md)
(ESS / case_round notes), and ADR [0116](./0116-cal-01-track-ownership.md)
(`day_step` / `day=` ownership) stay binding.

## Decision

We will:

1. **Refactor structure only.** Extract, dedupe, split, and delete proven-dead
   code. **No intentional behavior change.** The existing automated suite is the
   acceptance oracle — no new behavioral tests required for this milestone.
2. **Use new modules + thin re-export façades** at every locked import path
   (`filter.backends`, `filter.age_likelihood`, `filter` / `sim` / `simulator` /
   `controller` / `viz.m15` / `viz.fil11` public and AST-pinned names, etc.).
   Callers and scanners keep working without test edits.
3. **Keep a real top-level `def _rbpf_update(...):` in
   `filter/backends.py`** that delegates to an implementation living under
   `filter/particle/` (e.g. `counts_update.py`). Body may move; the **`def` must
   remain** in `backends.py` so AST scanners that parse that file stay green.
   Preserve other file-pinned markers (`_rbpf_update_end_marker`,
   `_SHARED_MC_KERNELS`, identity tricks) the same way.
4. **Freeze intentional forks — do not unify:**
   - Ceil case rounding in `simulator/day_driver.py` / open-loop `sim` vs
     nearest `controller.ordering.case_round`
   - Dual public `Policy.order` signatures (day-first vs belief-first); a shared
     `invoke_order` helper may centralize `inspect.signature` dispatch but must
     **not** collapse the public Protocol to one signature
   - Per-call-site τ grids for empty/oracle shelf belief (do not canonicalize one
     grid)
   - Order-gate / `day=` wiring differences across episode vs VOI/m2 paths (do
     not silently add gates where absent)
5. **Execute in waves A→B→C** (parallel leaves within a wave; C after B helpers
   exist): filter/model splits and dead trim → shared day-tick / belief /
   protection / invoke helpers → thin-wrap drivers, peel rollout, slim viz
   façades. Optional deeper peels only if a file remains >~400 LOC after a wave
   and time allows — still behind the same façades.
6. **Add no new runtime dependencies.** Do not rename `sim/` vs `simulator/`,
   change ESS (`< 0.5 * N`), production backend selection, WOR weights, or
   `RBPF._state` pokeable layout (`.counts` / `.age_post` / `.weights`).
7. **Zero edits under `tests/`** for this milestone. Prefer façades over
   updating AST path strings. Semantic unification items go to `.team/backlog.md`
   as notes only — not fixed here.

## Alternatives considered

- **Edit AST / hygiene tests to follow moved symbols** — rejected: the milestone
  rule is zero test edits; façades keep scanners on the old `__file__` and
  import paths.
- **Unify ceil vs nearest rounding and dual `Policy.order` signatures in the
  same tip** — rejected: tests lock both; unification changes behavior and is
  backlog, not structure.
- **Big-bang rewrite of day loops with one “correct” order-gate + τ grid** —
  rejected: would change VOI/m2 scores relative to closed-loop episode; out of
  scope for behavior-frozen work.
- **Leave god-modules until a greenfield package rename (`sim`/`simulator`)** —
  rejected: import debt is orthogonal; façade splits unblock maintainability now
  without the rename fight.

## Consequences

**Easy:** Parallel leaf worktrees can own disjoint paths behind stable façades;
verify stays “full suite green on Python 3.11”; reviewers check “no test changes
/ façades intact” instead of numeric science claims.

**Hard / cost:** Temporary double surfaces (implementation module + façade);
merge discipline across wave tips; implementers must resist “while we’re here”
semantic fixes; dead-code deletes require grep proof.

**Locked in:** Locked import paths and `def _rbpf_update` in `backends.py`;
existing suite as AC; intentional forks remain until a later ADR explicitly
unifies them.

**Revisit if:** Oliver authorizes a behavior-changing unify ticket (order gates,
rounding, Policy signature), or a package rename of `sim`/`simulator` that
makes façades obsolete.
