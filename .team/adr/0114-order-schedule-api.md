# 0114. OrderSchedule type and API (Track A)

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: CAL-A1
GROUP: CAL
PROVENANCE: CAL-01 Wave 0
TIER: 1
MILESTONE: CAL-01 — calendar realism

## Context

With MWF delivery and LT=1 ([0112](./0112-x-11-mwf-delivery-base-case.md)), every episode loop,
controller, and UI advance needs a single definition of “may I order today?”, “when is the next
order day?”, and “how many demand days does this order protect?”. Scattering weekday arithmetic
across controllers invites silent 3-vs-4 bugs.

Episode calendar epoch is already `date(2024, 1, 1)` (Monday) + episode day index.

## Decision

We will introduce a frozen **`OrderSchedule`** type in library code under
`src/blueberries_voi/sim/` (or `controller/` if implement prefers; Track A owns the module):

**Defaults (binding):**

- `delivery_weekdays = frozenset({0, 2, 4})`  # Mon / Wed / Fri
- `lead_time_days = 1`
- `order_weekdays = frozenset({6, 1, 3})`  # Sun / Tue / Thu
- Epoch weekday: `weekday(day) = (date(2024, 1, 1) + timedelta(days=day)).weekday()`

**API (binding names):**

| Method | Behaviour |
|--------|-----------|
| `can_order(day: int) -> bool` | True iff `weekday(day)` ∈ order weekdays |
| `next_order_day(day: int) -> int` | Smallest `d > day` with `can_order(d)` (strictly after `day`) |
| `protection_days(day: int) -> int` | On an order day: days until next order day + `lead_time_days` → **3 / 3 / 4** on Sun / Tue / Thu |

**Ownership:** Track A (`controller/` + episode / session / day_driver order gates). Web consumes
exported schedule fields; it does not redefine weekday math.

v1 keeps `lead_time_days = 1` fixed in the base case even if the type can represent other LTs.

## Alternatives considered

- **Inline weekday checks per call site** — rejected: duplicates the 3/3/4 rule and drifts.
- **Weekly physics tick replacing daily days** — rejected: ADR 0112 keeps daily `day_step`.
- **Protection = lead_time only (always 2)** — rejected: that is the daily-cadence formula and
  understates Fri→Mon coverage.
- **`next_order_day` inclusive of today when `can_order`** — rejected: UI “advance to next order
  day” needs a strict successor; order-today is a separate `can_order` check.

## Consequences

**Easy:** one tested module for 3/3/4; gates and UI share the same clock.

**Hard / cost:** every order path must consult `can_order` or force zero; tests must pin epoch
Monday alignment.

**Locked in:** OrderSchedule API names, default MWF/LT=1/Sun–Tue–Thu, epoch `2024-01-01`.

**Revisit if:** LT≠1 becomes a product dial or delivery set changes.
