# T-044 MF sweeps=5, bakeoff stub markers, backlog/docstring hygiene

## Context

Production P1 mean-field updates hard-code `max_sweeps=2` while `age_likelihood` defaults to 5;
bakeoff `SlidingWindowBackend` / `FullJointBackend` still look like real filters; and backlog /
controller docstrings still describe pre-merge M2/M3 state. ADR 0104 locks shared sweeps=5 and
non-citeable stub markers; this ticket also corrects hygiene only.

## Acceptance criteria

- [ ] A shared library constant `MF_MAX_SWEEPS` with value **5** is the default used by both
      `filter/age_likelihood` mean-field updates and the production P1 `mean_field_update` call in
      `filter/backends.py` (the hard-coded `max_sweeps=2` on that production path is gone unless a
      caller passes an explicit override).
- [ ] Observably, the production backends P1 path invokes mean-field with `max_sweeps=5` by default
      (unit/integration assertion on call kwargs or equivalent constant wiring).
- [ ] `SlidingWindowBackend` and `FullJointBackend` are marked as **non-production / non-citeable
      stubs**: each has a docstring (or class docstring section) stating they must not be cited as
      production filters, **and** a machine-checkable marker (e.g. class attribute `is_stub is True`
      or `IS_STUB is True`) that tests can assert.
- [ ] `MeanFieldBackend` (production) is **not** marked as a stub (`is_stub` false / absent per the
      chosen convention).
- [ ] `controller/__init__.py` module docstring no longer says only “Controller stubs (M2).” — it
      accurately describes the shipped controller surface (policies / ordering helpers are real).
- [ ] Stale `sim/alpha_tune.py` comment that closed-loop “passes belief=None” is corrected to match
      current closed-loop belief wiring (or removed if obsolete).
- [ ] `.team/backlog.md` no longer claims M2/M3 are only tip-green pending merge onto `main` as if
      absent: wording reflects that M2+M3 library work is on `main` (at/after `f4a467f`), and may
      note audit remediation as in progress without claiming science VOI is citeable.
- [ ] `uv run pytest` for this ticket’s tests passes; ruff/mypy clean for touched modules.

## Out of scope

- Case-round unification (T-042)
- Abdella defaults, `DEFAULT_PROFIT_COSTS`, VOI α-table gate (T-043)
- Fixing ResearchParticleFilter count ±1 random walk or replacing stub backends with real joint/window filters
- M3 compute-reduction work / production VOI wall-clock
- Remainder report (Phase 4 on the integration tip)

## Interfaces

```text
# filter/age_likelihood.py and/or filter/backends.py
MF_MAX_SWEEPS: int = 5  # shared public or module-level constant imported by backends

# filter/backends.py
@dataclass
class SlidingWindowBackend:
    is_stub: bool = True  # or equivalent machine-checkable marker
    ...

@dataclass
class FullJointBackend:
    is_stub: bool = True
    ...

@dataclass
class MeanFieldBackend:
    is_stub: bool = False  # production; not a bakeoff stub
    ...
```

## Open questions

- [x] Stub marking mechanism — docstring **plus** machine-checkable flag (ADR 0104); warn-once is
      optional sugar, not required if `is_stub` is present.
- [x] File ownership — implement owns `filter/backends.py`, MF constant wiring (possibly
      `filter/age_likelihood.py`), `controller/__init__.py`, `.team/backlog.md`, α-tune comment only.
