# T-C2-A Verify

**Verdict:** PASS  
**Verifier role:** verify  
**Branch:** `team/feature-c2-a-f-native/integration-merge`  
**Commit:** integration-merge tip (post lint + test fixes)  
**Python:** 3.11.13

## CI parity commands (identical argv to live CI)

```bash
uv sync --all-extras --python 3.11
uv run --python 3.11 maturin develop --release --manifest-path crates/voi_py/Cargo.toml
uv run --python 3.11 ruff check .
uv run --python 3.11 ruff format --check .
uv run --python 3.11 mypy src tests
uv run --python 3.11 pytest -n auto --cov=blueberries_voi --cov-branch \
  --cov-report=term-missing --cov-report=xml --cov-fail-under=80
```

## Results

| Gate | Result |
|------|--------|
| `ruff check .` | PASS |
| `ruff format --check .` | PASS |
| `mypy src tests` | PASS (158 files) |
| `pytest -n auto --cov-fail-under=80` | PASS — **543 passed**, 58 skipped, 2 xfailed |

## Shard RED maps (W1)

- `.team/qa/T-C2-A-daystep-tests.md`
- `.team/qa/T-C2-A-unit-pf-tests.md`
- `.team/qa/T-C2-A-belief-policy-tests.md`
- `.team/qa/T-C2-A-session-wire-tests.md`
- `.team/qa/T-C2-A-frontend-tests.md`

All mapped tests green on integration tip.

## Review

`.team/reviews/T-C2-A.md` — APPROVED
