# Backlog

Escalations and items that need a human decision land here.

- **M2.5 Wave 0 done:** Architecture locked in ADRs
  [0086](./adr/0086-m25-richobs-unobserved-masks.md)–[0089](./adr/0089-m25-dynamic-l-sliding-window-fallback.md)
  and specs [T-008](./specs/T-008.md)–[T-018](./specs/T-018.md). Plan:
  [`.team/plans/M2.5-filter-complete.md`](./plans/M2.5-filter-complete.md).
  **Next:** Wave 2 / T-011 (honest MC LL) — Wave 1 behaviour verified; full-repo
  gates may still be red on T-011 RED until that ticket lands.
- **Resolved — experiments lint:** `experiments/fil11_a_scenarios.py` RUF001
  (`sigma`/`x` ASCII) + E501/format wrap fixed; `uv run ruff check experiments/`
  and `uv run ruff format experiments/` pass.
- **Do not reopen without Oliver:** ⚑ cards (FIL-01, FIL-08, FIL-12, MOD-14/15/17, SCN-P2/F3/B-clair, …).
- **M2.5 non-goals (binding):** no CTL, no VOI sweep, no browser, no new runtime deps without ADR.
- **Resolved — F2a Stage A pack_date emit (T-019):** Sim now emits synthetic ASN
  `pack_date` on delivery `DayLog` rows (non-delivery stays `None`). Stage A F2a
  contracts under smoke defaults; needs-human from T-016 is cleared.
