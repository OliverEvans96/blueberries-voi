---
title: Run it locally
sources:
  code: [README.md, scripts/build-wasm.sh, scripts/studio.sh, scripts/smoke-wasm.sh, scripts/build-rustdoc.sh, web/package.json, web/.env.example]
---

# Run it locally

Everything on this site can be run on your own machine: the Python package that the notebooks and command-line tool import, and the interactive browser studio that runs the same simulation compiled to WebAssembly — a format that lets compiled code run directly in a browser. Setting each one up looks a little different, because they're two separate build targets. But both compile from the same shared Rust code underneath, not two separate copies of the model.

## The idea

Running things locally lets you reproduce the numbers on this site yourself, poke at the model beyond what the docs show, or make a change and see its effect right away in the interactive studio. Here's how the pieces fit together, and how to get each one running.

The model's core computation lives in one place — a Rust code library called `voi_core` (in Rust, a packaged unit of code like this is called a "crate") — with two doors into it. Python notebooks, the command-line tool, and the test suite reach it through PyO3, a tool that lets Python code call directly into compiled Rust. The browser studio reaches the *same* Rust code by compiling it to WebAssembly with a tool called `wasm-pack`, then loading the result with Vite, the frontend build tool. Getting notebooks running only needs Python tooling. Getting the interactive studio running also needs a working Rust toolchain, because the browser's copy of the simulation has to be compiled from source before Vite can serve it.

### Python package, CLI, and notebooks

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11 (pinned in `.python-version`). From the repo root:

```bash
uv sync
```

That installs the package plus every optional extra (tests, notebooks, viz, data ingest). From there:

```bash
uv run pytest              # test suite
uv run blueberries-voi --help   # CLI
uv run jupyter lab         # notebooks
```

### Interactive studio

The studio needs a one-time frontend install and a Rust-to-WebAssembly build before its first launch.

```bash
cd web
npm install
cd ..
./scripts/build-wasm.sh     # needs rustc and wasm-pack; wasm-pack installs itself if missing
./scripts/studio.sh         # launches the Vite dev server
```

`./scripts/studio.sh` points the studio's engine adapter — the layer that lets the browser talk to the simulator — at the compiled simulator code running inside the browser, then starts Vite. Open the URL it prints (`http://127.0.0.1:5173` by default) in a browser. From `web/` you can also run `npm run studio`, a shorter alias for the same launcher script.

**Rebuild after any change under `crates/`.** `./scripts/build-wasm.sh` compiles `crates/voi_wasm` to `web/src/wasm/`, which Vite bundles directly — the studio does not re-read Rust source, so editing physics or filter code in Rust has no effect on the browser until you rerun the build script and reload.

To sanity-check the Rust-to-WebAssembly build in isolation, without the browser or Vite:

```bash
./scripts/smoke-wasm.sh
```

This builds `voi_wasm` for a Node.js target and drives it through the same request/response cycle the browser uses, checking that its responses have the shape the studio expects.

### Rust API docs (rustdoc)

The [Rust API reference](/reference/rust-api) published on this site is generated straight from each crate's own `///`/`//!` comments — `voi_core`, and its two thin wrappers `voi_py` and `voi_wasm` — and bundled into the site's own build (`npm run docs:build` runs this automatically). To regenerate it on its own, without a full docs-site build:

```bash
./scripts/build-rustdoc.sh
```

This runs `cargo doc --no-deps --workspace --locked` and copies the per-crate output, plus a
hand-authored landing page linking the three crates together, into
`docs/public/api/rust/`.

## Why it's modelled this way

The model's core computation lives in one Rust code library, reachable from both Python (via PyO3) and the browser (via `wasm-bindgen`, the tool that connects Rust to JavaScript). The alternative would have been a second, from-scratch implementation of the simulation written in JavaScript, or running Python itself inside the browser using a tool called Pyodide — either way, a second copy of the model to keep in sync with the first. A single shared implementation means the studio and the notebooks can't quietly drift apart on how freshness decays or how demand is drawn: there's exactly one version of the logic to keep correct. Other language choices for the shared core, like Julia or Numba/Cython, were set aside because none of them gives a browser target without still needing something like Pyodide. Rust's and NumPy's random-number generators don't produce identical output from the same seed — there's no public specification for NumPy's generator to match bit-for-bit against. Instead, tests check that the Rust and Python paths produce matching summary statistics (moments, like the mean and variance) and matching distributions, not identical numbers.

**Caveat.** This design's cost is the extra local build step described above. Python is the source of truth for the Value of Information (VOI) numbers published on this site. The project also carries two working implementations of the same physics rather than one, so a change to the model has to be made — or at least checked — in both places. And anyone running the studio locally needs a working Rust toolchain that notebook-only users don't.

## In the code

| Concept | Command / file | File:line |
| --- | --- | --- |
| Python package + all extras | `uv sync` | `README.md:21` |
| Test suite | `uv run pytest` | `README.md:155` |
| CLI entry point | `uv run blueberries-voi --help` | `README.md:180` |
| Rust-to-WebAssembly build (crate → `web/src/wasm/`, mirrored to `packaging/wasm/pkg/`) | `./scripts/build-wasm.sh` | `scripts/build-wasm.sh:13` |
| Studio dev-server launcher (sets `VITE_ENGINE_ADAPTER=wasm`, runs Vite) | `./scripts/studio.sh` | `scripts/studio.sh:8` |
| Same launcher via npm | `npm run studio` (from `web/`) | `web/package.json:18` |
| Compiled-simulator response check, Node.js target (drives the `init`/`reset`/`step`/`act` calls) | `./scripts/smoke-wasm.sh` | `scripts/smoke-wasm.sh:1` |
| Engine adapter env flags (`wasm` default; `mock` debug-only) | `web/.env.example` | `web/.env.example:4` |
| Rust API docs (rustdoc) build | `./scripts/build-rustdoc.sh` | `scripts/build-rustdoc.sh:1` |

## Caveats

- `mock` is a debug-only engine adapter (`VITE_ENGINE_ADAPTER=mock`) and is never selected silently by the launcher script — if you see mock data in the studio, an environment variable was set explicitly.
- The tests that compare Rust and Python — regression tests that check outputs stay consistent — hold the deterministic parts of the simulation to a tight numeric tolerance, and the random parts to matching summary statistics (moments, like the mean and variance), not identical output. Don't expect a Rust run and a Python run seeded the same way to produce byte-for-byte identical results.
- These are the commands this page could verify against `README.md` and the scripts themselves; other repo scripts under `scripts/` and `packaging/` exist for CI and release workflows and are out of scope here.
