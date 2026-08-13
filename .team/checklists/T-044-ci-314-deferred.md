# T-044 → T-046: Python 3.14 CI matrix deferral

STATUS: deferred  
DATE: 2026-08-12  
TICKET: T-044  
TARGET: T-046

## Why deferred here

Protocol hard-limits forbid this role from editing `.github/workflows/`. Landing a
Python **3.14** job stub in `ci.yml` is therefore deferred to **T-046** (slim
wheel + GH Release + Pyodide **314.0.4** / CPython **3.14.2**), which already
owns CI matrix expansion for 3.14 alongside 3.11 and 3.12 (see
`.team/specs/T-046.md` and ADR 0099).

## Checklist for T-046

- [ ] Add `"3.14"` to the GitHub Actions CI matrix (or a dedicated slim-import job)
- [ ] Keep native/API coverage on 3.11 and 3.12
- [ ] Document Pyodide 314.0.4 / CPython 3.14.2 pin in packaging workflow comments
