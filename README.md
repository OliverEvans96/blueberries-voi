# blueberries-voi

Simulation, filtering, ordering, and value-of-information (VOI) analysis for a
perishable blueberry store — a typed Python package, a local HTTP API, and an
interactive D3 studio that can run the same engine in the browser.

The default store orders for **Monday / Wednesday / Friday** deliveries with a
calendar-shaped weekly demand pattern (not every-day i.i.d. sales). Citeable VOI
numbers from the older daily base case need to be regenerated.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and **Python 3.11** (pin:
`.python-version`; `requires-python >=3.11`). For the optional pytest-testmon
cache seed, also install [Git LFS](https://git-lfs.com/) and run
`git lfs install` / `git lfs pull` after clone so `.testmondata` is a real SQLite
file (not a pointer).

```bash
uv sync --all-extras
```

Optional extras if you are not installing everything:

| Extra | Use |
|-------|-----|
| `dev` | pytest, ruff, mypy, coverage, xdist, testmon, plus desktop data/viz/API deps |
| `notebooks` | Jupyter + ipykernel |
| `api` | FastAPI local session host |
| `data` | pyarrow (Abdella Parquet / Gate 0) |
| `viz` | matplotlib (static figures) |
| `browser` | empty marker; slim wheel has no pyarrow/matplotlib |
| `freshnet` | Hugging Face `datasets` ingest/fit only |

## Interactive studio

The studio (`web/`) is a Vite + D3 store simulator. You can step day by day,
choose among six observation levels (books-only through age at receipt), and
Autopilot-play with controller policy knobs.

Two live engines share the Python library:

- **HTTP (dev):** Vite talks to a local FastAPI `EngineSession`.
- **Pyodide (prod / in-browser):** a Web Worker loads the slim wheel via
  `micropip.install`.

```bash
cd web
cp .env.example .env.local   # optional; see flags below
npm install
```

**Dev / HTTP** — start the API, then Vite:

```bash
uv sync --extra api
uv run --with uvicorn uvicorn blueberries_voi.api.app:app --host 127.0.0.1 --port 8000

# another terminal
cd web
VITE_ENGINE_ADAPTER=http VITE_ENGINE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

**Pyodide** — build the slim wheel so Vite can serve it at `/wheels/`, then:

```bash
uv run python scripts/build_slim_wheel.py
cd web
VITE_ENGINE_ADAPTER=pyodide npm run dev
```

`web/.env.example` documents `VITE_ENGINE_ADAPTER` (`http` | `pyodide` | `mock`),
the API base URL, and the Vite-served worker / wheel URLs. `mock` is debug-only
and is never selected silently.

The API is a **development host** (in-process sessions, localhost CORS for Vite
on port 5173). It is not a production multi-tenant service.

## Quality gates

Verify / CI is **Python 3.11** only, with coverage + xdist and **no** testmon
selection. Live GitHub Actions installs with pip (`pip install -e ".[dev]"`).
The format gate is check-only:

```bash
uv run --python 3.11 ruff check .
uv run --python 3.11 ruff format --check .
uv run --python 3.11 mypy src tests
uv run --python 3.11 pytest -n auto --cov=blueberries_voi --cov-branch \
  --cov-report=term-missing --cov-report=xml --cov-fail-under=80
```

Everyday loops (no coverage):

```bash
uv run pytest                 # full suite
uv run pytest --testmon       # deselect tests unaffected by local edits
./scripts/refresh-testmon.sh  # rebuild LFS-tracked .testmondata after a green tip
```

Front-end unit tests (from `web/`):

```bash
npm test                      # vitest
```

See `AGENTS.md` for the role gate ladder, conflict policy, and LFS notes.

## Notebooks

```bash
uv sync --extra notebooks
uv run jupyter lab
```

Put notebooks under `notebooks/` and import `blueberries_voi` rather than
copying logic into cells.

## CLI

```bash
uv run blueberries-voi --help
uv run python -m blueberries_voi --version
```

## Package layout

Reusable code lives under `src/blueberries_voi/`:

| Module | Role |
|--------|------|
| `model/` | Shared physics (aging, picking, demand, shipments) |
| `sim/` | Forward simulation, profit, closed-loop episodes |
| `filter/` | Particle / arrival-only age filter |
| `controller/` | Ordering policies (age-blind, survival-weighted, rollout, …) |
| `voi/` | Knowledge-scenario sweep and VOI metrics |
| `simulator/` | Interactive `EngineSession` (Snapshot / DayDelta) |
| `api/` | FastAPI session host for the studio |
| `viz/` | Static figures (desktop; not the browser charts) |

JS owns studio charts and economics projection; Python owns the engine.

## Browser / Pyodide packaging

The slim interactive wheel is distributed via **GitHub Release** (not PyPI).
See [`packaging/README.md`](packaging/README.md) for the `micropip.install`
Release URL pattern, Pyodide **314.0.4** / CPython **3.14.2** pins, local
`scripts/build_slim_wheel.py` / `scripts/smoke_slim_wheel.py`, and the note
about copying canonical workflows from `packaging/github-workflows/` into the
live GitHub Actions workflows directory.

Quality CI on GitHub is Python **3.11** only. The Pyodide / CPython 3.14 pins
are for the in-browser wheel, not the native quality job.

## Team workflow

This repo follows the agent-dev-team protocol. Project state lives in `.team/`
(intake, specs, ADRs, reviews, QA reports, changelog). See `AGENTS.md`.
