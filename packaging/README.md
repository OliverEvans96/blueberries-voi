# Packaging (slim / browser wheel)

ADR [0099](../.team/adr/0099-eng-01-packaging-pyodide-wheels.md) locks the
browser install story: a **slim wheel** without hard `pyarrow` / `matplotlib`,
distributed via **GitHub Release** for `micropip.install` (**not PyPI**).

## Runtime pins

| Component | Pin |
|-----------|-----|
| Pyodide | **314.0.4** |
| CPython (Pyodide) | **3.14.2** |

Native CI also covers Python **3.11**, **3.12**, and **3.14** (see
`packaging/github-workflows/ci.yml`).

## Install in Pyodide (`micropip`)

Use the GitHub Release download URL for the slim wheel (replace tag / asset
name as published):

```python
import micropip

await micropip.install(
    "https://github.com/<org>/blueberries-voi/releases/download/v0.1.0/"
    "blueberries_voi-0.1.0-py3-none-any.whl"
)
```

Do **not** install the browser artifact from PyPI; the production path is the
Release URL pattern above.

Derived Abdella arrival ages ship as package data
(`blueberries_voi/data/abdella_arrival_ages.npz`) and may also appear as a
Release asset.

## Build + METADATA smoke (local)

```bash
python scripts/build_slim_wheel.py
python scripts/smoke_slim_wheel.py
```

## Human: copy workflows into `.github/`

Agent protocol forbids writing live `.github/workflows/`. Canonical sources:

| Canonical | Live destination |
|-----------|------------------|
| `packaging/github-workflows/ci.yml` | `.github/workflows/ci.yml` |
| `packaging/github-workflows/release-slim-wheel.yml` | `.github/workflows/release-slim-wheel.yml` |

Copy or symlink those files before CI/Release jobs run on GitHub.
