# CAL-01 — FIL-13 measured-L remotesure note

**Date:** 2026-08-13  
**Milestone:** CAL-01 (T-088 close-out)  
**Related:** ADR [0091](../adr/0091-fil13-production-mean-field.md) (production mean-field);
prior bakeoff / L notes under [FIL-13-bakeoff-findings.md](./FIL-13-bakeoff-findings.md)

## Remeasure

CAL-01 changes the scientific **base case** from daily delivery + i.i.d. demand to
**Mon/Wed/Fri delivery (LT=1)** and **calendar-shaped weekly demand**. That shift can
change empirical live-cohort length **L** relative to numbers measured under the old
cadence and demand model.

**Before citing any filter L claim** (memory bounds, Stage A dwell stress, bakeoff
comparability to production, or similar), **remeasure L** under the new MWF + calendar
demand defaults and the controller actually used. Do not treat pre–CAL-01 measured L as
authoritative for the new base case.

## Non-reopen

This note does **not** reopen joint / `K^L` production. Production FIL-13 remains
**mean-field** (ADR 0091). Joint production stays parked until a **new** ADR says
otherwise.
