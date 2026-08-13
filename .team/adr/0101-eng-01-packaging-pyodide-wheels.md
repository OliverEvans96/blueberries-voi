# 0101. ENG-01 packaging: derived Abdella, extras, GH Release, Pyodide 314

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: ENG-01 reopen Wave 0 (Oliver packaging prefs)
TIER: 1
MILESTONE: ENG-01 — interactive dual-runtime simulator

## Context

Runtime deps today include **matplotlib** (ADR 0084) and **pyarrow** (ADR 0085) for Abdella
Parquet. Neither belongs in a Pyodide worker: pyarrow is heavy / unavailable under typical
browser wheels, and matplotlib is the wrong presentation path for the interactive demo (JS owns
charts; static figures stay desktop).

Browser prod needs a **derived Abdella arrival-age product** (arrays), optional install extras so
core / browser installs do not pull parquet or plotting, a **CI → GitHub Release** wheel
distribution (not PyPI), and an explicit **Pyodide 314.0.4 / CPython 3.14.2** pin with CI coverage
of 3.14 while keeping 3.11+3.12 for native/API.

## Decision

We will:

1. **Derived Abdella product:** offline (or CI) conversion from vendored Parquet into a
   numpy-/JSON-friendly arrival-age artifact shipped with the browser wheel / Release assets.
   Interactive and `[browser]` paths **must not** import pyarrow or read parquet.
2. **Optional extras (direction):** move or gate matplotlib and pyarrow behind extras such as
   `[viz]` / `[data]` (exact names in implement tickets) so a slim / browser install can omit them.
   Core interactive façade imports must not eagerly pull Abdella parquet loaders or `viz/`.
3. **Distribute** the slim / pyemscripten-compatible wheel via **CI → GitHub Release** URLs for
   `micropip.install`. **Not** PyPI for the browser artifact in v1.
4. **Pin:** document and test against **Pyodide 314.0.4** (CPython **3.14.2**). Add **Python 3.14**
   to the GitHub Actions matrix; keep **3.11** and **3.12** for native library / API until a
   separate ADR drops them.
5. **Worker-only Pyodide:** packaging and host docs assume the interpreter runs in a Web Worker;
   main thread never holds PyProxy.

ADR 0084 / 0085 remain valid for **desktop / data** workflows; this ADR constrains the **browser
and slim interactive** install graph without silently deleting desktop Gate 0 parquet tooling.

## Alternatives considered

- **Ship parquet + pyarrow into Pyodide** — rejected: unavailable or oversized; Oliver locked
  derived product.
- **Publish browser wheel to PyPI** — rejected: Release URL + micropip is the locked distribution
  path for the Astro/demo host.
- **Keep matplotlib as hard runtime dep for all installs** — rejected: browser path must not pull
  plotting; JS owns interactive figures.
- **Drop 3.11/3.12 immediately when adding 3.14** — rejected: native/API retain 3.11+3.12 until a
  separate drop decision.
- **Pin an older Pyodide (e.g. 0.26 / 3.12)** — rejected: Oliver locked current latest 314.0.4 /
  3.14.2.

## Consequences

**Easy:** browser worker installs a small wheel; desktop Gate 0 still uses pyarrow under `[data]`
(or equivalent); CI proves 3.14 import/smoke.

**Hard / cost:** extras refactor may break “one `uv sync` gets everything” unless `[dev]` meta-extra
is updated; building pyemscripten wheels is a new CI skill; derived Abdella must stay bit-stable
enough for golden demos.

**Locked in:** derived Abdella in-browser; GH Release wheels; no matplotlib/pyarrow on browser
path; Pyodide 314.0.4 / 3.14.2; CI 3.11+3.12+3.14.

**Revisit if:** Pyodide 314 cannot install required numpy/scipy wheels — then pin adjustment needs
Oliver, not a silent downgrade.

**Depends on:** ADR [0084](./0084-runtime-deps-numpy-scipy-matplotlib.md),
[0085](./0085-pyarrow-abdella-parquet.md), [0099](./0099-eng-01-dual-runtime-ap.md)
