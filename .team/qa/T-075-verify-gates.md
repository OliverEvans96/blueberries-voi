# T-075 verify gates

STATUS: PASS  
DATE: 2026-08-13  
TIP: `0f3bafb`

Commands (once):
- `uv run ruff check .` — PASS
- `uv run ruff format --check .` — PASS
- `uv run mypy src tests` — PASS
- `uv run pytest -n auto --cov=blueberries_voi --cov-branch --cov-fail-under=80` — PASS (coverage ≥80%)
