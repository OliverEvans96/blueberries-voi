STATUS: APPROVED
ROUND: 1
TICKET: T-044
BASE: c10a457 (qa) / f4a467f (main)
TIP: b92a2defa24d54906f63b82e3562171419fb03a3 (`team/audit-remediation-integ`)

## Blocking

(none)

## Non-blocking

- [src/blueberries_voi/filter/backends.py:561] `is_stub` is a mutable dataclass field (callers can pass `is_stub=False`). Class/default marker meets AC; a `ClassVar` would be harder to misuse.

## Summary

Shared `MF_MAX_SWEEPS=5` wired through age_likelihood default and production P1 `_particle_filter_update`. SlidingWindow/FullJoint marked non-citeable stubs; MeanField not a stub. Controller docstring, α-tune belief comment, and backlog M2+M3-on-main wording updated. T-044 audit tests green.
