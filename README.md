# blueberries-voi

Simulation, filtering, ordering, and value-of-information (VOI) analysis for a
perishable blueberry store — a typed Python package for notebooks and batch
studies, plus an interactive D3 studio that runs the same Rust engine in the
browser via WebAssembly.

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
uv sync
```

`uv sync` installs every optional extra by default (via the `all` meta-extra and
the `dev` dependency group). To install only the slim core:

```bash
uv sync --no-default-groups
```

Individual extras remain available for `pip install blueberries-voi[…]` consumers:

| Extra | Use |
|-------|-----|
| `all` | every extra below (default for `uv sync`) |
| `dev` | pytest, ruff, mypy, coverage, xdist, testmon, plus desktop data/viz deps |
| `notebooks` | Jupyter + ipykernel + Ax BO (PyTorch) |
| `data` | pyarrow (Abdella Parquet / Gate 0) |
| `viz` | matplotlib (static figures) |
| `freshnet` | Hugging Face `datasets` ingest/fit only |
| `rust` | maturin (PyO3 extension builds) |
| `modal` | Modal batch map for notebook heavy jobs |

## Interactive studio

The studio (`web/`) is a Vite + D3 store simulator. You can step day by day,
choose among six observation levels (books-only through age at receipt), and
Autopilot-play with controller policy knobs.

The live engine runs in a **Web Worker** with the wasm-pack kernel at `/wasm/`
(ADR 0129). There is no in-browser Python path and no local HTTP session API —
notebooks and CLI still use the native PyO3 `EngineSession`.

Open the UI at **http://127.0.0.1:5173** after Vite starts. The footer says
“Live WASM studio”; the header chip is Loading / Ready / Error. `mock` is
debug-only (`VITE_ENGINE_ADAPTER=mock`) and is never selected silently.

One-time frontend install (from the repo root):

```bash
cd web
cp .env.example .env.local   # optional; launcher sets WASM URLs without this
npm install
```

Build the Rust kernel (needs `rustc` and `wasm-pack`), then launch the studio:

```bash
./scripts/build-wasm.sh
./scripts/studio.sh
```

From `web/` you can use `npm run studio` (thin alias for the same script).

Vite serves the worker at `/packaging/wasm/worker.js` and the wasm-pack output
at `/wasm/` from `packaging/wasm/pkg/` (dev middleware; no `web/public`
symlinks). If `packaging/wasm/pkg/` is missing, the launcher reminds you to run
`./scripts/build-wasm.sh`. Rebuild after Rust crate changes. Smoke the kernel
with `./scripts/smoke-wasm.sh` (see
[`packaging/wasm/README.md`](packaging/wasm/README.md)).

### Env flags

`web/.env.example` and `./scripts/studio.sh` document the same keys. The
launcher sets `VITE_ENGINE_ADAPTER=wasm` plus `VITE_WASM_WORKER_URL` and
`VITE_WASM_PKG_URL`. `mock` is debug-only and is never selected by the launcher.

## Studio embed releases

The publishable React embed is `@oliverevans96/blueberries-voi-studio` (`web/package.json`).
It ships as a GitHub Release tarball after green CI on `main`.

### What to do in each PR

If your change affects the published embed bundle, **bump `version` in
`web/package.json` in the same PR**:

| Change | Bump |
|--------|------|
| Bugfix or bundle output fix | **patch** (`0.1.x`) |
| New feature, non-breaking API | **minor** (`0.x.0`) |
| Breaking embed API | **major** |

CI requires a strictly higher semver when any **publishable path** changes vs
`main`:

- `web/src/`, `web/vite.lib.config.ts`, `web/scripts/`
- `crates/voi_core/`, `crates/voi_wasm/`
- `scripts/build-wasm.sh`

Guard: `tests/test_studio_release_version.py`.

### What happens automatically on merge

Once the release workflow is live (canonical draft under
`packaging/github-workflows/release-studio.yml`), each green `main` CI run:

1. Republishes **`studio-latest`** (moving target; reinstall to pick up changes).
2. Creates **`studio-v{version}`** when that tag does not exist yet (immutable pin).

No manual `git tag` is needed for normal releases.

### Downstream consumers

Pin URLs and Astro embedding patterns: [`EMBEDDING.md`](EMBEDDING.md).

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

JS owns studio charts and economics projection; the Rust kernel owns hot
compute in the browser; Python owns notebooks, sweep, and CLI orchestration.

## Browser packaging

The sole browser host is the WASM kernel under `packaging/wasm/`. See
[`packaging/README.md`](packaging/README.md) and
[`packaging/wasm/README.md`](packaging/wasm/README.md) for build/smoke steps and
the note about copying canonical workflows from `packaging/github-workflows/`
into the live GitHub Actions workflows directory.

Quality CI on GitHub is Python **3.11** only. Rust kernel tests run via
`cargo test -p voi_core -p voi_wasm`.

## Team workflow

This repo follows the agent-dev-team protocol. Project state lives in `.team/`
(intake, specs, ADRs, reviews, QA reports, changelog). See `AGENTS.md`.
