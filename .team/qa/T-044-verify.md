# T-044 verify

STATUS: PASS  
DATE: 2026-08-12  
ROLE: verify  
BRANCH: `team/T-044/verify`  
TIP: `b612dca0e0f7e4b426d6bc11b34d455754873927`  
WORKTREE: `.worktrees/T-044-verify`

## Commands run

- `uv sync --all-extras` → exit 0, Resolved 125 packages / Installed 119
- `uv run ruff check .` → exit 0, All checks passed!
- `uv run ruff format --check .` → exit 0, 106 files already formatted
- `uv run mypy src tests` → exit 0, Success: no issues found in 81 source files
- `uv run pytest` → exit 0, **511 passed**, 1 skipped; coverage 89.16% (≥80%)
- `uv run pytest tests/test_m15_closeout.py::test_no_production_ctl_voi_browser_under_m15 tests/test_m2_closeout.py::test_no_browser_or_pyodide_packaging_modules_in_src -o addopts='-ra --strict-markers --strict-config'` → exit 0, **2 passed** (prior FAIL closeout guards)

## Acceptance criteria

- [x] Derived Abdella arrival-age product built from vendored Parquet (numpy-/JSON-friendly; no Pyodide) — verified by full suite (`tests/test_derived_abdella_product.py`) + `src/blueberries_voi/data/abdella_arrival_ages.npz` present; `build_derived_abdella_product` in `abdella_product.py`
- [x] Loader reads derived product without importing pyarrow — verified by full suite / `load_derived_abdella_arrival_ages`
- [x] `[browser]` omits pyarrow/matplotlib **or** interactive entry imports clean when absent — verified by `tests/test_t044_packaging_extras.py` + `pyproject.toml` extras (`browser = []`, `data`/`viz` hold heavy deps); `from blueberries_voi.browser import *` succeeds
- [x] Eager Abdella parquet I/O gated off browser import graph — verified by full suite (browser façade / product module tests)
- [x] Desktop Gate 0 / Parquet under `[data]` (pyarrow) — verified by `test_t044_packaging_extras.py` + `pyproject.toml` `[data]`
- [x] `ruff` / `mypy` / `pytest` pass — all AGENTS.md gates exit 0 on tip `b612dca`
- [x] CI Python 3.14 deferred with checklist → T-046 — verified by `.team/checklists/T-044-ci-314-deferred.md`

## Incomplete

- None.

## Notes

- Re-verify after closeout fix on implement tip: M1.5 / M2 closeout tests allowlist `browser.py` (`_ALLOWED_BROWSER_MODULES`); previously failing closeout cases now pass.
- Prior verify FAIL tip was pre-fix; this tip includes `T-044 (implement): allow ENG-01 browser façade in closeout guards`.
