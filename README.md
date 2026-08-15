# blueberries-voi

Simulation, filtering, ordering, and value-of-information (VOI) analysis for a
perishable blueberry store — a typed Python package and an interactive D3 studio
that runs the same Rust engine in the browser.

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
| `dev` | pytest, ruff, mypy, coverage, xdist, testmon, plus desktop data/viz deps |
| `notebooks` | Jupyter + ipykernel |
| `data` | pyarrow (Abdella Parquet / Gate 0) |
| `viz` | matplotlib (static figures) |
| `freshnet` | Hugging Face `datasets` ingest/fit only |
| `rust` | maturin (native PyO3 extension builds) |

## Interactive studio

The studio (`web/`) is a Vite + D3 store simulator. You can step day by day,
choose among six observation levels (books-only through age at receipt), and
Autopilot-play with controller policy knobs.

The browser studio runs the **Rust WASM kernel** — the same native engine used
from Python notebooks and batch studies, compiled for the browser. Open the UI
at **http://127.0.0.1:5173** after Vite starts. The footer says “Live WASM
studio”; the header chip is Loading / Ready / Error. `mock` is debug-only
(`VITE_ENGINE_ADAPTER=mock`) and is never selected silently.

One-time frontend install (from the repo root):

```bash
cd web
cp .env.example .env.local   # optional; launcher sets WASM URLs without this
npm install
```

Build the WASM kernel (needs `rustc` and `wasm-pack`), then launch the studio:

```bash
./scripts/build-wasm.sh
./scripts/studio.sh
```

From `web/` you can also run `npm run studio` (thin alias for the same script).

Vite serves the worker at `/packaging/wasm/worker.js` and the wasm-pack output
at `/wasm/` from `packaging/wasm/pkg/` (dev middleware; no `web/public`
symlinks). Rebuild after Rust crate changes. Smoke the kernel with
`./scripts/smoke-wasm.sh` (see
[`packaging/wasm/README.md`](packaging/wasm/README.md)).

### Env flags

`web/.env.example` and `./scripts/studio.sh` document the same keys. The
launcher sets `VITE_ENGINE_ADAPTER=wasm` and the WASM worker/pkg URLs.
`mock` is debug-only and is never selected by the launcher.

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
| `viz/` | Static figures (desktop; not the browser charts) |

JS owns studio charts and economics projection; the Rust kernel owns the engine
in the browser; Python owns orchestration for notebooks, CLI, and batch studies.

## Browser packaging

The studio’s sole browser host is the Rust WASM kernel under
[`packaging/wasm/`](packaging/wasm/). See
[`packaging/README.md`](packaging/README.md) for the packaging layout and
workflow-copy notes.

## Team workflow

This repo follows the agent-dev-team protocol. Project state lives in `.team/`
(intake, specs, ADRs, reviews, QA reports, changelog). See `AGENTS.md`.
