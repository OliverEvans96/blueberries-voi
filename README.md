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

Three live engines. Pick one per session:

| Mode | When to use | Engine |
|------|-------------|--------|
| **HTTP / API** | Local development against FastAPI | Native Python `EngineSession` on port 8000 |
| **Pyodide** | In-browser / prod-shaped Python path | Web Worker + `micropip.install` of the slim wheel |
| **WASM** | In-browser Rust kernel | Web Worker + wasm-pack pkg at `/wasm/` |

Open the UI at **http://127.0.0.1:5173** after Vite starts. The footer says
“Live HTTP studio”, “Live Pyodide studio”, or “Live WASM studio”; the header
chip is Loading / Ready / Error. `mock` is debug-only
(`VITE_ENGINE_ADAPTER=mock`) and is never selected silently.

One-time frontend install (from the repo root):

```bash
cd web
cp .env.example .env.local   # optional; see flags below
npm install
```

### HTTP / API mode

Two processes: the FastAPI session host, then Vite. CORS allows only the Vite
origins `http://127.0.0.1:5173` and `http://localhost:5173`.

Terminal 1 — API:

```bash
uv sync --extra api
uv run --with uvicorn python -m uvicorn blueberries_voi.api.app:app \
  --host 127.0.0.1 --port 8000
# If :8000 is already taken (OpenHands, etc.), use --port 8001 and set
# VITE_ENGINE_API_BASE_URL=http://127.0.0.1:8001 before starting Vite.
```

Terminal 2 — studio:

```bash
cd web
VITE_ENGINE_ADAPTER=http VITE_ENGINE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

If you copied `web/.env.example` to `.env.local` with those same keys set, you
can run `npm run dev` without the inline env. Restart Vite after changing
`VITE_*` values.

The API is a **development host** (in-process sessions, localhost CORS). It is
not a production multi-tenant service. If the chip stays on Connecting / Error,
confirm port 8000 is up and that you opened the studio on port 5173 (not
another origin).

### Pyodide mode

Vite serves the worker at `/packaging/pyodide/worker.js` and the slim wheel at
`/wheels/*.whl` from repo `dist/`. Build the wheel first (first load downloads
Pyodide **314.0.4** and can take a minute):

```bash
uv run python scripts/build_slim_wheel.py
cd web
VITE_ENGINE_ADAPTER=pyodide npm run dev
```

No FastAPI process is required. If the worker fails to install the package,
check that `dist/blueberries_voi-*-py3-none-any.whl` exists and that
http://127.0.0.1:5173/wheels/blueberries_voi-0.1.0-py3-none-any.whl returns
200. Rebuild the wheel after Python package changes.

### WASM mode

Vite serves the worker at `/packaging/wasm/worker.js` and the wasm-pack output
at `/wasm/` from `packaging/wasm/pkg/` (dev middleware; no `web/public`
symlinks). Build the crate first (needs `rustc` and `wasm-pack`):

```bash
./scripts/build-wasm.sh
cd web
VITE_ENGINE_ADAPTER=wasm \
  VITE_WASM_WORKER_URL=/packaging/wasm/worker.js \
  VITE_WASM_PKG_URL=/wasm/ \
  npm run dev
```

No FastAPI process is required. Rebuild after Rust crate changes. Smoke the
kernel with `./scripts/smoke-wasm.sh` (see
[`packaging/wasm/README.md`](packaging/wasm/README.md)).

### Env flags

`web/.env.example` documents:

| Variable | Role |
|----------|------|
| `VITE_ENGINE_ADAPTER` | `http` \| `pyodide` \| `wasm` \| `mock` (explicit wins) |
| `VITE_ENGINE_API_BASE_URL` | FastAPI base (`http://127.0.0.1:8000`) |
| `VITE_PYODIDE_WORKER_URL` | default `/packaging/pyodide/worker.js` |
| `VITE_PYODIDE_WHEEL_URL` | default `/wheels/blueberries_voi-0.1.0-py3-none-any.whl` |
| `VITE_WASM_WORKER_URL` | default `/packaging/wasm/worker.js` |
| `VITE_WASM_PKG_URL` | default `/wasm/` |

Without `VITE_ENGINE_ADAPTER`, development with an API base URL selects HTTP;
otherwise the studio prefers Pyodide (including production builds). For the
GitHub Release wheel URL used in production, see
[`packaging/README.md`](packaging/README.md).

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
