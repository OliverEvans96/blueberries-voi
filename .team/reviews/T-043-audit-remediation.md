STATUS: APPROVED
ROUND: 1
TICKET: T-043
BASE: c10a457 (qa) / f4a467f (main)
TIP: b92a2defa24d54906f63b82e3562171419fb03a3 (`team/audit-remediation-integ`)

## Blocking

(none)

## Non-blocking

- [src/blueberries_voi/voi/crn.py:247-282] `run_voi_crn_cell` still accepts omitted `alpha_table_path` and falls back to fixed α=0.9. Production fail-closed is on `run_voi_sweep(smoke=False)` (spec “and/or”). Callers that invoke the CRN cell directly without a table can still get silent 0.9 — acceptable under AC, but tighter CRN-level require-or-smoke would close the loophole.
- [src/blueberries_voi/voi/crn.py:68-70] Deprecated `_fixture_shipments` alias remains; it delegates to `smoke_cool_shipments` and is no longer the `shipments=None` default.

## Summary

`DEFAULT_PROFIT_COSTS` documented as uncalibrated; production modules use it. `default_shipments` → Abdella; `smoke_cool_shipments` explicit. Production VOI sweep requires `alpha_table_path`; smoke keeps α=0.9 + cool fixture. T-043 audit tests green.
