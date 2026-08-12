# Changelog

Plain-English notes of what shipped, for non-technical readers.

## 2026-08-12

- Built the first working inventory simulator and age-tracking filter for the blueberry
  study, including real cold-chain temperature traces and a bakeoff that chose the
  tractable full joint age model for production at the small live-cohort counts we
  measured.
- Ran the first hard filter check (does the age posterior tighten under realistic
  arrival mix?): it did **not** — that negative result is documented and later
  calibration stages were stopped on purpose.
- At Oliver’s request, still ran the follow-on calibration and toy-scale exact
  checks as diagnostics (not as claiming the first check passed): coverage was
  too high / ranks skewed (filter looks underconfident), while the small-grid
  exact match stayed within tolerance.
- Set up the project so we can write Python simulations and analyses with a
  clear package layout, automated checks, and a place for team decisions and
  ticket status.
