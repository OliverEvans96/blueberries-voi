# T-042 Unify `case_round` to nearest / half-away-from-zero

## Context

Closed-loop episode code still carries a **ceil** `case_round` while policies use
`controller.ordering.case_round` (nearest, half-away-from-zero). ADR 0104 locks a single semantic so
VOI / closed-loop cannot silently re-round with a different rule.

## Acceptance criteria

- [ ] `blueberries_voi.controller.ordering.case_round` remains the definition of nearest /
      half-away-from-zero rounding (fixture: midpoints such as `x=4` with `case_size=8` → `8`;
      `x=12` → `16`; non-midpoints match nearest).
- [ ] `blueberries_voi.sim.episode` does **not** implement ceil-to-case: no `np.ceil` (or equivalent
      ceil-to-case arithmetic) in its `case_round` path; any public `sim.episode.case_round` /
      `sim.case_round` is the controller function or a thin wrapper that returns identical results
      for the same `(x, case_size)`.
- [ ] For a representative value where ceil and nearest disagree (e.g. `x=9`, `case_size=8`: nearest
      → `8`, ceil → `16`), both controller and sim exports return **8**.
- [ ] `run_closed_loop_episode` places orders using that single nearest semantic (a policy that
      returns a raw quantity in the disagreeing band yields the nearest case multiple, not ceil).
- [ ] Existing T-026 nearest fixture expectations in `tests/test_ordering.py` still pass; any test
      that asserted ceil-to-case via `sim.episode.case_round` is updated or removed so the suite
      encodes nearest only.
- [ ] `uv run pytest` for this ticket’s tests passes; no production behaviour change outside
      case-rounding unification.

## Out of scope

- Abdella / cool shipment defaults (T-043)
- `DEFAULT_PROFIT_COSTS` and VOI α-table gating (T-043)
- MF sweep count / bakeoff stub markers / backlog wording (T-044)
- RBPF count physics, Stage A honesty, M3 compute reduction

## Interfaces

```text
# controller/ordering.py (unchanged semantic; sole definition)
def case_round(x: float, case_size: int = 8) -> int:
    """Nearest non-negative multiple of case_size; ties half-away-from-zero."""
    ...

# sim/episode.py — re-export or thin wrapper only (no ceil body)
from blueberries_voi.controller.ordering import case_round  # or equivalent wrapper
```

## Open questions

- [x] Rounding mode — Oliver lock: nearest / half-away-from-zero (ADR 0104).
- [x] File ownership — implement owns `controller/ordering.py` + `sim/episode.py` case_round path;
      T-043 must not edit episode `case_round`.
