# Documentation figures

PNG assets for the VitePress site live under `docs/public/figures/`. They are
stored with **Git LFS** (see `.gitattributes`).

After cloning or adding a worktree, fetch LFS objects before building docs:

```bash
git lfs install
git lfs pull
```

Without `git lfs pull`, figure paths may exist as tiny pointer files and images
will not render in the docs site.
