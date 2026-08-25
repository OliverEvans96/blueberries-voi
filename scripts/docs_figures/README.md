# Documentation figures

PNG assets for the VitePress site live under `docs/public/figures/`. They are
stored with **Git LFS** (see `.gitattributes`: `docs/public/figures/*.png`).

After cloning or adding a worktree, fetch LFS objects before building docs:

```bash
git lfs install
git lfs pull
```

Without `git lfs pull`, figure paths may exist as tiny pointer files and images
will not render in the docs site.

## Regenerate figures

Run from the repository root after `pip install -e ".[dev]"` (and rebuild
`blueberries_voi._core` if PyO3 shims changed):

```bash
python scripts/docs_figures/render_all.py
```

After adding new PNGs, confirm they are LFS-tracked:

```bash
git lfs ls-files docs/public/figures/
```

Section subpackages under `scripts/docs_figures/` each export a `render(out_dir)`
function; `render_all.py` imports and calls them all.
