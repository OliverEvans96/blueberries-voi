---
title: Run it locally
sources:
  code: [README.md, scripts/build-wasm.sh, scripts/studio.sh, scripts/smoke-wasm.sh, scripts/build-rustdoc.sh, web/package.json, web/.env.example]
---

# Run it locally

Everything on this site can be run on your own machine: the Python package that notebooks and the CLI import, and the interactive browser studio that runs the same physics compiled to WebAssembly. The two have separate setup steps because they're separate build targets from one shared Rust core, not two independent implementations of the model.

> **Figure (coming soon):** a small diagram of the three run surfaces — Python package/CLI/notebooks, the Rust `voi_core` crate, and the browser studio — showing which artifact (wheel vs. `.wasm` bundle) each one consumes.

## The idea

The model's hot compute lives in one place — the Rust crate `voi_core` — with two doors into it. Python notebooks, the CLI, and pytest reach it through a PyO3 extension built by `uv`. The browser studio reaches the *same* Rust code through a `wasm-pack` build compiled to WebAssembly and loaded by Vite. Getting notebooks running only needs Python tooling; getting the interactive studio running also needs a working Rust toolchain, because the browser's copy of the physics has to be compiled from source before Vite can serve it.

### Python package, CLI, and notebooks

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11 (pinned in `.python-version`). From the repo root:

```bash
uv sync --all-extras
```

That installs the package plus every optional extra (tests, notebooks, viz, data ingest). From there:

```bash
uv run pytest              # test suite
uv run blueberries-voi --help   # CLI
uv sync --extra notebooks && uv run jupyter lab   # notebooks
```

### Interactive studio

The studio needs a one-time frontend install and a Rust→WASM build before its first launch.

```bash
cd web
npm install
cd ..
./scripts/build-wasm.sh     # needs rustc and wasm-pack; wasm-pack installs itself if missing
./scripts/studio.sh         # launches the Vite dev server
```

`./scripts/studio.sh` sets the engine adapter to the live WASM kernel and starts Vite; open the URL it prints (`http://127.0.0.1:5173` by default) in a browser. From `web/` you can also run `npm run studio`, a thin alias for the same launcher script.

**Rebuild after any change under `crates/`.** `./scripts/build-wasm.sh` compiles `crates/voi_wasm` to `web/src/wasm/`, which Vite bundles directly — the studio does not re-read Rust source, so editing physics or filter code in Rust has no effect on the browser until you rerun the build script and reload.

To sanity-check the Rust↔WASM build in isolation, without the browser or Vite:

```bash
./scripts/smoke-wasm.sh
```

This builds `voi_wasm` for a Node target and drives the same init/reset/step/act contract the browser worker uses, checking that responses have the shape the studio expects.

### Rust API docs (rustdoc)

The [Rust API reference](/reference/rust-api) published on this site is generated straight from each crate's own `///`/`//!` comments — `voi_core`, and its two thin wrappers `voi_py` and `voi_wasm` — and bundled into the site's own build (`npm run docs:build` runs this automatically). To regenerate it on its own, without a full docs-site build:

```bash
./scripts/build-rustdoc.sh
```

This runs `cargo doc --no-deps --workspace` and copies the per-crate output, plus a
hand-authored landing page linking the three crates together, into
`docs/public/api/rust/`.

## Why it's modelled this way

The model's hot compute lives in one Rust crate, reachable from both Python (via PyO3) and the browser (via `wasm-bindgen`), rather than a second from-scratch implementation of the physics in JavaScript or running Python itself in the browser (Pyodide). A shared kernel means the studio and the notebooks can't quietly drift apart on how freshness decays or how demand is drawn — there is exactly one implementation to keep correct. Other language choices for the shared core (Julia, Numba/Cython) were set aside because none gives a browser target without still needing something like Pyodide. Rust and NumPy random-number streams are not made bit-identical, because NumPy's generator isn't a public bit-stable contract to port against; instead Rust and Python paths are held to matching moments/distributions in tests, not identical numbers.

**Caveat.** This design's cost is the extra local build step above. Python is the source of truth for citeable VOI numbers, and the repo carries two working implementations of the same physics rather than one — so a change to the model has to be made (or at least checked) in both places, and anyone running the studio locally needs a working Rust toolchain that notebook-only users don't.

## In the code

| Concept | Command / file | File:line |
| --- | --- | --- |
| Python package + all extras | `uv sync --all-extras` | `README.md:21` |
| Test suite | `uv run pytest` | `README.md:135` |
| CLI entry point | `uv run blueberries-voi --help` | `README.md:161` |
| Rust→WASM build (crate → `web/src/wasm/`, mirrored to `packaging/wasm/pkg/`) | `./scripts/build-wasm.sh` | `scripts/build-wasm.sh:13` |
| Studio dev-server launcher (sets `VITE_ENGINE_ADAPTER=wasm`, runs Vite) | `./scripts/studio.sh` | `scripts/studio.sh:8` |
| Same launcher via npm | `npm run studio` (from `web/`) | `web/package.json:18` |
| WASM kernel contract smoke test (Node target) | `./scripts/smoke-wasm.sh` | `scripts/smoke-wasm.sh:1` |
| Engine adapter env flags (`wasm` default; `mock` debug-only) | `web/.env.example` | `web/.env.example:4` |
| Rust API docs (rustdoc) build | `./scripts/build-rustdoc.sh` | `scripts/build-rustdoc.sh:1` |

## Caveats

- `mock` is a debug-only engine adapter (`VITE_ENGINE_ADAPTER=mock`) and is never selected silently by the launcher script — if you see mock data in the studio, an environment variable was set explicitly.
- The Rust↔Python golden tests hold deterministic kernels to tight numeric tolerance and stochastic paths to matching moments, not bit-identical output — do not expect a Rust run and a Python run seeded the same way to produce byte-identical traces.
- These are the commands this page could verify against `README.md` and the scripts themselves; other repo scripts under `scripts/` and `packaging/` exist for CI and release workflows and are out of scope here.
