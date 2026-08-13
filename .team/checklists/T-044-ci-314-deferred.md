# T-044 → T-046: Python 3.14 CI matrix deferral

STATUS: **cleared by T-046** (canonical source landed)  
DATE: 2026-08-12  
TICKET: T-044  
TARGET: T-046  
CLEARED: 2026-08-12 (T-046 implement)

## Why deferred here

Protocol hard-limits forbid agent roles from editing live GitHub Actions
workflows. Landing a Python **3.14** job stub was therefore deferred to
**T-046** (slim wheel + GH Release + Pyodide **314.0.4** / CPython **3.14.2**).

## Checklist for T-046

- [x] Add `"3.14"` to the GitHub Actions CI matrix (or a dedicated slim-import job)
  — encoded in `packaging/github-workflows/ci.yml` (canonical; human must
  copy/symlink to the live workflows directory)
- [x] Keep native/API coverage on 3.11 and 3.12
- [x] Document Pyodide 314.0.4 / CPython 3.14.2 pin in packaging workflow comments
  — see `packaging/github-workflows/*.yml` env/comments and `packaging/README.md`

## needs-human

Copy or symlink:

- `packaging/github-workflows/ci.yml` → live `ci.yml`
- `packaging/github-workflows/release-slim-wheel.yml` → live `release-slim-wheel.yml`
